from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict

import requests


@dataclass
class MCPAdapterResult:
    jd_text: str
    source: str


class MCPEnhanceAdapter:
    """
    Pluggable adapter for JD extraction.

    - If MCP_ENHANCE_ENDPOINT is configured, call external MCP service.
    - Otherwise, fallback to direct page fetch as a local stub.
    """

    def __init__(self) -> None:
        self.endpoint = (os.getenv("MCP_ENHANCE_ENDPOINT") or "").strip()

    def fetch_jd_text(self, job_url: str, timeout_sec: int = 10) -> MCPAdapterResult:
        if not job_url:
            return MCPAdapterResult(jd_text="", source="none")

        if self.endpoint:
            jd = self._fetch_via_external_mcp(job_url=job_url, timeout_sec=timeout_sec)
            if jd:
                return MCPAdapterResult(jd_text=jd, source="external_mcp")

        jd = self._fetch_via_http(job_url=job_url, timeout_sec=timeout_sec)
        return MCPAdapterResult(jd_text=jd, source="http_stub")

    def _fetch_via_external_mcp(self, job_url: str, timeout_sec: int) -> str:
        try:
            response = requests.post(
                self.endpoint,
                json={"job_url": job_url, "timeout": timeout_sec},
                timeout=timeout_sec,
            )
            response.raise_for_status()
            payload: Dict[str, Any] = response.json()
            return str(payload.get("jd_text", ""))[:6000]
        except Exception:
            return ""

    @staticmethod
    def _fetch_via_http(job_url: str, timeout_sec: int) -> str:
        try:
            response = requests.get(job_url, timeout=timeout_sec)
            response.raise_for_status()
            text = re.sub(r"<[^>]+>", " ", response.text)
            text = re.sub(r"\s+", " ", text)
            return text[:6000]
        except Exception:
            return ""
