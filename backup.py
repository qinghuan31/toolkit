#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backup.py - 项目备份脚本（双保险机制之一）

使用方式（可在任意目录执行）：
    python backup.py
    python backup.py --note "闪退修复前快照"
    python backup.py --keep 20  # 自定义保留份数

行为：
1. 自动识别 backup.py 所在目录为项目根目录
2. 复制整个项目到 E:\\工作目录\\backups\\<项目目录名>\\<时间戳>\\
3. 排除 __pycache__/、.venv/、.git/、.workbuddy/、data/、logs/
4. 只保留最近 N 份（默认 10），超出自动删旧
5. 打印备份路径供 Z 验证
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


# ============== 配置 ==============
PROJECT_ROOT = Path(__file__).parent.resolve()
PROJECT_NAME = PROJECT_ROOT.name
BACKUP_BASE = Path("E:/工作目录/backups") / PROJECT_NAME
KEEP_DEFAULT = 10

# 排除目录（基于项目 .gitignore 进一步精简）
EXCLUDE_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".git",
    ".workbuddy",
    "data",
    "logs",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".egg-info",
}

EXCLUDE_FILES = {
    "*.pyc",
    "*.pyo",
    "*.egg-info",
    "*.tmp",
    "*.bak",
    "*.log",
    "Thumbs.db",
    ".DS_Store",
}


# ============== 工具函数 ==============
def should_exclude_dir(name: str) -> bool:
    return name in EXCLUDE_DIRS


def should_exclude_file(name: str) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(name, p) for p in EXCLUDE_FILES)


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def get_dir_size(path: Path) -> int:
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not should_exclude_dir(d)]
        for f in files:
            fp = Path(root) / f
            if not should_exclude_file(f) and fp.exists():
                total += fp.stat().st_size
    return total


def copy_project(src: Path, dst: Path) -> int:
    """复制项目到目标目录，返回总字节数"""
    total = 0
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        dirs[:] = [d for d in dirs if not should_exclude_dir(d)]

        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            if should_exclude_file(f):
                continue
            src_file = Path(root) / f
            dst_file = target_dir / f
            shutil.copy2(src_file, dst_file)
            total += src_file.stat().st_size
    return total


def cleanup_old_backups(base: Path, keep: int) -> list[Path]:
    """删除超出 keep 数量的旧备份，返回被删除的列表"""
    if not base.exists():
        return []
    backups = sorted([p for p in base.iterdir() if p.is_dir()],
                     key=lambda p: p.stat().st_mtime, reverse=True)
    to_delete = backups[keep:]
    deleted = []
    for p in to_delete:
        try:
            shutil.rmtree(p)
            deleted.append(p)
        except Exception as e:
            print(f"  [WARN] 删除失败: {p} -> {e}")
    return deleted


# ============== 主流程 ==============
def main():
    parser = argparse.ArgumentParser(description="项目备份脚本")
    parser.add_argument("--note", default="", help="本次备份备注（写入日志）")
    parser.add_argument("--keep", type=int, default=KEEP_DEFAULT, help=f"保留份数（默认 {KEEP_DEFAULT}）")
    parser.add_argument("--dry-run", action="store_true", help="只展示将复制的内容，不实际执行")
    args = parser.parse_args()

    if not PROJECT_ROOT.exists():
        print(f"[ERROR] 项目根目录不存在: {PROJECT_ROOT}")
        sys.exit(1)

    # 时间戳格式: 2026-06-13_22-05-41
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    note_suffix = f"_{args.note}" if args.note else ""
    backup_name = f"{ts}{note_suffix}"
    backup_path = BACKUP_BASE / backup_name

    print("=" * 60)
    print(f"项目备份 | {PROJECT_NAME}")
    print("=" * 60)
    print(f"源目录: {PROJECT_ROOT}")
    print(f"目标:   {backup_path}")
    print(f"保留:   最近 {args.keep} 份")
    if args.note:
        print(f"备注:   {args.note}")
    print()

    if args.dry_run:
        print("[DRY-RUN] 跳过实际复制，仅统计文件数")
        file_count = sum(1 for _ in PROJECT_ROOT.rglob("*")
                         if _.is_file()
                         and not should_exclude_file(_.name)
                         and not any(should_exclude_dir(p) for p in _.relative_to(PROJECT_ROOT).parts))
        print(f"将复制: {file_count} 个文件")
        return

    # 复制
    print("[1/2] 正在复制...")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    bytes_copied = copy_project(PROJECT_ROOT, backup_path)
    print(f"      复制完成: {human_size(bytes_copied)}")

    # 清理旧备份
    print(f"\n[2/2] 清理超过 {args.keep} 份的旧备份...")
    deleted = cleanup_old_backups(BACKUP_BASE, args.keep)
    if deleted:
        for p in deleted:
            print(f"      已删除: {p.name}")
    else:
        print("      无需清理")

    # 写日志
    log_path = backup_path / "_backup.log"
    log_path.write_text(
        f"backup_time: {ts}\n"
        f"project:     {PROJECT_NAME}\n"
        f"size:        {human_size(bytes_copied)}\n"
        f"note:        {args.note or '(无)'}\n",
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("✅ 备份完成")
    print(f"   路径: {backup_path}")
    print(f"   大小: {human_size(bytes_copied)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
