# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

# ==================== 配置区 ====================

# 要扫描的目录。留空字符串 "" 表示使用当前脚本所在目录
# Windows 示例：  r"D:\Projects\myproject"
# macOS/Linux 示例："/Users/you/projects/myproject"
TARGET_DIR = r"D:\study\programming\python\project"

# 是否弹出文件夹选择对话框（True 则忽略上面的 TARGET_DIR）
USE_FOLDER_DIALOG = False

# 是否显示每个文件的大小
SHOW_SIZE = True

# 最大递归深度，None 表示不限制
MAX_DEPTH = None

# 是否把结果同时保存到 txt 文件（None 表示不保存）
OUTPUT_FILE = "tree_output.txt"   # 例如改成 None 就不保存

# 需要忽略的目录/文件（支持 * 后缀匹配）
IGNORE = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".idea", ".vscode", ".DS_Store", ".mypy_cache", ".pytest_cache",
    "dist", "build", "*.pyc", "*.egg-info", "*.log",
}

# =========================================================


def format_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def is_ignored(name: str) -> bool:
    for pat in IGNORE:
        if pat == name:
            return True
        if pat.startswith("*") and name.endswith(pat[1:]):
            return True
    return False


def scan_tree(root: Path):
    """返回 (树状文本, 统计字典)"""
    stats = {"dirs": 0, "files": 0, "size": 0}
    lines = [root.name + os.sep]
    visited = set()

    def walk(path: Path, prefix: str, depth: int):
        if MAX_DEPTH is not None and depth >= MAX_DEPTH:
            return
        try:
            children = [p for p in path.iterdir() if not is_ignored(p.name)]
        except PermissionError:
            lines.append(prefix + "└── [权限不足]")
            return

        # 目录在前、文件在后，同类按名称排序（忽略大小写）
        children.sort(key=lambda p: (p.is_file(), p.name.lower()))

        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            connector = "└── " if is_last else "├── "
            new_prefix = prefix + ("    " if is_last else "│   ")

            try:
                is_dir = child.is_dir()
            except OSError:
                is_dir = False

            if is_dir:
                stats["dirs"] += 1
                # 符号链接防死循环
                if child.is_symlink():
                    real = child.resolve()
                    if real in visited:
                        lines.append(prefix + connector + child.name + os.sep + " [循环链接]")
                        continue
                    visited.add(real)
                lines.append(prefix + connector + child.name + os.sep)
                walk(child, new_prefix, depth + 1)
            else:
                stats["files"] += 1
                extra = ""
                if SHOW_SIZE:
                    try:
                        sz = child.stat().st_size
                        stats["size"] += sz
                        extra = f"  ({format_size(sz)})"
                    except OSError:
                        pass
                lines.append(prefix + connector + child.name + extra)

    if root.is_dir():
        walk(root, "", 0)
    return "\n".join(lines), stats


def pick_directory() -> str:
    """弹出选择文件夹对话框（tkinter 是 Python 自带库，无需安装）"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = filedialog.askdirectory(title="选择要扫描的文件夹")
        root.destroy()
        return chosen
    except Exception as e:
        print(f"[提示] 无法弹出选择框（{e}），改用 TARGET_DIR 配置。")
        return ""


def main():
    # 1. 决定扫描哪个目录
    if USE_FOLDER_DIALOG:
        path_str = pick_directory()
        if not path_str:
            print("未选择文件夹，程序退出。")
            return
    elif TARGET_DIR.strip():
        path_str = TARGET_DIR
    else:
        path_str = str(Path(__file__).resolve().parent)

    root = Path(path_str).expanduser().resolve()

    # 2. 检查路径
    if not root.exists():
        print(f"[错误] 路径不存在：{root}")
        print("请检查配置区 TARGET_DIR 是否正确（Windows 路径建议加 r 前缀）。")
        return
    if not root.is_dir():
        print(f"[错误] 这不是一个文件夹：{root}")
        return

    # 3. 扫描
    print(f"正在扫描：{root}\n")
    tree, stats = scan_tree(root)

    summary = (
        f"\n\n统计：{stats['dirs']} 个目录, "
        f"{stats['files']} 个文件"
    )
    if SHOW_SIZE:
        summary += f", 合计 {format_size(stats['size'])}"

    result = tree + summary
    print(result)

    # 4. 保存到文件
    if OUTPUT_FILE:
        out = Path(OUTPUT_FILE)
        if not out.is_absolute():
            out = Path(__file__).resolve().parent / out
        out.write_text(result + "\n", encoding="utf-8")
        print(f"\n结果已保存到：{out}")


if __name__ == "__main__":
    main()