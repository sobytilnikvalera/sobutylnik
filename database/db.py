import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")


async def _connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return await asyncpg.connect(url, ssl="require")


async def _fetchrow(query: str, *args):
    db = await _connect()
    try:
        row = await db.fetchrow(query, *args)
        return dict(row) if row else None
    finally:
        await db.close()


async def _fetch(query: str, *args):
    db = await _connect()
    try:
        return [dict(row) for row in await db.fetch(query, *args)]
    finally:
        await db.close()


async def _execute(query: str, *args):
    db = await _connect()
    try:
        return await db.execute(query, *args)
    finally:
        await db.close()


async def init_db():
    """Initialize the PostgreSQL schema used by the bot."""
    db = await _connect()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL,
                age INTEGER,
                bio TEXT,
                rating DOUBLE PRECISION DEFAULT 0.0,
                reviews_count INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                is_banned INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id),
                title TEXT NOT NULL,
                description TEXT,
                drinks TEXT,
                snacks TEXT,
                photo_id TEXT,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                location_name TEXT,
                max_people INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMPTZ
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                id BIGSERIAL PRIMARY KEY,
                from_user_id BIGINT NOT NULL REFERENCES users(id),
                to_user_id BIGINT NOT NULL REFERENCES users(id),
                listing_id BIGINT NOT NULL REFERENCES listings(id),
                is_like INTEGER NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_user_id, to_user_id, listing_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id BIGSERIAL PRIMARY KEY,
                listing_id BIGINT NOT NULL REFERENCES listings(id),
                host_id BIGINT NOT NULL REFERENCES users(id),
                guest_id BIGINT NOT NULL REFERENCES users(id),
                status TEXT DEFAULT 'active',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMPTZ
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id BIGSERIAL PRIMARY KEY,
                meeting_id BIGINT NOT NULL REFERENCES meetings(id),
                from_user_id BIGINT NOT NULL REFERENCES users(id),
                to_user_id BIGINT NOT NULL REFERENCES users(id),
                rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                text TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
    finally:
        await db.close()


async def get_user(user_id: int) -> Optional[Dict]:
    return await _fetchrow("SELECT * FROM users WHERE id = $1", user_id)


async def create_user(user_id: int, username: str, first_name: str) -> None:
    await _execute(
        "INSERT INTO users (id, username, first_name) VALUES ($1, $2, $3) ON CONFLICT (id) DO NOTHING",
        user_id, username, first_name,
    )


async def update_user_profile(user_id: int, age: Optional[int], bio: Optional[str]) -> None:
    await _execute("UPDATE users SET age = $1, bio = $2 WHERE id = $3", age, bio, user_id)


async def get_user_reviews(user_id: int) -> List[Dict]:
    return await _fetch("""
        SELECT r.*, u.first_name AS author_name, u.username AS author_username
        FROM reviews r JOIN users u ON r.from_user_id = u.id
        WHERE r.to_user_id = $1
          AND r.meeting_id IN (SELECT meeting_id FROM reviews GROUP BY meeting_id HAVING COUNT(id) >= 2)
        ORDER BY r.created_at DESC
    """, user_id)


async def create_listing(user_id: int, title: str, description: str, drinks: str, snacks: str,
                         photo_id: str, latitude: float, longitude: float,
                         location_name: str, max_people: int) -> int:
    expires_at = datetime.utcnow() + timedelta(hours=48)
    row = await _fetchrow("""
        INSERT INTO listings
        (user_id, title, description, drinks, snacks, photo_id, latitude, longitude, location_name, max_people, expires_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id
    """, user_id, title, description, drinks, snacks, photo_id, latitude, longitude, location_name, max_people, expires_at)
    return row["id"]


async def get_next_listing_for_user(user_id: int, lat: float, lon: float) -> Optional[Dict]:
    now = datetime.utcnow()
    try:
        return await _fetchrow("""
            SELECT l.*, u.first_name, u.username, u.rating, u.reviews_count,
            (6371 * acos(cos(radians($1)) * cos(radians(l.latitude)) *
             cos(radians(l.longitude) - radians($2)) + sin(radians($1)) * sin(radians(l.latitude)))) AS distance
            FROM listings l JOIN users u ON l.user_id = u.id
            WHERE l.status = 'active' AND l.user_id != $3 AND l.expires_at > $4
              AND l.id NOT IN (SELECT listing_id FROM likes WHERE from_user_id = $3)
            ORDER BY distance ASC LIMIT 1
        """, lat, lon, user_id, now)
    except Exception:
        rows = await _fetch("""
            SELECT l.*, u.first_name, u.username, u.rating, u.reviews_count
            FROM listings l JOIN users u ON l.user_id = u.id
            WHERE l.status = 'active' AND l.user_id != $1 AND l.expires_at > $2
              AND l.id NOT IN (SELECT listing_id FROM likes WHERE from_user_id = $1)
            ORDER BY l.created_at DESC
        """, user_id, now)
        if not rows:
            return None
        from utils.helpers import calculate_distance
        for item in rows:
            item["distance"] = calculate_distance(lat, lon, item["latitude"], item["longitude"])
        return sorted(rows, key=lambda item: item["distance"])[0]


async def add_like(from_user_id: int, to_user_id: int, listing_id: int, is_like: int):
    await _execute("""
        INSERT INTO likes (from_user_id, to_user_id, listing_id, is_like)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT (from_user_id, to_user_id, listing_id)
        DO UPDATE SET is_like = EXCLUDED.is_like
    """, int(from_user_id), int(to_user_id), int(listing_id), int(is_like))
    if is_like == 1:
        row = await _fetchrow("""
            SELECT id FROM likes WHERE from_user_id = $1 AND to_user_id = $2 AND is_like = 1
        """, int(to_user_id), int(from_user_id))
        return row is not None
    return False


