"""Vaiheen 2 savutestiskripti: komentotulkki, tekstinmuunnos ja Win32-toiminnot.

Käyttö:
    # Turvallinen kuiva-ajo (ei lähetä näppäimiä eikä käynnistä ohjelmia):
    .\\.venv\\Scripts\\python.exe scripts\\test_win32_actions.py --dry-run

    # Oikea Windows-työpöytätesti (avaa Muistion ja Laskimen, kirjoittaa ääkkösiä,
    # tallentaa t1/t2, vaihtaa fokusta ja minimoi t2):
    .\\.venv\\Scripts\\python.exe scripts\\test_win32_actions.py --live
"""

import argparse
from collections.abc import Sequence
import sys
import time

from puhis.core.actions import InputAction, WindowInfo
from puhis.core.app_state import AssistantMode
from puhis.core.config_store import AppConfig
from puhis.core.utterance_router import UtteranceRouter
from puhis.core.window_registry import WindowRegistry
from puhis.platform.app_launcher import AppLauncher
from puhis.platform.keyboard_injector import KeyboardInjector
from puhis.platform.window_manager import WindowManager


class _DryRunKeyboard:
    def send_actions(self, actions: Sequence[InputAction]) -> bool:
        print(f"  [DryRun SendInput] {list(actions)}")
        return True


class _DryRunWindowManager:
    def __init__(self) -> None:
        self._current = WindowInfo(hwnd=101, title="Nimetön – Muistio", process_name="notepad.exe")

    def set_simulated_active(self, info: WindowInfo) -> None:
        self._current = info

    def get_active_window(self) -> WindowInfo | None:
        return self._current

    def is_window_valid(self, hwnd: int) -> bool:
        return hwnd > 0

    def focus_window(self, hwnd: int) -> bool:
        print(f"  [DryRun SetForegroundWindow] hwnd={hwnd}")
        return True

    def minimize_window(self, hwnd: int) -> bool:
        print(f"  [DryRun ShowWindow SW_MINIMIZE] hwnd={hwnd}")
        return True


def run_dry_run() -> int:
    print("Ajetaan Vaiheen 2 kuiva-ajo (--dry-run)...")
    config = AppConfig()
    registry = WindowRegistry()
    windows = _DryRunWindowManager()
    launcher = AppLauncher(
        config.app_aliases,
        popen_fn=lambda cmd: print(f"  [DryRun Popen] {list(cmd)}"),
    )
    router = UtteranceRouter(
        config=config,
        window_registry=registry,
        keyboard_injector=_DryRunKeyboard(),
        window_manager=windows,
        app_launcher=launcher,
    )

    mode = AssistantMode.IDLE
    steps = [
        "puhis avaa muistio",
        "puhis save t1",
        "puhis sanele",
        "Hei pilkku ääkköset toimivat kaksoispiste ä ö å huutomerkki enter tab",
        "puhis avaa laskin",
    ]
    for phrase in steps:
        print(f"> {phrase!r} (tila={mode.value})")
        res = router.handle_utterance(phrase, mode)
        print(f"  -> {res}")
        if not res.success:
            return 1
        if res.new_mode is not None:
            mode = res.new_mode

    windows.set_simulated_active(WindowInfo(hwnd=202, title="Laskin", process_name="calc.exe"))
    for phrase in ["puhis save t2", "puhis t1", "puhis fokus t2", "puhis piilota t2", "puhis seis"]:
        print(f"> {phrase!r} (tila={mode.value})")
        res = router.handle_utterance(phrase, mode)
        print(f"  -> {res}")
        if not res.success:
            return 1
        if res.new_mode is not None:
            mode = res.new_mode

    print("Kuiva-ajo onnistui.")
    return 0


def run_live() -> int:
    print("Ajetaan oikea Windows-työpöytätesti (--live)...")
    config = AppConfig()
    registry = WindowRegistry()
    windows = WindowManager()
    keyboard = KeyboardInjector()
    launcher = AppLauncher(config.app_aliases)
    router = UtteranceRouter(
        config=config,
        window_registry=registry,
        keyboard_injector=keyboard,
        window_manager=windows,
        app_launcher=launcher,
    )

    mode = AssistantMode.IDLE

    def step(phrase: str, pause: float = 1.0) -> None:
        nonlocal mode
        print(f"> {phrase!r}")
        res = router.handle_utterance(phrase, mode)
        print(f"  -> {res.message} (ok={res.success})")
        if res.new_mode is not None:
            mode = res.new_mode
        time.sleep(pause)

    step("puhis avaa muistio", pause=1.5)
    step("puhis save t1", pause=0.5)
    step("puhis sanele", pause=0.3)
    step("Hei pilkku ääkköset toimivat kaksoispiste ä ö å huutomerkki enter tab sisennetty rivi piste", pause=1.0)
    step("puhis avaa laskin", pause=1.5)
    step("puhis save t2", pause=0.5)
    step("puhis t1", pause=1.0)
    step("puhis fokus t2", pause=1.0)
    step("puhis piilota t2", pause=0.8)
    step("puhis seis", pause=0.2)
    print("Live-testi suoritettu.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Turvallinen kuiva-ajo ilman Win32-vaikutuksia")
    group.add_argument("--live", action="store_true", help="Suorita oikeilla Windows-ikkunoilla (Muistio & Laskin)")
    args = parser.parse_args()

    if args.live:
        return run_live()
    return run_dry_run()


if __name__ == "__main__":
    sys.exit(main())
