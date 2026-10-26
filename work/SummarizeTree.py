from pathlib import Path
from collections import Counter
import re

TREE = Path("tree_output.txt")
OUT = Path("tree_summary.txt")

# 需要折叠成 "N*files" 的目录名
COLLAPSE_DIRS = {"stock-fin-data-xbx"}

size_re = re.compile(r"\(([\d.]+)\s*(B|KB|MB|GB)\)\s*$", re.I)


def read_tree_text(path: Path) -> str:
    """自动检测编码读取 tree 文件，避免 GBK/UTF-8 不匹配导致乱码"""
    raw = path.read_bytes()
    candidates = []
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        score = (
            text.count("├")
            + text.count("└")
            + text.count("│")
            + text.count("+---")
            + text.count("\\---")
        )
        candidates.append((score, enc, text))

    if not candidates:
        print("[警告] 所有编码都失败，使用 utf-8 replace")
        return raw.decode("utf-8", errors="replace")

    candidates.sort(key=lambda x: x[0], reverse=True)
    score, enc, text = candidates[0]
    print(f"[读取] 编码={enc}  树形字符匹配={score}")

    if score == 0:
        print(
            "[警告] 未检测到任何树形字符，输出仍可能乱码。\n"
            "       建议重新生成:  tree /F /A xbx_stock_data > tree_output.txt"
        )
    return text


class Node:
    def __init__(self, name, prefix):
        self.name = name
        self.prefix = prefix
        self.children = []
        self.ext_counts = Counter()
        self.file_prefix = None
        self.direct_files = 0
        self.total_files = 0


def parse_line(line: str):
    s = line.rstrip("\r\n")
    if not s.strip():
        return None

    # 目录行：以反斜杠结尾
    if s.rstrip().endswith("\\"):
        pos = s.rfind("\\")
        before = s[:pos].rstrip()
        m = re.search(r"(\S+)$", before)
        if m:
            return s[:m.start(1)], m.group(1), True
        return None

    # 文件行：必须带 (大小)
    m_size = size_re.search(s)
    if not m_size:
        return None
    left = s[:m_size.start()].rstrip()
    m = re.search(r"(\S+)$", left)
    if not m:
        return None
    return s[:m.start(1)], m.group(1), False


# ---------- 解析 ----------
text = read_tree_text(TREE)

root = None
stack = []  # [(prefix_len, Node), ...]

for line in text.splitlines():
    parsed = parse_line(line)
    if not parsed:
        continue

    prefix, name, is_dir = parsed
    plen = len(prefix)

    if is_dir:
        while stack and stack[-1][0] >= plen:
            stack.pop()

        node = Node(name, prefix)
        if stack:
            stack[-1][1].children.append(node)
        else:
            if root is None:
                root = node
            else:
                root.children.append(node)

        stack.append((plen, node))
    else:
        if not stack:
            continue
        cur = stack[-1][1]
        ext = Path(name).suffix.lower()
        ext = ext[1:] if ext else "无扩展名"
        cur.ext_counts[ext] += 1
        cur.direct_files += 1
        if cur.file_prefix is None:
            cur.file_prefix = prefix


def calc_total(node: Node):
    total = node.direct_files
    for child in node.children:
        calc_total(child)
        total += child.total_files
    node.total_files = total


if root:
    calc_total(root)


# ---------- 输出 ----------
def render(node: Node, out: list):
    out.append(f"{node.prefix}{node.name}\\")

    # 折叠目录：不展开子文件夹，直接输出 "N*files"
    if node.name in COLLAPSE_DIRS:
        if node.children:
            # 沿用第一个子项的前缀，保证对齐；把 ├── 换成 └──
            line_prefix = node.children[0].prefix.replace("├──", "└──", 1)
        else:
            line_prefix = node.file_prefix or (node.prefix + "└── ")
        out.append(f"{line_prefix}{node.total_files}*files")
        return

    # 普通目录：直属文件按扩展名汇总
    if node.ext_counts:
        summary = "  ".join(
            f"{e}*{n}" for e, n in sorted(node.ext_counts.items())
        )
        prefix = (
            node.file_prefix
            if node.file_prefix is not None
            else node.prefix + "│   ├── "
        )
        out.append(f"{prefix}{summary}")

    for child in node.children:
        render(child, out)


lines = []
if root:
    render(root, lines)

OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines[:100]))
print(f"\n共 {len(lines)} 行，已写入 {OUT}")