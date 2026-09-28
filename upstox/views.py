import os

from django.http import HttpResponse
from django.shortcuts import redirect
from dotenv import load_dotenv
import requests

from .models import UpstoxToken

load_dotenv()


def upstox_login(request):
    api_key = os.getenv("UPSTOX_API_KEY")
    redirect_uri = os.getenv("UPSTOX_REDIRECT_URI")

    if not api_key or not redirect_uri:
        return HttpResponse(
            "Upstox API credentials are not configured.",
            status=500,
        )

    login_url = (
        "https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code"
        f"&client_id={api_key}"
        f"&redirect_uri={redirect_uri}"
    )

    return redirect(login_url)


def upstox_callback(request):
    code = request.GET.get("code")

    if not code:
        return HttpResponse(
            "Upstox authorization code was not received.",
            status=400,
        )

    api_key = os.getenv("UPSTOX_API_KEY")
    api_secret = os.getenv("UPSTOX_API_SECRET")
    redirect_uri = os.getenv("UPSTOX_REDIRECT_URI")

    token_url = "https://api.upstox.com/v2/login/authorization/token"

    response = requests.post(
        token_url,
        headers={
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "code": code,
            "client_id": api_key,
            "client_secret": api_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )

    if response.status_code != 200:
        return HttpResponse(
            f"Upstox token exchange failed: {response.text}",
            status=500,
        )

    token_data = response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return HttpResponse(
            "Upstox did not return an access token.",
            status=500,
        )

    UpstoxToken.objects.all().delete()

    UpstoxToken.objects.create(
        access_token=access_token,
    )

    return HttpResponse(
        "Upstox connected successfully. Access token saved."
    )
