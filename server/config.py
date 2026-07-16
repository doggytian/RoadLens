"""配置解析：从 config.yaml 读取并暴露为全局 CONFIG。

优先顺序：环境变量 ROADLENS_CONFIG（指定路径）> 仓库根目录 config.yaml。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_config_path() -> str:
    env = os.environ.get("ROADLENS_CONFIG")
    if env:
        return env
    return os.path.join(_ROOT, "config.yaml")


@dataclass
class Config:
    raw: Dict[str, Any] = field(default_factory=dict)

    # server
    host: str = "0.0.0.0"
    port: int = 8124
    debug: bool = False

    # workspace
    workspace_root: str = "workspace"
    cleanup_max_age_hours: float = 12.0
    cleanup_interval_seconds: float = 1800.0

    # tiles
    grid_size_deg: float = 0.01
    sample_tile_id: str = "sample_city"

    # data
    sample_dir: str = "sample_data"
    crs: str = "EPSG:4326"

    # qc
    std_lane_width: float = 3.5
    corridor_width_tolerance: float = 0.35
    centerline_coverage_threshold: float = 0.9
    corridor_buffer_distance: float = 0.5
    overlap_min_area: float = 1.0
    min_valid_area: float = 0.01

    @classmethod
    def load(cls, path: str | None = None) -> "Config":
        path = path or _default_config_path()
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        c = cls(raw=raw)
        c.host = raw.get("server", {}).get("host", c.host)
        c.port = int(raw.get("server", {}).get("port", c.port))
        c.debug = bool(raw.get("server", {}).get("debug", c.debug))

        ws = raw.get("workspace", {})
        c.workspace_root = ws.get("root", c.workspace_root)
        c.cleanup_max_age_hours = float(ws.get("cleanup_max_age_hours", c.cleanup_max_age_hours))
        c.cleanup_interval_seconds = float(ws.get("cleanup_interval_seconds", c.cleanup_interval_seconds))

        tl = raw.get("tiles", {})
        c.grid_size_deg = float(tl.get("grid_size_deg", c.grid_size_deg))
        c.sample_tile_id = tl.get("sample_tile_id", c.sample_tile_id)

        dt = raw.get("data", {})
        c.sample_dir = dt.get("sample_dir", c.sample_dir)
        c.crs = dt.get("crs", c.crs)

        qc = raw.get("qc", {})
        c.std_lane_width = float(qc.get("std_lane_width", c.std_lane_width))
        c.corridor_width_tolerance = float(qc.get("corridor_width_tolerance", c.corridor_width_tolerance))
        c.centerline_coverage_threshold = float(qc.get("centerline_coverage_threshold", c.centerline_coverage_threshold))
        c.corridor_buffer_distance = float(qc.get("corridor_buffer_distance", c.corridor_buffer_distance))
        c.overlap_min_area = float(qc.get("overlap_min_area", c.overlap_min_area))
        c.min_valid_area = float(qc.get("min_valid_area", c.min_valid_area))
        return c

    def resolve_workspace_root(self) -> str:
        return self.workspace_root if os.path.isabs(self.workspace_root) else os.path.join(_ROOT, self.workspace_root)

    def resolve_sample_dir(self) -> str:
        return self.sample_dir if os.path.isabs(self.sample_dir) else os.path.join(_ROOT, self.sample_dir)


CONFIG = Config.load()
