"""Pluggable VLM client for local LLM-guided page analysis."""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageAnalysisPayload:
    objective: str
    current_url: str
    page_title: str
    visible_text_excerpt: str
    links: list[dict[str, str]] = field(default_factory=list)
    buttons: list[str] = field(default_factory=list)
    forms: list[dict[str, str]] = field(default_factory=list)
    screenshot_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "current_url": self.current_url,
            "page_title": self.page_title,
            "visible_text_excerpt": self.visible_text_excerpt[:500] if self.visible_text_excerpt else "",
            "links": self.links[:20],
            "buttons": self.buttons,
            "forms": self.forms,
            "screenshot_path": self.screenshot_path,
        }


@dataclass(frozen=True)
class PageAnalysisDecision:
    page_relevance: str
    dataset_hints: list[str]
    recommended_action: str
    target_text: str | None
    form_values: dict[str, str]
    avoid_targets: list[str]
    reason: str
    confidence: float


class VLMClient(ABC):
    @abstractmethod
    def analyze_page(self, payload: PageAnalysisPayload) -> PageAnalysisDecision | None:
        raise NotImplementedError


class NullVLMClient(VLMClient):
    def analyze_page(self, payload: PageAnalysisPayload) -> PageAnalysisDecision | None:
        return None


class OllamaVLMClient(VLMClient):
    def __init__(self, endpoint: str = "http://localhost:11434", model: str | None = None, timeout: float = 60.0):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout

    def analyze_page(self, payload: PageAnalysisPayload) -> PageAnalysisDecision | None:
        model = self.model or "llava"
        prompt = self._build_prompt(payload)
        try:
            response = requests.post(
                f"{self.endpoint}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "")
            return self._parse_response(raw)
        except requests.RequestException as exc:
            LOGGER.warning("VLM request failed: %s", exc)
            return None

    def _build_prompt(self, payload: PageAnalysisPayload) -> str:
        return (
            "You are a financial data extraction assistant. Analyze this page:\n"
            f"URL: {payload.current_url}\n"
            f"Title: {payload.page_title}\n"
            f"Objective: {payload.objective}\n"
            f"Links: {json.dumps(payload.links[:10])}\n"
            f"Text: {payload.visible_text_excerpt[:300]}\n\n"
            "Return JSON with: page_relevance (high/medium/low/irrelevant), "
            "dataset_hints (array), recommended_action (click/select/download/skip), "
            "target_text (string or null), avoid_targets (array), reason (string), confidence (0-1)"
        )

    def _parse_response(self, raw: str) -> PageAnalysisDecision | None:
        try:
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(raw[json_start:json_end])
                return PageAnalysisDecision(
                    page_relevance=data.get("page_relevance", "unknown"),
                    dataset_hints=data.get("dataset_hints", []),
                    recommended_action=data.get("recommended_action", "skip"),
                    target_text=data.get("target_text"),
                    form_values=data.get("form_values", {}),
                    avoid_targets=data.get("avoid_targets", []),
                    reason=data.get("reason", ""),
                    confidence=float(data.get("confidence", 0.5)),
                )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            LOGGER.warning("VLM response parse failed: %s", exc)
        return None