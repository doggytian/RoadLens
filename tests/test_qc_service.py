"""qc_service 质检测试：验证 8 类质检可跑通、返回结构正确，并能检出问题。"""
from __future__ import annotations

import pytest

from server.qc_service import CHECK_NAMES, QCService


def _corridor(cid, coords, lane_count=1):
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coords]},
        "properties": {
            "feature_type": "RoadCorridor",
            "id": cid,
            "lane_count": lane_count,
        },
    }


def _link(lid, coords, corridor_id=None):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "feature_type": "ReferenceLink",
            "id": lid,
            "corridor_id": corridor_id,
        },
    }


def _sample_tile():
    """一张小合成 tile：含一个明显过窄的走廊 + 一条孤立参考线。"""
    # 极窄的走廊（约 0.00001 度 ~ 1m 宽），车道数=2 -> 期望约 7m，触发宽度异常
    narrow = _corridor(
        "c_narrow",
        [
            [116.400, 39.910],
            [116.402, 39.910],
            [116.402, 39.910011],
            [116.400, 39.910011],
            [116.400, 39.910],
        ],
        lane_count=2,
    )
    # 一条未绑定任何走廊、两端悬空的孤立参考线
    lone = _link("l_lone", [[116.410, 39.915], [116.412, 39.916]])
    return {"type": "FeatureCollection", "features": [narrow, lone]}


@pytest.fixture
def qc():
    return QCService()


def test_run_all_returns_all_checks(qc):
    result = qc.run_all(_sample_tile())
    assert set(result.keys()) == set(CHECK_NAMES)
    for name, fc in result.items():
        assert fc["type"] == "FeatureCollection"
        assert fc["check_type"] == name
        assert fc["count"] == len(fc["features"])


def test_run_one_unknown_raises(qc):
    with pytest.raises(ValueError):
        qc.run_one("not_a_real_check", _sample_tile())


def test_corridor_width_detects_narrow(qc):
    fc = qc.run_one("corridor_width", _sample_tile())
    assert fc["count"] >= 1
    assert all(f["properties"]["check_type"] == "corridor_width" for f in fc["features"])


def test_reference_topology_detects_isolated(qc):
    fc = qc.run_one("reference_topology", _sample_tile())
    # 孤立段应被检出
    assert fc["count"] >= 1
    messages = " ".join(f["properties"]["message"] for f in fc["features"])
    assert "孤立" in messages or "悬空" in messages


def test_reference_binding_detects_unbound(qc):
    fc = qc.run_one("reference_binding", _sample_tile())
    # 未绑定参考线的走廊应被检出
    assert fc["count"] >= 1


def test_empty_tile_runs_clean(qc):
    result = qc.run_all({"type": "FeatureCollection", "features": []})
    for fc in result.values():
        assert fc["count"] == 0
