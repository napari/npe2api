"""Network utilities with retry logic."""

import time
from urllib import error, request


def urlopen_with_retry(url: str, max_retries: int = 3, backoff: float = 1.0):
    """
    Open a URL with exponential backoff retry logic.

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        backoff: Initial backoff time in seconds (doubles with each retry)

    Returns:
        File-like object from urllib.request.urlopen

    Raises:
        URLError: If all retries are exhausted
    """
    for attempt in range(max_retries):
        try:
            return request.urlopen(url)
        except (error.URLError, TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            wait_time = backoff * (2**attempt)
            print(f"⚠ Network error fetching {url}, retrying in {wait_time}s... ({e})")
            time.sleep(wait_time)
