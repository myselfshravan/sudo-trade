"""LLM-powered sentiment analyzer for market data."""

import json
from datetime import datetime
from typing import Any

from src.analysis.base import Analyzer, Signal, SignalType
from src.llm.client import OpenAIClient
from src.core.events import EventBus
from src.core.logger import get_logger

log = get_logger()

ANALYSIS_PROMPT = """You are a quantitative market analyst. Analyze the following market data and provide a trading signal.

{data}

Respond in JSON only, no markdown:
{{
  "signal": <float between -1.0 (very bearish) and 1.0 (very bullish)>,
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence>",
  "action": "<BUY|SELL|HOLD>",
  "key_factors": ["<factor1>", "<factor2>"]
}}"""


class SentimentAnalyzer:
    name = "sentiment"

    def __init__(self, llm: OpenAIClient, events: EventBus):
        self._llm = llm
        self._events = events

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def analyze(self, data: Any) -> list[Signal]:
        prompt = ANALYSIS_PROMPT.format(data=data)

        try:
            raw = await self._llm.analyze(prompt, temperature=0.3)
            parsed = self._parse_response(raw)
        except Exception as e:
            log.error(f"sentiment analysis failed: {e}")
            return []

        signal = Signal(
            type=SignalType.SENTIMENT,
            symbol=parsed.get("symbol", "UNKNOWN"),
            value=float(parsed.get("signal", 0)),
            confidence=float(parsed.get("confidence", 0)),
            source="llm_sentiment",
            reasoning=parsed.get("reasoning", ""),
            metadata={
                "action": parsed.get("action", "HOLD"),
                "key_factors": parsed.get("key_factors", []),
                "model": self._llm.model,
            },
        )

        await self._events.emit("signal:generated", signal=signal)
        return [signal]

    async def analyze_quote(self, symbol: str, quote_data: dict) -> list[Signal]:
        data = f"""Stock: {symbol}
Price: ₹{quote_data.get('price', 0):,.2f}
Day Change: {quote_data.get('day_change_perc', 0):.2f}%
Volume: {quote_data.get('volume', 0):,}
Open: ₹{quote_data.get('ohlc', {}).get('open', 0):,.2f}
High: ₹{quote_data.get('ohlc', {}).get('high', 0):,.2f}
Low: ₹{quote_data.get('ohlc', {}).get('low', 0):,.2f}
Close: ₹{quote_data.get('ohlc', {}).get('close', 0):,.2f}
52W High: ₹{quote_data.get('week_52_high', 0):,.2f}
52W Low: ₹{quote_data.get('week_52_low', 0):,.2f}
Upper Circuit: ₹{quote_data.get('upper_circuit', 0):,.2f}
Lower Circuit: ₹{quote_data.get('lower_circuit', 0):,.2f}"""

        signals = await self.analyze(data)
        for s in signals:
            s.symbol = symbol
        return signals

    async def analyze_historical(
        self, symbol: str, candles: list[dict], period: str = ""
    ) -> list[Signal]:
        if len(candles) > 30:
            candles = candles[-30:]

        lines = [f"Stock: {symbol}", f"Period: last {len(candles)} {period or 'candles'}", ""]
        lines.append("Date       | Open    | High    | Low     | Close   | Volume")
        lines.append("-" * 70)
        for c in candles:
            ts = c.get("timestamp", 0)
            if isinstance(ts, (int, float)):
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            else:
                date = str(ts)[:10]
            lines.append(
                f"{date} | {c['open']:>7.1f} | {c['high']:>7.1f} | "
                f"{c['low']:>7.1f} | {c['close']:>7.1f} | {c.get('volume', 0):>10,}"
            )

        if len(candles) >= 2:
            first_close = candles[0]["close"]
            last_close = candles[-1]["close"]
            change_pct = (last_close - first_close) / first_close * 100
            lines.append(f"\nPeriod return: {change_pct:+.2f}%")

        signals = await self.analyze("\n".join(lines))
        for s in signals:
            s.symbol = symbol
        return signals

    def _parse_response(self, raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        return json.loads(raw)
