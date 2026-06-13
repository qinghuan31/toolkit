# -*- coding: utf-8 -*-
"""
自动更新检查器
- 从 GitHub Releases 拉取最新版本信息
- 比较本地版本,提示用户升级
- 走 gh-proxy 代理加速下载
"""

import json
import re
import socket
import ssl
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional, Tuple

from config import config, get_version


@dataclass
class UpdateInfo:
    """更新信息"""
    has_update: bool
    current_version: str
    latest_version: str
    release_name: str
    release_url: str
    download_url: str            # 原始 GitHub 下载链接
    accelerated_url: str         # gh-proxy 加速后链接
    release_notes: str
    error: Optional[str] = None


def _parse_version(v: str) -> Tuple[int, ...]:
    """'v1.5.1' -> (1, 5, 1)"""
    nums = re.findall(r"\d+", v)
    return tuple(int(n) for n in nums)


def _is_newer(latest: str, current: str) -> bool:
    """latest > current ?"""
    l = _parse_version(latest)
    c = _parse_version(current)
    # 短版补 0
    pad = max(len(l), len(c))
    l = l + (0,) * (pad - len(l))
    c = c + (0,) * (pad - len(c))
    return l > c


def _find_exe_asset(assets: list) -> Optional[str]:
    """从 release assets 找 .exe 资产的下载 URL"""
    for a in assets:
        name = a.get("name", "").lower()
        if name.endswith(".exe") and "toolkit" in name:
            return a.get("browser_download_url")
    return None


def _build_proxy_url(raw_url: str) -> str:
    """拼接 gh-proxy 代理前缀"""
    if not raw_url:
        return ""
    proxy = config.github_proxy or ""
    if not proxy:
        return raw_url
    if not proxy.endswith("/"):
        proxy += "/"
    return proxy + raw_url


def _http_get_json(url: str, timeout: int = 8) -> dict:
    """极简 HTTP GET JSON —— 不依赖 requests/httpx,纯标准库"""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Toolkit-AutoUpdater/1.0",
        },
    )
    ctx = ssl.create_default_context()
    # 兼容公司/自签证书环境
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_for_update() -> UpdateInfo:
    """
    检查 GitHub Releases 是否有新版本

    Returns:
        UpdateInfo —— 即使出错也返回,error 字段描述
    """
    current = get_version()
    api_url = (
        f"https://api.github.com/repos/"
        f"{config.github_owner}/{config.github_repo}/releases/latest"
    )
    try:
        data = _http_get_json(api_url)
    except (urllib.error.URLError, socket.timeout, ssl.SSLError) as e:
        return UpdateInfo(
            has_update=False, current_version=current,
            latest_version=current, release_name="",
            release_url="", download_url="", accelerated_url="",
            release_notes="", error=f"网络错误: {e}",
        )
    except Exception as e:
        return UpdateInfo(
            has_update=False, current_version=current,
            latest_version=current, release_name="",
            release_url="", download_url="", accelerated_url="",
            release_notes="", error=f"解析失败: {e}",
        )

    latest_tag = data.get("tag_name", current)
    latest_ver = latest_tag.lstrip("v").lstrip("ci-build-")
    current_ver = current.lstrip("v")

    has_update = _is_newer(latest_ver, current_ver)
    raw_dl = _find_exe_asset(data.get("assets", [])) or ""
    return UpdateInfo(
        has_update=has_update,
        current_version=current_ver,
        latest_version=latest_ver,
        release_name=data.get("name", latest_tag),
        release_url=data.get("html_url", ""),
        download_url=raw_dl,
        accelerated_url=_build_proxy_url(raw_dl),
        release_notes=data.get("body", ""),
    )
