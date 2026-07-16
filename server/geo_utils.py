"""等距投影工具：把 WGS84 经纬度转换为以某中心为原点的米制平面坐标。

用于几何计算（宽度、面积、缓冲），避免经纬度直接做欧氏距离带来的形变。
"""
from __future__ import annotations

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

_WGS84 = "EPSG:4326"


def make_local_transformer(center_lon: float, center_lat: float):
    """构造 (经纬度 -> 米制平面) 与 (米制平面 -> 经纬度) 两个转换器。

    使用方位等距投影（Azimuthal Equidistant），以 center 为原点，
    在公里级尺度上距离与面积误差极小。
    """
    proj_crs = (
        f"+proj=aeqd +lat_0={center_lat} +lon_0={center_lon} "
        f"+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )
    to_local = Transformer.from_crs(_WGS84, proj_crs, always_xy=True)
    to_wgs84 = Transformer.from_crs(proj_crs, _WGS84, always_xy=True)
    return to_local, to_wgs84


def to_local_geom(geom_wgs84, center):
    """把 shapely 几何（WGS84）投影到局部米制平面。"""
    to_local, _ = make_local_transformer(center[0], center[1])
    return shapely_transform(to_local.transform, geom_wgs84)


def to_wgs84_geom(geom_local, center):
    """把局部米制平面几何投影回 WGS84。"""
    _, to_wgs84 = make_local_transformer(center[0], center[1])
    return shapely_transform(to_wgs84.transform, geom_local)


def tile_center_from_features(features: list) -> tuple:
    """从 FeatureCollection 估算一个合适的投影中心（取所有坐标均值）。"""
    lons, lats = [], []
    for f in features:
        g = shape(f.get("geometry") or {})
        if g.is_empty:
            continue
        for lon, lat in _coords_iter(g):
            lons.append(lon)
            lats.append(lat)
    if not lons:
        return (0.0, 0.0)
    return (sum(lons) / len(lons), sum(lats) / len(lats))


def _coords_iter(geom):
    """yield (lon, lat) 遍历几何所有坐标。"""
    t = geom.geom_type
    if t == "Point":
        yield geom.x, geom.y
    elif t in ("LineString", "LinearRing"):
        yield from geom.coords
    elif t in ("Polygon",):
        for ring in geom.interiors:
            yield from ring.coords
        yield from geom.exterior.coords
    else:  # Multi*
        for sub in geom.geoms:
            yield from _coords_iter(sub)


def tile_id_for_lonlat(lon: float, lat: float, grid_size_deg: float) -> str:
    """根据经纬度与网格大小计算 tile id（整数行列拼接）。"""
    col = int(lon // grid_size_deg)
    row = int(lat // grid_size_deg)
    return f"tile_{col}_{row}"
