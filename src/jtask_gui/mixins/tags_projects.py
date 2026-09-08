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
        def check() -> tuple[int, int]:
            return (
                taskwarrior.project_task_count(name),
                taskwarrior.project_deleted_count(name),
            )

        def ask(counts: tuple[int, int]) -> None:
            n, zombie = counts
            if n == 0:
                if zombie == 0:
                    self._toast.show_message(t("msg.project_empty", project=name))
                    return
                # nothing pending/completed left — just an already-deleted
                # task still naming this project, keeping it listed with
                # all-zero counts. Nothing user-visible is being destroyed,
                # so clean it up directly rather than asking for a
                # destructive confirm over 0 real tasks.
                self._write(
                    functools.partial(taskwarrior.delete_project, name),
                    t("msg.project_deleted", project=name),
                )
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

    # --- saved filters: toolbar dropdown + pinned chips + manager ----

    def _save_filter(self, name: str, raw: str) -> None:
        self.settings.save_filter(name, raw)
        self._refresh_saved_filters()
        self._toast.show_message(t("msg.filter_saved", name=name))

    def _rename_filter(self, old: str, new: str) -> None:
        self.settings.rename_filter(old, new)
        self._refresh_saved_filters()
        self._toast.show_message(t("msg.filter_renamed", name=new))

    def _delete_filter(self, name: str) -> None:
        self.settings.delete_filter(name)
        self._refresh_saved_filters()

    def _apply_saved_filter(self, raw: str) -> None:
        self._filter_bar.set_text(raw)
        self._filter_bar._apply()

    def _edit_saved_filter(self, raw: str) -> None:
        self._apply_saved_filter(raw)
        self._filter_bar._edit.setFocus()
        self._toast.show_message(t("msg.filter_edit_hint"))

    def _toggle_pin_filter(self, name: str) -> None:
        pinned = self.settings.pinned_filters()
        if name in pinned:
            pinned.remove(name)
        else:
            pinned.append(name)
        self.settings.set_pinned_filters(pinned)
        self._refresh_saved_filters()

    def _open_saved_filter_menu(self) -> None:
        from ..widgets.saved_filter_menu import SavedFilterMenu

        if self._saved_filter_menu is None:
            m = self._saved_filter_menu = SavedFilterMenu(self)
            m.filterActivated.connect(self._apply_saved_filter)
            m.editRequested.connect(self._edit_saved_filter)
            m.renameRequested.connect(self._rename_filter)
            m.deleteRequested.connect(self._delete_filter)
            m.pinToggled.connect(self._toggle_pin_filter)
            m.manageRequested.connect(self._open_filter_manager)
        self._populate_saved_filter_menu()
        btn = self._filters_btn
        self._saved_filter_menu.popup_at(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _open_filter_manager(self) -> None:
        from ..widgets.filter_manager import FilterManagerDialog

        dlg = FilterManagerDialog(self.settings, self)
        dlg.changed.connect(self._refresh_saved_filters)
        dlg.exec()

    def _populate_saved_filter_menu(self) -> None:
        if self._saved_filter_menu is None:
            return
        self._saved_filter_menu.set_data(
            self.settings.saved_filters(), self._saved_counts,
            self.settings.pinned_filters(), self.settings.filter_order(),
            self.settings.theme,
        )

    def _rebuild_pin_chips(self) -> None:
        from PyQt6.QtWidgets import QToolButton

        for chip in self._pin_chips:
            chip.deleteLater()
        self._pin_chips = []
        row2 = self._toolbars[1]
        saved = self.settings.saved_filters()
        for name in self.settings.pinned_filters():
            raw = saved.get(name)
            if raw is None:
                continue
            leaf = name.rpartition("/")[2]
            chip = QToolButton()
            chip.setObjectName("PinChip")
            chip.setText(leaf if len(leaf) <= 16 else leaf[:15] + "…")
            chip.setToolTip(f"{name}\n{raw}")
            chip.clicked.connect(lambda _c=False, r=raw: self._apply_saved_filter(r))
            row2.insertWidget(self._pin_anchor, chip)
            self._pin_chips.append(chip)

    def _refresh_saved_filters(self) -> None:
        self._rebuild_pin_chips()
        self._populate_saved_filter_menu()

    def _on_view_counts(self, counts: dict) -> None:
        self._sidebar.set_view_counts(counts)
        self._saved_counts = counts
        self._populate_saved_filter_menu()

