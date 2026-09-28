import pandas as pd

from django.core.management.base import BaseCommand
from django.utils import timezone
from scanners.models import ScanRun, ScanResult
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator


class Command(BaseCommand):
    help = "Find swing trading breakout stocks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Scan date in YYYY-MM-DD format. Defaults to latest EOD date.",
        )

    def handle(self, *args, **options):

        from stocks.models import Stock
        from marketdata.models import DailyPrice

        requested_date = options.get("date")

        if requested_date:
            try:
                scan_date = pd.to_datetime(requested_date).date()
            except Exception:
                self.stdout.write(
                    self.style.ERROR("Invalid date. Use YYYY-MM-DD.")
                )
                return
        else:
            scan_date = (
                DailyPrice.objects
                .order_by("-date")
                .values_list("date", flat=True)
                .first()
            )

        if not scan_date:
            self.stdout.write(
                self.style.ERROR("No EOD market data found.")
            )
            return

        self.stdout.write(
            f"Starting Priyan Swing Breakout Scanner for {scan_date}..."
        )

        stocks = Stock.objects.filter(
            is_active=True
        )

        results = []

        for stock in stocks:

            prices = list(
                DailyPrice.objects
                .filter(stock=stock)
                .order_by("date")
                .values(
                    "date",
                    "close",
                    "high",
                    "low",
                    "volume",
                )
            )

            if len(prices) < 60:
                continue

            df = pd.DataFrame(prices)

            for column in [
                "close",
                "high",
                "low",
                "volume",
            ]:
                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

            df = df.dropna(
                subset=[
                    "close",
                    "high",
                    "low",
                    "volume",
                ]
            )

            if len(df) < 60:
                continue

            # ==============================================
            # INDICATORS
            # ==============================================

            df["ema20"] = EMAIndicator(
                close=df["close"],
                window=20,
            ).ema_indicator()

            df["ema50"] = EMAIndicator(
                close=df["close"],
                window=50,
            ).ema_indicator()

            df["rsi"] = RSIIndicator(
                close=df["close"],
                window=14,
            ).rsi()

            df["volume20"] = (
                df["volume"]
                .rolling(20)
                .mean()
            )

            # ==============================================
            # RECENT RESISTANCE
            # ==============================================

            # Previous 20 trading-day high,
            # excluding today's candle.
            df["resistance20"] = (
                df["high"]
                .shift(1)
                .rolling(20)
                .max()
            )

            latest = df.iloc[-1]

            if pd.isna(
                latest["resistance20"]
            ):
                continue

            close = float(
                latest["close"]
            )

            high = float(
                latest["high"]
            )

            resistance = float(
                latest["resistance20"]
            )

            volume = float(
                latest["volume"]
            )

            volume20 = float(
                latest["volume20"]
            )

            ema20 = float(
                latest["ema20"]
            )

            ema50 = float(
                latest["ema50"]
            )

            rsi = float(
                latest["rsi"]
            )

            if volume20 <= 0:
                continue

            # ==============================================
            # BREAKOUT
            # ==============================================

            breakout_percent = (
                (close - resistance)
                / resistance
                * 100
            )

            # ==============================================
            # RELATIVE VOLUME
            # ==============================================

            relative_volume = (
                volume / volume20
            )

            # ==============================================
            # SCORE — 100 POINTS
            # ==============================================

            score = 0.0

            # ----------------------------------------------
            # 1. BREAKOUT STRENGTH — 25 POINTS
            # ----------------------------------------------
            breakout_score = min(
                max(breakout_percent, 0) / 5,
                1,
            ) * 25

            score += breakout_score

            # ----------------------------------------------
            # 2. VOLUME CONFIRMATION — 25 POINTS
            # Cap extreme volume at 4x
            # ----------------------------------------------
            volume_factor = min(
                max(relative_volume, 1.5),
                4.0,
            )

            volume_score = (
                (volume_factor - 1.5)
                / (4.0 - 1.5)
            ) * 25

            score += volume_score

            # ----------------------------------------------
            # 3. EMA TREND — 20 POINTS
            # ----------------------------------------------
            trend_score = 0

            if close > ema20:
                trend_score += 7

            if ema20 > ema50:
                trend_score += 7

            if close > ema50:
                trend_score += 6

            score += trend_score

            # ----------------------------------------------
            # 4. RSI QUALITY — 15 POINTS
            # ----------------------------------------------
            if 55 <= rsi <= 70:
                rsi_score = 15
            elif 50 <= rsi < 55:
                rsi_score = 10
            elif 70 < rsi <= 75:
                rsi_score = 10
            elif 45 <= rsi < 50:
                rsi_score = 5
            else:
                rsi_score = 0

            score += rsi_score

            # ----------------------------------------------
            # 5. 20-DAY PRICE MOMENTUM — 10 POINTS
            # ----------------------------------------------
            return20 = (
                df["close"]
                .pct_change(20)
                .iloc[-1]
                * 100
            )

            price_score = min(
                max(return20, 0) / 20,
                1,
            ) * 10

            score += price_score

            # ----------------------------------------------
            # 6. BREAKOUT DISTANCE — 5 POINTS
            # Prefer controlled breakouts
            # ----------------------------------------------
            distance_score = max(
                0,
                5 - max(breakout_percent - 2, 0),
            )

            score += distance_score
            # ==============================================
            # REQUIRE ACTUAL BREAKOUT
            # ==============================================

            if close <= resistance:
                continue

            if relative_volume < 1.5:
                continue

            if breakout_percent < 2:
                continue

            if rsi > 75:
                continue

            if close <= ema20:
                continue

            if ema20 <= ema50:
                continue

            # ==============================================
            # STORE RESULT
            # ==============================================

            results.append(
                {
                    "symbol": stock.symbol,
                    "company": stock.company_name,
                    "score": min(score, 100),
                    "close": close,
                    "resistance": resistance,
                    "breakout": breakout_percent,
                    "relative_volume": relative_volume,
                    "rsi": rsi,
                    "return20": return20,
                }
            )

        # ==============================================
        # RANK
        # ==============================================

        results.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        top20 = results[:20]

        # ==============================================
        # SAVE SCAN TO DATABASE
        # ==============================================

        scan_run = ScanRun.objects.create(
            scan_type="SWING",
            scan_date=scan_date,
        )

        for rank, item in enumerate(top20, start=1):

            stock_obj = Stock.objects.get(
                symbol=item["symbol"]
            )

            ScanResult.objects.create(
                scan_run=scan_run,
                stock=stock_obj,
                rank=rank,
                score=round(item["score"], 2),
                close=round(item["close"], 2),
                breakout_percent=round(
                    item["breakout"], 2
                ),
                relative_volume=round(
                    item["relative_volume"], 2
                ),
                rsi=round(item["rsi"], 2),
                return_20=round(
                    item["return20"], 2
                ),
            )
        # ==============================================
        # OUTPUT
        # ==============================================

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "PRIYAN SCANNER â€” SWING BREAKOUTS"
            )
        )

        self.stdout.write("=" * 120)

        self.stdout.write(
            f"{'Rank':<5}"
            f"{'Symbol':<15}"
            f"{'Score':>7}"
            f"{'Close':>10}"
            f"{'Breakout':>11}"
            f"{'RelVol':>9}"
            f"{'RSI':>8}"
            f"{'20D %':>10}"
        )

        self.stdout.write("-" * 120)

        for rank, stock in enumerate(
            top20,
            start=1,
        ):

            self.stdout.write(
                f"{rank:<5}"
                f"{stock['symbol']:<15}"
                f"{stock['score']:>7.2f}"
                f"{stock['close']:>10.2f}"
                f"{stock['breakout']:>10.2f}%"
                f"{stock['relative_volume']:>9.2f}"
                f"{stock['rsi']:>8.2f}"
                f"{stock['return20']:>10.2f}%"
            )

        self.stdout.write("=" * 120)

        self.stdout.write(
            f"Breakout stocks found: {len(results)}"
        )







