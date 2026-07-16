"""/api/data/... 状态、示例加载、可用 tile 列表。"""
from __future__ import annotations

import os

from flask import Blueprint

from server.config import CONFIG
from server.data_loader import loader
from server.routes.common import current_user_id, ok

bp = Blueprint("data", __name__, url_prefix="/api/data")


@bp.get("/state")
def state():
    """返回当前用户的可用 tile 列表与示例 tile 是否就绪。"""
    user = current_user_id()
    tiles = loader.list_available_tiles(user)
    sample_path = loader.sample_tile_path(CONFIG.sample_tile_id)
    sample_ready = os.path.exists(sample_path)
    return ok({
        "user_id": user,
        "tiles": tiles,
        "sample_tile_id": CONFIG.sample_tile_id,
        "sample_available": sample_ready,
        "qc_checks": [
            "corridor_width", "buffer_break", "centerline_coverage",
            "overlap", "diamond_topology", "geometry_validity",
            "reference_binding", "reference_topology",
        ],
    })


@bp.post("/load_sample")
def load_sample():
    """确保内置示例 tile 可用（随仓库提供，无需网络）。"""
    user = current_user_id()
    # 把内置示例复制到用户工作目录，便于后续在用户隔离空间查看
    src = loader.sample_tile_path(CONFIG.sample_tile_id)
    import os
    import shutil
    if not os.path.exists(src):
        return ok({"loaded": False, "reason": "未找到内置示例数据，请运行 scripts/fetch_sample.py"})
    dst = loader.tile_path(user, CONFIG.sample_tile_id)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    loader._cache.pop(f"{user}::{CONFIG.sample_tile_id}", None)
    return ok({"loaded": True, "tile_id": CONFIG.sample_tile_id})
