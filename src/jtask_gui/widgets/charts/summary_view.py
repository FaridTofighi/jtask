"""Summary — per-project completion progress + pending/overdue counts."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QWidget,
)

from ... import fmt
from ... import tokens as tok
from ...i18n import t


class SummaryView(QScrollArea):
    def __init__(self, theme_name: str = "dark", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailScroll")
        self.setWidgetResizable(True)
        self._theme = theme_name
        self._rows: list[dict] = []
        self._body = QWidget()
        self._body.setObjectName("DetailPanel")
        self._grid = QGridLayout(self._body)
        self._grid.setContentsMargins(*tok.INSET_DIALOG)
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(12)
        self.setWidget(self._body)

    def set_theme(self, theme_name: str) -> None:
        self._theme = theme_name
        self._rebuild()

    def set_data(self, rows: list[dict]) -> None:
        self._rows = sorted(rows, key=lambda r: (-r.get("pct", 0), r["project"]))
        self._rebuild()

    def _rebuild(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._rows:
            lbl = QLabel(t("chart.summary.empty"))
            lbl.setObjectName("Muted")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(lbl, 0, 0, 1, 3)
            return

        header = (
            t("chart.summary.col.project"),
            t("chart.summary.col.progress"),
            t("chart.summary.col.open_overdue"),
        )
        for c, text in enumerate(header):
            h = QLabel(text)
            h.setObjectName("Section")
            self._grid.addWidget(h, 0, c)

        for i, row in enumerate(self._rows, start=1):
            name = QLabel(row["project"])
            name.setObjectName("H2" if row.get("pct", 0) == 100 else "")
            self._grid.addWidget(name, i, 0)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(round(row.get("pct", 0))))
            bar.setFormat(fmt.pct(int(round(row.get("pct", 0)))))
            bar.setTextVisible(True)
            self._grid.addWidget(bar, i, 1)

            counts = QLabel(
                t("chart.summary.open", n=fmt.num(row.get("open", 0)))
                + (t("chart.summary.overdue", n=fmt.num(row["overdue"]))
                   if row.get("overdue") else "")
            )
            counts.setObjectName("Muted")
            self._grid.addWidget(counts, i, 2)

        self._grid.setRowStretch(len(self._rows) + 1, 1)
