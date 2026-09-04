"""Triage mode: rapid accept/reject/edit/delete over a filtered queue.

Split out of ``main_window.py`` (mission: MainWindow decomposition,
2026-09-05) — a mixin composed by ``MainWindow``, not a standalone class.
Method bodies are unchanged; only their file location moved.
"""

from __future__ import annotations

import functools

from jtask import reports, taskwarrior

from ..i18n import t
from ..widgets.confirm import confirm
from ..workers import submit


class TriageModeMixin:
    def _start_triage(self, column_index: int | None = None) -> None:
        import shlex

        from ..boards import builtin_board

        board = self._board.current_board() or builtin_board("gtd")
        if column_index is not None and 0 <= column_index < len(board.columns):
            col = board.columns[column_index]
        else:  # default: the first "view only" column (Inbox), else the first
            col = next(
                (c for c in board.columns if c.drop.get("type", "none") == "none"),
                board.columns[0] if board.columns else None,
            )
        if col is None:
            return
        tokens = shlex.split(col.filter)

        def loaded(rows: list[dict]) -> None:
            self._triage.set_projects(taskwarrior.list_projects())
            self._triage.start(board, rows)
            self._pre_triage_spec = dict(self._view_spec)
            self._content.setCurrentIndex(3)

        self._begin_busy(t("status.loading"))
        submit(
            functools.partial(reports.report_list, tokens),
            lambda rows: (self._end_busy(), loaded(rows)),
            self._on_load_error,
        )

    def _triage_decision(self, uuid: str, verb: str, mods: list) -> None:
        self._write(
            functools.partial(taskwarrior.command, [uuid], verb, mods),
            t("msg.task_updated"), refresh=False, then=self._triage.advance,
        )

    def _triage_project(self, uuid: str, project: str) -> None:
        self._write(
            functools.partial(taskwarrior.command, [uuid], "modify", [f"project:{project}"]),
            t("msg.task_updated"), refresh=False, then=self._triage.advance,
        )

    def _triage_delete(self, uuid: str) -> None:
        if not confirm(
            self,
            title=t("confirm.delete.title"),
            body=t("confirm.delete.body"),
            count=1,
            destructive=True,
            confirm_label=t("confirm.delete.ok"),
        ):
            return
        self._write(
            functools.partial(taskwarrior.command, [uuid], "delete"),
            t("msg.tasks_deleted"), refresh=False, then=self._triage.advance,
        )

    def _triage_edit(self, uuid: str) -> None:
        self._return_to_triage = True
        self._content.setCurrentIndex(0)
        submit(
            functools.partial(taskwarrior.export, [uuid]),
            lambda rows: self._show_detail(rows[0]) if rows else None,
            self._error,
        )

    def _after_triage_edit(self) -> None:
        if not self._return_to_triage:
            return
        self._return_to_triage = False
        self._content.setCurrentIndex(3)
        self._triage.advance()

    def _exit_triage(self) -> None:
        self._return_to_triage = False
        self._content.setCurrentIndex(0)
        if getattr(self, "_pre_triage_spec", None) is not None:
            self._on_view_selected(self._pre_triage_spec)
        else:
            self.refresh_all()

