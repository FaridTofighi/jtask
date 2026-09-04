"""Raw command console, command palette, shortcut sheet, view navigation, settings dialog.

Split out of ``main_window.py`` (mission: MainWindow decomposition,
2026-09-05) — a mixin composed by ``MainWindow``, not a standalone class.
Method bodies are unchanged; only their file location moved.
"""

from __future__ import annotations

import functools

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QComboBox,
)

from jtask import taskwarrior
from jtask.rtl import set_digit_mode

from ..i18n import t


class ConsolePaletteMixin:
    def _after_console_command(self) -> None:
        """A mutating command ran in the console — re-read everything so the
        change (a new context, task, config value…) shows immediately.
        ``refresh_all`` already drops the lookup caches."""
        self.refresh_all()
        self._toast.show_message(t("msg.console_synced"))

    def _toggle_console(self, visible: bool) -> None:
        self._console_dock.setVisible(visible)
        self.settings.console_visible = visible

    def _collect_commands(self) -> list:
        from ..widgets.command_palette import Command

        cmds: list[Command] = []
        seen: set[str] = set()
        for act in self.findChildren(QAction):
            text = act.text().replace("&", "").strip()
            if not text or act.isSeparator() or not act.isEnabled() or text in seen:
                continue
            seen.add(text)
            sc = act.shortcut().toString()
            cmds.append(
                Command(text, t("palette.cat.action"), act.trigger, hint=sc)
            )
        for label, section, spec in self._sidebar.navigation_targets():
            if spec.get("kind") == "saved":
                continue  # added from settings below, with a stable category
            cmds.append(
                Command(
                    label, section or t("palette.cat.view"),
                    functools.partial(self._sidebar.activate_spec, spec),
                )
            )
        for name, raw in self.settings.saved_filters().items():
            cmds.append(
                Command(
                    name, t("palette.cat.filter"),
                    functools.partial(self._apply_saved_filter, raw),
                )
            )
        for name in self._board_names():
            cmds.append(
                Command(name, t("status.boards"),
                        functools.partial(self._show_board, name))
            )
        return cmds

    def _open_command_palette(self) -> None:
        from ..widgets.command_palette import CommandPalette

        pal = CommandPalette(self._collect_commands(), self)
        pal.move(
            self.geometry().center().x() - pal.width() // 2,
            self.geometry().top() + self.height() // 6,
        )
        pal.exec()

    def _open_shortcut_sheet(self) -> None:
        from PyQt6.QtWidgets import QLineEdit, QPlainTextEdit, QTextEdit

        # "?" must not fire while the user is typing it into a field
        fw = self.focusWidget()
        if isinstance(fw, QLineEdit | QComboBox | QTextEdit | QPlainTextEdit):
            return
        from ..widgets.shortcut_sheet import ShortcutSheet

        ShortcutSheet(self).exec()

    def _focus_filter(self) -> None:
        self._filter_bar._edit.setFocus()
        self._filter_bar._edit.selectAll()

    _FN_COUNT_FILTER = {
        "report_ready": ["+READY"],
        "report_waiting": ["+WAITING"],
        "report_blocked": ["+BLOCKED"],
        "report_completed": ["status:completed"],
    }

    def _view_counts(self) -> dict:
        """Match counts for the quick views + saved filters (runs off-thread)."""
        import shlex

        from ..widgets.sidebar import QUICK_VIEWS

        out: dict[str, int] = {}
        for _lbl, _glyph, spec in QUICK_VIEWS:
            if spec.get("fn"):
                flt = self._FN_COUNT_FILTER.get(spec["fn"])
                if flt is None:
                    continue
            else:
                flt = spec.get("filter")
                flt = flt() if callable(flt) else list(flt or [])
            out[spec["key"]] = taskwarrior.count(flt)
        for name, raw in self.settings.saved_filters().items():
            try:
                out[name] = taskwarrior.count(shlex.split(raw))
            except ValueError:
                out[name] = taskwarrior.count(raw.split())
        return out

    def _goto_view(self, key: str) -> None:
        from ..widgets.sidebar import QUICK_VIEWS

        for label_key, _glyph, spec in QUICK_VIEWS:
            if spec.get("key") == key:
                self._sidebar.activate_spec(dict(spec, title=t(label_key)))
                return

    def _open_settings(self) -> None:
        from ..settings_dialog import SettingsDialog

        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            set_digit_mode(self.settings.persian_digits)
            self._model.set_persian_digits(self.settings.persian_digits)
            self._model.set_due_soon_days(self.settings.due_soon_days)
            self._table.set_density(self.settings.density)
            self._reports.refresh_digits()
            self._apply_theme(self.settings.theme)
            self._notify.reconfigure()
            self.refresh_all()

