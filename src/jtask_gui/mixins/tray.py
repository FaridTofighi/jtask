"""System tray icon, background-run window show/hide, quit.

Split out of ``main_window.py`` (mission: MainWindow decomposition,
2026-09-05) — a mixin composed by ``MainWindow``, not a standalone class.
Method bodies are unchanged; only their file location moved.
"""

from __future__ import annotations

from ..i18n import t


class TrayMixin:
    def _build_tray(self) -> None:
        from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

        from ..app import app_icon
        from ..notifications import NotificationManager

        self._tray = QSystemTrayIcon(app_icon(), self)
        self._tray.setToolTip("jtask")
        menu = QMenu(self)
        act_show = menu.addAction(t("tray.toggle_window"))
        act_show.triggered.connect(self._toggle_window)
        act_add = menu.addAction(t("tray.quick_add"))
        act_add.triggered.connect(self._focus_quick_add_from_tray)
        menu.addSeparator()
        act_quit = menu.addAction(t("tray.quit"))
        act_quit.triggered.connect(self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()

        self._notify = NotificationManager(self.settings, self._tray, self)
        self._notify.taskActivated.connect(self._raise_window)

    def _on_tray_activated(self, reason) -> None:
        from PyQt6.QtWidgets import QSystemTrayIcon

        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self._raise_window()

    def _raise_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _focus_quick_add_from_tray(self) -> None:
        self._raise_window()
        self._quick_add.focus()

    def _quit(self) -> None:
        from PyQt6.QtWidgets import QApplication

        self._really_quit = True
        QApplication.quit()

