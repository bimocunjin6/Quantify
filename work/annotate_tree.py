# -*- coding: utf-8 -*-
"""
读取 tree_summary.txt，修复 CP1251/UTF-8 显示乱码，
并为每一行目录行/文件统计行追加中文注释。
输出 UTF-8 文件。
"""
import re
import sys
from pathlib import Path


def fix_mojibake(s: str) -> str:
    """尝试把 CP1251 显示错位的 UTF-8 文本还原为正常 UTF-8。"""
    rev = {}
    for i in range(256):
        try:
            rev[bytes([i]).decode("cp1251")] = i
        except Exception:
            pass

    b = bytearray()
    for ch in s:
        if ch in rev:
            b.append(rev[ch])
        elif ord(ch) < 256:
            b.append(ord(ch))
        else:
            # 含正常非 CP1251 字符，认为不是可修复乱码
            return s
    try:
        return bytes(b).decode("utf-8")
    except UnicodeDecodeError:
        return s


DIR_NOTES = {
    "xbx_stock_data": "根目录：股票/债券/加密货币/期货/指数/事件/实盘系统总目录",
    "bond-15m-close-price": "债券15分钟收盘价数据集；CSV约930个",
    "bond-5m-close-price": "债券5分钟收盘价数据集；CSV约930个",
    "bond-trading-data-pro": "债券专业交易数据；CSV约930个",
    "bond_and_stock": "股债联动/跨资产相关目录",
    "code": "程序代码与运行环境总目录；含 aqua/data/fuel/rocket/zeus",
    "data": "运行数据目录；含 err/log/temp 等",
    "err": "错误记录目录",
    "log": "日志目录",
    "temp": "临时/日更缓存目录",
    "aqua": "Aqua 程序及 Python 打包运行环境",
    "fuel": "Fuel 程序及 Python 打包运行环境",
    "rocket": "Rocket 程序及交易数据/运行环境",
    "zeus": "Zeus 程序及 Python 打包运行环境",
    "coin-binance-candle-csv-1h": "币安现货1小时K线；CSV约662个",
    "coin-binance-swap-candle-csv-1h": "币安合约1小时K线；CSV约787个",
    "coin-binance-spot-swap-preprocess-pkl-1h": "币安现货/合约预处理结果；含 output 与 split/spot、split/swap",
    "output": "预处理输出目录",
    "split": "训练/验证/测试切分数据目录",
    "spot": "现货切分数据",
    "swap": "合约切分数据",
    "coin-cap": "加密资产市值数据；CSV约884个",
    "coin-coinmarketcap": "CoinMarketCap 数据；CSV约910个",
    "events": "事件数据；CSV约5127个",
    "min_futures_data": "分钟期货数据；含 IC/IF/IH/IM 四个期货品种",
    "IC_future_data": "IC 中证500股指期货分钟数据",
    "IF_future_data": "IF 沪深300股指期货分钟数据",
    "IH_future_data": "IH 上证50股指期货分钟数据",
    "IM_future_data": "IM 中证1000股指期货分钟数据",
    "min_index_data": "分钟指数数据",
    "其他": "其他分钟指数数据/杂项",
    "min_stocks_data": "分钟股票数据；按年份 2019—2025 存放",
    "real_trading": "实盘交易系统数据与结果",
    "回测结果": "策略回测结果目录",
    "实盘信息": "按日期存放的实盘信息",
    "实盘选股结果": "实盘选股结果目录",
    "运行缓存": "实盘运行缓存目录",
    "logs": "实盘日志目录",
    "信号库": "信号 Python 源码库",
    "因子库": "因子 Python 源码库",
    "截面因子库": "截面因子 Python 源码库",
    "策略库": "策略 Python 源码库",
    "外部数据": "外部补充数据目录",
    "交易统计": "交易统计目录",
    "历史信息": "历史交易信息目录",
    "买入计划": "买入计划数据",
    "卖出计划": "卖出计划数据",
    "持仓信息": "持仓信息数据",
    "订单信息": "订单信息数据",
    "系统日志": "Rocket 系统日志",
    "系统缓存": "Rocket 系统缓存",
    "账户信息": "账户信息数据",
    "ui_status": "UI 状态数据",
    "stock_concept_IFIND": "同花顺/IFIND 概念数据；CSV约5452个",
    "xbx_temporary_data": "临时数据目录；含少量 stock 日更数据",
    "xueqiu-hot-data": "雪球热股数据；CSV约4502个",
    "zip": "压缩包目录",
}

