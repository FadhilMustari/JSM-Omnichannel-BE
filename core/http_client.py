from typing import Optional

import httpx

_async_client: Optional[httpx.AsyncClient] = None

def init_async_client() -> None:
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0, read=15.0, write=15.0),
        )

def get_async_client() -> httpx.AsyncClient:
    if _async_client is None:
        init_async_client()
    return _async_client

async def close_async_client() -> None:
    global _async_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None
