"""Theme toggle/sync/apply.

Split out of ``main_window.py`` (mission: MainWindow decomposition,
2026-09-05) — a mixin composed by ``MainWindow``, not a standalone class.
Method bodies are unchanged; only their file location moved.
"""

from __future__ import annotations

from .. import icons
from ..i18n import t
from ..theme import other_theme, render_qss


class ThemeMixin:
    def _sync_theme_action(self) -> None:
        nxt = other_theme(self.settings.theme)
        glyph = "theme_light" if nxt == "light" else "theme_dark"
        self._theme_action.setIcon(icons.icon(glyph))
        self._theme_action.setText(t("theme.switch_label", name=t(f"theme.{nxt}")))
        self._theme_action.setToolTip(t("theme.switch_tip", name=t(f"theme.{nxt}")))

    def _toggle_theme(self) -> None:
        self._apply_theme(other_theme(self.settings.theme))

    def _apply_theme(self, name: str) -> None:
        from PyQt6.QtWidgets import QApplication

        self.settings.theme = name
        icons.set_theme(name)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(render_qss(name))
        else:  # pragma: no cover
            self.setStyleSheet(render_qss(name))
        self._model.set_theme(name)
        self._table.set_theme(name)
        self._detail.set_theme(name)
        self._sidebar.retint()
        self._filter_bar.retint()
        self._reports.set_theme(name)
        self._board.set_theme(name)
        self._sync_theme_action()
        self._undo_action.setIcon(icons.icon("undo"))
        self._settings_action.setIcon(icons.icon("settings"))
        self._console_action.setIcon(icons.icon("console"))
        self._add_full_action.setIcon(icons.icon("add", "primary_fg"))
        self._log_action.setIcon(icons.icon("completed"))
        self._data_btn.setIcon(icons.icon("data"))
        self._export_action.setIcon(icons.icon("export"))
        self._import_action.setIcon(icons.icon("import"))
        self._sync_action.setIcon(icons.icon("sync"))

