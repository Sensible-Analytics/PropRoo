import h3


ZOOM_TO_H3_RES = {
    range(0, 8): 4,
    range(8, 11): 6,
    range(11, 13): 7,
    range(13, 22): 9,
}


def zoom_to_resolution(zoom: int) -> int:
    for zoom_range, res in ZOOM_TO_H3_RES.items():
        if zoom in zoom_range:
            return res
    return 7


def lat_lng_to_h3(lat: float, lng: float, resolution: int) -> str:
    return h3.geo_to_h3(lat, lng, resolution)


def h3_to_boundary(h3_index: str) -> list[list[float]]:
    return list(h3.h3_to_geo_boundary(h3_index, geo_json=True))
