from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
import pandas as pd
from ta.momentum import RSIIndicator

from marketdata.models import DailyPrice
from scanners.models import ScanRun
from stocks.models import Stock
from upstox.models import LivePrice


@login_required
def home(request):
    momentum_run = (
        ScanRun.objects
        .filter(scan_type="MOMENTUM")
        .prefetch_related("results__stock")
        .first()
    )
    swing_run = (
        ScanRun.objects
        .filter(scan_type="SWING")
        .prefetch_related("results__stock")
        .first()
    )
    investment_run = (
        ScanRun.objects
        .filter(scan_type="INVESTMENT")
        .prefetch_related("results__stock")
        .first()
    )

    search_query = request.GET.get("q", "").strip()
    search_results = Stock.objects.none()

    if search_query:
        search_results = (
            Stock.objects
            .filter(is_active=True)
            .filter(
                Q(symbol__icontains=search_query)
                | Q(company_name__icontains=search_query)
            )
            .order_by("symbol")[:20]
        )

    context = {
        "momentum_run": momentum_run,
        "swing_run": swing_run,
        "investment_run": investment_run,
        "search_query": search_query,
        "search_results": search_results,
    }

    return render(request, "dashboard/home.html", context)


@login_required
def stock_detail(request, symbol):
    stock = get_object_or_404(
        Stock,
        symbol=symbol.upper(),
    )

    prices = (
        DailyPrice.objects
        .filter(stock=stock)
        .order_by("-date")[:250]
    )

    scan_results = (
        stock.scan_results
        .select_related("scan_run")
        .order_by(
            "-scan_run__scan_date",
            "rank",
        )
    )[:30]

    live_price = (
        LivePrice.objects
        .filter(stock=stock)
        .first()
    )

    live_change = None
    live_change_percent = None

    if (
        live_price
        and live_price.ltp is not None
        and live_price.previous_close
    ):
        live_change = live_price.ltp - live_price.previous_close
        live_change_percent = (
            live_change / live_price.previous_close
        ) * 100

    context = {
        "stock": stock,
        "prices": prices,
        "scan_results": scan_results,
        "live_price": live_price,
        "live_change": live_change,
        "live_change_percent": live_change_percent,
    }

    return render(request, "dashboard/stock_detail.html", context)


@login_required
def live_price_api(request, symbol):
    stock = get_object_or_404(
        Stock,
        symbol=symbol.upper(),
    )

    live_price = (
        LivePrice.objects
        .filter(stock=stock)
        .first()
    )

    if not live_price:
        return JsonResponse(
            {
                "ltp": None,
                "previous_close": None,
                "day_high": None,
                "day_low": None,
                "volume": None,
            }
        )

    change = None
    change_percent = None

    if (
        live_price.ltp is not None
        and live_price.previous_close
    ):
        change = live_price.ltp - live_price.previous_close
        change_percent = (
            change / live_price.previous_close
        ) * 100

    return JsonResponse(
        {
            "ltp": float(live_price.ltp) if live_price.ltp is not None else None,
            "previous_close": float(live_price.previous_close) if live_price.previous_close is not None else None,
            "day_high": float(live_price.day_high) if live_price.day_high is not None else None,
            "day_low": float(live_price.day_low) if live_price.day_low is not None else None,
            "volume": live_price.volume,
            "change": float(change) if change is not None else None,
            "change_percent": float(change_percent) if change_percent is not None else None,
        }
    )


@login_required
def price_history_api(request, symbol):
    stock = get_object_or_404(
        Stock,
        symbol=symbol.upper(),
    )

    prices = list(
        DailyPrice.objects
        .filter(stock=stock)
        .order_by("date")
    )

    closes = pd.Series(
        [float(price.close) for price in prices],
        dtype="float64",
    )

    ema20_values = (
        closes
        .ewm(span=20, adjust=False)
        .mean()
        .tolist()
    )

    ema50_values = (
        closes
        .ewm(span=50, adjust=False)
        .mean()
        .tolist()
    )

    ema200_values = (
        closes
        .ewm(span=200, adjust=False)
        .mean()
        .tolist()
    )

    rsi_values = (
        RSIIndicator(
            close=closes,
            window=14,
            fillna=False,
        )
        .rsi()
        .tolist()
    )

    data = []

    for index, price in enumerate(prices):
        rsi14 = rsi_values[index]

        data.append(
            {
                "date": price.date.isoformat(),
                "open": float(price.open),
                "high": float(price.high),
                "low": float(price.low),
                "close": float(price.close),
                "volume": price.volume,
                "ema20": float(ema20_values[index]),
                "ema50": float(ema50_values[index]),
                "ema200": float(ema200_values[index]),
                "rsi14": (
                    float(rsi14)
                    if pd.notna(rsi14)
                    else None
                ),
            }
        )

    return JsonResponse({"data": data})
