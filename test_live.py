import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "priyan_scanner.settings")
django.setup()

import upstox_client
from upstox.models import UpstoxToken


token_obj = UpstoxToken.objects.first()

if not token_obj:
    print("ERROR: No Upstox access token found.")
    raise SystemExit(1)

access_token = token_obj.access_token

configuration = upstox_client.Configuration()
configuration.access_token = access_token

streamer = upstox_client.MarketDataStreamerV3(
    upstox_client.ApiClient(configuration),
    ["NSE_EQ|INE0LCL01028"],
    "ltpc",
)


def on_open():
    print("CONNECTED TO UPSTOX LIVE FEED")
    print("Waiting for AVALON live price...")

    streamer.subscribe(
        ["NSE_EQ|INE0LCL01028"],
        "ltpc",
    )


def on_message(message):
    try:
        feeds = message.get("feeds", {})
        avalon = feeds.get("NSE_EQ|INE0LCL01028")

        if avalon:
            ltpc = avalon.get("ltpc", {})

            print(
                f"AVALON LTP: {ltpc.get('ltp')} | "
                f"Previous Close: {ltpc.get('cp')}"
            )

    except Exception as e:
        print("MESSAGE ERROR:", e)


def on_error(error):
    print("WEBSOCKET ERROR:", error)


def on_close():
    print("WEBSOCKET CLOSED")


streamer.on("open", on_open)
streamer.on("message", on_message)
streamer.on("error", on_error)
streamer.on("close", on_close)

print("Starting Priyan Scanner live feed...")
streamer.connect()
