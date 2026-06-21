from geopy.distance import geodesic
from typing import List, Dict
from datetime import datetime


def get_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками в километрах."""
    return geodesic((lat1, lon1), (lat2, lon2)).km


def filter_by_radius(listings: List[Dict], lat: float, lon: float, radius_km: float = 5.0) -> List[Dict]:
    """Фильтрует объявления по радиусу и добавляет поле distance_km."""
    result = []
    for listing in listings:
        dist = get_distance_km(lat, lon, listing["latitude"], listing["longitude"])
        if dist <= radius_km:
            listing["distance_km"] = round(dist, 2)
            result.append(listing)
    result.sort(key=lambda x: x["distance_km"])
    return result


def stars(rating: float) -> str:
    """Преобразует рейтинг в звёздочки."""
    full = int(round(rating))
    return "⭐" * full + "☆" * (5 - full)


def format_user_profile(user: Dict) -> str:
    name = user.get("first_name", "Аноним")
    username = f"@{user['username']}" if user.get("username") else "нет"
    age = f"{user['age']} лет" if user.get("age") else "не указан"
    bio = user.get("bio") or "не заполнено"
    rating = user.get("rating", 0.0)
    reviews_count = user.get("reviews_count", 0)

    return (
        f"👤 *{name}* ({username})\n"
        f"🎂 Возраст: {age}\n"
        f"📝 О себе: {bio}\n"
        f"⭐ Рейтинг: {stars(rating)} ({rating:.1f} / {reviews_count} отзывов)"
    )


def format_listing(listing: Dict, show_distance: bool = False) -> str:
    name = listing.get("first_name", "Аноним")
    username = f"@{listing['username']}" if listing.get("username") else ""
    rating = listing.get("rating", 0.0)
    reviews_count = listing.get("reviews_count", 0)

    drinks = listing.get("drinks") or "не указано"
    snacks = listing.get("snacks") or "не указано"
    description = listing.get("description") or ""
    location = listing.get("location_name") or "геолокация"
    max_p = listing.get("max_people", 1)

    expires_at = listing.get("expires_at", "")
    try:
        exp_dt = datetime.fromisoformat(str(expires_at))
        time_left = exp_dt - datetime.now()
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        exp_str = f"{hours}ч {minutes}мин"
    except Exception:
        exp_str = "скоро"

    dist_str = ""
    if show_distance and "distance_km" in listing:
        dist_str = f"\n📍 Расстояние: *{listing['distance_km']} км*"

    status_emoji = {"active": "🟢", "closed": "🔴", "expired": "⏰"}.get(listing.get("status", ""), "")

    text = (
        f"{status_emoji} *{listing['title']}*\n"
        f"👤 {name} {username} — {stars(rating)} ({rating:.1f})\n"
    )
    if description:
        text += f"💬 {description}\n"
    text += (
        f"🍾 Выпивка: {drinks}\n"
        f"🍕 Закуска: {snacks}\n"
        f"👥 Мест: {max_p}\n"
        f"📌 Место: {location}"
        f"{dist_str}\n"
        f"⏳ Истекает через: {exp_str}"
    )
    return text


def format_meeting(meeting: Dict, current_user_id: int) -> str:
    is_host = meeting["host_id"] == current_user_id
    partner_name = meeting["guest_name"] if is_host else meeting["host_name"]
    partner_username = meeting["guest_username"] if is_host else meeting["host_username"]
    role = "хозяин" if is_host else "гость"
    status_map = {"active": "🟢 Активна", "completed": "✅ Завершена", "cancelled": "❌ Отменена"}
    status = status_map.get(meeting["status"], meeting["status"])
    partner_str = f"@{partner_username}" if partner_username else partner_name

    return (
        f"🤝 Встреча #{meeting['id']}\n"
        f"Вы: {role}\n"
        f"Партнёр: {partner_str}\n"
        f"Статус: {status}"
    )
