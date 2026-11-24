"""OpenRouter REST API -asiakas epäselvien puhekomentojen tulkintaan."""

from collections.abc import Collection, Sequence
import json
import logging
import os
import urllib.error
import urllib.request

from puhis.core.actions import ParsedCommand
from puhis.core.config_store import DEFAULT_OPENROUTER_MODELS
from puhis.core.llm_intent import build_intent_messages, parse_llm_intent_response

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 4.0


class OpenRouterIntentClient:
    """Kutsuu OpenRouterin Chat Completions -rajapintaa varamalliketjulla."""

    def __init__(
        self,
        *,
        api_key: str = "",
        primary_model: str = DEFAULT_OPENROUTER_MODELS[0],
        fallback_models: Sequence[str] = DEFAULT_OPENROUTER_MODELS[1:],
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        endpoint_url: str = OPENROUTER_CHAT_URL,
    ) -> None:
        self._api_key = api_key.strip()
        self._primary_model = primary_model.strip() or DEFAULT_OPENROUTER_MODELS[0]
        self._fallback_models = [m.strip() for m in fallback_models if m.strip()]
        self._timeout_seconds = max(0.5, float(timeout_seconds))
        self._endpoint_url = endpoint_url

    def update_settings(
        self,
        *,
        api_key: str,
        primary_model: str,
        fallback_models: Sequence[str],
    ) -> None:
        """Päivittää OpenRouter-asetukset lennossa."""
        self._api_key = api_key.strip()
        self._primary_model = primary_model.strip() or DEFAULT_OPENROUTER_MODELS[0]
        self._fallback_models = [m.strip() for m in fallback_models if m.strip()]

    def interpret_intent(
        self,
        text: str,
        *,
        known_window_aliases: Collection[str],
        known_app_aliases: Collection[str],
    ) -> ParsedCommand | None:
        """Tulkkaa puhekomennon OpenRouterin avulla; palauttaa `None` virheessä."""
        api_key = self._resolve_api_key()
        if not api_key or not text.strip():
            return None

        messages = build_intent_messages(
            text,
            known_window_aliases=known_window_aliases,
            known_app_aliases=known_app_aliases,
        )
        for model in self._model_chain():
            raw_content = self._request_completion(api_key=api_key, model=model, messages=messages)
            if raw_content is None:
                continue
            parsed = parse_llm_intent_response(
                raw_content,
                text,
                known_window_aliases=known_window_aliases,
                known_app_aliases=known_app_aliases,
            )
            if parsed is not None:
                return parsed
            return None
        return None

    def _resolve_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return os.environ.get("OPENROUTER_API_KEY", "").strip()

    def _model_chain(self) -> list[str]:
        seen: set[str] = set()
        chain: list[str] = []
        for model in (self._primary_model, *self._fallback_models):
            if model and model not in seen:
                seen.add(model)
                chain.append(model)
        return chain

    def _request_completion(
        self,
        *,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
    ) -> str | None:
        body = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 80,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/puhis-app",
                "X-Title": "Puhis",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            logger.warning("OpenRouter HTTP %s mallilla %s", exc.code, model)
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("OpenRouter-kutsu epäonnistui mallilla %s: %s", model, exc)
            return None

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        return content if isinstance(content, str) else None
