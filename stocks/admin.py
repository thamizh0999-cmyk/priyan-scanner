from django.contrib import admin
from .models import Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = (
        "symbol",
        "company_name",
        "sector",
        "industry",
        "is_active",
    )

    list_filter = (
        "is_active",
        "sector",
    )

    search_fields = (
        "symbol",
        "company_name",
        "isin",
    )

    ordering = ("symbol",)