STOCK_NOTES = {
    "stock-15m-close-price": "股票15分钟收盘价",
    "stock-1h-index-data": "股票1小时指数数据",
    "stock-1h-trading-data": "股票1小时交易数据",
    "stock-5m-close-price": "股票5分钟收盘价",
    "stock-activation-records": "股票激活记录",
    "stock-analyst-predicted": "分析师预测数据",
    "stock-analyst-ranking": "分析师排名数据",
    "stock-anti-trend-factors": "反趋势因子",
    "stock-asset-classification": "资产分类数据",
    "stock-basic-bond": "债券基础信息",
    "stock-call-auction-data": "集合竞价数据",
    "stock-call-auction-data-0920": "集合竞价数据 0920 版本/缓存",
    "stock-call-auction-data_selfProcessed": "集合竞价数据自处理版本",
    "stock-chip-distribution": "筹码分布数据",
    "stock-cny-rate": "人民币汇率数据",
    "stock-dividend-delivery": "分红送配数据",
    "stock-energy-factors": "能源因子",
    "stock-equity": "股本/权益数据",
    "stock-etf-trading-data": "ETF 交易数据",
    "stock-fin-data-xbx": "财务数据；约5932个文件",
    "stock-fin-pre-data-sina": "新浪财务预告/预披露数据",
    "stock-fin-pre-fore-data-xbx": "财务预测/预告数据",
    "stock-hk-stock-data": "港股数据",
    "stock-ind-element-equity": "行业成分/权益数据",
    "stock-interest-rate": "利率数据",
    "stock-lhb-organ": "龙虎榜机构数据",
    "stock-main-index-data": "主要指数数据",
    "stock-money-flow": "资金流数据",
    "stock-money-flow-xbx": "资金流数据 XBX 版本",
    "stock-multi-factor-series": "多因子序列",
    "stock-notices-title": "公告标题数据",
    "stock-oscillator-factors": "振荡因子",
    "stock-popular-concept-detail": "热门概念详情",
    "stock-technical-factors": "技术因子",
    "stock-trading-data": "股票交易数据",
    "stock-trading-data-pro": "股票专业交易数据",
    "stock-trading-date": "交易日历数据",
    "stock-trend-factors": "趋势因子",
    "stock-us-dividend-delivery-data": "美股分红送配数据",
    "stock-us-main-index-data": "美股主要指数数据",
    "stock-us-trading-data": "美股交易数据；CSV约13516个",
    "stock-volume-price-factors": "量价因子",
    "stock-xueqiu-hot-stock": "雪球热股数据",
}

DEP_NOTE = {
    "numpy": "NumPy 数值计算库",
    "pandas": "Pandas 数据分析库",
    "scipy": "SciPy 科学计算库",
    "sklearn": "Scikit-learn 机器学习库",
    "matplotlib": "Matplotlib 绘图库",
    "pyarrow": "PyArrow/Parquet 列式数据支持",
    "lxml": "XML/HTML 解析库",
    "numba": "Numba JIT 加速库",
    "llvmlite": "LLVM 运行时依赖",
    "cryptography": "加密库",
    "certifi": "CA 证书库",
    "charset_normalizer": "字符编码检测库",
    "dateutil": "日期解析库",
    "pytz": "时区数据库",
    "setuptools": "Python 打包工具",
    "wheel": "Python wheel 打包工具",
    "win32": "pywin32 Windows 扩展",
    "win32com": "pywin32 COM 支持",
    "Pythonwin": "pywin32 Pythonwin 支持",
    "zstandard": "Zstandard 压缩库",
    "tcl8": "Tcl/Tk 运行时数据",
    "tornado": "Tornado Web 框架",
    "psutil": "系统进程/资源监控库",
    "PIL": "Pillow 图像处理库",
    "plotly": "Plotly 绘图库",
    "lz4": "LZ4 压缩库",
    "markupsafe": "MarkupSafe 模板转义库",
}

