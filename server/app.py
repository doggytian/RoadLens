"""RoadLens Flask 应用入口。

启动：python -m server.app   （或 ./start.sh）
访问：http://localhost:8124
"""
from __future__ import annotations

import logging
import os

from flask import Flask, send_from_directory
from flask_compress import Compress

from server.config import CONFIG
from server.routes import register_routes
from server.cleanup import start_cleanup_thread

_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


def create_app() -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__, static_folder=_STATIC_DIR, static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

    Compress(app)
    register_routes(app)

    @app.route("/")
    def index():
        return send_from_directory(_STATIC_DIR, "index.html")

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def _err(e):  # noqa: ANN001
        from flask import jsonify
        return jsonify({"error": getattr(e, "description", str(e))}), e.code

    return app


app = create_app()

# 启动后台清理线程
start_cleanup_thread()


def main() -> None:
    app.run(host=CONFIG.host, port=CONFIG.port, debug=CONFIG.debug, threaded=True)


if __name__ == "__main__":
    main()
