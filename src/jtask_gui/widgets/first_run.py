"""First-run setup dialog: theme, digits, Vazirmatn check, notifications.

Uses the same label-beside-field ``QFormLayout`` as the Settings dialog (§ d3)
so the two read consistently.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from jtask import fonts

from .. import tokens as tok
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
        root.setContentsMargins(*tok.INSET_DIALOG)
        root.setSpacing(tok.SP_14)

        title = QLabel(t("firstrun.heading"))
        title.setObjectName("H1")
        root.addWidget(title)
        intro = QLabel(t("firstrun.intro"))
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(tok.SP_10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        root.addLayout(form)

        # theme
        self._theme_group = QButtonGroup(self)
        trow = QHBoxLayout()
        trow.setContentsMargins(0, 0, 0, 0)
        for i, name in enumerate(THEMES):
            rb = QRadioButton(t(f"theme.{name}"))
            if name == settings.theme:
                rb.setChecked(True)
            self._theme_group.addButton(rb, i)
            trow.addWidget(rb)
        trow.addStretch(1)
        theme_w = QWidget()
        theme_w.setLayout(trow)
        form.addRow(t("firstrun.section.theme"), theme_w)
        self._theme_names = list(THEMES)

        # digits
        self._digits = QCheckBox(t("firstrun.digits"))
        self._digits.setChecked(settings.persian_digits)
        form.addRow("", self._digits)

        # font check
        font_row = QHBoxLayout()
        font_row.setContentsMargins(0, 0, 0, 0)
        self._font_status = QLabel("—")
        check_btn = QPushButton(t("firstrun.check_font"))
        check_btn.clicked.connect(self._check_font)
        font_row.addWidget(self._font_status, 1)
        font_row.addWidget(check_btn)
        font_w = QWidget()
        font_w.setLayout(font_row)
        form.addRow(t("firstrun.section.font"), font_w)
        self._check_font()

        # notifications
        self._notify = QCheckBox(t("firstrun.notify"))
        self._notify.setChecked(settings.notifications_enabled)
        form.addRow(t("firstrun.section.notifications"), self._notify)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(t("firstrun.start"))
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
        buttons.accepted.connect(self._finish)
        root.addWidget(buttons)

    def _check_font(self) -> None:
        found, _ = fonts.is_vazir_installed()
        self._font_status.setText(
            t("firstrun.font.found") if found else t("firstrun.font.missing")
        )

    def _finish(self) -> None:
        idx = self._theme_group.checkedId()
        self._settings.theme = self._theme_names[idx if idx >= 0 else 0]
        # Only an explicit deviation from the language default counts as a
        # user override (Resolution 1); otherwise digit mode keeps following
        # the UI language.
        if self._digits.isChecked() != self._settings.persian_digits:
            self._settings.digit_mode_user_overridden = True
            self._settings.persian_digits = self._digits.isChecked()
        self._settings.notifications_enabled = self._notify.isChecked()
        self._settings.wizard_done = True
        self._settings.sync()
        self.accept()
