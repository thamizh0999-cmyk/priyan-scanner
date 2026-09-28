import io
import re
import zipfile
from datetime import datetime, timedelta

import pandas as pd
import requests

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from stocks.models import Stock
from marketdata.models import DailyPrice


class Command(BaseCommand):
    help = "Import latest NSE equity UDiFF bhavcopy"

    PRODUCT_PATTERN = re.compile(
        r"ETF|AMC -|AMC-|AMC |MUTUAL FUND|NIFTY|SENSEX|"
        r"LIQUID FUND|GOLD ETF|SILVER ETF|BOND ETF|GILT|INDEX FUND",
        re.IGNORECASE,
    )

    KEEP_SYMBOLS = {
        "ABSLAMC",
        "CRAMC",
        "HDFCAMC",
        "ICICIAMC",
        "PNBGILTS",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Specific trade date in YYYYMMDD format",
        )
        parser.add_argument(
            "--lookback",
            type=int,
            default=10,
            help="Number of previous calendar days to search",
        )

    def handle(self, *args, **options):

        requested_date = options.get("date")
        lookback = options.get("lookback", 10)

        if requested_date:
            try:
                current_date = datetime.strptime(
                    requested_date,
                    "%Y%m%d",
                ).date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(
                        "Invalid date. Use YYYYMMDD."
                    )
                )
                return

            search_dates = [current_date]

        else:
            current_date = timezone.localdate()

            search_dates = [
                current_date - timedelta(days=i)
                for i in range(lookback + 1)
            ]

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

        response = None
        trade_date = None
        url = None

        for candidate_date in search_dates:

            date_text = candidate_date.strftime("%Y%m%d")

            candidate_url = (
                "https://nsearchives.nseindia.com/"
                "content/cm/"
                f"BhavCopy_NSE_CM_0_0_0_{date_text}_F_0000.csv.zip"
            )

            self.stdout.write(
                f"Checking NSE bhavcopy: {date_text}"
            )

            try:
                candidate_response = requests.get(
                    candidate_url,
                    headers=headers,
                    timeout=30,
                )

                if candidate_response.status_code == 200:
                    response = candidate_response
                    trade_date = candidate_date
                    url = candidate_url
                    break

            except requests.RequestException:
                continue

        if response is None:
            self.stdout.write(
                self.style.ERROR(
                    "No NSE bhavcopy found within the requested "
                    f"{lookback}-day lookback period."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"NSE bhavcopy found for "
                f"{trade_date.strftime('%Y-%m-%d')}"
            )
        )

        try:
            with zipfile.ZipFile(
                io.BytesIO(response.content)
            ) as z:

                csv_files = [
                    name
                    for name in z.namelist()
                    if name.lower().endswith(".csv")
                ]

                if not csv_files:
                    self.stdout.write(
                        self.style.ERROR(
                            "No CSV file found inside ZIP."
                        )
                    )
                    return

                csv_name = csv_files[0]

                with z.open(csv_name) as csv_file:
                    df = pd.read_csv(csv_file)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Could not read NSE file: {e}"
                )
            )
            return

        self.stdout.write(
            f"Total NSE records: {len(df)}"
        )

        df = df[
            (df["FinInstrmTp"] == "STK")
            & (df["SctySrs"] == "EQ")
        ].copy()

        self.stdout.write(
            f"Equity records after filtering: {len(df)}"
        )

        if df.empty:
            self.stdout.write(
                self.style.WARNING(
                    "No equity records found."
                )
            )
            return

        imported_stocks = 0
        skipped_products = 0
        imported_prices = 0

        with transaction.atomic():

            for _, row in df.iterrows():

                symbol = str(
                    row["TckrSymb"]
                ).strip()

                isin = str(
                    row["ISIN"]
                ).strip()

                company_name = str(
                    row["FinInstrmNm"]
                ).strip()

                if not symbol:
                    continue

                existing_stock = (
                    Stock.objects
                    .filter(symbol=symbol)
                    .first()
                )

                if existing_stock:

                    existing_stock.company_name = company_name
                    existing_stock.isin = isin

                    existing_stock.save(
                        update_fields=[
                            "company_name",
                            "isin",
                            "updated_at",
                        ]
                    )

                    stock = existing_stock

                else:

                    is_product = (
                        symbol not in self.KEEP_SYMBOLS
                        and self.PRODUCT_PATTERN.search(
                            company_name
                        ) is not None
                    )

                    if is_product:
                        skipped_products += 1
                        continue

                    stock = Stock.objects.create(
                        symbol=symbol,
                        company_name=company_name,
                        isin=isin,
                        is_active=True,
                    )

                    imported_stocks += 1

                DailyPrice.objects.update_or_create(
                    stock=stock,
                    date=trade_date,
                    defaults={
                        "open": row["OpnPric"],
                        "high": row["HghPric"],
                        "low": row["LwPric"],
                        "close": row["ClsPric"],
                        "volume": int(
                            row["TtlTradgVol"]
                        ),
                        "traded_value": row["TtlTrfVal"],
                    },
                )

                imported_prices += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "NSE EOD IMPORT COMPLETED"
            )
        )

        self.stdout.write(
            f"Trade date: {trade_date}"
        )

        self.stdout.write(
            f"Source: {url}"
        )

        self.stdout.write(
            f"New genuine stocks created: {imported_stocks}"
        )

        self.stdout.write(
            f"New product instruments skipped: {skipped_products}"
        )

        self.stdout.write(
            f"Daily prices processed: {imported_prices}"
        )
