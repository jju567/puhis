"""Windowsin ilmaisinalueen (System Tray) kuvake."""

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from puhis.core.app_state import AssistantMode
from puhis.core.config_store import CatTheme
from puhis.ui.app_menu import MODE_LABELS_FI
from puhis.ui.cat_painter import render_cat_icon


class PuhisTrayIcon(QSystemTrayIcon):
    """Varakuvake, jonka kautta kissan saa takaisin näkyviin."""

    def __init__(
        self,
        menu: QMenu,
        parent: QObject | None = None,
        theme: CatTheme = CatTheme.CHARCOAL,
    ) -> None:
        super().__init__(parent)
        self.setContextMenu(menu)
        self._mode = AssistantMode.IDLE
        self._icons = self._build_icons(theme)
        self.set_mode(AssistantMode.IDLE)

    def set_mode(self, mode: AssistantMode) -> None:
        """Päivittää kuvakkeen ja työkaluvihjeen tilan mukaiseksi."""
        self._mode = mode
        self.setIcon(self._icons[mode])
        self.setToolTip(f"Puhis – {MODE_LABELS_FI.get(mode, str(mode))}")

    def set_theme(self, theme: CatTheme) -> None:
        """Päivittää Tray-kuvakkeiden väriteeman."""
        self._icons = self._build_icons(theme)
        self.set_mode(self._mode)

    @staticmethod
    def _build_icons(theme: CatTheme) -> dict[AssistantMode, object]:
        return {mode: render_cat_icon(mode, theme=theme) for mode in AssistantMode}
