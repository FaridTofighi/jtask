"""Kanban-style board management: switching, persistence, card drops.

Split out of ``main_window.py`` (mission: MainWindow decomposition,
2026-09-05) — a mixin composed by ``MainWindow``, not a standalone class.
Method bodies are unchanged; only their file location moved.
"""

from __future__ import annotations

import functools

from jtask import taskwarrior

from ..i18n import t
from ..workers import submit


class BoardsMixin:
    def _board_names(self) -> list[str]:
        from .. import boards as B

        return [b.name for b in B.all_builtins()] + list(self.settings.boards())

    def _resolve_board(self, name: str):
        from .. import boards as B

        spec = self.settings.boards().get(name)
        if spec is not None:
            return B.Board.from_dict({"name": name, **spec})
        for b in B.all_builtins():
            if b.name == name:
                return b
        return None

    def _persist_column_sort(self, col_index: int, order: str) -> None:
        """A per-column sort change is already applied live by BoardView. Save
        it for *user* boards through the normal board-persistence path;
        built-in presets are session-only (like their filters/titles/drops —
        duplicate the preset for a permanent change)."""
        board = self._board.current_board()
        if board is None:
            return
        user = self.settings.boards()
        if board.name in user:
            self.settings.save_board(
                board.name, {"columns": [c.to_dict() for c in board.columns]}
            )
        else:
            self._toast.show_message(t("board.sort.session_only"))

    def _toggle_board(self, on: bool) -> None:
        self._board_mode = on
        self._group_combo.setEnabled(not on)
        if on and self._board.current_board() is None:
            from ..boards import builtin_board
            self._board.set_board(builtin_board("gtd"))
        self._load_current_view()

    def _show_board(self, name: str) -> None:
        board = self._resolve_board(name)
        if board is None:
            return
        self._board.set_board(board)
        self._board_mode = True
        self._group_combo.setEnabled(False)
        self._board_action.setChecked(True)
        self._load_current_view()

    def _open_board_manager(self) -> None:
        from ..widgets.board_manager import BoardManagerDialog

        dlg = BoardManagerDialog(self.settings, self)
        dlg.changed.connect(self._on_boards_changed)
        dlg.exec()

    def _on_boards_changed(self) -> None:
        self._sidebar.populate_boards(self._board_names())
        cur = self._board.current_board()
        if self._board_mode and cur is not None:
            refreshed = self._resolve_board(cur.name)
            if refreshed is not None:
                self._board.set_board(refreshed)

    def _open_card(self, uuid: str) -> None:
        self._board_action.setChecked(False)  # back to the table

        def show(rows: list[dict]) -> None:
            if rows:
                self._show_detail(rows[0])

        submit(functools.partial(taskwarrior.export, [uuid]), show, self._error)

    def _board_drop(self, task: dict, drop: dict) -> None:
        from ..boards import compile_drop

        uuid = task.get("uuid")
        compiled = compile_drop(drop)
        if not uuid or compiled is None:
            return
        verb, mods = compiled
        self._write(
            functools.partial(taskwarrior.command, [uuid], verb, mods),
            t("msg.task_updated"),
        )

