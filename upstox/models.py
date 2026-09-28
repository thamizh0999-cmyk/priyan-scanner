from django.db import models
from stocks.models import Stock


class UpstoxToken(models.Model):
    access_token = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Upstox Access Token"


class LivePrice(models.Model):
    stock = models.OneToOneField(
        Stock,
        on_delete=models.CASCADE,
        related_name="live_price",
    )
    ltp = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    previous_close = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    day_high = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    day_low = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    volume = models.BigIntegerField(
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.stock.symbol} - {self.ltp}"
