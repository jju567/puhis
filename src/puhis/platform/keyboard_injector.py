"""Win32 SendInput -pohjainen näppäin- ja Unicode-tekstinsyöttö."""

import ctypes
import logging
import sys
import time
from collections.abc import Callable, Sequence
from ctypes import wintypes
from typing import Protocol

from puhis.core.actions import InputAction, KeyAction, TextAction, VirtualKey

logger = logging.getLogger(__name__)

INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_DELETE = 0x2E
VK_A = 0x41
VK_V = 0x56

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

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
        events.extend(_build_inputs_for_single_action(action))
    return events


def _build_inputs_for_single_action(action: InputAction) -> list[INPUT]:
    if isinstance(action, TextAction):
        return _build_unicode_text_inputs(action.text)
    if isinstance(action, KeyAction):
        if action.key is VirtualKey.CTRL_BACKSPACE:
            return _build_key_combo_inputs(VK_CONTROL, VK_BACK)
        if action.key is VirtualKey.CLEAR_ALL:
            return [
                *_build_key_combo_inputs(VK_CONTROL, VK_A),
                *_build_virtual_key_inputs(VK_BACK),
            ]
        vk = _VK_MAP.get(action.key)
        if vk is not None:
            return _build_virtual_key_inputs(vk)
    return []


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


