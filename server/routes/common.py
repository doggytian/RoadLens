"""路由公共工具：用户身份解析与统一 JSON 响应。"""
from __future__ import annotations

import re

from flask import current_app, jsonify, request

_USER_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")


def current_user_id() -> str:
    """从 X-User-Id 请求头解析并校验用户标识。"""
    uid = (request.headers.get("X-User-Id") or "").strip()
    if not _USER_RE.match(uid):
        from werkzeug.exceptions import BadRequest
        raise BadRequest("缺少或非法的 X-User-Id（1~32 位字母数字下划线）")
    return uid


def ok(payload: dict, status: int = 200):
    return jsonify(payload), status


def fail(message: str, status: int = 400):
    return jsonify({"error": message}), status
