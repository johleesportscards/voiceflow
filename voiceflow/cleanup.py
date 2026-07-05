"""Transcript cleanup backends: Claude Haiku, Ollama, or none.

`auto` mode tries claude -> ollama -> raw; any error or timeout falls through,
so dictation never blocks on cleanup.
"""
from __future__ import annotations

import logging
import os
import re

import httpx

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You clean up dictated speech transcripts. Remove filler words (um, uh, "
    "like, you know), fix punctuation, casing and obvious mis-hearings, and "
    "break into sentences/paragraphs where natural. Keep the speaker's words, "
    "meaning, tone and language — do not add, summarize, translate or answer "
    "questions in the text. Return only the cleaned text."
)

TIMEOUT_S = 5.0


def _strip_thinking(text: str) -> str:
    """Drop <think>…</think> blocks that reasoning models prepend."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


class ClaudeCleanup:
    name = "claude"

    def __init__(self) -> None:
        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(timeout=TIMEOUT_S)

    def clean(self, text: str) -> str:
        resp = self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        out = "".join(b.text for b in resp.content if b.type == "text").strip()
        return out or text


class OllamaCleanup:
    name = "ollama"

    def __init__(self, url: str, model: str) -> None:
        self.url = url.rstrip("/")
        self.model = model
        # fail fast at startup if Ollama isn't reachable
        httpx.get(f"{self.url}/api/version", timeout=2.0).raise_for_status()

    def clean(self, text: str) -> str:
        resp = httpx.post(
            f"{self.url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "stream": False,
                "think": False,
            },
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        out = _strip_thinking(resp.json()["message"]["content"])
        return out or text


class LMStudioCleanup:
    name = "lmstudio"

    def __init__(self, url: str, model: str) -> None:
        self.url = url.rstrip("/")
        # fail fast at startup if LM Studio's server isn't running
        resp = httpx.get(f"{self.url}/v1/models", timeout=2.0)
        resp.raise_for_status()
        if model:
            self.model = model
        else:
            chat_models = [
                m["id"] for m in resp.json()["data"] if "embed" not in m["id"].lower()
            ]
            if not chat_models:
                raise RuntimeError("no chat models available in LM Studio")
            self.model = chat_models[0]
        self._warm_up()

    def _warm_up(self) -> None:
        """LM Studio JIT-loads models on first request, which can take far
        longer than the per-dictation budget — trigger the load at startup."""
        httpx.post(
            f"{self.url}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            },
            timeout=120.0,
        ).raise_for_status()

    def clean(self, text: str) -> str:
        resp = httpx.post(
            f"{self.url}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "temperature": 0.2,
            },
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        out = _strip_thinking(resp.json()["choices"][0]["message"]["content"])
        return out or text


class RawCleanup:
    name = "raw"

    def clean(self, text: str) -> str:
        return text


class FastCleanup:
    """Instant string-level cleanup: filler-word removal + custom dictionary.

    Runs in microseconds, so dictation latency is just the transcription
    itself — no LLM in the hot path unless the user opts in.
    """

    name = "fast"

    def __init__(self, filler_words: list[str], dictionary: dict[str, str]) -> None:
        fillers = [re.escape(w.strip()) for w in filler_words if w and w.strip()]
        self._filler_re = (
            re.compile(r"\b(?:" + "|".join(fillers) + r")\b[,.]?\s*", re.IGNORECASE)
            if fillers
            else None
        )
        self._dictionary = [
            (re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE), v)
            for k, v in (dictionary or {}).items()
        ]

    def clean(self, text: str) -> str:
        cleaned = text
        if self._filler_re:
            cleaned = self._filler_re.sub("", cleaned)
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        for pattern, replacement in self._dictionary:
            cleaned = pattern.sub(replacement, cleaned)
        if not cleaned:
            return text
        # a removed leading filler shouldn't leave the sentence lowercase
        if text[:1].isupper() and cleaned[:1].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned


def build_chain(mode: str, cfg) -> list:
    """Return cleanup backends in fallback order for the configured mode."""
    if mode == "fast":
        log.info("Cleanup chain: fast (regex, no LLM)")
        return [FastCleanup(cfg.filler_words, cfg.dictionary)]
    chain: list = []
    want = ("claude", "ollama", "lmstudio") if mode == "auto" else (mode,)
    if "claude" in want:
        try:
            chain.append(ClaudeCleanup())
        except Exception as e:
            log.warning("Claude cleanup unavailable: %s", e)
    if "ollama" in want:
        try:
            chain.append(OllamaCleanup(cfg.ollama_url, cfg.ollama_model))
        except Exception as e:
            log.warning("Ollama cleanup unavailable: %s", e)
    if "lmstudio" in want:
        try:
            chain.append(LMStudioCleanup(cfg.lmstudio_url, cfg.lmstudio_model))
        except Exception as e:
            log.warning("LM Studio cleanup unavailable: %s", e)
    chain.append(RawCleanup())
    log.info("Cleanup chain: %s", " -> ".join(b.name for b in chain))
    return chain


def clean(chain: list, text: str) -> str:
    for backend in chain:
        try:
            return backend.clean(text)
        except Exception as e:
            log.warning("Cleanup via %s failed (%s), falling back", backend.name, e)
    return text
