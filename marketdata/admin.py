from django.contrib import admin
from .models import DailyPrice


@admin.register(DailyPrice)
class DailyPriceAdmin(admin.ModelAdmin):
    list_display = (
        "stock",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "traded_value",
    )

    list_filter = (
        "date",
        "stock",
    )

    search_fields = (
        "stock__symbol",
        "stock__company_name",
    )

    ordering = ("-date",)