"""M7 data safety: export / import / sync dialogs, the config/tools managers,
and opening the add/edit task form.

Split out of ``main_window.py`` (mission: MainWindow decomposition,
2026-09-05) — a mixin composed by ``MainWindow``, not a standalone class.
Method bodies are unchanged; only their file location moved.
"""

from __future__ import annotations

import functools

from jtask import taskwarrior
from jtask.rtl import bidi_isolate

from .. import fmt
from ..i18n import t
from ..workers import submit


class DataSafetyMixin:
    def _open_export(self) -> None:
        from ..widgets.export_dialog import ExportDialog, write_export

        dlg = ExportDialog(self._extra_filter, self)
        if not dlg.exec():
            return
        spec = dlg.spec()
        if not spec["path"]:
            self.statusBar().showMessage(t("msg.export.no_path"), 2500)
            return
        self._begin_busy(t("op.exporting"))

        def done(res: dict) -> None:
            self._end_busy()
            self._op_status.success(t("msg.export.done"))
            self.statusBar().showMessage(
                t("msg.export.saved", n=fmt.num(res["count"]),
                  path=bidi_isolate(res["path"])), 5000
            )

        submit(functools.partial(write_export, spec), done, self._op_failed)

    def _open_import(self) -> None:
        from ..widgets.import_dialog import ImportDialog

        dlg = ImportDialog(self)
        if not dlg.exec():
            return
        path = dlg.path()
        self._begin_busy(t("op.importing"))

        def done(res: dict) -> None:
            self._end_busy()
            self._op_status.success(t("msg.import.done"))
            self.statusBar().showMessage(
                t("msg.import.summary", added=fmt.num(res["added"]),
                  modified=fmt.num(res["modified"])),
                5000,
            )
            self.refresh_all()

        submit(functools.partial(taskwarrior.import_file, path), done, self._op_failed)

    def _open_sync(self) -> None:
        from ..widgets.sync_dialog import SyncManagerDialog

        dlg = SyncManagerDialog(self.settings, self)
        dlg.synced.connect(self.refresh_all)
        dlg.exec()

    def _open_manager(self) -> None:
        from ..widgets.manager_dialog import ManagerDialog

        dlg = ManagerDialog(self)
        dlg.changed.connect(self.refresh_all)
        dlg.exec()

    def _open_tools(self) -> None:
        from ..widgets.tools_dialog import ToolsDialog

        dlg = ToolsDialog(self)
        dlg.sendToConsole.connect(self._send_to_console)
        dlg.exec()

    def _send_to_console(self, text: str) -> None:
        self._reveal_console()
        self._console.prefill(text)

    def _open_task_form(self, mode: str, *, project: str | None = None) -> None:
        from ..widgets.task_form import TaskFormDialog

        dlg = TaskFormDialog(
            mode, taskwarrior.list_projects(), taskwarrior.list_tags(), self,
            settings=self.settings,
        )
        if project:
            dlg._project.setCurrentText(project)
            dlg._description.setFocus()
        if not dlg.exec():
            return
        args = dlg.args()
        verb = taskwarrior.log if mode == "log" else taskwarrior.add
        self._write(
            functools.partial(verb, args),
            t("msg.log_added") if mode == "log" else t("msg.task_added"),
        )

