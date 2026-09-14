from __future__ import annotations

import math
from typing import Iterable

EARTH_RADIUS_M = 6371008.8


def destination_point(lat: float, lng: float, distance_m: float, bearing_deg: float) -> tuple[float, float]:
    angular = distance_m / EARTH_RADIUS_M
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lng)
    lat2 = math.asin(math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(bearing))
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def haversine_m(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    p1 = math.radians(a_lat)
    p2 = math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlambda = math.radians(b_lng - a_lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def point_in_polygon(lat: float, lng: float, polygon: list[dict]) -> bool:
    # Ray casting using lng as x and lat as y. Suitable for small urban extents.
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]['lng'], polygon[i]['lat']
        xj, yj = polygon[j]['lng'], polygon[j]['lat']
        intersects = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def polygon_area_m2(points: list[dict]) -> float:
    if len(points) < 3:
        return 0.0
    lat0 = math.radians(sum(p['lat'] for p in points) / len(points))
    coords = []
    for p in points:
        x = math.radians(p['lng']) * EARTH_RADIUS_M * math.cos(lat0)
        y = math.radians(p['lat']) * EARTH_RADIUS_M
        coords.append((x, y))
    area = 0.0
    for i, (x1, y1) in enumerate(coords):
        x2, y2 = coords[(i + 1) % len(coords)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def make_grid(center_lat: float, center_lng: float, radius_m: int, spacing_m: int = 350) -> list[dict]:
    pts: list[dict] = []
    steps = max(1, radius_m // spacing_m)
    for iy in range(-steps, steps + 1):
        north = iy * spacing_m
        base_lat, base_lng = destination_point(center_lat, center_lng, abs(north), 0 if north >= 0 else 180)
        for ix in range(-steps, steps + 1):
            east = ix * spacing_m
            lat, lng = destination_point(base_lat, base_lng, abs(east), 90 if east >= 0 else 270)
            if haversine_m(center_lat, center_lng, lat, lng) <= radius_m:
                pts.append({'lat': lat, 'lng': lng})
    return pts


def centroid(points: Iterable[dict]) -> dict:
    pts = list(points)
    if not pts:
        return {'lat': 0.0, 'lng': 0.0}
    return {
        'lat': sum(p['lat'] for p in pts) / len(pts),
        'lng': sum(p['lng'] for p in pts) / len(pts),
    }
