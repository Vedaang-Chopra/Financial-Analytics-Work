from __future__ import annotations

from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_USER_AGENT = (
    "Financial-Analytics-Work-AMFI-Ingestion/1.0 "
    "(respectful research crawler; https://github.com/Vedaang-Chopra/Financial-Analytics-Work)"
)


@dataclass(frozen=True)
class HttpSettings:
    timeout_seconds: float = 30
    retries: int = 2
    backoff_factor: float = 1
    user_agent: str = DEFAULT_USER_AGENT


def build_session(settings: HttpSettings) -> requests.Session:
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
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session
