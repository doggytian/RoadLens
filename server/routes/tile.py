"""/api/tile/... 几何与质检查询。"""
from __future__ import annotations

from flask import Blueprint, request

from server.data_loader import loader
from server.qc_service import qc_service, CHECK_NAMES
from server.routes.common import current_user_id, fail, ok

bp = Blueprint("tile", __name__, url_prefix="/api/tile")


@bp.get("/<tile_id>")
def get_tile(tile_id: str):
    """返回某个 tile 的全部要素（GeoJSON FeatureCollection）。"""
    user = current_user_id()
    data = loader.load_tile(user, tile_id)
    return ok(data)


@bp.get("/<tile_id>/feature/<feature_id>")
def get_feature(tile_id: str, feature_id: str):
    """返回某个要素（用于属性面板，含完整 properties 与 geometry）。"""
    user = current_user_id()
    ft = loader.get_feature(user, tile_id, feature_id)
    if ft is None:
        return fail("要素不存在", 404)
    return ok(ft)


@bp.get("/<tile_id>/qc")
def get_qc_all(tile_id: str):
    """运行全部 8 类质检并返回按 check_type 分组的 FeatureCollection。"""
    user = current_user_id()
    data = loader.load_tile(user, tile_id)
    results = qc_service.run_all(data)
    return ok({"tile_id": tile_id, "checks": list(results.keys()), "results": results})


@bp.get("/<tile_id>/qc/<check_name>")
def get_qc_one(tile_id: str, check_name: str):
    """运行单个质检。"""
    user = current_user_id()
    if check_name not in CHECK_NAMES:
        return fail(f"未知质检项：{check_name}", 404)
    data = loader.load_tile(user, tile_id)
    result = qc_service.run_one(check_name, data)
    return ok({"tile_id": tile_id, "check_type": check_name, **result})
