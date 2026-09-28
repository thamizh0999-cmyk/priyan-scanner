from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Connect to Upstox live market feed for all active NSE equities"

    def handle(self, *args, **options):
        import os
        import django

        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE",
            "priyan_scanner.settings",
        )
        django.setup()

        import upstox_client
        from upstox.models import UpstoxToken, LivePrice
        from stocks.models import Stock

        token_obj = UpstoxToken.objects.first()

        if not token_obj:
            self.stdout.write(
                self.style.ERROR("No Upstox access token found.")
            )
            return

        stocks = list(
            Stock.objects
            .filter(is_active=True)
            .exclude(isin="")
            .exclude(isin__isnull=True)
            .order_by("symbol")
        )

        if not stocks:
            self.stdout.write(
                self.style.ERROR("No active stocks with ISIN found.")
            )
            return

        instrument_map = {
            f"NSE_EQ|{stock.isin}": stock
            for stock in stocks
        }

        instrument_keys = list(instrument_map.keys())

        self.stdout.write(
            f"Preparing live feed for {len(instrument_keys)} stocks..."
        )

        configuration = upstox_client.Configuration()
        configuration.access_token = token_obj.access_token

        streamer = upstox_client.MarketDataStreamerV3(
            upstox_client.ApiClient(configuration),
            instrument_keys,
            "ltpc",
        )

        def on_open():
            self.stdout.write(
                self.style.SUCCESS(
                    f"CONNECTED TO UPSTOX LIVE FEED | "
                    f"{len(instrument_keys)} instruments"
                )
            )

            streamer.subscribe(
                instrument_keys,
                "ltpc",
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"SUBSCRIBED TO {len(instrument_keys)} NSE EQUITIES (LTPC)"
                )
            )

        def on_message(message):
            try:
                feeds = message.get("feeds", {})

                for instrument_key, feed in feeds.items():

                    stock = instrument_map.get(instrument_key)

                    if not stock:
                        continue

                    ltpc = feed.get("ltpc", {})

                    full_feed = feed.get("fullFeed", {})
                    market_ff = full_feed.get("marketFF", {})
                    ltpc_full = market_ff.get("ltpc", {})

                    ltp = (
                        ltpc.get("ltp")
                        or ltpc_full.get("ltp")
                    )

                    previous_close = (
                        ltpc.get("cp")
                        or ltpc_full.get("cp")
                    )

                    market_ohlc = market_ff.get(
                        "marketOHLC",
                        {},
                    )

                    ohlc_list = market_ohlc.get(
                        "ohlc",
                        [],
                    )

                    day_high = None
                    day_low = None
                    volume = None

                    for item in ohlc_list:
                        if item.get("interval") == "1d":
                            day_high = item.get("high")
                            day_low = item.get("low")
                            volume = item.get("vol")
                            break

                    LivePrice.objects.update_or_create(
                        stock=stock,
                        defaults={
                            "ltp": ltp,
                            "previous_close": previous_close,
                            "day_high": day_high,
                            "day_low": day_low,
                            "volume": volume,
                        },
                    )

                    if ltp is not None:
                        self.stdout.write(
                            f"{stock.symbol} | "
                            f"LTP: {ltp} | "
                            f"Prev: {previous_close} | "
                            f"High: {day_high} | "
                            f"Low: {day_low} | "
                            f"Volume: {volume}"
                        )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"MESSAGE ERROR: {e}"
                    )
                )

        def on_error(error):
            self.stdout.write(
                self.style.ERROR(
                    f"WEBSOCKET ERROR: {error}"
                )
            )

        def on_close(*args):
            self.stdout.write(
                f"WEBSOCKET CLOSED | {args}"
            )

        streamer.on("open", on_open)
        streamer.on("message", on_message)
        streamer.on("error", on_error)
        streamer.on("close", on_close)

        self.stdout.write(
            "Starting Priyan Scanner live market service..."
        )

        streamer.connect()

