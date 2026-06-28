import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

DB_PATH = "sobutylnik.db"

async def init_db():
    """Инициализация базы данных и создание таблиц."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL,
                age INTEGER,
                bio TEXT,
                rating REAL DEFAULT 0.0,
                reviews_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_banned INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                drinks TEXT,
                snacks TEXT,
                photo_id TEXT, -- Поле для хранения ID фото из Telegram
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                location_name TEXT,
                max_people INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                listing_id INTEGER NOT NULL,
                is_like INTEGER NOT NULL, -- 1 для лайка, 0 для дизлайка
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users(id),
                FOREIGN KEY (to_user_id) REFERENCES users(id),
                FOREIGN KEY (listing_id) REFERENCES listings(id),
                UNIQUE(from_user_id, to_user_id, listing_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                host_id INTEGER NOT NULL,
                guest_id INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                FOREIGN KEY (listing_id) REFERENCES listings(id),
                FOREIGN KEY (host_id) REFERENCES users(id),
                FOREIGN KEY (guest_id) REFERENCES users(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                text TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id),
                FOREIGN KEY (from_user_id) REFERENCES users(id),
                FOREIGN KEY (to_user_id) REFERENCES users(id)
            )
        """)

        await db.commit()

# ─── USERS ────────────────────────────────────────────────────────────────────

async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def create_user(user_id: int, username: str, first_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )
        await db.commit()

async def update_user_profile(user_id: int, age: Optional[int], bio: Optional[str]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET age = ?, bio = ? WHERE id = ?",
            (age, bio, user_id)
        )
        await db.commit()

async def get_user_reviews(user_id: int) -> List[Dict]:
    """Получить отзывы пользователя, но только те, где оба участника встречи оставили отзыв."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.*, u.first_name as author_name, u.username as author_username
            FROM reviews r
            JOIN users u ON r.from_user_id = u.id
            WHERE r.to_user_id = ? 
              AND r.meeting_id IN (
                  SELECT meeting_id FROM reviews GROUP BY meeting_id HAVING COUNT(id) >= 2
              )
            ORDER BY r.created_at DESC
        """, (user_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

# ─── LISTINGS ─────────────────────────────────────────────────────────────────

async def create_listing(
    user_id: int, title: str, description: str,
    drinks: str, snacks: str, photo_id: str,
    latitude: float, longitude: float,
    location_name: str, max_people: int
) -> int:
    # Установим время жизни 48 часов, чтобы наверняка
    # Используем UTC для всех операций со временем
    expires_at = (datetime.utcnow() + timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO listings
            (user_id, title, description, drinks, snacks, photo_id, latitude, longitude, location_name, max_people, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, title, description, drinks, snacks, photo_id, latitude, longitude, location_name, max_people, expires_at))
        await db.commit()
        return cur.lastrowid

async def get_next_listing_for_user(user_id: int, lat: float, lon: float) -> Optional[Dict]:
    """Получить следующую анкету в радиусе 5 км, которую пользователь еще не оценивал."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        # SQL-запрос с формулой Гаверсинуса для фильтрации по расстоянию (5 км)
        # 6371 - радиус Земли в км
        query = """
            SELECT l.*, u.first_name, u.username, u.rating, u.reviews_count,
            (6371 * acos(cos(radians(?)) * cos(radians(l.latitude)) * cos(radians(l.longitude) - radians(?)) + sin(radians(?)) * sin(radians(l.latitude)))) AS distance
            FROM listings l
            JOIN users u ON l.user_id = u.id
            WHERE l.status = 'active' 
              AND l.user_id != ?
              AND l.expires_at > ?
              AND l.id NOT IN (SELECT listing_id FROM likes WHERE from_user_id = ?)
              AND (6371 * acos(cos(radians(?)) * cos(radians(l.latitude)) * cos(radians(l.longitude) - radians(?)) + sin(radians(?)) * sin(radians(l.latitude)))) <= 5
            ORDER BY distance ASC
            LIMIT 1
        """
        
        try:
            async with db.execute(query, (lat, lon, lat, user_id, now, user_id, lat, lon, lat)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None
        except Exception:
            # Если SQLite не поддерживает acos/cos (зависит от сборки), используем упрощенный квадратный фильтр и сортировку в Python
            async with db.execute("""
                SELECT l.*, u.first_name, u.username, u.rating, u.reviews_count
                FROM listings l
                JOIN users u ON l.user_id = u.id
                WHERE l.status = 'active' 
                  AND l.user_id != ?
                  AND l.expires_at > ?
                  AND l.id NOT IN (SELECT listing_id FROM likes WHERE from_user_id = ?)
                  AND l.latitude BETWEEN ? - 0.05 AND ? + 0.05
                  AND l.longitude BETWEEN ? - 0.05 AND ? + 0.05
                ORDER BY l.created_at DESC
            """, (user_id, now, user_id, lat, lat, lon, lon)) as cur:
                rows = await cur.fetchall()
                if not rows: return None
                
                from utils.helpers import calculate_distance
                listings_list = [dict(r) for r in rows]
                for item in listings_list:
                    item['distance'] = calculate_distance(lat, lon, item['latitude'], item['longitude'])
                
                # Фильтруем по 5 км и берем ближайшую
                nearby = [i for i in listings_list if i['distance'] <= 5]
                if not nearby: return None
                return sorted(nearby, key=lambda x: x['distance'])[0]

async def add_like(from_user_id: int, to_user_id: int, listing_id: int, is_like: int):
    # Принудительное приведение к int для надежности
    f_uid, t_uid, l_id = int(from_user_id), int(to_user_id), int(listing_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Записываем наш лайк
        # Используем INSERT OR REPLACE, чтобы обновить решение, если пользователь передумал
        await db.execute("""
            INSERT OR REPLACE INTO likes (from_user_id, to_user_id, listing_id, is_like)
            VALUES (?, ?, ?, ?)
        """, (f_uid, t_uid, l_id, int(is_like)))
        await db.commit()
        
        if is_like == 1:
            # 2. Ищем ВЗАИМНЫЙ лайк
            # Матч случается, если t_uid когда-либо лайкнул f_uid (is_like = 1)
            # Мы проверяем таблицу лайков, где t_uid - отправитель, а f_uid - получатель
            async with db.execute("""
                SELECT id FROM likes 
                WHERE from_user_id = ? AND to_user_id = ? AND is_like = 1
            """, (t_uid, f_uid)) as cur:
                match = await cur.fetchone()
                if match:
                    return True
    return False

async def get_user_active_listing(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        async with db.execute("""
            SELECT * FROM listings 
            WHERE user_id = ? AND status = 'active' AND expires_at > ?
        """, (user_id, now)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def close_listing(listing_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE listings SET status = 'closed' WHERE id = ?", (listing_id,))
        await db.commit()

async def expire_old_listings() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE listings SET status = 'expired'
            WHERE status = 'active' AND expires_at <= CURRENT_TIMESTAMP
        """)
        await db.commit()