async def get_user_active_listing(user_id: int) -> Optional[Dict]:
    return await _fetchrow("""
        SELECT * FROM listings WHERE user_id = $1 AND status = 'active' AND expires_at > CURRENT_TIMESTAMP
    """, user_id)


async def close_listing(listing_id: int) -> None:
    await _execute("UPDATE listings SET status = 'closed' WHERE id = $1", listing_id)


async def expire_old_listings() -> None:
    await _execute("UPDATE listings SET status = 'expired' WHERE status = 'active' AND expires_at <= CURRENT_TIMESTAMP")


async def create_meeting(listing_id: int, host_id: int, guest_id: int) -> int:
    row = await _fetchrow("""
        INSERT INTO meetings (listing_id, host_id, guest_id) VALUES ($1,$2,$3) RETURNING id
    """, listing_id, host_id, guest_id)
    return row["id"]


async def create_review(meeting_id: int, from_user_id: int, to_user_id: int, rating: int, text: str) -> bool:
    db = await _connect()
    try:
        async with db.transaction():
            await db.execute("""
                INSERT INTO reviews (meeting_id, from_user_id, to_user_id, rating, text)
                VALUES ($1,$2,$3,$4,$5)
            """, meeting_id, from_user_id, to_user_id, rating, text)
            count = await db.fetchval("SELECT COUNT(id) FROM reviews WHERE meeting_id = $1", meeting_id)
            if count >= 2:
                meeting = await db.fetchrow("SELECT host_id, guest_id FROM meetings WHERE id = $1", meeting_id)
                if meeting:
                    for uid in (meeting["host_id"], meeting["guest_id"]):
                        row = await db.fetchrow("""
                            SELECT AVG(rating) AS avg_rating, COUNT(id) AS review_count
                            FROM reviews
                            WHERE to_user_id = $1 AND meeting_id IN
                              (SELECT meeting_id FROM reviews GROUP BY meeting_id HAVING COUNT(id) >= 2)
                        """, uid)
                        if row and row["review_count"] > 0:
                            await db.execute("UPDATE users SET rating = $1, reviews_count = $2 WHERE id = $3",
                                             row["avg_rating"], row["review_count"], uid)
                return True
            return False
    finally:
        await db.close()


async def get_listing(listing_id: int) -> Optional[Dict]:
    return await _fetchrow("""
        SELECT l.*, u.first_name, u.username, u.rating, u.reviews_count
        FROM listings l JOIN users u ON l.user_id = u.id WHERE l.id = $1
    """, listing_id)


async def get_meeting(meeting_id: int) -> Optional[Dict]:
    return await _fetchrow("""
        SELECT m.*, u1.first_name AS host_name, u1.username AS host_username,
               u2.first_name AS guest_name, u2.username AS guest_username
        FROM meetings m JOIN users u1 ON m.host_id = u1.id JOIN users u2 ON m.guest_id = u2.id
        WHERE m.id = $1
    """, meeting_id)


async def get_user_meetings(user_id: int) -> List[Dict]:
    return await _fetch("""
        SELECT m.*, u1.first_name AS host_name, u2.first_name AS guest_name
        FROM meetings m JOIN users u1 ON m.host_id = u1.id JOIN users u2 ON m.guest_id = u2.id
        WHERE m.host_id = $1 OR m.guest_id = $1 ORDER BY m.created_at DESC
    """, user_id)


async def complete_meeting(meeting_id: int) -> None:
    await _execute("UPDATE meetings SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = $1", meeting_id)


async def has_review(meeting_id: int, from_user_id: int) -> bool:
    return await _fetchrow("SELECT id FROM reviews WHERE meeting_id = $1 AND from_user_id = $2", meeting_id, from_user_id) is not None


async def admin_counts():
    row = await _fetchrow("""
        SELECT (SELECT COUNT(*) FROM users) AS users_count,
               (SELECT COUNT(*) FROM listings WHERE status = 'active') AS active_listings
    """)
    return row["users_count"], row["active_listings"]


async def admin_ban_user(user_id: int) -> None:
    await _execute("UPDATE users SET is_banned = 1 WHERE id = $1", user_id)


async def admin_list_users(limit: int = 15) -> List[Dict]:
    return await _fetch("SELECT id, first_name, username FROM users ORDER BY created_at DESC LIMIT $1", limit)


async def admin_user_ids() -> List[int]:
    rows = await _fetch("SELECT id FROM users")
    return [row["id"] for row in rows]


async def admin_list_listings(limit: int = 30, status: str = "active") -> List[Dict]:
    return await _fetch("""
        SELECT l.id, l.user_id, l.title, l.description, l.drinks, l.snacks,
               l.photo_id, l.location_name, l.max_people, l.status,
               l.created_at, l.expires_at,
               u.first_name, u.username
        FROM listings l
        JOIN users u ON u.id = l.user_id
        WHERE l.status = $1
        ORDER BY l.created_at DESC
        LIMIT $2
    """, status, limit)


async def admin_list_user_listings(user_id: int, limit: int = 30) -> List[Dict]:
    return await _fetch("""
        SELECT id, user_id, title, description, drinks, snacks,
               photo_id, location_name, max_people, status, created_at, expires_at
        FROM listings
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
    """, user_id, limit)