def _build_key_combo_inputs(modifier_vk: int, key_vk: int) -> list[INPUT]:
    """Luo näppäinyhdistelmän (esim. Ctrl+Backspace) painallus- ja vapautustapahtumat."""
    key_flags = KEYEVENTF_EXTENDEDKEY if key_vk in _EXTENDED_VKS else 0
    return [
        _make_keybd_input(w_vk=modifier_vk, w_scan=0, flags=0),
        _make_keybd_input(w_vk=key_vk, w_scan=0, flags=key_flags),
        _make_keybd_input(w_vk=key_vk, w_scan=0, flags=key_flags | KEYEVENTF_KEYUP),
        _make_keybd_input(w_vk=modifier_vk, w_scan=0, flags=KEYEVENTF_KEYUP),
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


DEFAULT_INTER_KEY_DELAY_S = 0.002
PASTE_SETTLE_DELAY_S = 0.08


class ClipboardProtocol(Protocol):
    """Rajapinta leikepöydän tekstin lukuun ja kirjoitukseen."""

    def get_text(self) -> str | None:
        """Palauttaa leikepöydän nykyisen tekstin tai `None`, jos se ei ole tekstiä."""

    def set_text(self, text: str) -> bool:
        """Asettaa tekstin leikepöydälle. Palauttaa `True` onnistuessaan."""


class Win32Clipboard:
    """Win32-leikepöydän luku ja kirjoitus (`CF_UNICODETEXT`)."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            self._available = False
            return
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        self._user32.OpenClipboard.argtypes = [wintypes.HWND]
        self._user32.OpenClipboard.restype = wintypes.BOOL
        self._user32.CloseClipboard.argtypes = []
        self._user32.CloseClipboard.restype = wintypes.BOOL
        self._user32.EmptyClipboard.argtypes = []
        self._user32.EmptyClipboard.restype = wintypes.BOOL
        self._user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        self._user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
        self._user32.GetClipboardData.argtypes = [wintypes.UINT]
        self._user32.GetClipboardData.restype = wintypes.HANDLE
        self._user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        self._user32.SetClipboardData.restype = wintypes.HANDLE

        self._kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        self._kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        self._kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        self._kernel32.GlobalFree.restype = wintypes.HGLOBAL
        self._kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        self._kernel32.GlobalLock.restype = ctypes.c_void_p
        self._kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        self._kernel32.GlobalUnlock.restype = wintypes.BOOL
        self._available = True

    def _open_with_retry(self) -> bool:
        if not self._available:
            return False
        for _ in range(3):
            if self._user32.OpenClipboard(None):
                return True
            time.sleep(0.01)
        return False

    def get_text(self) -> str | None:
        if not self._available or not self._user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        if not self._open_with_retry():
            return None
        try:
            handle = self._user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            ptr = self._kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                return ctypes.wstring_at(ptr)
            finally:
                self._kernel32.GlobalUnlock(handle)
        finally:
            self._user32.CloseClipboard()

    def set_text(self, text: str) -> bool:
        if not self._open_with_retry():
            return False
        try:
            if not self._user32.EmptyClipboard():
                return False
            encoded = (text + "\0").encode("utf-16-le")
            h_mem = self._kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not h_mem:
                return False
            ptr = self._kernel32.GlobalLock(h_mem)
            if not ptr:
                self._kernel32.GlobalFree(h_mem)
                return False
            try:
                ctypes.memmove(ptr, encoded, len(encoded))
            finally:
                self._kernel32.GlobalUnlock(h_mem)

            if not self._user32.SetClipboardData(CF_UNICODETEXT, h_mem):
                self._kernel32.GlobalFree(h_mem)
                return False
            return True
        finally:
            self._user32.CloseClipboard()


class KeyboardInjector:
    """Lähettää teksti- ja näppäintapahtumat aktiiviseen ikkunaan Win32 SendInputilla."""

    def __init__(
        self,
        send_input_fn: SendInputFunc | None = None,
        inter_key_delay_s: float = DEFAULT_INTER_KEY_DELAY_S,
        clipboard: ClipboardProtocol | None = None,
        paste_settle_delay_s: float = PASTE_SETTLE_DELAY_S,
    ) -> None:
        self._send_input = send_input_fn if send_input_fn is not None else _DEFAULT_SEND_INPUT
        self._inter_key_delay_s = max(0.0, inter_key_delay_s)
        if clipboard is not None:
            self._clipboard: ClipboardProtocol | None = clipboard
        elif send_input_fn is None and sys.platform == "win32":
            self._clipboard = Win32Clipboard()
        else:
            self._clipboard = None
        self._paste_settle_delay_s = max(0.0, paste_settle_delay_s)

    def send_actions(self, actions: Sequence[InputAction]) -> bool:
        """Lähettää annetut toiminnot aktiiviseen ikkunaan."""
        if not actions:
            return True

        if self._send_input is None:
            logger.error("SendInput ei ole käytettävissä tässä ympäristössä")
            return False

        for action_idx, action in enumerate(actions):
            if isinstance(action, TextAction):
                if not self._send_text_action(action.text):
                    return False
                if self._inter_key_delay_s > 0.0 and action_idx + 1 < len(actions):
                    time.sleep(self._inter_key_delay_s)
                continue

            events = _build_inputs_for_single_action(action)
            if not events:
                continue
            if not self._send_batch(events):
                return False
            if self._inter_key_delay_s > 0.0 and action_idx + 1 < len(actions):
                time.sleep(self._inter_key_delay_s)
        return True

    def _send_text_action(self, text: str) -> bool:
        if not text:
            return True

        # Leikepöytä + Ctrl+V on luotettavin tapa syöttää tekstiä Windows 11:n
        # WinUI-kenttiin (kuten Muistio), joissa KEYEVENTF_UNICODE voi toistua.
        if self._clipboard is not None and self._paste_via_clipboard(text):
            return True

        events = _build_unicode_text_inputs(text)
        total = len(events)
        for idx in range(0, total, 2):
            chunk = events[idx : idx + 2]
            if not self._send_batch(chunk):
                return False
            if self._inter_key_delay_s > 0.0 and idx + len(chunk) < total:
                time.sleep(self._inter_key_delay_s)
        return True

    def _paste_via_clipboard(self, text: str) -> bool:
        assert self._clipboard is not None
        previous = self._clipboard.get_text()
        if not self._clipboard.set_text(text):
            return False
        try:
            paste_events = _build_key_combo_inputs(VK_CONTROL, VK_V)
            if not self._send_batch(paste_events):
                return False
            if self._paste_settle_delay_s > 0.0:
                time.sleep(self._paste_settle_delay_s)
            return True
        finally:
            if previous is not None:
                self._clipboard.set_text(previous)

    def _send_batch(self, events: list[INPUT]) -> bool:
        if self._send_input is None:
            return False
        count = len(events)
        array_type = INPUT * count
        arr = array_type(*events)
        sent = self._send_input(count, arr, ctypes.sizeof(INPUT))
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
