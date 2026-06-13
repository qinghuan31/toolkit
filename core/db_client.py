# -*- coding: utf-8 -*-
"""
DB 同步客户端
访问远端 server(部署在另一台机器的 toolkit 实例)提供的 HTTP API

依赖:仅标准库(urllib + json),与 updater 风格一致
"""

import json
import socket
import ssl
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from config import config
from core.logger import get_logger


logger = get_logger("db.client")


class DatabaseClient:
    """DB 客户端 —— 访问远端 server 的 HTTP API"""

    def __init__(self, base_url: str = None, token: str = None, timeout: int = 10):
        self.base_url = (base_url or config.db.server_url).rstrip("/")
        self.token = token or config.db.api_token
        self.timeout = timeout
        if not self.base_url:
            raise ValueError(
                "client 模式需要 server_url (例: http://192.168.1.100:8765)"
            )

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        """底层 HTTP 请求"""
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Toolkit-DB-Client/1.6.0",
            },
        )
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            # 【v1.7.0】403 write_denied 友好提示
            if e.code == 403:
                try:
                    err_data = json.loads(err_body)
                    if err_data.get("error") == "write_denied":
                        raise PermissionError(
                            err_data.get("message", "服务端已禁用远程写入。请联系管理员开启写入权限。")
                        ) from e
                except (json.JSONDecodeError, KeyError):
                    pass
            raise RuntimeError(
                f"server 返回 {e.code}: {err_body[:200]}"
            ) from e
        except (urllib.error.URLError, socket.timeout) as e:
            raise RuntimeError(f"连接 server 失败: {e}") from e

    # === CRUD 接口(与本地 DatabaseManager 风格一致) ===

    def query_all(self, table: str, where: str = "1=1", params: list = None) -> List[Dict]:
        """查询多条"""
        body = {"where": where, "params": params or []}
        return self._request("POST", f"/api/{table}/query", body)

    def query_one(self, table: str, where: str = "1=1", params: list = None) -> Optional[Dict]:
        """查询单条"""
        rows = self.query_all(table, where, params)
        return rows[0] if rows else None

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """插入,返回新 rowid"""
        result = self._request("POST", f"/api/{table}/insert", {"data": data})
        return result.get("rowid", 0) if result else 0

    def update(self, table: str, data: Dict[str, Any], where: str, params: list = None) -> int:
        """更新"""
        body = {"data": data, "where": where, "params": params or []}
        result = self._request("POST", f"/api/{table}/update", body)
        return result.get("affected", 0) if result else 0

    def delete(self, table: str, where: str, params: list = None) -> int:
        """删除"""
        body = {"where": where, "params": params or []}
        result = self._request("POST", f"/api/{table}/delete", body)
        return result.get("affected", 0) if result else 0

    def health(self) -> Dict:
        """健康检查"""
        return self._request("GET", "/api/health")
