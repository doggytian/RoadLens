"""API 路由包。"""
from __future__ import annotations

from flask import Blueprint

from server.routes import data, tile

__all__ = ["data", "tile", "register_routes"]

BLUEPRINTS: list[Blueprint] = [tile.bp, data.bp]


def register_routes(app) -> None:
    for bp in BLUEPRINTS:
        app.register_blueprint(bp)
