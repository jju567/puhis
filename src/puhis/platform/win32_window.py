"""Win32-apufunktiot kelluvalle ikkunalle (ctypes)."""

import ctypes
import logging
import sys
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

_LONG_PTR = ctypes.c_ssize_t


@dataclass(frozen=True, slots=True)
class _User32Api:
    get_window_long: Callable[..., int]
    set_window_long: Callable[..., int]
    set_window_pos: Callable[..., int]


def _load_user32() -> _User32Api | None:
    if sys.platform != "win32":
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    # 32-bittisessä Pythonissa *LongPtrW-funktioita ei ole, vaan ne ovat makroja *LongW:lle.
    get_long = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    set_long = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    get_long.restype = _LONG_PTR
    set_long.argtypes = [wintypes.HWND, ctypes.c_int, _LONG_PTR]
    set_long.restype = _LONG_PTR

    set_pos = user32.SetWindowPos
    set_pos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    set_pos.restype = wintypes.BOOL
    return _User32Api(get_long, set_long, set_pos)


_USER32 = _load_user32()


def apply_floating_tool_style(hwnd: int) -> bool:
    """Asettaa ikkunalle WS_EX_NOACTIVATE-, WS_EX_TOOLWINDOW- ja WS_EX_TOPMOST-tyylit.

    WS_EX_NOACTIVATE estää kissaa varastamasta fokusta aktiiviselta ikkunalta,
    jolloin sanelu kohdistuu edelleen käyttäjän editoriin. WS_EX_TOOLWINDOW
    piilottaa ikkunan tehtäväpalkista ja Alt+Tab-listasta.

    Returns:
        True, jos tyylit asetettiin onnistuneesti.
    """
    if _USER32 is None:
        logger.debug("Ei Windows-ympäristö, ikkunatyylejä ei aseteta")
        return False
    if not hwnd:
        logger.warning("Virheellinen ikkunakahva, ikkunatyylejä ei aseteta")
        return False

    # Tyyli voi aidosti olla 0, joten virhe tunnistetaan vain last error -arvosta.
    ctypes.set_last_error(0)
    style = _USER32.get_window_long(hwnd, GWL_EXSTYLE)
    if style == 0 and ctypes.get_last_error() != 0:
        logger.error("GetWindowLongPtrW epäonnistui (virhe %d)", ctypes.get_last_error())
        return False

    new_style = style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
    ctypes.set_last_error(0)
    previous = _USER32.set_window_long(hwnd, GWL_EXSTYLE, new_style)
    if previous == 0 and ctypes.get_last_error() != 0:
        logger.error("SetWindowLongPtrW epäonnistui (virhe %d)", ctypes.get_last_error())
        return False

    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
    if not _USER32.set_window_pos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags):
        logger.error("SetWindowPos epäonnistui (virhe %d)", ctypes.get_last_error())
        return False
    return True
