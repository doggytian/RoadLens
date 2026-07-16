#!/usr/bin/env python3
"""生成 RoadLens 示例 tile 数据。

优先尝试用 Overpass API（公开、无需密钥）拉取一小块 OSM 路网并转换为
RoadCorridor / Lane / ReferenceLink 模型；若网络不可用或转换失败，
则回退到内置的合成生成器，确保总能产出可用的示例 tile。

用法:
    python scripts/fetch_sample.py                 # 默认：尝试 OSM，失败回退合成
    python scripts/fetch_sample.py --osm           # 强制使用 OSM（失败即报错）
    python scripts/fetch_sample.py --synthetic     # 强制合成
    python scripts/fetch_sample.py --bbox <w,s,e,n> --out <path>

输出: sample_data/tile_sample_city.geojson（默认）
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _local_proj(center_lon: float, center_lat: float):
    from pyproj import Transformer
    proj = (
        f"+proj=aeqd +lat_0={center_lat} +lon_0={center_lon} "
        f"+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )
    to_local = Transformer.from_crs("EPSG:4326", proj, always_xy=True)
    to_wgs = Transformer.from_crs(proj, "EPSG:4326", always_xy=True)
    return to_local, to_wgs


# --------------------------------------------------------------------------- #
# 合成生成器
# --------------------------------------------------------------------------- #
def _normal(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1.0
    return (-dy / L, dx / L)


def _offset_line(pts, dist):
    out = []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        if i == 0:
            nx, ny = _normal(pts[0], pts[1])
        elif i == n - 1:
            nx, ny = _normal(pts[-2], pts[-1])
        else:
            nx, ny = _normal(pts[i - 1], pts[i + 1])
        out.append((x + nx * dist, y + ny * dist))
    return out


def _corridor_from_centerline(center_local, lane_count, lane_w, cid, to_wgs,
                              missing_ref=False, ref_center_local=None):
    """由局部米制中心线与车道数构造走廊多边形 / 车道 / 参考中心线。

    ref_center_local: 参考中心线使用的中心线路径（默认与走廊中心线一致）。
    对于「共享结点的平行走廊」，可传入真正的结点连线，使多条走廊的
    参考中心线在路口处汇聚（符合真实分流/合流拓扑）。
    """
    half = lane_w / 2.0
    # 外侧边界（基于走廊中心线偏移）
    left = _offset_line(center_local, (lane_count / 2.0) * lane_w + half)
    right = _offset_line(center_local, -((lane_count / 2.0) * lane_w + half))
    poly_local = left + right[::-1]
    poly_wgs = [to_wgs.transform(x, y) for x, y in poly_local]

    feats = [{
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[round(a, 7), round(b, 7)] for a, b in poly_wgs]]},
        "properties": {
            "feature_type": "RoadCorridor", "id": cid,
            "tile_id": "sample_city", "lane_count": lane_count,
            "name": f"合成走廊 {cid}", "highway": "primary",
        },
    }]
    # 车道（平行偏移）
    spacing = lane_w
    for k in range(lane_count):
        off = -((lane_count - 1) / 2.0) * spacing + k * spacing
        lane_local = _offset_line(center_local, off)
        lane_wgs = [to_wgs.transform(x, y) for x, y in lane_local]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[round(a, 7), round(b, 7)] for a, b in lane_wgs]},
            "properties": {
                "feature_type": "Lane", "id": f"{cid}_L{k}",
                "tile_id": "sample_city", "corridor_id": cid, "lane_index": k,
            },
        })
    # 参考中心线（默认用走廊中心线；可指定真正的结点连线）
    if not missing_ref:
        ref_local = ref_center_local if ref_center_local is not None else center_local
        ref_wgs = [to_wgs.transform(x, y) for x, y in ref_local]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[round(a, 7), round(b, 7)] for a, b in ref_wgs]},
            "properties": {
                "feature_type": "ReferenceLink", "id": f"{cid}_R",
                "tile_id": "sample_city", "corridor_id": cid,
            },
        })
    return feats


def _corridor_between(j1, j2, lane_count, lane_w, offset, cid, to_wgs, missing_ref=False):
    """在结点 j1->j2 之间生成一条走廊，整体沿法向偏移 offset（米）。

    参考中心线落在真正的结点连线 j1->j2 上，因此共享同一对结点的两条
    走廊其参考中心线会在路口处汇聚（构成「菱形拓扑」候选）。
    """
    dx, dy = j2[0] - j1[0], j2[1] - j1[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    c0 = (j1[0] + nx * offset, j1[1] + ny * offset)
    c1 = (j2[0] + nx * offset, j2[1] + ny * offset)
    n = max(8, int(L / 25))
    center = [(c0[0] + (c1[0] - c0[0]) * i / (n - 1), c0[1] + (c1[1] - c0[1]) * i / (n - 1)) for i in range(n)]
    # 参考中心线：真正的结点连线（不偏移）
    ref = [(j1[0] + (j2[0] - j1[0]) * i / (n - 1), j1[1] + (j2[1] - j1[1]) * i / (n - 1)) for i in range(n)]
    return _corridor_from_centerline(center, lane_count, lane_w, cid, to_wgs,
                                     missing_ref=missing_ref, ref_center_local=ref)


def gen_synthetic(center=(116.39, 39.91)):
    to_local, to_wgs = _local_proj(*center)
    # 局部米制结点（构成一张小型连通路网）
    J = {
        "J1": (0, 0), "J2": (300, 0), "J3": (300, 300),
        "J4": (0, 300), "J5": (600, 0),
        "J6": (0, -250), "J7": (200, -250),
    }
    feats = []
    # C1 / C2：J1<->J2 的两条平行走廊（参考线共享 J1/J2 结点）-> 菱形拓扑
    feats += _corridor_between(J["J1"], J["J2"], lane_count=3, lane_w=3.5, offset=-14, cid="C1", to_wgs=to_wgs)
    feats += _corridor_between(J["J1"], J["J2"], lane_count=2, lane_w=3.5, offset=14, cid="C2", to_wgs=to_wgs)
    # C3：J2<->J3 正常走廊
    feats += _corridor_between(J["J2"], J["J3"], lane_count=3, lane_w=3.5, offset=0, cid="C3", to_wgs=to_wgs)
    # C4：J6<->J7 支线，标称 2 车道但实际很宽 -> 走廊宽度异常（孤立支线）
    feats += _corridor_between(J["J6"], J["J7"], lane_count=2, lane_w=12.0, offset=0, cid="C4", to_wgs=to_wgs)
    # C5：J2<->J3 与 C3 平行且故意重叠 + 宽度异常 -> 压盖 + 走廊宽度异常
    feats += _corridor_between(J["J2"], J["J3"], lane_count=3, lane_w=5.0, offset=3, cid="C5", to_wgs=to_wgs)
    # C6：J3<->J4 正常，但故意缺失参考中心线 -> 参考绑定
    feats += _corridor_between(J["J3"], J["J4"], lane_count=3, lane_w=3.5, offset=0, cid="C6", to_wgs=to_wgs, missing_ref=True)
    # C7：J1<->J4 正常
    feats += _corridor_between(J["J1"], J["J4"], lane_count=3, lane_w=3.5, offset=0, cid="C7", to_wgs=to_wgs)
    # C8：J2<->J5 正常（延伸出路口）
    feats += _corridor_between(J["J2"], J["J5"], lane_count=3, lane_w=3.5, offset=0, cid="C8", to_wgs=to_wgs)
    # 孤立参考链（不挂接任何走廊）-> 参考拓扑
    iso = _corridor_from_centerline(
        [(0, -120), (80, -150), (160, -120)], lane_count=1, lane_w=3.5, cid="ISO", to_wgs=to_wgs
    )
    iso = [f for f in iso if f["properties"]["feature_type"] == "ReferenceLink"]
    feats += iso
    # C9：退化的空几何走廊 -> 几何有效性
    feats.append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": []},
        "properties": {
            "feature_type": "RoadCorridor", "id": "C9",
            "tile_id": "sample_city", "lane_count": 1, "name": "退化走廊", "highway": "primary",
        },
    })
    # C10：宽度小于负向缓冲距离（0.5m）的窄走廊 -> 缓冲断裂
    thin = [(50, 399.85), (250, 399.85), (250, 400.15), (50, 400.15), (50, 399.85)]
    thin_wgs = [to_wgs.transform(x, y) for x, y in thin]
    feats.append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[round(a, 7), round(b, 7)] for a, b in thin_wgs]]},
        "properties": {
            "feature_type": "RoadCorridor", "id": "C10",
            "tile_id": "sample_city", "lane_count": 1, "name": "窄走廊", "highway": "service",
        },
    })
    return feats


# --------------------------------------------------------------------------- #
# OSM / Overpass 路径
# --------------------------------------------------------------------------- #
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_overpass(bbox):
    import requests
    w, s, e, n = bbox
    q = (
        f"[out:json][timeout:25];("
        f'way["highway"]({s},{w},{n},{e}););out geom;'
    )
    r = requests.post(OVERPASS_URL, data={"data": q}, timeout=40)
    r.raise_for_status()
    ways = []
    for el in r.json().get("elements", []):
        if el["type"] == "way" and "geometry" in el:
            ways.append(el["geometry"])
    return ways


def build_from_osm(ways, center):
    from shapely.geometry import LineString, mapping
    from shapely.ops import unary_union
    from shapely import wkt  # noqa: F401  (ensure shapely import OK)
    to_local, to_wgs = _local_proj(*center)
    # 转到局部米制做缓冲与聚类
    local_lines = []
    for g in ways:
        pts = [(to_local.transform(lon, lat)) for lon, lat in [(p["lon"], p["lat"]) for p in g]]
        if len(pts) >= 2:
            local_lines.append(LineString(pts))

    # 贪心聚类：与已有聚类代表线距离 < 阈值 归为一组
    THRESH = 25.0
    clusters = []
    for ln in local_lines:
        mid = ln.interpolate(0.5)
        placed = False
        for cl in clusters:
            if cl["rep"].distance(mid) < THRESH:
                cl["lines"].append(ln)
                placed = True
                break
        if not placed:
            clusters.append({"rep": mid, "lines": [ln]})

    feats = []
    for i, cl in enumerate(clusters):
        cid = f"OSM_{i}"
        union = unary_union([l.buffer(2.0) for l in cl["lines"]])
        if union.is_empty:
            continue
        # 走廊多边形（转回 WGS84）
        if union.geom_type == "Polygon":
            polys = [union]
        else:
            polys = [g for g in union.geoms if g.geom_type == "Polygon"]
        for poly in polys:
            wgs = [to_wgs.transform(x, y) for x, y in poly.exterior.coords]
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[round(a, 7), round(b, 7)] for a, b in wgs]]},
                "properties": {"feature_type": "RoadCorridor", "id": f"{cid}_P",
                               "tile_id": "sample_city", "lane_count": len(cl["lines"])},
            })
        # Lane = 各 way
        for j, ln in enumerate(cl["lines"]):
            wgs = [to_wgs.transform(x, y) for x, y in ln.coords]
            feats.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[round(a, 7), round(b, 7)] for a, b in wgs]},
                "properties": {"feature_type": "Lane", "id": f"{cid}_L{j}",
                               "tile_id": "sample_city", "corridor_id": f"{cid}_P"},
            })
        # ReferenceLink = 最长 way
        longest = max(cl["lines"], key=lambda l: l.length)
        wgs = [to_wgs.transform(x, y) for x, y in longest.coords]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[round(a, 7), round(b, 7)] for a, b in wgs]},
            "properties": {"feature_type": "ReferenceLink", "id": f"{cid}_R",
                           "tile_id": "sample_city", "corridor_id": f"{cid}_P"},
        })
    return feats


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", action="store_true", help="强制使用 Overpass")
    ap.add_argument("--synthetic", action="store_true", help="强制合成")
    ap.add_argument("--bbox", default="116.38,39.90,116.40,39.92", help="w,s,e,n")
    ap.add_argument("--center", default="116.39,39.91", help="lon,lat")
    ap.add_argument("--out", default=os.path.join(ROOT, "sample_data", "tile_sample_city.geojson"))
    args = ap.parse_args()

    center = tuple(float(x) for x in args.center.split(","))
    bbox = tuple(float(x) for x in args.bbox.split(","))

    feats = None
    if not args.synthetic:
        try:
            print("尝试通过 Overpass 拉取 OSM 路网 ...")
            ways = fetch_overpass(bbox)
            if ways:
                feats = build_from_osm(ways, center)
                print(f"OSM 转换完成，要素数={len(feats)}")
            else:
                print("OSM 返回为空，回退合成。")
        except Exception as e:  # noqa: BLE001
            if args.osm:
                print(f"Overpass 拉取失败：{e}", file=sys.stderr)
                sys.exit(1)
            print(f"Overpass 不可用（{e}），回退到合成生成器。")

    if feats is None:
        feats = gen_synthetic(center)
        print(f"合成示例生成完成，要素数={len(feats)}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fc = {
        "type": "FeatureCollection",
        "tile_id": "sample_city",
        "source": "osm_or_synthetic",
        "features": feats,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    print(f"已写出: {args.out}")


if __name__ == "__main__":
    main()
