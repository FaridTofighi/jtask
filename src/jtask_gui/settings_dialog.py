"""Settings dialog: appearance + language + notifications."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .i18n import t
from .settings import Settings
from .theme import THEMES
from .widgets.fa_spinbox import FaSpinBox

_NOTIFY_STATES = [
    ("settings.notify.state.overdue", "overdue"),
    ("settings.notify.state.today", "today"),
    ("settings.notify.state.soon", "soon"),
]
_LANGUAGES = [("settings.language.fa", "fa"), ("settings.language.en", "en")]
_CALENDARS = [
    ("settings.calendar.jalali", "jalali"),
    ("settings.calendar.gregorian", "gregorian"),
]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(420)
        self._settings = settings

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self._language = QComboBox()
        for key, code in _LANGUAGES:
            self._language.addItem(t(key), code)
        self._language.setCurrentIndex(
            max(0, [c for _, c in _LANGUAGES].index(settings.language))
            if settings.language in [c for _, c in _LANGUAGES]
            else 0
        )
        form.addRow(t("settings.language"), self._language)

        self._calendar = QComboBox()
        for key, code in _CALENDARS:
            self._calendar.addItem(t(key), code)
        codes = [c for _, c in _CALENDARS]
        self._calendar.setCurrentIndex(
            codes.index(settings.calendar) if settings.calendar in codes else 0
        )
        form.addRow(t("settings.calendar"), self._calendar)

        self._theme = QComboBox()
        for key in THEMES:
            self._theme.addItem(t(f"theme.{key}"), key)
        self._theme.setCurrentIndex(
            max(0, list(THEMES).index(settings.theme))
            if settings.theme in THEMES else 0
        )
        form.addRow(t("settings.theme"), self._theme)

        self._digits = QCheckBox(t("settings.persian_digits"))
        self._digits.setChecked(settings.persian_digits)
        form.addRow("", self._digits)

        self._due_soon = FaSpinBox()
        self._due_soon.setRange(1, 30)
        self._due_soon.setValue(settings.due_soon_days)
        self._due_soon.setSuffix(t("settings.suffix.days"))
        form.addRow(t("settings.due_soon_threshold"), self._due_soon)

        self._density = QComboBox()
        for key in ("comfortable", "compact"):
            self._density.addItem(t(f"settings.density.{key}"), key)
        self._density.setCurrentIndex(
            max(0, self._density.findData(settings.density))
        )
        form.addRow(t("settings.density"), self._density)

        sec = QLabel(t("settings.notifications"))
        sec.setObjectName("Section")
        root.addWidget(sec)
        nform = QFormLayout()
        root.addLayout(nform)

        self._notify = QCheckBox(t("settings.notify.enabled"))
        self._notify.setChecked(settings.notifications_enabled)
        nform.addRow("", self._notify)

        self._states: dict[str, QCheckBox] = {}
        states_row = QHBoxLayout()
        enabled = set(settings.notify_states)
        for key, state in _NOTIFY_STATES:
            cb = QCheckBox(t(key))
            cb.setChecked(state in enabled)
            self._states[state] = cb
            states_row.addWidget(cb)
        sw = QWidget()
        sw.setLayout(states_row)
        nform.addRow(t("settings.notify.states"), sw)

        self._interval = FaSpinBox()
        self._interval.setRange(1, 240)
        self._interval.setValue(settings.notify_interval_min)
        self._interval.setSuffix(t("settings.suffix.minutes"))
        nform.addRow(t("settings.notify.interval"), self._interval)

        qs, qe = settings.quiet_hours
        self._quiet_start = FaSpinBox()
        self._quiet_start.setRange(0, 23)
        self._quiet_start.setValue(qs)
        self._quiet_end = FaSpinBox()
        self._quiet_end.setRange(0, 23)
        self._quiet_end.setValue(qe)
        quiet_row = QHBoxLayout()
        quiet_row.addWidget(QLabel(t("word.from")))
        quiet_row.addWidget(self._quiet_start)
        quiet_row.addWidget(QLabel(t("word.to")))
        quiet_row.addWidget(self._quiet_end)
        quiet_row.addStretch(1)
        qw = QWidget()
        qw.setLayout(quiet_row)
        nform.addRow(t("settings.notify.quiet_hours"), qw)

        tw_sec = QLabel(t("settings.taskwarrior"))
        tw_sec.setObjectName("Section")
        root.addWidget(tw_sec)
        twform = QFormLayout()
        root.addLayout(twform)

        self._tw_bin = _PathRow(directory=False)
        self._tw_bin.set_path(settings.task_bin)
        twform.addRow(t("settings.tw.bin"), self._tw_bin)
        self._tw_data = _PathRow(directory=True)
        self._tw_data.set_path(settings.taskdata)
        twform.addRow(t("settings.tw.data"), self._tw_data)
        self._tw_rc = _PathRow(directory=False)
        self._tw_rc.set_path(settings.taskrc)
        twform.addRow(t("settings.tw.rc"), self._tw_rc)

        hint = QLabel(t("settings.tw.hint"))
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        twform.addRow("", hint)

        self._reset_cols = QPushButton(t("settings.tw.reset_columns"))
        self._reset_cols.clicked.connect(self._do_reset_columns)
        twform.addRow("", self._reset_cols)

        sc_sec = QLabel(t("settings.shortcuts"))
        sc_sec.setObjectName("Section")
        root.addWidget(sc_sec)
        sc_hint = QLabel(t("settings.shortcuts.hint"))
        sc_hint.setObjectName("Muted")
        sc_hint.setWordWrap(True)
        root.addWidget(sc_hint)
        self._show_shortcuts = QPushButton(t("sc.sheet.title"))
        self._show_shortcuts.clicked.connect(self._open_shortcut_sheet)
        root.addWidget(self._show_shortcuts)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(t("btn.confirm"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("btn.cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept(self) -> None:
        s = self._settings
        s.theme = self._theme.currentData()

        # Resolution 1: a change here is an explicit user choice — record it so a
        # future language switch never silently rewrites the digit mode.
        if self._digits.isChecked() != s.persian_digits:
            s.digit_mode_user_overridden = True
        s.persian_digits = self._digits.isChecked()

        s.due_soon_days = self._due_soon.value()
        s.density = self._density.currentData()
        s.notifications_enabled = self._notify.isChecked()
        s.notify_states = [k for k, cb in self._states.items() if cb.isChecked()]
        s.notify_interval_min = self._interval.value()
        s.quiet_hours = (self._quiet_start.value(), self._quiet_end.value())

        new_lang = self._language.currentData()
        new_cal = self._calendar.currentData()
        tw_bin, tw_data, tw_rc = (
            self._tw_bin.path(), self._tw_data.path(), self._tw_rc.path(),
        )
        needs_restart = (
            new_lang != s.language
            or new_cal != s.calendar
            or tw_bin != s.task_bin
            or tw_data != s.taskdata
            or tw_rc != s.taskrc
        )
        s.language = new_lang
        s.calendar = new_cal
        s.task_bin = tw_bin
        s.taskdata = tw_data
        s.taskrc = tw_rc
        s.sync()

        self.accept()
        if needs_restart:
            self._prompt_restart()

    def _do_reset_columns(self) -> None:
        self._settings.reset_columns()
        self._reset_cols.setText(t("settings.tw.reset_columns.done"))
        self._reset_cols.setEnabled(False)

    def _open_shortcut_sheet(self) -> None:
        from .widgets.shortcut_sheet import ShortcutSheet

        ShortcutSheet(self).exec()

    def _prompt_restart(self) -> None:
        box = QMessageBox(self.parent() or self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(t("settings.restart.title"))
        box.setText(t("settings.restart.body"))
        now = box.addButton(t("settings.restart.now"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(t("settings.restart.later"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is now:
            from .app import request_restart

            request_restart()


class _PathRow(QWidget):
    """A line edit plus a browse button for a file (or directory) path."""

    def __init__(self, *, directory: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._directory = directory
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        row.addWidget(self._edit, 1)
        browse = QPushButton(t("btn.choose"))
        browse.clicked.connect(self._browse)
        row.addWidget(browse)

    def _browse(self) -> None:
        if self._directory:
            picked = QFileDialog.getExistingDirectory(self, t("btn.choose"), self.path())
        else:
            picked, _ = QFileDialog.getOpenFileName(self, t("btn.choose"), self.path())
        if picked:
            self._edit.setText(picked)

    def set_path(self, value: str) -> None:
        self._edit.setText(value or "")

    def path(self) -> str:
        return self._edit.text().strip()
