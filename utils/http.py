"""Shared HTTP utilities."""
from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LOGGER = logging.getLogger(__name__)
_LAST_REQUEST_AT: dict[str, float] = {}

DEFAULT_USER_AGENT = (
    "Financial-Analytics-Work-Agent/1.0 "
    "(respectful research crawler; https://github.com/Vedaang-Chopra/Financial-Analytics-Work)"
)


def _domain_from_url(url: str) -> str:
    """Return a normalized domain key for rate limiting."""
    return urlparse(url).netloc.lower().removeprefix("www.")


def wait_for_domain(url: str, min_interval_seconds: float = 2.0) -> None:
    """Sleep as needed so consecutive requests to a domain stay spaced out."""
    domain = _domain_from_url(url)
    last_request_at = _LAST_REQUEST_AT.get(domain)
    if last_request_at is not None:
        elapsed = time.monotonic() - last_request_at
        if elapsed < min_interval_seconds:
            sleep_for = min_interval_seconds - elapsed
            LOGGER.info("Sleeping %.2fs before GET %s", sleep_for, url)
            time.sleep(sleep_for)
    _LAST_REQUEST_AT[domain] = time.monotonic()


def get_with_retry(
    session: requests.Session,
    url: str,
    *,
    timeout: float,
    stream: bool = False,
    allow_redirects: bool = True,
) -> requests.Response:
    """Issue a GET request with logging, domain throttling, and one 429 retry."""
    wait_for_domain(url)
    LOGGER.info("GET %s", url)
    response = session.get(url, timeout=timeout, stream=stream, allow_redirects=allow_redirects)
    if response.status_code != 429:
        return response

    LOGGER.warning("GET %s returned 429; sleeping 60s before one retry", url)
    time.sleep(60)
    wait_for_domain(url)
    LOGGER.info("GET %s (retry)", url)
    return session.get(url, timeout=timeout, stream=stream, allow_redirects=allow_redirects)


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
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    session = requests.Session()
    session.headers.update({"User-Agent": settings.user_agent})
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
