"""M5 task-lifecycle verbs: delete, duplicate, append/prepend, annotate,
purge, bulk edit, start/stop, star, inline edit, save, undo, context.

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


class TaskLifecycleMixin:
    def _bulk(self, uuids: list[str], verb: str, msg: str) -> None:
        if not uuids:
            return
        self._write(functools.partial(taskwarrior.command, uuids, verb), msg)

    def _save_task_as_template(self, task: dict) -> None:
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self, t("form.template.save.title"), t("form.template.save.label")
        )
        if not (ok and name.strip()):
            return
        spec = {
            "description": task.get("description", ""),
            "project": task.get("project", "") or "",
            "tags": [x for x in (task.get("tags") or []) if not x.isupper()],
            "priority": task.get("priority", "") or "",
        }
        self.settings.save_template(name.strip(), spec)
        self._toast.show_message(t("msg.template_saved", name=name.strip()))

    # --- M5 task-lifecycle verbs --------------------------

    def _delete(self, uuids: list[str]) -> None:
        if not uuids:
            return
        if not confirm(
            self,
            title=t("confirm.delete.title"),
            body=(
                t("confirm.delete.body")
            ),
            count=len(uuids),
            destructive=True,
            confirm_label=t("confirm.delete.ok"),
        ):
            return
        self._bulk(uuids, "delete", t("msg.tasks_deleted"))

    def _duplicate(self, uuids: list[str]) -> None:
        if not uuids:
            return
        if len(uuids) == 1:
            self._begin_busy(t("op.duplicating"))

            def done(res: dict) -> None:
                self._end_busy()
                self._op_status.success(t("msg.duplicated"))
                new = res.get("id") or res.get("uuid") or ""
                self.statusBar().showMessage(
                    t("msg.duplicated_id", new=new) if new else t("msg.duplicated"), 3000
                )
                self.refresh_all()

            submit(
                functools.partial(taskwarrior.duplicate, uuids), done, self._op_failed
            )
        else:
            self._write(
                functools.partial(taskwarrior.command, uuids, "duplicate"),
                t("msg.duplicated_many"),
            )

    def _append_like(self, uuids: list[str], verb: str, title: str) -> None:
        if not uuids:
            return
        from PyQt6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(self, title, t("prompt.append.label"))
        text = text.strip()
        if not ok or not text:
            return
        if len(uuids) > 1 and not confirm(
            self,
            title=title,
            body=t("confirm.append.body", text=text, verb=title),
            count=len(uuids),
        ):
            return
        self._write(
            functools.partial(taskwarrior.command, uuids, verb, [text]),
            t("msg.description_updated"),
        )

    def _annotate_bulk(self, uuids: list[str]) -> None:
        if not uuids:
            return
        from PyQt6.QtWidgets import QInputDialog

        title = t("verb.annotate")
        text, ok = QInputDialog.getText(self, title, t("detail.annotation.new"))
        text = text.strip()
        if not ok or not text:
            return
        if len(uuids) > 1 and not confirm(
            self,
            title=title,
            body=t("confirm.append.body", text=text, verb=title),
            count=len(uuids),
        ):
            return
        self._write(
            functools.partial(taskwarrior.command, uuids, "annotate", [text]),
            t("msg.note_added"),
        )

    def _purge(self, uuids: list[str]) -> None:
        if not uuids:
            return
        if not confirm(
            self,
            title=t("confirm.purge.title"),
            body=(
                t("confirm.purge.body")
            ),
            count=len(uuids),
            destructive=True,
            confirm_label=t("confirm.purge.ok"),
            require_phrase=t("confirm.purge.phrase"),
        ):
            return
        self._write(
            functools.partial(taskwarrior.purge, uuids), t("msg.purged")
        )

    def _bulk_edit(self, uuids: list[str]) -> None:
        if not uuids:
            return
        from ..widgets.bulk_edit import BulkEditDialog

        dlg = BulkEditDialog(
            len(uuids),
            taskwarrior.list_projects(),
            taskwarrior.list_tags(),
            self,
        )
        if not dlg.exec():
            return
        mods = dlg.mods()
        if not mods:
            self.statusBar().showMessage(t("msg.no_change_selected"), 2000)
            return
        if len(uuids) > 1 and not confirm(
            self,
            title=t("confirm.bulk.title"),
            body=t("confirm.bulk.body", mods=" ".join(mods)),
            count=len(uuids),
        ):
            return
        self._write(
            functools.partial(taskwarrior.command, uuids, "modify", mods),
            t("msg.tasks_updated"),
        )

    def _start_stop(self, uuid: str, start: bool) -> None:
        self._write(
            functools.partial(taskwarrior.command, [uuid], "start" if start else "stop"),
            t("msg.timer_updated"),
        )

    def _toggle_star(self, uuid: str, on: bool) -> None:
        self._write(
            functools.partial(
                taskwarrior.command, [uuid], "modify",
                ["+starred" if on else "-starred"],
            ),
            t("msg.starred") if on else t("msg.unstarred"),
        )

    def _inline_edit(self, uuid: str, field: str, value: str) -> None:
        mod = f"{field}:{value}"  # empty value clears the attribute
        self._write(
            functools.partial(taskwarrior.command, [uuid], "modify", [mod]),
            t("msg.task_updated"),
        )

    def _save_task(self, uuid: str, mods: list[str]) -> None:
        # The detail panel already emits Taskwarrior-ready tokens: its Jalali
        # date pickers hand back Gregorian strings, so mods must NOT be run
        # through rewrite_args again (that would reject the Gregorian dates).
        self._write(
            functools.partial(taskwarrior.command, [uuid], "modify", mods),
            t("msg.task_updated"),
        )

    def _undo(self) -> None:
        """Show what the last transaction reverts, then confirm before applying."""
        self._begin_busy(t("op.undo_preparing"))
        submit(taskwarrior.undo_preview, self._confirm_undo, self._on_load_error)

    def _confirm_undo(self, preview: dict) -> None:
        self._end_busy()
        if preview.get("empty"):
            self._op_status.idle()
            self.statusBar().showMessage(t("msg.nothing_to_undo"), 2500)
            return
        ok = confirm(
            self,
            title=t("confirm.undo.title"),
            body=(
                t("confirm.undo.body")
            ),
            count=preview.get("count"),
            count_noun=t("confirm.undo.noun"),
            destructive=True,
            confirm_label=t("confirm.undo.ok"),
            details=preview.get("text"),
        )
        if ok:
            self._write(
                functools.partial(taskwarrior.run, ["undo"]), t("msg.undo_done")
            )

    def _change_context(self, name: str) -> None:
        self._write(
            functools.partial(taskwarrior.context_activate, name or None),
            t("msg.context_changed"),
        )

