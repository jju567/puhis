"""Win32-ikkunanhallinta: aktiivinen ikkuna, fokusointi ja piilotus (ctypes)."""

import ctypes
import logging
import sys
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from puhis.core.actions import WindowInfo

logger = logging.getLogger(__name__)

SW_MINIMIZE = 6
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PATH_BUFFER = 1024


@dataclass(frozen=True, slots=True)
class _Win32WindowApi:
    get_foreground_window: Callable[[], int]
    is_window: Callable[[int], int]
    is_iconic: Callable[[int], int]
    get_window_text_length: Callable[[int], int]
    get_window_text: Callable[[int, ctypes.Array[ctypes.c_wchar], int], int]
    get_window_thread_process_id: Callable[..., int]
    set_foreground_window: Callable[[int], int]
    show_window: Callable[[int, int], int]
    open_process: Callable[[int, int, int], int]
    query_full_process_image_name: Callable[..., int]
    close_handle: Callable[[int], int]


def _load_win32_api() -> _Win32WindowApi | None:
    if sys.platform != "win32":
        return None

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    get_fg = user32.GetForegroundWindow
    get_fg.argtypes = []
    get_fg.restype = wintypes.HWND

    is_win = user32.IsWindow
    is_win.argtypes = [wintypes.HWND]
    is_win.restype = wintypes.BOOL

    is_iconic = user32.IsIconic
    is_iconic.argtypes = [wintypes.HWND]
    is_iconic.restype = wintypes.BOOL

    get_text_len = user32.GetWindowTextLengthW
    get_text_len.argtypes = [wintypes.HWND]
    get_text_len.restype = ctypes.c_int

    get_text = user32.GetWindowTextW
    get_text.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    get_text.restype = ctypes.c_int

    get_pid = user32.GetWindowThreadProcessId
    get_pid.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    get_pid.restype = wintypes.DWORD

    set_fg = user32.SetForegroundWindow
    set_fg.argtypes = [wintypes.HWND]
    set_fg.restype = wintypes.BOOL

    show_win = user32.ShowWindow
    show_win.argtypes = [wintypes.HWND, ctypes.c_int]
    show_win.restype = wintypes.BOOL

    open_proc = kernel32.OpenProcess
    open_proc.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_proc.restype = wintypes.HANDLE

    query_img = kernel32.QueryFullProcessImageNameW
    query_img.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    query_img.restype = wintypes.BOOL

    close_h = kernel32.CloseHandle
    close_h.argtypes = [wintypes.HANDLE]
    close_h.restype = wintypes.BOOL

    return _Win32WindowApi(
        get_foreground_window=get_fg,
        is_window=is_win,
        is_iconic=is_iconic,
        get_window_text_length=get_text_len,
        get_window_text=get_text,
        get_window_thread_process_id=get_pid,
        set_foreground_window=set_fg,
        show_window=show_win,
        open_process=open_proc,
        query_full_process_image_name=query_img,
        close_handle=close_h,
    )


_API = _load_win32_api()


class WindowManager:
    """Hallitsee Windows-ikkunoita Win32 API -kutsuilla."""

    def __init__(self, api: _Win32WindowApi | None = _API) -> None:
        self._api = api

    def get_active_window(self) -> WindowInfo | None:
        """Palauttaa aktiivisen etualaikkunan tiedot (`hwnd`, otsikko, prosessi)."""
        if self._api is None:
            logger.debug("Win32-rajapinta ei ole käytettävissä")
            return None

        hwnd = int(self._api.get_foreground_window() or 0)
        if hwnd <= 0:
            return None

        title = self._read_window_title(hwnd)
        process_name = self._read_process_name(hwnd)
        return WindowInfo(hwnd=hwnd, title=title, process_name=process_name)

    def is_window_valid(self, hwnd: int) -> bool:
        """Tarkistaa, onko ikkunakahva edelleen voimassa."""
        if self._api is None or hwnd <= 0:
            return False
        return bool(self._api.is_window(hwnd))

    def focus_window(self, hwnd: int) -> bool:
        """Palauttaa ikkunan minimoinnista ja tuo sen etualalle."""
        if self._api is None:
            return False
        if not self.is_window_valid(hwnd):
            logger.warning("Fokusointi epäonnistui: ikkuna %d ei ole enää olemassa", hwnd)
            return False

        # Minimoitu ikkuna täytyy palauttaa ennen aktivointia, muuten fokus jää piiloon.
        if self._api.is_iconic(hwnd):
            self._api.show_window(hwnd, SW_RESTORE)

        ctypes.set_last_error(0)
        if not self._api.set_foreground_window(hwnd):
            err = ctypes.get_last_error()
            logger.warning("SetForegroundWindow(%d) epäonnistui (Win32-virhe %d)", hwnd, err)
            return False
        return True

    def minimize_window(self, hwnd: int) -> bool:
        """Minimoi (piilottaa) annetun ikkunan tehtäväpalkkiin."""
        if self._api is None:
            return False
        if not self.is_window_valid(hwnd):
            logger.warning("Piilotus epäonnistui: ikkuna %d ei ole enää olemassa", hwnd)
            return False

        ctypes.set_last_error(0)
        self._api.show_window(hwnd, SW_MINIMIZE)
        err = ctypes.get_last_error()
        if err != 0:
            logger.warning("ShowWindow(%d, SW_MINIMIZE) raportoi virheen %d", hwnd, err)
            return False
        return True

    def _read_window_title(self, hwnd: int) -> str:
        if self._api is None:
            return ""
        length = int(self._api.get_window_text_length(hwnd))
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        self._api.get_window_text(hwnd, buf, length + 1)
        return buf.value.strip()

    def _read_process_name(self, hwnd: int) -> str:
        if self._api is None:
            return ""
        pid = wintypes.DWORD(0)
        self._api.get_window_thread_process_id(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return ""

        handle = self._api.open_process(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(MAX_PATH_BUFFER)
            buf = ctypes.create_unicode_buffer(MAX_PATH_BUFFER)
            if not self._api.query_full_process_image_name(handle, 0, buf, ctypes.byref(size)):
                return ""
            return Path(buf.value).name
        finally:
            self._api.close_handle(handle)
