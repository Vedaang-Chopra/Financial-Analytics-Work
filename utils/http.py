"""Shared HTTP utilities."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_USER_AGENT = (
    "Financial-Analytics-Work-Agent/1.0 "
    "(respectful research crawler; https://github.com/Vedaang-Chopra/Financial-Analytics-Work)"
)


class HttpSettings:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30,
        retries: int = 2,
        backoff_factor: float = 1,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.user_agent = user_agent


def build_session(settings: HttpSettings | None = None) -> requests.Session:
    settings = settings or HttpSettings()
    retry = Retry(
        total=settings.retries,
        connect=settings.retries,
        read=settings.retries,
        backoff_factor=settings.backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    session = requests.Session()
    session.headers.update({"User-Agent": settings.user_agent})
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
