"""Tile 数据加载 + 简单 LRU 缓存。

每个 tile 是一个 GeoJSON FeatureCollection，文件位于：
  - 内置示例：<sample_dir>/<tile_id>.geojson
  - 用户数据：<workspace_root>/<user_id>/tiles/<tile_id>.geojson

支持的要素类型（feature_type 属性）：
  - RoadCorridor : 道路走廊多边形（Polygon/MultiPolygon）
  - Lane          : 单条车道线（LineString）
  - ReferenceLink : 走廊参考中心线（LineString）
"""
from __future__ import annotations

import json
import os
import re
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from server.config import CONFIG

_FEATURE_TYPES = ("RoadCorridor", "Lane", "ReferenceLink")
_USER_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")


class DataLoader:
    def __init__(self, max_cache: int = 16):
        self._cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self.max_cache = max_cache

    # ---------- 路径与用户校验 ----------
    def user_workspace(self, user_id: str) -> str:
        if not _USER_RE.match(user_id or ""):
            raise ValueError("invalid user_id (1~32 chars: A-Za-z0-9_)")
        root = CONFIG.resolve_workspace_root()
        path = os.path.join(root, user_id)
        os.makedirs(path, exist_ok=True)
        return path

    def tile_path(self, user_id: str, tile_id: str) -> str:
        return os.path.join(self.user_workspace(user_id), "tiles", f"{tile_id}.geojson")

    def sample_tile_path(self, tile_id: str) -> str:
        return os.path.join(CONFIG.resolve_sample_dir(), f"{tile_id}.geojson")

    # ---------- 加载 ----------
    def load_tile(self, user_id: str, tile_id: str) -> Dict[str, Any]:
        """加载并缓存某个 tile；优先用户目录，回退到内置示例。"""
        cache_key = f"{user_id}::{tile_id}"
        with self._lock:
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]

        path = self.tile_path(user_id, tile_id)
        if not os.path.exists(path):
            path = self.sample_tile_path(tile_id)

        if not os.path.exists(path):
            data: Dict[str, Any] = {
                "type": "FeatureCollection",
                "features": [],
                "tile_id": tile_id,
                "source": "empty",
            }
        else:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("tile_id", tile_id)
            data.setdefault("source", os.path.relpath(path, CONFIG.resolve_workspace_root()))

        data["features"] = self._normalize_features(data.get("features", []))
        with self._lock:
            self._cache[cache_key] = data
            if len(self._cache) > self.max_cache:
                self._cache.popitem(last=False)
        return data

    def _normalize_features(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤非法要素并补默认属性。"""
        out = []
        for ft in features:
            props = ft.get("properties") or {}
            ftype = props.get("feature_type")
            if ftype not in _FEATURE_TYPES:
                continue
            ft = dict(ft)
            ft["properties"] = dict(props)
            ft["properties"].setdefault("id", ft.get("id"))
            ft["properties"].setdefault("tile_id", "")
            out.append(ft)
        return out

    # ---------- 分类与查询 ----------
    def categorize(self, data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """按 feature_type 把要素分组。"""
        groups = {t: [] for t in _FEATURE_TYPES}
        for ft in data.get("features", []):
            ftype = ft["properties"].get("feature_type")
            groups.setdefault(ftype, []).append(ft)
        return groups

    def list_available_tiles(self, user_id: str) -> List[str]:
        """列出当前用户可用的 tile（用户目录 + 内置示例并集）。"""
        ids = set()
        user_tiles = os.path.join(self.user_workspace(user_id), "tiles")
        if os.path.isdir(user_tiles):
            for fn in os.listdir(user_tiles):
                if fn.endswith(".geojson"):
                    ids.add(fn[: -len(".geojson")])
        sample_dir = CONFIG.resolve_sample_dir()
        if os.path.isdir(sample_dir):
            for fn in os.listdir(sample_dir):
                if fn.endswith(".geojson"):
                    ids.add(fn[: -len(".geojson")])
        return sorted(ids)

    def get_feature(self, user_id: str, tile_id: str, feature_id: str) -> Optional[Dict[str, Any]]:
        data = self.load_tile(user_id, tile_id)
        for ft in data.get("features", []):
            if str(ft["properties"].get("id")) == str(feature_id):
                return ft
        return None


loader = DataLoader()
