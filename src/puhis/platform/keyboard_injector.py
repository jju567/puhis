"""Win32 SendInput -pohjainen näppäin- ja Unicode-tekstinsyöttö."""

import ctypes
import logging
import sys
from collections.abc import Callable, Sequence
from ctypes import wintypes

from puhis.core.actions import InputAction, KeyAction, TextAction, VirtualKey

logger = logging.getLogger(__name__)

INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_DELETE = 0x2E

_VK_MAP: dict[VirtualKey, int] = {
    VirtualKey.ENTER: VK_RETURN,
    VirtualKey.TAB: VK_TAB,
    VirtualKey.BACKSPACE: VK_BACK,
    VirtualKey.ESCAPE: VK_ESCAPE,
    VirtualKey.SPACE: VK_SPACE,
    VirtualKey.DELETE: VK_DELETE,
    VirtualKey.LEFT: VK_LEFT,
    VirtualKey.UP: VK_UP,
    VirtualKey.RIGHT: VK_RIGHT,
    VirtualKey.DOWN: VK_DOWN,
}

_EXTENDED_VKS = frozenset({VK_DELETE, VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN})

_ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    """Win32 MOUSEINPUT (tarvitaan, jotta INPUT-unionin koko täsmää 64-bittisessä Windowsissa)."""

    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    """Win32 KEYBDINPUT -rakenne."""

    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    """Win32 HARDWAREINPUT -rakenne."""

    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    """Win32 INPUT -rakenne SendInput-funktiolle."""

    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]


type SendInputFunc = Callable[[int, ctypes.Array[INPUT], int], int]


def _load_send_input() -> SendInputFunc | None:
    if sys.platform != "win32":
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    fn = user32.SendInput
    fn.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    fn.restype = wintypes.UINT

    def _call(count: int, inputs: ctypes.Array[INPUT], item_size: int) -> int:
        ctypes.set_last_error(0)
        return int(fn(count, inputs, item_size))

    return _call


_DEFAULT_SEND_INPUT = _load_send_input()


def build_inputs_for_actions(actions: Sequence[InputAction]) -> list[INPUT]:
    """Muodostaa Win32 INPUT -tapahtumalistan annetuista toiminnoista."""
    events: list[INPUT] = []
    for action in actions:
        if isinstance(action, TextAction):
            events.extend(_build_unicode_text_inputs(action.text))
        elif isinstance(action, KeyAction):
            vk = _VK_MAP.get(action.key)
            if vk is not None:
                events.extend(_build_virtual_key_inputs(vk))
    return events


def _build_unicode_text_inputs(text: str) -> list[INPUT]:
    """Luo KEYEVENTF_UNICODE -painallus/vapautusparit UTF-16LE-koodiyksiköittäin."""
    if not text:
        return []
    encoded = text.encode("utf-16-le")
    events: list[INPUT] = []
    for offset in range(0, len(encoded), 2):
        code_unit = int.from_bytes(encoded[offset : offset + 2], byteorder="little")
        events.append(_make_keybd_input(w_vk=0, w_scan=code_unit, flags=KEYEVENTF_UNICODE))
        events.append(
            _make_keybd_input(
                w_vk=0,
                w_scan=code_unit,
                flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
            )
        )
    return events


def _build_virtual_key_inputs(vk_code: int) -> list[INPUT]:
    """Luo virtuaalinäppäimen painallus- ja vapautustapahtumat."""
    base_flags = KEYEVENTF_EXTENDEDKEY if vk_code in _EXTENDED_VKS else 0
    return [
        _make_keybd_input(w_vk=vk_code, w_scan=0, flags=base_flags),
        _make_keybd_input(w_vk=vk_code, w_scan=0, flags=base_flags | KEYEVENTF_KEYUP),
    ]


def _make_keybd_input(w_vk: int, w_scan: int, flags: int) -> INPUT:
    item = INPUT()
    item.type = INPUT_KEYBOARD
    item.union.ki = KEYBDINPUT(
        wVk=w_vk,
        wScan=w_scan,
        dwFlags=flags,
        time=0,
        dwExtraInfo=0,
    )
    return item


class KeyboardInjector:
    """Lähettää teksti- ja näppäintapahtumat aktiiviseen ikkunaan Win32 SendInputilla."""

    def __init__(self, send_input_fn: SendInputFunc | None = None) -> None:
        self._send_input = send_input_fn if send_input_fn is not None else _DEFAULT_SEND_INPUT

    def send_actions(self, actions: Sequence[InputAction]) -> bool:
        """Lähettää annetut toiminnot kerralla aktiiviseen ikkunaan."""
        if not actions:
            return True

        events = build_inputs_for_actions(actions)
        if not events:
            return True

        if self._send_input is None:
            logger.error("SendInput ei ole käytettävissä tässä ympäristössä")
            return False

        count = len(events)
        array_type = INPUT * count
        input_array = array_type(*events)
        sent = self._send_input(count, input_array, ctypes.sizeof(INPUT))
        if sent != count:
            err = ctypes.get_last_error()
            logger.error(
                "SendInput lähetti vain %d/%d tapahtumaa (Win32-virhe %d, mahdollinen UIPI-esto)",
                sent,
                count,
                err,
            )
            return False
        return True

    def send_text(self, text: str) -> bool:
        """Apumetodi pelkän Unicode-tekstin lähettämiseen."""
        if not text:
            return True
        return self.send_actions([TextAction(text=text)])

    def send_key(self, key: VirtualKey) -> bool:
        """Apumetodi yksittäisen erikoisnäppäimen lähettämiseen."""
        return self.send_actions([KeyAction(key=key)])
