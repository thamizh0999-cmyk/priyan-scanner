from django.urls import path
from dashboard.views import home, stock_detail, live_price_api, price_history_api

urlpatterns = [
    path("", home, name="dashboard_home"),
    path("stock/<str:symbol>/", stock_detail, name="stock_detail"),
    path("api/live/<str:symbol>/", live_price_api, name="live_price_api"),
    path("api/history/<str:symbol>/", price_history_api, name="price_history_api"),
]
