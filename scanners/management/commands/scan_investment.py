from django.core.management.base import BaseCommand
from django.utils import timezone
from scanners.models import ScanRun, ScanResult
from stocks.models import Stock
from marketdata.models import DailyPrice
import pandas as pd
import numpy as np


class Command(BaseCommand):

    help = "Run Priyan Investment Breakout Scanner"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Scan date in YYYY-MM-DD format. Defaults to latest EOD date.",
        )

    def handle(self, *args, **options):

        requested_date = options.get("date")

        if requested_date:
            try:
                scan_date = pd.to_datetime(
                    requested_date
                ).date()
            except Exception:
                self.stdout.write(
                    self.style.ERROR(
                        "Invalid date. Use YYYY-MM-DD."
                    )
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
                self.style.ERROR(
                    "No EOD market data found."
                )
            )
            return

        self.stdout.write(
            f"Starting Priyan Investment Breakout Scanner for {scan_date}..."
        )

        results = []

        stocks = Stock.objects.filter(is_active=True)

        for stock in stocks:

            prices = list(
                DailyPrice.objects
                .filter(stock=stock)
                .order_by("date")
                .values(
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                )
            )

            if len(prices) < 200:
                continue

            df = pd.DataFrame(prices)

            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce",
                )

            df = df.dropna()

            if len(df) < 200:
                continue

            # ==================================================
            # MOVING AVERAGES
            # ==================================================

            df["ema50"] = (
                df["close"]
                .ewm(span=50, adjust=False)
                .mean()
            )

            df["ema200"] = (
                df["close"]
                .ewm(span=200, adjust=False)
                .mean()
            )

            # ==================================================
            # MOMENTUM
            # ==================================================

            return60 = (
                df["close"]
                .pct_change(60)
                .iloc[-1]
                * 100
            )

            return120 = (
                df["close"]
                .pct_change(120)
                .iloc[-1]
                * 100
            )

            return200 = (
                df["close"]
                .pct_change(200)
                .iloc[-1]
                * 100
            )

            # ==================================================
            # 52 WEEK HIGH
            # ==================================================

            high_52w = (
                df["high"]
                .tail(252)
                .max()
            )

            previous_52w_high = (
                df["high"]
                .iloc[:-1]
                .tail(252)
                .max()
            )

            close = float(df["close"].iloc[-1])
            ema50 = float(df["ema50"].iloc[-1])
            ema200 = float(df["ema200"].iloc[-1])

            breakout_percent = (
                (close - previous_52w_high)
                / previous_52w_high
                * 100
            )

            distance_from_high = (
                (high_52w - close)
                / high_52w
                * 100
            )

            # ==================================================
            # VOLUME
            # ==================================================

            volume20 = (
                df["volume"]
                .rolling(20)
                .mean()
                .iloc[-1]
            )

            current_volume = float(
                df["volume"].iloc[-1]
            )

            if volume20 <= 0:
                continue

            relative_volume = (
                current_volume / volume20
            )

            # ==================================================
            # RSI
            # ==================================================

            delta = df["close"].diff()

            gain = delta.clip(lower=0)

            loss = -delta.clip(upper=0)

            avg_gain = (
                gain
                .rolling(14)
                .mean()
            )

            avg_loss = (
                loss
                .rolling(14)
                .mean()
            )

            rs = avg_gain / avg_loss.replace(
                0,
                np.nan,
            )

            df["rsi"] = (
                100
                - (
                    100
                    / (1 + rs)
                )
            )

            rsi = float(
                df["rsi"].iloc[-1]
            )

            if np.isnan(rsi):
                continue

            # ==================================================
            # INVESTMENT BREAKOUT REQUIREMENTS
            # ==================================================

            if close <= ema200:
                continue

            if ema50 <= ema200:
                continue

            if breakout_percent < 2:
                continue

            if return60 <= 0:
                continue

            if return120 <= 0:
                continue

            if return200 <= 0:
                continue

            if distance_from_high > 5:
                continue

            if relative_volume < 1.2:
                continue

            if rsi < 50 or rsi > 75:
                continue

            # ==================================================
            # SCORE — 100 POINTS
            # ==================================================

            score = 0.0

            # 1. LONG TERM TREND — 25
            trend_score = 0

            if close > ema200:
                trend_score += 10

            if ema50 > ema200:
                trend_score += 10

            if close > ema50:
                trend_score += 5

            score += trend_score

            # 2. 6 MONTH MOMENTUM — 20
            momentum6_score = min(
                max(return120, 0) / 50,
                1,
            ) * 20

            score += momentum6_score

            # 3. 200 DAY MOMENTUM — 15
            momentum200_score = min(
                max(return200, 0) / 75,
                1,
            ) * 15

            score += momentum200_score

            # 4. 52 WEEK STRENGTH — 20
            high_score = max(
                0,
                20 - (
                    distance_from_high
                    / 15
                    * 20
                ),
            )

            score += high_score

            # 5. VOLUME — 10
            volume_factor = min(
                max(relative_volume, 1),
                3,
            )

            volume_score = (
                (volume_factor - 1)
                / 2
            ) * 10

            score += volume_score

            # 6. RSI QUALITY — 10
            if 55 <= rsi <= 70:
                rsi_score = 10
            elif 50 <= rsi < 55:
                rsi_score = 7
            elif 70 < rsi <= 75:
                rsi_score = 7
            elif 75 < rsi <= 80:
                rsi_score = 4
            else:
                rsi_score = 2

            score += rsi_score

            results.append(
                {
                    "symbol": stock.symbol,
                    "company": stock.company_name,
                    "score": min(score, 100),
                    "close": close,
                    "breakout": breakout_percent,
                    "distance_high": distance_from_high,
                    "return120": return120,
                    "return200": return200,
                    "relative_volume": relative_volume,
                    "rsi": rsi,
                }
            )

        # ==================================================
        # RANK
        # ==================================================

        results.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        top20 = results[:20]
        # ==================================================
        # SAVE SCAN TO DATABASE
        # ==================================================

        scan_run = ScanRun.objects.create(
            scan_type="INVESTMENT",
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
                breakout_percent=round(item["breakout"], 2),
                relative_volume=round(item["relative_volume"], 2),
                rsi=round(item["rsi"], 2),
                return_120=round(item["return120"], 2),
                return_200=round(item["return200"], 2),
            )

        # ==================================================
        # OUTPUT
        # ==================================================

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "PRIYAN SCANNER - INVESTMENT BREAKOUTS"
            )
        )

        self.stdout.write("=" * 125)

        self.stdout.write(
            f"{'Rank':<5}"
            f"{'Symbol':<15}"
            f"{'Score':>7}"
            f"{'Close':>10}"
            f"{'Breakout':>11}"
            f"{'52W Gap':>10}"
            f"{'6M %':>10}"
            f"{'1Y %':>10}"
            f"{'RelVol':>9}"
            f"{'RSI':>8}"
        )

        self.stdout.write("-" * 125)

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
                f"{stock['distance_high']:>9.2f}%"
                f"{stock['return120']:>9.2f}%"
                f"{stock['return200']:>9.2f}%"
                f"{stock['relative_volume']:>9.2f}"
                f"{stock['rsi']:>8.2f}"
            )

        self.stdout.write("=" * 125)

        self.stdout.write(
            f"Investment breakout stocks found: {len(results)}"
        )







