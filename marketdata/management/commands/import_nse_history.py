import io
import zipfile
from datetime import date, timedelta

import pandas as pd
import requests

from django.core.management.base import BaseCommand
from django.db import transaction

from stocks.models import Stock
from marketdata.models import DailyPrice


class Command(BaseCommand):
    help = "Import NSE historical equity data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of calendar days to check",
        )

    def handle(self, *args, **options):

        days = options["days"]

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        }

        end_date = date(2026, 9, 18)
        start_date = end_date - timedelta(days=days)

        total_prices = 0
        trading_days = 0

        current_date = start_date

        while current_date <= end_date:

            trade_date = current_date.strftime("%Y%m%d")

            url = (
                "https://nsearchives.nseindia.com/"
                f"content/cm/"
                f"BhavCopy_NSE_CM_0_0_0_{trade_date}_F_0000.csv.zip"
            )

            self.stdout.write(
                f"Checking {current_date}..."
            )

            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=30,
                )

                if response.status_code != 200:
                    current_date += timedelta(days=1)
                    continue

                with zipfile.ZipFile(
                    io.BytesIO(response.content)
                ) as z:

                    csv_files = [
                        name
                        for name in z.namelist()
                        if name.lower().endswith(".csv")
                    ]

                    if not csv_files:
                        current_date += timedelta(days=1)
                        continue

                    with z.open(csv_files[0]) as csv_file:
                        df = pd.read_csv(csv_file)

                # Only normal equity shares.
                df = df[
                    (df["FinInstrmTp"] == "STK")
                    & (df["SctySrs"] == "EQ")
                ].copy()

                if df.empty:
                    current_date += timedelta(days=1)
                    continue

                trading_days += 1

                prices_to_create = []

                with transaction.atomic():

                    for _, row in df.iterrows():

                        symbol = str(
                            row["TckrSymb"]
                        ).strip()

                        if not symbol:
                            continue

                        isin = str(
                            row["ISIN"]
                        ).strip()

                        company_name = str(
                            row["FinInstrmNm"]
                        ).strip()

                        stock, _ = Stock.objects.update_or_create(
                            symbol=symbol,
                            defaults={
                                "company_name": company_name,
                                "isin": isin,
                                "is_active": True,
                            },
                        )

                        prices_to_create.append(
                            DailyPrice(
                                stock=stock,
                                date=current_date,
                                open=row["OpnPric"],
                                high=row["HghPric"],
                                low=row["LwPric"],
                                close=row["ClsPric"],
                                volume=int(
                                    row["TtlTradgVol"]
                                ),
                                traded_value=row["TtlTrfVal"],
                            )
                        )

                    # Remove existing records for this date
                    # so the command can safely be re-run.
                    DailyPrice.objects.filter(
                        date=current_date
                    ).delete()

                    DailyPrice.objects.bulk_create(
                        prices_to_create,
                        batch_size=1000,
                    )

                    total_prices += len(prices_to_create)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Imported {len(prices_to_create)} stocks"
                    )
                )

            except Exception as e:

                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipped {current_date}: {e}"
                    )
                )

            current_date += timedelta(days=1)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "HISTORICAL NSE IMPORT COMPLETED"
            )
        )

        self.stdout.write(
            f"Trading days imported: {trading_days}"
        )

        self.stdout.write(
            f"Daily price records processed: {total_prices}"
        )
        