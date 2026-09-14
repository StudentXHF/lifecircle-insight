from app.utils.geo import destination_point, haversine_m, point_in_polygon, polygon_area_m2


def test_destination_distance_about_right():
    lat, lng = destination_point(31.2, 121.6, 1000, 90)
    assert 980 < haversine_m(31.2, 121.6, lat, lng) < 1020


def test_point_in_polygon():
    poly = [
        {'lat': 0, 'lng': 0}, {'lat': 0, 'lng': 1}, {'lat': 1, 'lng': 1}, {'lat': 1, 'lng': 0}
    ]
    assert point_in_polygon(.5, .5, poly)
    assert not point_in_polygon(2, 2, poly)
    assert polygon_area_m2(poly) > 1e9
