# -*- coding: utf-8 -*-
"""
DB 同步服务端(局域网 HTTP API)
零外部依赖:仅用标准库 http.server + sqlite3
- 监听 config.db.server_host:server_port(默认 0.0.0.0:8765)
- 提供 JSON HTTP API 包装本地 SQLite 的 CRUD
- 可选 Bearer Token 鉴权
- 适合 3~5 台设备的局域网小团队使用

启动方式:
    from core.db_server import start_server_in_thread
    start_server_in_thread()
    # 然后同局域网内的其他电脑,client 模式连过来即可
"""

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import urlparse

from config import config
from core.database import DatabaseManager
from core.logger import get_logger
from plugins.peel_data.models import PeelDataRecord, get_history_table_name


logger = get_logger("db.server")

# 白名单表(防止任意 SQL 注入)
# 【v1.7.0】遵循"插件名_数据库名"命名规范
ALLOWED_TABLES = {PeelDataRecord.get_table_name(), get_history_table_name()}

# 严格 WHERE 子句校验:只允许字母数字下划线点号比较运算符 and/or/in
import re
_SAFE_WHERE = re.compile(r"^[A-Za-z0-9_.\s<>=!\(\)\?,']+$")


class _DBHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def log_message(self, fmt, *args):
        """覆盖默认 stderr 日志,改用我们的 logger"""
        logger.info(f"{self.client_address[0]} - {fmt % args}")

    def _check_auth(self) -> bool:
        """Bearer Token 鉴权(空 token=无鉴权)"""
        token = config.db.api_token
        if not token:
            return True
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {token}":
            self._json(401, {"error": "unauthorized"})
            return False
        return True

    def _json(self, code: int, body: Any):
        """输出 JSON 响应"""
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def _read_json(self) -> Dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _check_table(self, path: str) -> str:
        """从 /api/<table>/... 路径里解析出表名,白名单校验"""
        parts = path.strip("/").split("/")
        # 期望: ["api", "<table>", "<action>"]
        if len(parts) < 3 or parts[0] != "api":
            self._json(404, {"error": "not found"})
            return ""
        table = parts[1]
        if table not in ALLOWED_TABLES:
            self._json(403, {"error": f"table '{table}' not in allowlist"})
            return ""
        return table

    def _check_where(self, where: str) -> bool:
        """WHERE 子句白名单(防 SQL 注入)"""
        return bool(where) and bool(_SAFE_WHERE.match(where))

    def do_GET(self):
        if not self._check_auth():
            return
        if self.path == "/api/health":
            self._json(200, {
                "status": "ok",
                "host": config.db.server_host,
                "port": config.db.server_port,
                "mode": "server",
                "allow_write": config.db.server_allow_write,
            })
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._check_auth():
            return
        parsed = urlparse(self.path)
        table = self._check_table(parsed.path)
        if not table:
            return
        action = parsed.path.strip("/").split("/")[2]
        try:
            body = self._read_json()
        except json.JSONDecodeError as e:
            self._json(400, {"error": f"invalid JSON: {e}"})
            return

        # 【v1.7.0】客户端写入限制:server_allow_write=False 时拒绝写操作
        WRITE_ACTIONS = {"insert", "update", "delete"}
        if action in WRITE_ACTIONS and not config.db.server_allow_write:
            self._json(403, {
                "error": "write_denied",
                "message": "服务端已禁用远程写入（server_allow_write=false）。请联系管理员开启写入权限，或在本地模式下操作。",
            })
            return

        db = DatabaseManager()
        try:
            if action == "query":
                where = body.get("where", "1=1")
                params = body.get("params", [])
                if not self._check_where(where):
                    self._json(400, {"error": "WHERE clause not allowed"})
                    return
                rows = db.query_all(f'SELECT * FROM "{table}" WHERE {where}', tuple(params))
                self._json(200, rows)
            elif action == "insert":
                data = body.get("data", {})
                rowid = db.insert(table, data)
                self._json(200, {"rowid": rowid, "ok": True})
            elif action == "update":
                data = body.get("data", {})
                where = body.get("where", "")
                params = body.get("params", [])
                if not self._check_where(where):
                    self._json(400, {"error": "WHERE clause not allowed"})
                    return
                affected = db.update(table, data, where, tuple(params))
                self._json(200, {"affected": affected, "ok": True})
            elif action == "delete":
                where = body.get("where", "")
                params = body.get("params", [])
                if not self._check_where(where):
                    self._json(400, {"error": "WHERE clause not allowed"})
                    return
                affected = db.delete(table, where, tuple(params))
                self._json(200, {"affected": affected, "ok": True})
            else:
                self._json(404, {"error": f"unknown action: {action}"})
        except Exception as e:
            logger.error(f"API {action} 失败: {e}", exc_info=True)
            self._json(500, {"error": str(e)})

    def do_OPTIONS(self):
        """CORS 预检"""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()


_server_thread: threading.Thread = None
_server: ThreadingHTTPServer = None


def start_server_in_thread() -> threading.Thread:
    """
    在后台线程启动 HTTP server
    适合在 GUI 主程序启动时调用,server 与 GUI 共享同一进程
    """
    global _server_thread, _server
    if _server is not None:
        logger.info("DB server 已在运行")
        return _server_thread

    # 【v1.6.0 修复】server 启动时确保所有白名单表的 schema 已建好
    # 否则其他电脑连过来 query 会报 "no such table"
    try:
        from plugins.peel_data.models import ensure_table, ensure_history_table
        ensure_table()
        ensure_history_table()
    except Exception as e:
        logger.warning(f"启动时确保表结构失败(可忽略): {e}")

    host = config.db.server_host
    port = config.db.server_port
    _server = ThreadingHTTPServer((host, port), _DBHandler)
    _server_thread = threading.Thread(
        target=_server.serve_forever, daemon=True, name="db-server"
    )
    _server_thread.start()
    logger.info(f"DB server 已启动: http://{host}:{port}")
    logger.info(f"白名单表: {sorted(ALLOWED_TABLES)}")
    if config.db.api_token:
        logger.info("鉴权已启用(Bearer Token)")
    return _server_thread


def stop_server():
    """停止 server"""
    global _server
    if _server is not None:
        _server.shutdown()
        _server = None
        logger.info("DB server 已停止")
