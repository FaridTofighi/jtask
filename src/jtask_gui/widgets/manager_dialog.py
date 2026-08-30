"""Taskwarrior management — Config / Context / UDA / Reports in one tabbed dialog.

Every write is a ``task config`` / ``task context`` call; ``.taskrc`` text is
never touched.  ``changed`` fires whenever any tab wrote something, so the main
window can refresh lookups and the current view.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout, QWidget

from ..i18n import t
from .config_manager import ConfigManager
from .context_manager import ContextManager
from .report_manager import ReportManager
from .uda_manager import UdaManager


class ManagerDialog(QDialog):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ManagerDialog")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowTitle(t("manage.title"))
        self.resize(760, 560)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        self._tabs = QTabWidget()
        self.config = ConfigManager()
        self.contexts = ContextManager()
        self.udas = UdaManager()
        self.reports = ReportManager()
        self._tabs.addTab(self.config, t("manage.tab.config"))
        self._tabs.addTab(self.contexts, t("manage.tab.contexts"))
        self._tabs.addTab(self.udas, t("manage.tab.udas"))
        self._tabs.addTab(self.reports, t("manage.tab.reports"))
        lay.addWidget(self._tabs, 1)

        for tab in (self.config, self.contexts, self.udas, self.reports):
            tab.changed.connect(self.changed)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.close"), QDialogButtonBox.ButtonRole.AcceptRole).clicked.connect(
            self.accept
        )
        lay.addWidget(btns)

        for tab in (self.config, self.contexts, self.udas, self.reports):
            tab.reload()
