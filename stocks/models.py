from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=20, unique=True)
    company_name = models.CharField(max_length=200)
    isin = models.CharField(max_length=20, blank=True)
    sector = models.CharField(max_length=100, blank=True)
    industry = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.symbol} - {self.company_name}"