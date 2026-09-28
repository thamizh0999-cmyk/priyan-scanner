import pandas as pd

from django.core.management.base import BaseCommand
from django.utils import timezone
from scanners.models import ScanRun, ScanResult
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator


class Command(BaseCommand):
    help = "Calculate continuous momentum scores and show Top 10 stocks"

    def handle(self, *args, **options):

        from stocks.models import Stock
        from marketdata.models import DailyPrice

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
            f"Starting Priyan Momentum Scanner for {scan_date}..."
        )


        stocks = Stock.objects.filter(is_active=True)

        results = []

        for stock in stocks:

            prices = list(
                DailyPrice.objects
                .filter(stock=stock)
                .order_by("date")
                .values(
                    "date",
                    "close",
                    "volume",
                )
            )

            if len(prices) < 200:
                continue

            df = pd.DataFrame(prices)

            df["close"] = pd.to_numeric(
                df["close"],
                errors="coerce",
            )

            df["volume"] = pd.to_numeric(
                df["volume"],
                errors="coerce",
            )

            df = df.dropna(
                subset=["close", "volume"]
            )

            if len(df) < 200:
                continue

            # ==================================================
            # INDICATORS
            # ==================================================

            df["ema20"] = EMAIndicator(
                close=df["close"],
                window=20,
            ).ema_indicator()

            df["ema50"] = EMAIndicator(
                close=df["close"],
                window=50,
            ).ema_indicator()

            df["ema200"] = EMAIndicator(
                close=df["close"],
                window=200,
            ).ema_indicator()

            df["rsi"] = RSIIndicator(
                close=df["close"],
                window=14,
            ).rsi()

            # ==================================================
            # RETURNS
            # ==================================================

            df["return20"] = (
                df["close"]
                .pct_change(20)
                * 100
            )

            df["return50"] = (
                df["close"]
                .pct_change(50)
                * 100
            )

            df["return200"] = (
                df["close"]
                .pct_change(200)
                * 100
            )

            # ==================================================
            # RELATIVE VOLUME
            # ==================================================

            df["volume20"] = (
                df["volume"]
                .rolling(20)
                .mean()
            )

            df["relative_volume"] = (
                df["volume"]
                / df["volume20"]
            )

            latest = df.iloc[-1]

            # ==================================================
            # VALIDATION
            # ==================================================

            required_values = [
                latest["close"],
                latest["ema20"],
                latest["ema50"],
                latest["ema200"],
                latest["rsi"],
                latest["return20"],
                latest["return50"],
                latest["return200"],
                latest["relative_volume"],
            ]

            if any(
                pd.isna(value)
                for value in required_values
            ):
                continue

            # ==================================================
            # SCORE
            # ==================================================

            score = 0.0

            # --------------------------------------------------
            # 1. 20-DAY RETURN â€” 20 POINTS
            # --------------------------------------------------

            return20 = float(
                latest["return20"]
            )

            score20 = min(
                max(return20, 0),
                20,
            )

            score += score20

            # --------------------------------------------------
            # 2. 50-DAY RETURN â€” 15 POINTS
            # --------------------------------------------------

            return50 = float(
                latest["return50"]
            )

            score50 = (
                min(max(return50, 0), 30)
                / 30
                * 15
            )

            score += score50

            # --------------------------------------------------
            # 3. 200-DAY RETURN â€” 10 POINTS
            # --------------------------------------------------

            return200 = float(
                latest["return200"]
            )

            score200 = (
                min(max(return200, 0), 50)
                / 50
                * 10
            )

            score += score200

            # --------------------------------------------------
            # 4. RELATIVE VOLUME â€” 15 POINTS
            # --------------------------------------------------

            relative_volume = float(
                latest["relative_volume"]
            )

            volume_score = (
                min(
                    max(relative_volume, 0),
                    3,
                )
                / 3
                * 15
            )

            score += volume_score

            # --------------------------------------------------
            # 5. RSI â€” 10 POINTS
            # --------------------------------------------------

            rsi = float(
                latest["rsi"]
            )

            if 55 <= rsi <= 70:

                rsi_score = 10

            elif 50 <= rsi < 55:

                rsi_score = 7

            elif 70 < rsi <= 75:

                rsi_score = 7

            elif 45 <= rsi < 50:

                rsi_score = 3

            else:

                rsi_score = 0

            score += rsi_score

            # --------------------------------------------------
            # 6. EMA TREND â€” 10 POINTS
            # --------------------------------------------------

            close = float(
                latest["close"]
            )

            ema20 = float(
                latest["ema20"]
            )

            ema50 = float(
                latest["ema50"]
            )

            ema200 = float(
                latest["ema200"]
            )

            trend_score = 0

            if close > ema20:
                trend_score += 3

            if ema20 > ema50:
                trend_score += 3

            if ema50 > ema200:
                trend_score += 4

            score += trend_score

            # --------------------------------------------------
            # 7. 52-WEEK HIGH PROXIMITY â€” 10 POINTS
            # --------------------------------------------------

            high_252 = (
                df["close"]
                .tail(252)
                .max()
            )

            distance_from_high = (
                (high_252 - close)
                / high_252
                * 100
            )

            high_score = max(
                0,
                10 - (
                    max(distance_from_high, 0)
                    / 20
                    * 10
                ),
            )

            score += high_score

            # --------------------------------------------------
            # 8. VOLATILITY â€” 5 POINTS
            # --------------------------------------------------

            daily_returns = (
                df["close"]
                .pct_change()
                .tail(20)
            )

            volatility = (
                daily_returns.std()
                * 100
            )

            # Moderate volatility gets the full score.
            if 1 <= volatility <= 4:

                volatility_score = 5

            elif volatility < 1:

                volatility_score = 3

            elif volatility <= 6:

                volatility_score = 3

            else:

                volatility_score = 1

            score += volatility_score

            # --------------------------------------------------
            # 9. LIQUIDITY â€” 5 POINTS
            # --------------------------------------------------

            average_value = (
                (
                    df["close"]
                    * df["volume"]
                )
                .tail(20)
                .mean()
            )

            if average_value >= 50_000_000:

                liquidity_score = 5

            elif average_value >= 10_000_000:

                liquidity_score = 4

            elif average_value >= 2_000_000:

                liquidity_score = 3

            elif average_value >= 500_000:

                liquidity_score = 2

            else:

                liquidity_score = 0

            score += liquidity_score

            # ==================================================
            # STORE RESULT
            # ==================================================

            results.append(
                {
                    "symbol": stock.symbol,
                    "company": stock.company_name,
                    "score": min(score, 100),
                    "close": close,
                    "return20": return20,
                    "return50": return50,
                    "return200": return200,
                    "rsi": rsi,
                    "relative_volume": relative_volume,
                    "distance_high": distance_from_high,
                }
            )

        # ======================================================
        # RANK
        # ======================================================

        results.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        top10 = results[:10]

        # ======================================================
        # SAVE SCAN TO DATABASE
        # ======================================================

        scan_run = ScanRun.objects.create(
            scan_type="MOMENTUM",
            scan_date=scan_date,
        )

        for rank, item in enumerate(top10, start=1):

            stock_obj = Stock.objects.get(
                symbol=item["symbol"]
            )

            ScanResult.objects.create(
                scan_run=scan_run,
                stock=stock_obj,
                rank=rank,
                score=round(item["score"], 2),
                close=round(item["close"], 2),
                relative_volume=round(
                    item["relative_volume"], 2
                ),
                rsi=round(item["rsi"], 2),
                return_20=round(
                    item["return20"], 2
                ),
                return_120=round(
                    item["return50"], 2
                ),
                return_200=round(
                    item["return200"], 2
                ),
            )
        # ======================================================
        # OUTPUT
        # ======================================================

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "PRIYAN SCANNER â€” TOP 10 MOMENTUM"
            )
        )

        self.stdout.write("=" * 120)

        self.stdout.write(
            f"{'Rank':<5}"
            f"{'Symbol':<15}"
            f"{'Score':>7}"
            f"{'1M %':>10}"
            f"{'3M %':>10}"
            f"{'6M %':>10}"
            f"{'RSI':>8}"
            f"{'RelVol':>9}"
            f"{'52W Gap':>10}"
        )

        self.stdout.write("-" * 120)

        for rank, stock in enumerate(
            top10,
            start=1,
        ):

            self.stdout.write(
                f"{rank:<5}"
                f"{stock['symbol']:<15}"
                f"{stock['score']:>7.2f}"
                f"{stock['return20']:>10.2f}"
                f"{stock['return50']:>10.2f}"
                f"{stock['return200']:>10.2f}"
                f"{stock['rsi']:>8.2f}"
                f"{stock['relative_volume']:>9.2f}"
                f"{stock['distance_high']:>10.2f}"
            )

        self.stdout.write("=" * 120)

        self.stdout.write(
            f"Stocks analysed: {len(results)}"
        )



