from django.db import models
from stocks.models import Stock


class DailyPrice(models.Model):
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name="daily_prices"
    )

    date = models.DateField()

    open = models.DecimalField(max_digits=12, decimal_places=2)
    high = models.DecimalField(max_digits=12, decimal_places=2)
    low = models.DecimalField(max_digits=12, decimal_places=2)
    close = models.DecimalField(max_digits=12, decimal_places=2)

    volume = models.BigIntegerField(default=0)
    traded_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["stock", "date"],
                name="unique_stock_date"
            )
        ]

    def __str__(self):
        return f"{self.stock.symbol} - {self.date}"