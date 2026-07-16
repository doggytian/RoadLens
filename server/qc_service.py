"""质量检查服务：用 shapely 在本地米制投影下实现 8 类通用检查。

输入一个 tile 的 GeoJSON FeatureCollection，输出每个检查对应的
FeatureCollection（带 check_type / severity / message 属性），供前端叠加。

注意：本模块仅依赖开源库（shapely / pyproj），不依赖任何专有数据或算法。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon, shape
from shapely.ops import unary_union

from server.config import CONFIG
from server.geo_utils import tile_center_from_features, to_local_geom

CHECK_NAMES = [
    "corridor_width",
    "buffer_break",
    "centerline_coverage",
    "overlap",
    "diamond_topology",
    "geometry_validity",
    "reference_binding",
    "reference_topology",
]


class QCService:
    def __init__(self):
        self.cfg = CONFIG

    # ------------------------------------------------------------------ #
    def run_all(self, tile_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        return {name: self.run_one(name, tile_data) for name in CHECK_NAMES}

    def run_one(self, name: str, tile_data: Dict[str, Any]) -> Dict[str, Any]:
        if name not in CHECK_NAMES:
            raise ValueError(f"unknown check: {name}")
        features = tile_data.get("features", [])
        center = tile_center_from_features(features)
        # 预投影到局部米制平面
        local = self._to_local_features(features, center)

        method = getattr(self, f"_check_{name}")
        problems = method(local, center)
        return self._to_feature_collection(name, problems, center)

    # ------------------------------------------------------------------ #
    # 工具
    # ------------------------------------------------------------------ #
    def _to_local_features(self, features, center) -> List[Dict[str, Any]]:
        out = []
        for ft in features:
            g = shape(ft.get("geometry") or {})
            lg = to_local_geom(g, center)
            out.append({"props": ft.get("properties", {}), "geom": lg, "geom_wgs": g})
        return out

    def _to_feature_collection(self, name, problems, center) -> Dict[str, Any]:
        feats = []
        for p in problems:
            feats.append({
                "type": "Feature",
                "geometry": p["geometry"],  # 已是 WGS84
                "properties": {
                    "check_type": name,
                    "severity": p.get("severity", "warning"),
                    "message": p.get("message", ""),
                    "feature_id": p.get("feature_id", ""),
                    "feature_type": p.get("feature_type", ""),
                },
            })
        return {
            "type": "FeatureCollection",
            "check_type": name,
            "features": feats,
            "count": len(feats),
        }

    def _by_type(self, local, ftype) -> List[Dict[str, Any]]:
        return [f for f in local if f["props"].get("feature_type") == ftype]

    def _lane_count(self, props) -> int:
        return max(1, int(props.get("lane_count", 1) or 1))

    # ------------------------------------------------------------------ #
    # 1. 走廊宽度异常
    # ------------------------------------------------------------------ #
    def _check_corridor_width(self, local, center) -> List[Dict[str, Any]]:
        problems = []
        for f in self._by_type(local, "RoadCorridor"):
            g = f["geom"]
            if not isinstance(g, (Polygon, MultiPolygon)) or g.area < 1e-6:
                continue
            # 用最小外接旋转矩形估算走廊长度与垂直宽度
            try:
                mrr = g.minimum_rotated_rectangle
            except Exception:
                continue
            coords = list(mrr.exterior.coords)
            # 取四边中最长与最短边
            edges = []
            for i in range(len(coords) - 1):
                a = coords[i]
                b = coords[i + 1]
                edges.append(math.hypot(b[0] - a[0], b[1] - a[1]))
            edges.sort()
            short, long = edges[0], edges[-1]
            perp_width = g.area / long if long > 0 else short
            expected = self._lane_count(f["props"]) * self.cfg.std_lane_width
            lo = expected * (1 - self.cfg.corridor_width_tolerance)
            hi = expected * (1 + self.cfg.corridor_width_tolerance)
            if not (lo <= perp_width <= hi):
                problems.append({
                    "geometry": f["geom_wgs"].__geo_interface__,
                    "feature_id": f["props"].get("id"),
                    "feature_type": "RoadCorridor",
                    "severity": "warning",
                    "message": (
                        f"走廊垂直宽度 {perp_width:.1f}m 偏离预期 "
                        f"{expected:.1f}m (车道数 {self._lane_count(f['props'])})"
                    ),
                })
        return problems

    # ------------------------------------------------------------------ #
    # 2. 缓冲断裂
    # ------------------------------------------------------------------ #
    def _check_buffer_break(self, local, center) -> List[Dict[str, Any]]:
        problems = []
        d = -self.cfg.corridor_buffer_distance
        for f in self._by_type(local, "RoadCorridor"):
            g = f["geom"]
            if not isinstance(g, (Polygon, MultiPolygon)) or g.area < 1e-6:
                continue
            try:
                buf = g.buffer(d)
            except Exception:
                continue
            if buf.is_empty:
                problems.append({
                    "geometry": f["geom_wgs"].__geo_interface__,
                    "feature_id": f["props"].get("id"),
                    "feature_type": "RoadCorridor",
                    "severity": "warning",
                    "message": "负向缓冲后走廊完全消失（宽度不足）",
                })
            elif buf.geom_type == "MultiPolygon" or (
                isinstance(buf, Polygon) and len(buf.interiors) > 0
            ):
                problems.append({
                    "geometry": f["geom_wgs"].__geo_interface__,
                    "feature_id": f["props"].get("id"),
                    "feature_type": "RoadCorridor",
                    "severity": "warning",
                    "message": "负向缓冲后走廊破碎为多部件（存在内孔/裂缝）",
                })
        return problems

    # ------------------------------------------------------------------ #
    # 3. 中心线覆盖
    # ------------------------------------------------------------------ #
    def _check_centerline_coverage(self, local, center) -> List[Dict[str, Any]]:
        corridors = self._by_type(local, "RoadCorridor")
        links = self._by_type(local, "ReferenceLink")
        # 建立 corridor_id -> corridor 几何
        cid_map = {c["props"].get("id"): c["geom"] for c in corridors}
        problems = []
        for ln in links:
            cid = ln["props"].get("corridor_id")
            corr = cid_map.get(cid)
            if corr is None:
                # 退化：用包含 link 起点的走廊
                for c in corridors:
                    if c["geom"].contains(ln["geom"].interpolate(0)):
                        corr = c["geom"]
                        break
            if corr is None:
                continue
            total = ln["geom"].length
            if total < 1e-6:
                continue
            inside = ln["geom"].intersection(corr).length
            ratio = inside / total
            if ratio < self.cfg.centerline_coverage_threshold:
                problems.append({
                    "geometry": ln["geom_wgs"].__geo_interface__,
                    "feature_id": ln["props"].get("id"),
                    "feature_type": "ReferenceLink",
                    "severity": "warning",
                    "message": f"中心线被走廊覆盖 {ratio * 100:.0f}% < 阈值 "
                               f"{self.cfg.centerline_coverage_threshold * 100:.0f}%",
                })
        return problems

    # ------------------------------------------------------------------ #
    # 4. 压盖检测
    # ------------------------------------------------------------------ #
    @staticmethod
    def _local_direction(geom_local) -> float:
        """返回多边形主轴方向（度，0~180），用最小外接旋转矩形的最长边估算。"""
        try:
            mrr = geom_local.minimum_rotated_rectangle
        except Exception:
            return 0.0
        coords = list(mrr.exterior.coords)
        best, ang = 0.0, 0.0
        for i in range(len(coords) - 1):
            dx = coords[i + 1][0] - coords[i][0]
            dy = coords[i + 1][1] - coords[i][1]
            d = math.hypot(dx, dy)
            if d > best:
                best, ang = d, math.degrees(math.atan2(dy, dx))
        return ang % 180.0

    def _check_overlap(self, local, center) -> List[Dict[str, Any]]:
        polys = self._by_type(local, "RoadCorridor")
        dirs = {id(f): self._local_direction(f["geom"]) for f in polys}
        problems = []
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                a, b = polys[i]["geom"], polys[j]["geom"]
                da, db = dirs[id(polys[i])], dirs[id(polys[j])]
                # 主轴方向夹角（取 0~90）
                diff = abs(((da - db + 90.0) % 180.0) - 90.0)
                if diff > 45.0:
                    # 近似垂直 -> 视为路口交叉而非并行压盖，跳过
                    continue
                try:
                    inter = a.intersection(b)
                except Exception:
                    continue
                if inter.area >= self.cfg.overlap_min_area:
                    # 用交集几何作为问题位置
                    try:
                        from server.geo_utils import to_wgs84_geom
                        wgs = to_wgs84_geom(inter, center)
                        geom_iface = wgs.__geo_interface__
                    except Exception:
                        geom_iface = polys[i]["geom_wgs"].__geo_interface__
                    problems.append({
                        "geometry": geom_iface,
                        "feature_id": f"{polys[i]['props'].get('id')}|{polys[j]['props'].get('id')}",
                        "feature_type": "RoadCorridor",
                        "severity": "error",
                        "message": f"走廊与另一走廊重叠 {inter.area:.1f} ㎡",
                    })
        return problems

    # ------------------------------------------------------------------ #
    # 5. 菱形拓扑（近似）：两走廊共享一对起讫 reference 节点
    # ------------------------------------------------------------------ #
    def _check_diamond_topology(self, local, center) -> List[Dict[str, Any]]:
        links = self._by_type(local, "ReferenceLink")
        if len(links) < 2:
            return []
        cid_map = {}
        for ln in links:
            cid = ln["props"].get("corridor_id")
            if cid is None:
                continue
            cid_map.setdefault(cid, []).append(ln["geom"])

        # 每个 corridor 的起讫节点（聚合并四舍五入避免浮点误差）
        def node_key(pt):
            return (round(pt[0], 1), round(pt[1], 1))

        endpoints: Dict[str, Tuple] = {}
        for cid, geoms in cid_map.items():
            starts, ends = [], []
            for g in geoms:
                if g.geom_type == "LineString":
                    starts.append(node_key(g.coords[0]))
                    ends.append(node_key(g.coords[-1]))
            if starts and ends:
                endpoints[cid] = (starts[0], ends[0])

        problems = []
        cids = list(endpoints.keys())
        for i in range(len(cids)):
            for j in range(i + 1, len(cids)):
                a, b = endpoints[cids[i]], endpoints[cids[j]]
                if a[0] == b[0] and a[1] == b[1]:
                    # 共享起讫节点 -> 菱形候选
                    p0 = list(a[0])
                    p1 = list(a[1])
                    from server.geo_utils import to_wgs84_geom
                    line = LineString([p0, p1])
                    wgs = to_wgs84_geom(line, center)
                    problems.append({
                        "geometry": wgs.__geo_interface__,
                        "feature_id": f"{cids[i]}|{cids[j]}",
                        "feature_type": "RoadCorridor",
                        "severity": "info",
                        "message": f"检测到菱形拓扑候选：走廊 {cids[i]} 与 {cids[j]} 共享起讫节点",
                    })
        return problems

    # ------------------------------------------------------------------ #
    # 6. 几何有效性
    # ------------------------------------------------------------------ #
    def _check_geometry_validity(self, local, center) -> List[Dict[str, Any]]:
        problems = []
        for f in local:
            g = f["geom"]
            ftype = f["props"].get("feature_type")
            if g.is_empty:
                problems.append(self._geom_prob(f, "error", "空几何"))
                continue
            if not g.is_valid:
                problems.append(self._geom_prob(f, "error", "无效几何（自相交/环未闭合）"))
                continue
            if g.geom_type in ("Polygon", "MultiPolygon"):
                if g.area < self.cfg.min_valid_area:
                    problems.append(self._geom_prob(f, "warning", f"零面积/过小（{g.area:.4f}㎡）"))
            else:
                if g.length < 1e-3:
                    problems.append(self._geom_prob(f, "warning", "零长度线"))
        return problems

    def _geom_prob(self, f, severity, msg) -> Dict[str, Any]:
        return {
            "geometry": f["geom_wgs"].__geo_interface__,
            "feature_id": f["props"].get("id"),
            "feature_type": f["props"].get("feature_type"),
            "severity": severity,
            "message": msg,
        }

    # ------------------------------------------------------------------ #
    # 7. 参考绑定：走廊未挂接任何 ReferenceLink
    # ------------------------------------------------------------------ #
    def _check_reference_binding(self, local, center) -> List[Dict[str, Any]]:
        corridors = self._by_type(local, "RoadCorridor")
        links = self._by_type(local, "ReferenceLink")
        bound_ids = set()
        for ln in links:
            cid = ln["props"].get("corridor_id")
            if cid:
                bound_ids.add(cid)
        problems = []
        for c in corridors:
            cid = c["props"].get("id")
            if cid in bound_ids:
                continue
            # 退化：检查有无 link 落入该走廊
            hit = any(c["geom"].contains(ln["geom"].interpolate(0)) for ln in links)
            if hit:
                continue
            problems.append({
                "geometry": c["geom_wgs"].__geo_interface__,
                "feature_id": cid,
                "feature_type": "RoadCorridor",
                "severity": "warning",
                "message": "走廊未挂接任何 ReferenceLink",
            })
        return problems

    # ------------------------------------------------------------------ #
    # 8. 参考拓扑：ReferenceLink 链条断裂 / 孤立段
    # ------------------------------------------------------------------ #
    def _check_reference_topology(self, local, center) -> List[Dict[str, Any]]:
        links = self._by_type(local, "ReferenceLink")
        if not links:
            return []
        node_degree: Dict[Tuple, int] = {}
        node_link: Dict[Tuple, List[int]] = {}

        def key(pt):
            return (round(pt[0], 1), round(pt[1], 1))

        for idx, ln in enumerate(links):
            g = ln["geom"]
            if g.geom_type != "LineString" or len(g.coords) < 2:
                continue
            s, e = key(g.coords[0]), key(g.coords[-1])
            for n in (s, e):
                node_degree[n] = node_degree.get(n, 0) + 1
                node_link.setdefault(n, []).append(idx)

        problems = []
        isolated = set()
        for idx, ln in enumerate(links):
            g = ln["geom"]
            if g.geom_type != "LineString" or len(g.coords) < 2:
                problems.append({
                    "geometry": ln["geom_wgs"].__geo_interface__,
                    "feature_id": ln["props"].get("id"),
                    "feature_type": "ReferenceLink",
                    "severity": "error",
                    "message": "ReferenceLink 几何非法（非 LineString 或点不足）",
                })
                continue
            s, e = key(g.coords[0]), key(g.coords[-1])
            deg_s, deg_e = node_degree.get(s, 0), node_degree.get(e, 0)
            if deg_s == 1 and deg_e == 1:
                isolated.add(idx)
                problems.append({
                    "geometry": ln["geom_wgs"].__geo_interface__,
                    "feature_id": ln["props"].get("id"),
                    "feature_type": "ReferenceLink",
                    "severity": "warning",
                    "message": "孤立段：两端均为悬空节点",
                })
            elif deg_s == 1 or deg_e == 1:
                problems.append({
                    "geometry": ln["geom_wgs"].__geo_interface__,
                    "feature_id": ln["props"].get("id"),
                    "feature_type": "ReferenceLink",
                    "severity": "warning",
                    "message": "悬空端点：ReferenceLink 链条在端点处断裂",
                })
        return problems


qc_service = QCService()
