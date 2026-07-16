"""后台清理线程：删除超龄的用户数据目录。"""
from __future__ import annotations

import logging
import os
import shutil
import threading
import time

from server.config import CONFIG

logger = logging.getLogger("roadlens.cleanup")


def _user_dirs() -> list:
    root = CONFIG.resolve_workspace_root()
    if not os.path.isdir(root):
        return []
    return [os.path.join(root, d) for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))]


def _cleanup_once() -> int:
    max_age = CONFIG.cleanup_max_age_hours * 3600
    now = time.time()
    removed = 0
    for d in _user_dirs():
        try:
            age = now - os.path.getmtime(d)
            if age > max_age:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
                logger.info("清理超龄用户目录: %s (%.1fh)", d, age / 3600)
        except OSError as e:
            logger.warning("清理失败 %s: %s", d, e)
    return removed


def start_cleanup_thread() -> threading.Thread:
    """启动守护线程，周期性清理超龄用户目录。"""
    def loop():
        while True:
            try:
                _cleanup_once()
            except Exception as e:  # noqa: BLE001
                logger.warning("清理线程异常: %s", e)
            time.sleep(max(30, CONFIG.cleanup_interval_seconds))

    t = threading.Thread(target=loop, name="roadlens-cleanup", daemon=True)
    t.start()
    logger.info("清理线程已启动，间隔 %.0f 秒", CONFIG.cleanup_interval_seconds)
    return t
