from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class HTTPConfig:
    base_url: str = "https://opendataapi.dmi.dk"
    timeout: float = 30.0
    headers: dict[str, str] | None = None


class DMIHTTPClient:
    """Small, shared transport client for the DMI Frie Data APIs."""

    def __init__(self, config: HTTPConfig | None = None) -> None:
        self.config = config or HTTPConfig()
        self._client = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers=self.config.headers or {},
        )

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def get_bytes(self, path: str) -> bytes:
        response = self._client.get(path)
        response.raise_for_status()
        return response.content

    def download(self, path: str, *, destination: str) -> str:
        response = self._client.get(path)
        response.raise_for_status()
        with open(destination, "wb") as handle:
            handle.write(response.content)
        return destination

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DMIHTTPClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
