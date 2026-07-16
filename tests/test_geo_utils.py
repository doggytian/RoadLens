"""geo_utils 投影工具测试：验证 WGS84 <-> 局部米制平面往返精度及辅助函数。"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Point

from server.geo_utils import (
    tile_center_from_features,
    tile_id_for_lonlat,
    to_local_geom,
    to_wgs84_geom,
)

# 以北京附近某点为投影中心
CENTER = (116.40, 39.91)


def test_roundtrip_point_precision():
    """点经过 (WGS84 -> 局部 -> WGS84) 往返后，误差应在毫米级以下。"""
    pt = Point(116.41, 39.92)
    local = to_local_geom(pt, CENTER)
    back = to_wgs84_geom(local, CENTER)
    assert abs(back.x - pt.x) < 1e-7
    assert abs(back.y - pt.y) < 1e-7


def test_local_distance_is_metric():
    """局部平面上的距离应为米制：中心点到自身经度 +0.01 度约为 850~950m（该纬度带）。"""
    p0 = to_local_geom(Point(CENTER[0], CENTER[1]), CENTER)
    p1 = to_local_geom(Point(CENTER[0] + 0.01, CENTER[1]), CENTER)
    dist = math.hypot(p1.x - p0.x, p1.y - p0.y)
    # 经度 0.01 度在纬度 39.91 处约 850m
    assert 800 < dist < 950


def test_roundtrip_linestring():
    line = LineString([(116.40, 39.91), (116.41, 39.92), (116.42, 39.90)])
    local = to_local_geom(line, CENTER)
    back = to_wgs84_geom(local, CENTER)
    for (bx, by), (ox, oy) in zip(back.coords, line.coords):
        assert abs(bx - ox) < 1e-7
        assert abs(by - oy) < 1e-7


def test_tile_center_from_features():
    features = [
        {"geometry": {"type": "Point", "coordinates": [116.0, 39.0]}},
        {"geometry": {"type": "Point", "coordinates": [118.0, 41.0]}},
    ]
    lon, lat = tile_center_from_features(features)
    assert abs(lon - 117.0) < 1e-9
    assert abs(lat - 40.0) < 1e-9


def test_tile_center_empty_returns_origin():
    assert tile_center_from_features([]) == (0.0, 0.0)


def test_tile_id_for_lonlat():
    tid = tile_id_for_lonlat(116.405, 39.915, 0.01)
    # 116.405 // 0.01 = 11640, 39.915 // 0.01 = 3991
    assert tid == "tile_11640_3991"
