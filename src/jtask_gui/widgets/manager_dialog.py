"""Taskwarrior management — Config / Context / UDA / Reports in one tabbed dialog.

Every write is a ``task config`` / ``task context`` call; ``.taskrc`` text is
never touched.  ``changed`` fires whenever any tab wrote something, so the main
window can refresh lookups and the current view.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout, QWidget

from .. import tokens as tok
from ..i18n import t
from .config_manager import ConfigManager
from .context_manager import ContextManager
from .hook_manager import HookManager
from .report_manager import ReportManager
from .uda_manager import UdaManager


class ManagerDialog(QDialog):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ManagerDialog")
        self.setWindowTitle(t("manage.title"))
        self.resize(760, 560)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*tok.INSET_PANEL)
        lay.setSpacing(tok.SP_10)

        self._tabs = QTabWidget()
        self.config = ConfigManager()
        self.contexts = ContextManager()
        self.udas = UdaManager()
        self.reports = ReportManager()
        self.hooks = HookManager()
        self._tabs.addTab(self.config, t("manage.tab.config"))
        self._tabs.addTab(self.contexts, t("manage.tab.contexts"))
        self._tabs.addTab(self.udas, t("manage.tab.udas"))
        self._tabs.addTab(self.reports, t("manage.tab.reports"))
        self._tabs.addTab(self.hooks, t("manage.tab.hooks"))
        lay.addWidget(self._tabs, 1)

        self._all_tabs = (self.config, self.contexts, self.udas, self.reports, self.hooks)
        for tab in self._all_tabs:
            tab.changed.connect(self.changed)

        btns = QDialogButtonBox()
        btns.addButton(t("btn.close"), QDialogButtonBox.ButtonRole.AcceptRole).clicked.connect(
            self.accept
        )
        lay.addWidget(btns)

        for tab in self._all_tabs:
            tab.reload()
