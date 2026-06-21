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
            CREATE TABLE IF NOT EXISTS join_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                from_user_id INTEGER NOT NULL,
                message TEXT,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (listing_id) REFERENCES listings(id),
                FOREIGN KEY (from_user_id) REFERENCES users(id)
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
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.*, u.first_name as author_name, u.username as author_username
            FROM reviews r
            JOIN users u ON r.from_user_id = u.id
            WHERE r.to_user_id = ?
            ORDER BY r.created_at DESC
        """, (user_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ─── LISTINGS ─────────────────────────────────────────────────────────────────

async def create_listing(
    user_id: int, title: str, description: str,
    drinks: str, snacks: str,
    latitude: float, longitude: float,
    location_name: str, max_people: int
) -> int:
    expires_at = datetime.now() + timedelta(hours=6)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO listings
            (user_id, title, description, drinks, snacks, latitude, longitude, location_name, max_people, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, title, description, drinks, snacks, latitude, longitude, location_name, max_people, expires_at))
        await db.commit()
        return cur.lastrowid


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


async def get_active_listings_near(lat: float, lon: float, radius_km: float = 5.0) -> List[Dict]:
    """Получить активные объявления — фильтрация по расстоянию делается в Python."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT l.*, u.first_name, u.username, u.rating, u.reviews_count
            FROM listings l
            JOIN users u ON l.user_id = u.id
            WHERE l.status = 'active'
              AND l.expires_at > CURRENT_TIMESTAMP
            ORDER BY l.created_at DESC
            LIMIT 200
        """) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_user_listings(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM listings WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 10
        """, (user_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def close_listing(listing_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE listings SET status = 'closed' WHERE id = ?",
            (listing_id,)
        )
        await db.commit()


async def expire_old_listings() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE listings SET status = 'expired'
            WHERE status = 'active' AND expires_at <= CURRENT_TIMESTAMP
        """)
        await db.commit()


# ─── JOIN REQUESTS ────────────────────────────────────────────────────────────

async def create_join_request(listing_id: int, from_user_id: int, message: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO join_requests (listing_id, from_user_id, message)
            VALUES (?, ?, ?)
        """, (listing_id, from_user_id, message))
        await db.commit()
        return cur.lastrowid


async def get_join_request(request_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT jr.*, u.first_name, u.username, u.rating, u.reviews_count
            FROM join_requests jr
            JOIN users u ON jr.from_user_id = u.id
            WHERE jr.id = ?
        """, (request_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_pending_requests_for_listing(listing_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT jr.*, u.first_name, u.username, u.rating, u.reviews_count
            FROM join_requests jr
            JOIN users u ON jr.from_user_id = u.id
            WHERE jr.listing_id = ? AND jr.status = 'pending'
        """, (listing_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def update_join_request_status(request_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE join_requests SET status = ? WHERE id = ?",
            (status, request_id)
        )
        await db.commit()


async def has_pending_request(listing_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM join_requests
            WHERE listing_id = ? AND from_user_id = ? AND status IN ('pending', 'accepted')
        """, (listing_id, user_id)) as cur:
            row = await cur.fetchone()
            return row is not None


# ─── MEETINGS ─────────────────────────────────────────────────────────────────

async def create_meeting(listing_id: int, host_id: int, guest_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO meetings (listing_id, host_id, guest_id)
            VALUES (?, ?, ?)
        """, (listing_id, host_id, guest_id))
        await db.commit()
        return cur.lastrowid


async def get_meeting(meeting_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT m.*,
                   h.first_name as host_name, h.username as host_username,
                   g.first_name as guest_name, g.username as guest_username
            FROM meetings m
            JOIN users h ON m.host_id = h.id
            JOIN users g ON m.guest_id = g.id
            WHERE m.id = ?
        """, (meeting_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_meetings(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT m.*,
                   h.first_name as host_name, h.username as host_username,
                   g.first_name as guest_name, g.username as guest_username
            FROM meetings m
            JOIN users h ON m.host_id = h.id
            JOIN users g ON m.guest_id = g.id
            WHERE (m.host_id = ? OR m.guest_id = ?)
            ORDER BY m.created_at DESC LIMIT 20
        """, (user_id, user_id)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def complete_meeting(meeting_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE meetings SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (meeting_id,))
        await db.commit()


# ─── REVIEWS ──────────────────────────────────────────────────────────────────

async def create_review(
    meeting_id: int, from_user_id: int, to_user_id: int,
    rating: int, text: str
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO reviews (meeting_id, from_user_id, to_user_id, rating, text)
            VALUES (?, ?, ?, ?, ?)
        """, (meeting_id, from_user_id, to_user_id, rating, text))

        # Пересчёт рейтинга пользователя
        async with db.execute("""
            SELECT AVG(rating) as avg_r, COUNT(*) as cnt
            FROM reviews WHERE to_user_id = ?
        """, (to_user_id,)) as cur:
            row = await cur.fetchone()
            avg_r = row[0] or 0.0
            cnt = row[1] or 0

        await db.execute(
            "UPDATE users SET rating = ?, reviews_count = ? WHERE id = ?",
            (round(avg_r, 2), cnt, to_user_id)
        )
        await db.commit()


async def has_review(meeting_id: int, from_user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM reviews
            WHERE meeting_id = ? AND from_user_id = ?
        """, (meeting_id, from_user_id)) as cur:
            row = await cur.fetchone()
            return row is not None
