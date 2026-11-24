"""Yksikkötestit OpenRouter-komentotulkinnalle ja UtteranceRouter-varatielle."""

import io
import json
import os
import unittest
from unittest.mock import patch
import urllib.error

from puhis.core.actions import CommandType, ParsedCommand
from puhis.core.app_state import AssistantMode
from puhis.core.config_store import AppConfig
from puhis.core.llm_intent import build_intent_messages, parse_llm_intent_response
from puhis.core.utterance_router import UtteranceRouter
from puhis.core.window_registry import WindowRegistry
from puhis.platform.openrouter_client import OpenRouterIntentClient


class _FakeKeyboard:
    def __init__(self) -> None:
        self.events: list[object] = []

    def send_actions(self, actions: object) -> bool:
        self.events.append(actions)
        return True


class _FakeWindowManager:
    def get_foreground_window(self) -> tuple[int, str, str] | None:
        return (100, "notepad.exe", "Nimetön")

    def focus_window(self, hwnd: int) -> bool:
        return True

    def hide_window(self, hwnd: int) -> bool:
        return True


class _FakeLauncher:
    def __init__(self) -> None:
        self.launched: list[str] = []

    def launch(self, alias: str) -> tuple[bool, str]:
        self.launched.append(alias)
        return True, f"Käynnistetty: {alias}"


class _FakeInterpreter:
    def __init__(self, result: ParsedCommand | None) -> None:
        self.result = result
        self.calls: list[str] = []

    def interpret_intent(
        self,
        text: str,
        *,
        known_window_aliases: object,
        known_app_aliases: object,
    ) -> ParsedCommand | None:
        self.calls.append(text)
        return self.result


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class LlmIntentTests(unittest.TestCase):
    def test_build_intent_messages_contains_aliases(self) -> None:
        msgs = build_intent_messages(
            "puhis pistä selain piiloon",
            known_window_aliases=["t1"],
            known_app_aliases=["laskin", "muistio"],
        )
        self.assertEqual(len(msgs), 2)
        self.assertIn("laskin", msgs[0]["content"])
        self.assertIn("t1", msgs[0]["content"])
        self.assertEqual(msgs[1]["content"], "puhis pistä selain piiloon")

    def test_parse_valid_json_with_fences(self) -> None:
        raw = '```json\n{"command": "launch_app", "target": "Laskin"}\n```'
        parsed = parse_llm_intent_response(
            raw,
            "puhis pistä laskin päälle",
            known_window_aliases=["t1"],
            known_app_aliases=["laskin"],
        )
        self.assertEqual(
            parsed,
            ParsedCommand(
                command_type=CommandType.LAUNCH_APP,
                target="laskin",
                raw_text="puhis pistä laskin päälle",
            ),
        )

    def test_rejects_unlisted_app_target(self) -> None:
        raw = '{"command": "launch_app", "target": "cmd.exe"}'
        parsed = parse_llm_intent_response(
            raw,
            "puhis avaa cmd",
            known_window_aliases=[],
            known_app_aliases=["laskin"],
        )
        self.assertIsNone(parsed)

    def test_rejects_unknown_or_wake_or_bad_json(self) -> None:
        self.assertIsNone(
            parse_llm_intent_response(
                '{"command": "unknown", "target": null}',
                "puhis hei",
                known_window_aliases=[],
                known_app_aliases=[],
            )
        )
        self.assertIsNone(
            parse_llm_intent_response(
                '{"command": "wake", "target": null}',
                "puhis",
                known_window_aliases=[],
                known_app_aliases=[],
            )
        )
        self.assertIsNone(
            parse_llm_intent_response(
                "ei ole jsonia",
                "puhis",
                known_window_aliases=[],
                known_app_aliases=[],
            )
        )

    def test_hide_window_allows_null_target(self) -> None:
        parsed = parse_llm_intent_response(
            '{"command": "hide_window", "target": null}',
            "puhis piilota tämä",
            known_window_aliases=[],
            known_app_aliases=[],
        )
        self.assertEqual(
            parsed,
            ParsedCommand(
                command_type=CommandType.HIDE_WINDOW,
                target=None,
                raw_text="puhis piilota tämä",
            ),
        )

    def test_client_skips_network_without_key(self) -> None:
        client = OpenRouterIntentClient(api_key="")
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("urllib.request.urlopen") as mock_open,
        ):
            result = client.interpret_intent(
                "puhis avaa laskin",
                known_window_aliases=[],
                known_app_aliases=["laskin"],
            )
        self.assertIsNone(result)
        mock_open.assert_not_called()

    def test_client_falls_back_to_next_model_on_http_error(self) -> None:
        client = OpenRouterIntentClient(
            api_key="sk-or-test-key",
            primary_model="model-a:free",
            fallback_models=["model-b:free"],
        )
        err_404 = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=404,
            msg="Not Found",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b""),
        )
        ok_resp = _FakeHttpResponse(
            {"choices": [{"message": {"content": '{"command": "mute", "target": null}'}}]}
        )
        with patch("urllib.request.urlopen", side_effect=[err_404, ok_resp]) as mock_open:
            result = client.interpret_intent(
                "puhis ole hiljaa",
                known_window_aliases=[],
                known_app_aliases=[],
            )
        self.assertEqual(mock_open.call_count, 2)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.command_type, CommandType.MUTE)

    def test_router_uses_llm_only_on_unknown_wake_command(self) -> None:
        cfg = AppConfig(llm_enabled=True)
        launcher = _FakeLauncher()
        interpreter = _FakeInterpreter(
            ParsedCommand(
                command_type=CommandType.LAUNCH_APP,
                target="laskin",
                raw_text="puhis pistä laskin päälle",
            )
        )
        router = UtteranceRouter(
            config=cfg,
            window_registry=WindowRegistry(),
            keyboard_injector=_FakeKeyboard(),
            window_manager=_FakeWindowManager(),
            app_launcher=launcher,
            intent_interpreter=interpreter,
        )

        # Tunnettu komento ei kutsu LLM:ää.
        router.handle_utterance("puhis avaa laskin", AssistantMode.IDLE)
        self.assertEqual(interpreter.calls, [])

        # Tavallinen sanelu ei kutsu LLM:ää.
        router.handle_utterance("tämä on tavallista tekstiä", AssistantMode.DICTATING)
        self.assertEqual(interpreter.calls, [])

        # Epäselvä herätesanakomento kutsuu LLM:ää.
        _, res = router.handle_candidates(
            ["puhis voisitko laittaa sen apurin päälle"],
            AssistantMode.IDLE,
        )
        self.assertTrue(res.handled)
        self.assertEqual(len(interpreter.calls), 1)
        self.assertEqual(launcher.launched, ["laskin", "laskin"])

    def test_config_round_trip_preserves_openrouter_fields(self) -> None:
        cfg = AppConfig(
            llm_enabled=True,
            openrouter_api_key="sk-or-abc",
            openrouter_model="google/gemma-4-31b-it:free",
            openrouter_fallback_models=["nvidia/nemotron-3.5-lightning:free"],
        )
        restored = AppConfig.from_dict(cfg.to_dict())
        self.assertTrue(restored.llm_enabled)
        self.assertEqual(restored.openrouter_api_key, "sk-or-abc")
        self.assertEqual(restored.openrouter_model, "google/gemma-4-31b-it:free")
        self.assertEqual(
            restored.openrouter_fallback_models,
            ["nvidia/nemotron-3.5-lightning:free"],
        )


if __name__ == "__main__":
    unittest.main()
