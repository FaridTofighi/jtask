"""Drag-and-drop reassignment, tag rename/remove, project rename/delete/
colour, and saved-filter CRUD.

Split out of ``main_window.py`` (mission: MainWindow decomposition,
2026-09-05) — a mixin composed by ``MainWindow``, not a standalone class.
Method bodies are unchanged; only their file location moved.
"""

from __future__ import annotations

import functools

from jtask import taskwarrior

from ..i18n import t
from ..widgets.confirm import confirm
from ..workers import submit


class TagsProjectsMixin:
    def _reassign_project(self, uuids: list[str], project: str) -> None:
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", [f"project:{project}"]),
            t("msg.moved_to_project", project=project),
        )

    def _reschedule(self, uuids: list[str], gregorian: str) -> None:
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", [f"due:{gregorian}"]),
            t("msg.due_updated"),
        )

    # --- tag management -----------------------------------

    def _add_tag_to(self, uuids: list[str], tag: str) -> None:
        """Drop tasks onto a sidebar tag → add that tag to them."""
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", [f"+{tag}"]),
            t("msg.tagged", tag=tag),
        )

    def _rename_tag(self, old: str, new: str) -> None:
        def check() -> int:
            return taskwarrior.tag_count(old)

        def ask(n: int) -> None:
            if n == 0:
                self._toast.show_message(t("msg.tag_unused", tag=old))
                return
            if not confirm(
                self,
                title=t("sidebar.tag_rename.title"),
                body=t("confirm.tag_rename.body", old=old, new=new),
                count=n,
                count_noun=t("confirm.tag.noun"),
            ):
                return
            self._write(
                functools.partial(taskwarrior.rename_tag, old, new),
                t("msg.tag_renamed", old=old, new=new),
            )

        submit(check, ask, self._error)

    def _remove_tag(self, tag: str) -> None:
        def check() -> int:
            return taskwarrior.tag_count(tag)

        def ask(n: int) -> None:
            if n == 0:
                self._toast.show_message(t("msg.tag_unused", tag=tag))
                return
            if not confirm(
                self,
                title=t("sidebar.tag_remove.title"),
                body=t("confirm.tag_remove.body", tag=tag),
                count=n,
                count_noun=t("confirm.tag.noun"),
                destructive=True,
            ):
                return
            self._write(
                functools.partial(taskwarrior.remove_tag, tag),
                t("msg.tag_removed", tag=tag),
            )

        submit(check, ask, self._error)

    # --- project management ------------------------------

    def _rename_project(self, old: str, new: str) -> None:
        def check() -> int:
            return taskwarrior.project_task_count(old)

        def ask(n: int) -> None:
            if n == 0:
                self._toast.show_message(t("msg.project_empty", project=old))
                return
            if not confirm(
                self,
                title=t("sidebar.project_rename.title"),
                body=t("confirm.project_rename.body", old=old, new=new),
                count=n,
                count_noun=t("confirm.tag.noun"),
            ):
                return
            self._write(
                functools.partial(taskwarrior.rename_project, old, new),
                t("msg.project_renamed", old=old, new=new),
            )

        submit(check, ask, self._error)

    def _delete_project(self, name: str) -> None:
        def check() -> int:
            return taskwarrior.project_task_count(name)

        def ask(n: int) -> None:
            if n == 0:
                self._toast.show_message(t("msg.project_empty", project=name))
                return
            if not confirm(
                self,
                title=t("sidebar.project_delete.title"),
                body=t("confirm.project_delete.body", project=name),
                count=n,
                count_noun=t("confirm.tag.noun"),
                destructive=True,
                require_phrase=name,
            ):
                return
            self._write(
                functools.partial(taskwarrior.delete_project, name),
                t("msg.project_deleted", project=name),
            )

        submit(check, ask, self._error)

    def _set_project_color(self, name: str, color: str) -> None:
        self._write(
            functools.partial(taskwarrior.set_project_color, name, color),
            t("msg.project_colored", project=name),
        )

    def _clear_project_color(self, name: str) -> None:
        self._write(
            functools.partial(taskwarrior.clear_project_color, name),
            t("msg.project_color_cleared", project=name),
        )

    def _save_filter(self, name: str, raw: str) -> None:
        self.settings.save_filter(name, raw)
        self._sidebar.populate_saved_filters(self.settings.saved_filters())
        self._toast.show_message(t("msg.filter_saved", name=name))

    def _rename_filter(self, old: str, new: str) -> None:
        self.settings.rename_filter(old, new)
        self._sidebar.populate_saved_filters(self.settings.saved_filters())
        self._toast.show_message(t("msg.filter_renamed", name=new))

    def _delete_filter(self, name: str) -> None:
        self.settings.delete_filter(name)
        self._sidebar.populate_saved_filters(self.settings.saved_filters())

    def _apply_saved_filter(self, raw: str) -> None:
        self._filter_bar.set_text(raw)
        self._filter_bar._apply()

