"""Pick a Taskwarrior colour for a project — curated swatches + a raw field."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as tok
from ..i18n import t
from ..tw_color import CURATED, to_hex


def swatch(hex_colour: str, size: int = 12) -> QIcon:
    """A filled round colour chip as a QIcon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(hex_colour))
    p.drawEllipse(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(pm)


class ProjectColorDialog(QDialog):
    def __init__(self, project: str, current: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProjectColorDialog")
        self.setWindowTitle(t("project_color.title", project=project))
        self._result: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(*tok.INSET_DIALOG)
        root.setSpacing(tok.SP_12)

        root.addWidget(QLabel(t("project_color.pick")))
        grid = QGridLayout()
        grid.setSpacing(tok.SP_6)
        for i, name in enumerate(CURATED):
            b = QToolButton()
            b.setToolTip(name)
            b.setIconSize(QSize(18, 18))
            hx = to_hex(name)
            if hx:
                b.setIcon(swatch(hx, 18))
            b.clicked.connect(lambda _c, n=name: self._field.setText(n))
            grid.addWidget(b, i // 7, i % 7)
        grid_wrap = QWidget()
        grid_wrap.setLayout(grid)
        root.addWidget(grid_wrap)

        row = QHBoxLayout()
        row.setSpacing(tok.SP_8)
        row.addWidget(QLabel(t("project_color.raw")))
        self._field = QLineEdit(current)
        self._field.setPlaceholderText(t("project_color.raw.placeholder"))
        self._field.textChanged.connect(self._preview)
        row.addWidget(self._field, 1)
        self._preview_dot = QLabel()
        row.addWidget(self._preview_dot)
        root.addLayout(row)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.cancel"), QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(
            self.reject
        )
        clear = btns.addButton(
            t("project_color.clear"), QDialogButtonBox.ButtonRole.DestructiveRole
        )
        clear.clicked.connect(self._on_clear)
        ok = btns.addButton(t("btn.apply"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("Primary")
        ok.clicked.connect(self._on_apply)
        root.addWidget(btns)

        self._preview()

    def _preview(self) -> None:
        hx = to_hex(self._field.text())
        self._preview_dot.setPixmap(swatch(hx, 14).pixmap(14, 14) if hx else QPixmap())

    def _on_apply(self) -> None:
        self._result = self._field.text().strip()
        self.accept()

    def _on_clear(self) -> None:
        self._result = ""
        self.accept()

    def result_color(self) -> str | None:
        """The chosen colour string, ``""`` to clear, or ``None`` if cancelled."""
        return self._result