EXT_DESC = {
    "csv": "CSV 文件",
    "pkl": "pickle 文件",
    "txt": "文本文件",
    "zip": "ZIP 压缩包",
    "7z": "7z 压缩包",
    "gz": "gzip 压缩文件",
    "json": "JSON 文件",
    "py": "Python 源码",
    "pyd": "Python 扩展模块",
    "pyx": "Cython 源码",
    "pxd": "Cython 声明",
    "pxi": "Cython include",
    "c": "C 源码",
    "cpp": "C++ 源码",
    "h": "C/C++ 头文件",
    "hpp": "C++ 头文件",
    "dll": "Windows 动态库",
    "exe": "可执行文件",
    "lib": "静态库/导入库",
    "xml": "XML 文件",
    "lua": "Lua 脚本",
    "ini": "配置文件",
    "log4cxx": "日志配置",
    "tpl": "模板文件",
    "tab": "时区表",
    "zi": "时区信息",
    "xsl": "XSL 样式表",
    "rng": "RELAX NG 模式",
    "terms": "Tk 术语文件",
    "msg": "Tcl/Tk 消息文件",
    "enc": "Tcl 编码文件",
    "tcl": "Tcl 脚本",
    "tm": "Tcl 模块文件",
    "mplstyle": "Matplotlib 样式",
    "feather": "Feather 数据文件",
    "orc": "ORC 列式数据",
    "parquet": "Parquet 列式数据",
    "npy": "NumPy 数组",
    "npz": "NumPy 压缩数组",
    "dat": "数据文件",
    "db": "数据库文件",
    "lock": "锁文件",
    "yml": "YAML 配置",
    "xlsx": "Excel 文件",
    "ts": "TypeScript/时间序列文件",
    "css": "CSS 样式",
    "js": "JavaScript",
    "html": "HTML 文件",
    "md": "Markdown",
    "rst": "reStructuredText",
}


def dir_note(n: str, path: str) -> str:
    if n in DIR_NOTES:
        return DIR_NOTES[n]
    if n.startswith("stock-") or n.startswith("stock_"):
        return STOCK_NOTES.get(n, "股票主题数据集目录")
    if n.endswith("-daily"):
        return "日更缓存目录：对应数据集的每日增量/临时文件"
    if n in DEP_NOTE:
        return "Python/运行时依赖：" + DEP_NOTE[n]
    if re.match(r".*-\d+(\.\d+)*\.dist-info$", n):
        return "Python 包元数据/许可证目录"
    if "libs" in n.lower():
        return "动态库目录：第三方二进制依赖"
    if path.startswith("xbx_stock_data/code/") or path.startswith("xbx_stock_data/real_trading/rocket"):
        return "程序运行/打包环境子目录"
    return "目录"


def stat_note(name: str) -> str:
    m = re.fullmatch(r"(\d+)\*files", name)
    if m:
        return f"文件统计：{m.group(1)} 个文件"

    tokens = re.findall(r"([^\s]+)\*(\d+)", name)
    if tokens:
        parts = []
        for ext, cnt in tokens:
            ext = ext.strip()
            if ext == "无扩展名":
                desc = "无扩展名文件"
            else:
                desc = EXT_DESC.get(ext.lower(), ext.upper() + " 文件")
            parts.append(f"{desc} {cnt} 个")
        return "文件统计：" + "；".join(parts)
    return "文件/统计行"


def annotate(in_path: str, out_path: str) -> None:
    raw_lines = Path(in_path).read_text(encoding="utf-8").splitlines()
    stack = []
    out_lines = []

    for raw in raw_lines:
        line = fix_mojibake(raw.rstrip("\n"))

        m = re.search(r"([├└]── )", line)
        if m:
            prefix = line[:m.start()]
            depth = len(prefix) // 4 + 1
            name_start = m.end()
        else:
            depth = 0
            name_start = 0

        name = line[name_start:].strip()
        is_dir = name.endswith("\\")

        if is_dir:
            n = name.rstrip("\\")
            parent = "/".join(stack[:depth])
            path = (parent + "/" + n) if parent else n
            note = dir_note(n, path)

            stack = stack[:depth]
            stack.append(n)
        else:
            note = stat_note(name)

        out_lines.append(f"{line}  # {note}")

    Path(out_path).write_text("\n".join(out_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "tree_summary.txt"
    dst = sys.argv[2] if len(sys.argv) > 2 else "tree_summary_annotated_utf8.txt"
    annotate(src, dst)
    print(f"已生成 UTF-8 注释文件：{dst}")