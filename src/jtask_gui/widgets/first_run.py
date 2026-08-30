"""First-run setup dialog: theme, digits, Vazirmatn check, notifications."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from jtask import fonts

from ..i18n import t
from ..settings import Settings
from ..theme import THEMES


class FirstRunWizard(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle(t("firstrun.title"))
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        root.setSpacing(14)

        title = QLabel(t("firstrun.heading"))
        title.setObjectName("H1")
        root.addWidget(title)
        root.addWidget(QLabel(
            t("firstrun.intro")
        ))

        # theme
        root.addWidget(_section(t("firstrun.section.theme")))
        self._theme_group = QButtonGroup(self)
        trow = QHBoxLayout()
        for i, name in enumerate(THEMES):
            rb = QRadioButton(t(f"theme.{name}"))
            if name == settings.theme:
                rb.setChecked(True)
            self._theme_group.addButton(rb, i)
            trow.addWidget(rb)
        trow.addStretch(1)
        root.addLayout(trow)
        self._theme_names = list(THEMES)

        # digits
        self._digits = QCheckBox(t("firstrun.digits"))
        self._digits.setChecked(settings.persian_digits)
        root.addWidget(self._digits)

        # font check
        root.addWidget(_section(t("firstrun.section.font")))
        font_row = QHBoxLayout()
        self._font_status = QLabel("—")
        check_btn = QPushButton(t("firstrun.check_font"))
        check_btn.clicked.connect(self._check_font)
        font_row.addWidget(self._font_status, 1)
        font_row.addWidget(check_btn)
        root.addLayout(font_row)
        self._check_font()

        # notifications
        root.addWidget(_section(t("firstrun.section.notifications")))
        self._notify = QCheckBox(t("firstrun.notify"))
        self._notify.setChecked(settings.notifications_enabled)
        root.addWidget(self._notify)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(t("firstrun.start"))
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
        buttons.accepted.connect(self._finish)
        root.addWidget(buttons)

    def _check_font(self) -> None:
        found, _ = fonts.is_vazir_installed()
        if found:
            self._font_status.setText(t("firstrun.font.found"))
        else:
            self._font_status.setText(
                t("firstrun.font.missing")
            )

    def _finish(self) -> None:
        idx = self._theme_group.checkedId()
        self._settings.theme = self._theme_names[idx if idx >= 0 else 0]
        self._settings.persian_digits = self._digits.isChecked()
        self._settings.notifications_enabled = self._notify.isChecked()
        self._settings.wizard_done = True
        self._settings.sync()
        self.accept()


def _section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Section")
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
    return lbl
