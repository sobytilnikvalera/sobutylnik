from geopy.distance import geodesic

def calculate_distance(lat1, lon1, lat2, lon2):
    """Расчет расстояния в километрах между двумя точками."""
    if None in (lat1, lon1, lat2, lon2):
        return 999.0
    return geodesic((lat1, lon1), (lat2, lon2)).kilometers

def filter_by_radius(listings, lat, lon, radius_km=10.0):
    """Фильтрация списка объявлений по радиусу."""
    result = []
    for l in listings:
        d = calculate_distance(lat, lon, l['latitude'], l['longitude'])
        if d <= radius_km:
            l['distance'] = d
            result.append(l)
    return sorted(result, key=lambda x: x['distance'])

def stars(rating):
    """Преобразование числового рейтинга в эмодзи звезд."""
    if not rating:
        return "Нет оценок"
    full_stars = int(rating)
    empty_stars = 5 - full_stars
    return "⭐" * full_stars + "🔘" * empty_stars
