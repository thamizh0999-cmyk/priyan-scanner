from django.db import models


class ScanRun(models.Model):

    SCAN_TYPES = [
        ("MOMENTUM", "Momentum"),
        ("SWING", "Swing Breakout"),
        ("INVESTMENT", "Investment Breakout"),
    ]

    scan_type = models.CharField(
        max_length=20,
        choices=SCAN_TYPES,
    )

    scan_date = models.DateField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-scan_date", "-created_at"]

    def __str__(self):
        return f"{self.scan_type} - {self.scan_date}"


class ScanResult(models.Model):

    scan_run = models.ForeignKey(
        ScanRun,
        on_delete=models.CASCADE,
        related_name="results",
    )

    stock = models.ForeignKey(
        "stocks.Stock",
        on_delete=models.CASCADE,
        related_name="scan_results",
    )

    rank = models.PositiveIntegerField()

    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
    )

    close = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    breakout_percent = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    relative_volume = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    rsi = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    return_20 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    return_120 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    return_200 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["rank"]

    def __str__(self):
        return (
            f"{self.scan_run} - "
            f"{self.stock.symbol} - "
            f"Rank {self.rank}"
        )
