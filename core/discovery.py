# -*- coding: utf-8 -*-
"""
局域网设备自动发现
- 启动时按本机所在子网扫描其他 Toolkit 实例
- 每个 IP 探测 /api/health，超时即跳过
- 零外部依赖（仅 socket + urllib）
"""

import json
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

from config import config
from core.logger import get_logger


logger = get_logger("discovery")


def get_local_subnet(cidr_prefix: int = 24) -> str:
    """
    获取本机所在子网的网络号（例: 192.168.1.0/24）
    通过创建一个 UDP socket 假装连外网来获取出口 IP（不发真实数据包）
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # 不需要目标可达，只是为了让系统选出口网卡
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        return ""

    # 计算网络号
    parts = local_ip.split(".")
    if len(parts) != 4:
        return ""
    if cidr_prefix == 24:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
    elif cidr_prefix == 16:
        return f"{parts[0]}.{parts[1]}.0.0"
    elif cidr_prefix == 8:
        return f"{parts[0]}.0.0.0"
    return f"{parts[0]}.{parts[1]}.{parts[2]}.0"


def _probe(ip: str, port: int, timeout: float) -> Optional[Dict]:
    """探测单个 IP 的 /api/health"""
    url = f"http://{ip}:{port}/api/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "ok":
                return {
                    "ip": ip,
                    "url": f"http://{ip}:{port}",
                    "port": port,
                    "mode": data.get("mode", "server"),
                }
    except Exception:
        return None
    return None


def discover_devices(
    port: int = None,
    cidr_prefix: int = None,
    timeout: float = None,
    max_workers: int = 64,
) -> List[Dict]:
    """
    扫描子网内运行 Toolkit server 的所有设备

    Returns:
        [{"ip": "192.168.1.100", "url": "http://...", "port": 8765, "mode": "server"}]
    """
    port = port or config.db.server_port
    cidr_prefix = cidr_prefix or config.db.discovery_cidr_prefix
    timeout = timeout or config.db.discovery_timeout

    subnet = get_local_subnet(cidr_prefix)
    if not subnet:
        logger.warning("无法确定本机子网，跳过设备发现")
        return []

    # 生成子网内所有 IP
    parts = subnet.split(".")
    base = ".".join(parts[:3])
    targets = [f"{base}.{i}" for i in range(1, 255)]

    # 并发探测
    found: List[Dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_probe, ip, port, timeout): ip for ip in targets}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                found.append(result)
                logger.info(f"发现设备: {result['ip']}:{result['port']}")

    # 按 IP 排序
    found.sort(key=lambda d: tuple(int(x) for x in d["ip"].split(".")))
    return found