# ─── MEETINGS & REVIEWS (оставляем для системы отзывов) ────────────────────────

async def create_meeting(listing_id: int, host_id: int, guest_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO meetings (listing_id, host_id, guest_id)
            VALUES (?, ?, ?)
        """, (listing_id, host_id, guest_id))
        await db.commit()
        return cur.lastrowid

async def create_review(meeting_id: int, from_user_id: int, to_user_id: int, rating: int, text: str) -> bool:
    """Создать отзыв. Возвращает True, если это второй отзыв во встрече (т.е. теперь оба оставили)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO reviews (meeting_id, from_user_id, to_user_id, rating, text)
            VALUES (?, ?, ?, ?, ?)
        """, (meeting_id, from_user_id, to_user_id, rating, text))
        
        # Проверяем, сколько отзывов теперь у этой встречи
        async with db.execute("SELECT COUNT(id) FROM reviews WHERE meeting_id = ?", (meeting_id,)) as cur:
            count_meeting = (await cur.fetchone())[0]
            
        if count_meeting >= 2:
            # Если оба оставили, обновляем рейтинг для ОБОИХ участников этой встречи
            # Сначала найдем всех участников этой встречи
            async with db.execute("SELECT host_id, guest_id FROM meetings WHERE id = ?", (meeting_id,)) as cur:
                meeting = await cur.fetchone()
                if meeting:
                    for uid in [meeting[0], meeting[1]]:
                        # Считаем рейтинг только по "завершенным" (взаимным) отзывам
                        async with db.execute("""
                            SELECT AVG(rating), COUNT(id) FROM reviews 
                            WHERE to_user_id = ? 
                              AND meeting_id IN (SELECT meeting_id FROM reviews GROUP BY meeting_id HAVING COUNT(id) >= 2)
                        """, (uid,)) as cur_rating:
                            row = await cur_rating.fetchone()
                            if row and row[1] > 0:
                                await db.execute(
                                    "UPDATE users SET rating = ?, reviews_count = ? WHERE id = ?",
                                    (row[0], row[1], uid)
                                )
            await db.commit()
            return True
            
        await db.commit()
        return False

async def get_listing(listing_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT l.*, u.first_name, u.username, u.rating, u.reviews_count
            FROM listings l
            JOIN users u ON l.user_id = u.id
            WHERE l.id = ?
        """, (listing_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_meeting(meeting_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT m.*, 
                   u1.first_name as host_name, u1.username as host_username,
                   u2.first_name as guest_name, u2.username as guest_username
            FROM meetings m
            JOIN users u1 ON m.host_id = u1.id
            JOIN users u2 ON m.guest_id = u2.id
            WHERE m.id = ?
        """, (meeting_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_user_meetings(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT m.*, 
                   u1.first_name as host_name, u2.first_name as guest_name
            FROM meetings m
            JOIN users u1 ON m.host_id = u1.id
            JOIN users u2 ON m.guest_id = u2.id
            WHERE m.host_id = ? OR m.guest_id = ?
            ORDER BY m.created_at DESC
        """, (user_id, user_id)) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

async def complete_meeting(meeting_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE meetings SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (meeting_id,)
        )
        await db.commit()

async def has_review(meeting_id: int, from_user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM reviews WHERE meeting_id = ? AND from_user_id = ?",
            (meeting_id, from_user_id)
        ) as cur:
            row = await cur.fetchone()
            return row is not None
