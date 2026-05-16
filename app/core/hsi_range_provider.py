from __future__ import annotations

import math
import socket
import threading
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from futu import AuType, KLType, KL_FIELD, OpenQuoteContext, RET_OK


DEFAULT_HOST = "127.0.0.1"
DEFAULT_OPEND_PORT = 11111
DEFAULT_CODE = "HK.800000"
DEFAULT_LOOKBACK = 200


class HSIRangeError(RuntimeError):
    pass


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def pct_rank(series: pd.Series, value: float) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return 0.0
    return float((clean <= value).sum() / len(clean) * 100)


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class HSIRangeDataProvider:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_OPEND_PORT, code: str = DEFAULT_CODE, lookback: int = DEFAULT_LOOKBACK) -> None:
        self.host = host
        self.port = port
        self.code = code
        self.lookback = lookback
        self.lock = threading.Lock()
        self.ctx = OpenQuoteContext(host=host, port=port)
        self.history = self._load_history()
        self.stats = self._build_stats(self.history)

    def close(self) -> None:
        with self.lock:
            self.ctx.close()

    def _load_history(self) -> pd.DataFrame:
        fields = [
            KL_FIELD.DATE_TIME,
            KL_FIELD.OPEN,
            KL_FIELD.HIGH,
            KL_FIELD.LOW,
            KL_FIELD.CLOSE,
            KL_FIELD.CHANGE_RATE,
            KL_FIELD.TRADE_VAL,
        ]
        start = (date.today() - timedelta(days=365)).isoformat()
        end = date.today().isoformat()

        with self.lock:
            ret, data, _ = self.ctx.request_history_kline(
                self.code,
                start=start,
                end=end,
                ktype=KLType.K_DAY,
                autype=AuType.NONE,
                fields=fields,
                max_count=1000,
            )

        if ret != RET_OK:
            raise HSIRangeError(f"读取历史日 K 失败：{data}")
        if data is None or data.empty:
            raise HSIRangeError(f"未获取到 {self.code} 的历史日 K 数据。")

        df = data.copy()
        df["date"] = pd.to_datetime(df["time_key"]).dt.date
        for column in ["open", "high", "low", "close", "change_rate", "turnover"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        df = df.sort_values("date").drop_duplicates("date")
        df = df[df["date"] < date.today()]
        df = df.dropna(subset=["date", "open", "high", "low", "close"])
        df = df[df["open"] > 0]
        df["range_points"] = df["high"] - df["low"]
        df["range_pct"] = df["range_points"] / df["open"] * 100
        df = df.tail(self.lookback).reset_index(drop=True)

        if len(df) < self.lookback:
            raise HSIRangeError(f"历史完整交易日只有 {len(df)} 个，少于要求的 {self.lookback} 个。")

        return df[
            [
                "date",
                "open",
                "high",
                "low",
                "close",
                "range_points",
                "range_pct",
                "change_rate",
                "turnover",
            ]
        ]

    def _build_stats(self, history: pd.DataFrame) -> dict[str, Any]:
        ranges = history["range_pct"]
        return {
            "lookback": self.lookback,
            "start_date": history["date"].iloc[0].isoformat(),
            "end_date": history["date"].iloc[-1].isoformat(),
            "mean_pct": float(ranges.mean()),
            "median_pct": float(ranges.median()),
            "p75_pct": float(ranges.quantile(0.75)),
            "p90_pct": float(ranges.quantile(0.90)),
            "max_pct": float(ranges.max()),
            "mean_points": float(history["range_points"].mean()),
            "median_points": float(history["range_points"].median()),
            "p75_points": float(history["range_points"].quantile(0.75)),
            "p90_points": float(history["range_points"].quantile(0.90)),
            "max_points": float(history["range_points"].max()),
        }

    def _snapshot(self) -> pd.Series:
        with self.lock:
            ret, data = self.ctx.get_market_snapshot([self.code])
        if ret != RET_OK:
            raise HSIRangeError(f"读取实时快照失败：{data}")
        if data is None or data.empty:
            raise HSIRangeError(f"未获取到 {self.code} 的实时快照。")
        return data.iloc[0]

    def state(self) -> dict[str, Any]:
        snapshot = self._snapshot()
        open_price = finite_float(snapshot.get("open_price"))
        high_price = finite_float(snapshot.get("high_price"))
        low_price = finite_float(snapshot.get("low_price"))
        last_price = finite_float(snapshot.get("last_price"))
        turnover = finite_float(snapshot.get("turnover"))

        warnings: list[str] = []
        if open_price is None or high_price is None or low_price is None or last_price is None:
            raise HSIRangeError("实时快照缺少开盘价、最高价、最低价或现价。")
        if open_price <= 0:
            raise HSIRangeError("实时快照开盘价为 0，无法计算当日振幅百分比。")

        range_points = high_price - low_price
        range_pct = range_points / open_price * 100
        if range_points > 0:
            position_pct = (last_price - low_price) / range_points * 100
            position_pct = max(0.0, min(100.0, position_pct))
        else:
            position_pct = 50.0
            warnings.append("当前最高价和最低价相同，区间位置暂按 50% 显示。")

        rank = pct_rank(self.history["range_pct"], range_pct)
        p75_left = self.stats["p75_pct"] - range_pct
        p90_left = self.stats["p90_pct"] - range_pct

        update_time = str(snapshot.get("update_time", ""))
        if update_time:
            try:
                update_dt = datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")
                if datetime.now() - update_dt > timedelta(hours=8):
                    warnings.append("快照更新时间较久，可能处于休市或数据未刷新状态。")
            except ValueError:
                pass

        status = self._status(range_pct, position_pct)
        return {
            "ok": True,
            "code": self.code,
            "name": str(snapshot.get("name", self.code)),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "snapshot": {
                "update_time": update_time,
                "last_price": last_price,
                "open_price": open_price,
                "high_price": high_price,
                "low_price": low_price,
                "turnover": turnover,
            },
            "intraday": {
                "range_points": range_points,
                "range_pct": range_pct,
                "rank_pct": rank,
                "position_pct": position_pct,
                "p75_left_pct": p75_left,
                "p90_left_pct": p90_left,
                "p75_left_points": p75_left / 100 * open_price,
                "p90_left_points": p90_left / 100 * open_price,
            },
            "status": status,
            "stats": self.stats,
            "warnings": warnings,
        }

    def _status(self, range_pct: float, position_pct: float) -> dict[str, str]:
        median = self.stats["median_pct"]
        p75 = self.stats["p75_pct"]
        p90 = self.stats["p90_pct"]

        if range_pct < median:
            level = "normal"
            label = "正常"
            message = "当日振幅低于 200 日中位数，波动预算尚未明显消耗。"
        elif range_pct < p75:
            level = "tighten"
            label = "开始收紧"
            message = "当日振幅已高于中位数，不宜继续按低波动日预期加仓。"
        elif range_pct < p90:
            level = "protect"
            label = "保护浮盈"
            message = "当日振幅进入 200 日高位区，优先考虑移动止损或分批保护利润。"
        else:
            level = "tail"
            label = "只留尾仓/谨慎追价"
            message = "当日振幅超过 200 日 90 分位，继续期待大空间需要强趋势确认。"

        if range_pct >= p75:
            if position_pct >= 75:
                message += " 当前价格仍靠近当日高位，趋势尾仓可用跟踪止损管理。"
            elif position_pct <= 35:
                message += " 当前价格已回到当日区间下部，浮盈回吐风险较高。"
            else:
                message += " 当前价格在区间中部，继续持仓的盈亏比需要重新评估。"

        return {"level": level, "label": label, "message": message}


class ResilientHSIRangeProvider:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_OPEND_PORT, code: str = DEFAULT_CODE, lookback: int = DEFAULT_LOOKBACK) -> None:
        self.host = host
        self.port = port
        self.code = code
        self.lookback = lookback
        self.lock = threading.Lock()
        self.provider: HSIRangeDataProvider | None = None

    def close(self) -> None:
        with self.lock:
            if self.provider is not None:
                self.provider.close()
                self.provider = None

    def state(self) -> dict[str, Any]:
        with self.lock:
            if self.provider is None:
                if not is_port_open(self.host, self.port):
                    raise HSIRangeError(f"无法连接富途 OpenD：{self.host}:{self.port}。请确认 OpenD 已启动并登录。")
                self.provider = HSIRangeDataProvider(self.host, self.port, self.code, self.lookback)
            provider = self.provider

        try:
            return provider.state()
        except Exception:
            with self.lock:
                if self.provider is provider:
                    self.provider.close()
                    self.provider = None
            raise

