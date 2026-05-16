#!/usr/bin/env python3
"""TopTrader 后端共享工具函数。

这里的函数是 dal.py 和 api_server.py 的公共基础设施。
local_web.py 暂时保留自己的副本，待后续 Phase 统一。
"""

from __future__ import annotations

from typing import Any


def clean_text(value: Any) -> str:
    """把任意值转为干净字符串，null/none 视为空字符串。"""
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"null", "none"}:
        return ""
    return text


def to_int(value: Any) -> int | None:
    """安全转 int，空值或非法值返回 None。"""
    text = clean_text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def to_float(value: Any) -> float | None:
    """安全转 float，支持带逗号的数字字符串，空值返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_bool_int(value: Any) -> int:
    """转为 SQLite 兼容的布尔整数（0 或 1）。"""
    return 1 if value is True or str(value).lower() in {"1", "true", "yes", "on"} else 0


def meaningful_text(value: Any) -> int:
    """判断字符串是否有意义（用于 SQLite 自定义函数）。
    规则：去除空白后长度 >= 4，且不是纯数字。
    """
    text = clean_text(value)
    if not text:
        return 0
    compact = "".join(char for char in text if char.isalnum())
    if len(compact) < 4:
        return 0
    if compact.isdigit():
        return 0
    return 1


def format_number(value: float | None, *, suffix: str = "") -> str:
    """格式化数字；None 返回 '--'。"""
    if value is None:
        return "--"
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def numeric_almost_equal(left: float | None, right: float | None, *, tolerance: float = 1e-9) -> bool:
    """浮点近似比较。"""
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance


def trade_pnl_total(trades: list[dict[str, Any]]) -> float | None:
    """汇总交易列表的 pnl_amount。"""
    pnl_values = [to_float(trade.get("pnl_amount")) for trade in trades]
    pnl_values = [value for value in pnl_values if value is not None]
    if not pnl_values:
        return None
    return sum(pnl_values)
