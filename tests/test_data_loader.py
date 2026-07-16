"""data_loader 测试：用户校验、要素归一化/过滤、分类、tile 列举与查询。"""
from __future__ import annotations

import json
import os

import pytest

from server.config import CONFIG
from server.data_loader import DataLoader, _FEATURE_TYPES


def _feature(ftype, fid, geom_type="LineString"):
    return {
        "type": "Feature",
        "id": fid,
        "geometry": {"type": geom_type, "coordinates": [[0, 0], [1, 1]]},
        "properties": {"feature_type": ftype},
    }


@pytest.fixture
def dl():
    return DataLoader(max_cache=4)


def test_invalid_user_id_rejected(dl):
    for bad in ["", "has space", "a" * 33, "bad/slash", "汉字"]:
        with pytest.raises(ValueError):
            dl.user_workspace(bad)


def test_valid_user_id_creates_workspace(dl):
    path = dl.user_workspace("ci_user_1")
    assert os.path.isdir(path)
    assert path.startswith(CONFIG.resolve_workspace_root())


def test_normalize_filters_unknown_types(dl):
    features = [
        _feature("RoadCorridor", "c1", "Polygon"),
        _feature("Lane", "l1"),
        _feature("ReferenceLink", "r1"),
        _feature("UnknownType", "x1"),  # 应被过滤
        {"type": "Feature", "geometry": None, "properties": {}},  # 无 feature_type
    ]
    out = dl._normalize_features(features)
    kept_types = {f["properties"]["feature_type"] for f in out}
    assert kept_types == set(_FEATURE_TYPES)
    assert len(out) == 3
    # 归一化补齐默认属性
    for f in out:
        assert "id" in f["properties"]
        assert "tile_id" in f["properties"]


def test_categorize_groups_by_type(dl):
    data = {
        "features": dl._normalize_features(
            [
                _feature("RoadCorridor", "c1", "Polygon"),
                _feature("RoadCorridor", "c2", "Polygon"),
                _feature("Lane", "l1"),
                _feature("ReferenceLink", "r1"),
            ]
        )
    }
    groups = dl.categorize(data)
    assert len(groups["RoadCorridor"]) == 2
    assert len(groups["Lane"]) == 1
    assert len(groups["ReferenceLink"]) == 1


def test_load_missing_tile_returns_empty(dl):
    data = dl.load_tile("ci_user_1", "no_such_tile_xyz")
    assert data["type"] == "FeatureCollection"
    assert data["features"] == []
    assert data["tile_id"] == "no_such_tile_xyz"


def test_load_and_cache_roundtrip(tmp_path, dl):
    user = "ci_user_2"
    tiles_dir = os.path.join(dl.user_workspace(user), "tiles")
    os.makedirs(tiles_dir, exist_ok=True)
    tile_id = "unit_tile_a"
    fc = {
        "type": "FeatureCollection",
        "features": [_feature("Lane", "l1"), _feature("UnknownType", "x1")],
    }
    with open(os.path.join(tiles_dir, f"{tile_id}.geojson"), "w", encoding="utf-8") as f:
        json.dump(fc, f)

    data = dl.load_tile(user, tile_id)
    assert len(data["features"]) == 1  # UnknownType 被过滤
    # 命中缓存返回同一对象
    assert dl.load_tile(user, tile_id) is data
    assert tile_id in dl.list_available_tiles(user)

    # get_feature 能按 id 命中
    ft = dl.get_feature(user, tile_id, "l1")
    assert ft is not None and ft["properties"]["feature_type"] == "Lane"
    assert dl.get_feature(user, tile_id, "nope") is None


def test_cache_eviction(dl):
    user = "ci_user_3"
    tiles_dir = os.path.join(dl.user_workspace(user), "tiles")
    os.makedirs(tiles_dir, exist_ok=True)
    for i in range(6):  # 超过 max_cache=4
        tid = f"evict_tile_{i}"
        with open(os.path.join(tiles_dir, f"{tid}.geojson"), "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": []}, f)
        dl.load_tile(user, tid)
    assert len(dl._cache) <= dl.max_cache
