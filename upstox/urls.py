from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.upstox_login, name="upstox_login"),
    path("callback/", views.upstox_callback, name="upstox_callback"),
]
