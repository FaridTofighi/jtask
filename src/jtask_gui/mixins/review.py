"""Weekly-review wizard: open/step/exit.

Split out of ``main_window.py`` (mission: MainWindow decomposition,
2026-09-05) — a mixin composed by ``MainWindow``, not a standalone class.
Method bodies are unchanged; only their file location moved.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
)

from .. import fmt
from ..i18n import t
from ..workers import submit


class ReviewWizardMixin:
    def _build_review(self) -> None:
        from ..widgets.review_wizard import ReviewWizard

        self._review = ReviewWizard()
        self._review.stepEntered.connect(self._on_review_step)
        self._review.exited.connect(self._exit_review)
        self._review.addNextActionRequested.connect(
            lambda proj: self._open_task_form("add", project=proj)
        )
        self._review_active = False
        self._pre_review_spec: dict | None = None
        dock = QDockWidget(t("dock.review"), self)
        dock.setObjectName("ReviewDock")
        dock.setWidget(self._review)
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, dock)
        dock.setVisible(False)
        dock.visibilityChanged.connect(
            lambda vis: self._exit_review() if not vis and self._review_active else None
        )
        self._review_dock = dock

    def _open_review(self) -> None:
        import datetime

        from PyQt6.QtWidgets import QMessageBox

        at = 0
        started, step = self.settings.review_started, self.settings.review_step
        fresh = False
        if started:
            try:
                fresh = datetime.datetime.now() - datetime.datetime.fromisoformat(
                    started
                ) < datetime.timedelta(hours=48)
            except ValueError:
                fresh = False
        if fresh and step > 0 and not self._review_active:
            box = QMessageBox(self)
            box.setWindowTitle(t("review.resume.title"))
            box.setText(t("review.resume.body", n=fmt.num(step + 1)))
            resume = box.addButton(t("review.resume.yes"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(t("review.resume.restart"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            at = step if box.clickedButton() is resume else 0
        if at == 0:
            self.settings.review_started = datetime.datetime.now().isoformat(
                timespec="seconds"
            )
        if not self._review_active:
            self._pre_review_spec = dict(self._view_spec)
        self._review_active = True
        self._review_dock.setVisible(True)
        self._review_dock.raise_()
        self._review.start(at)

    def _on_review_step(self, index: int) -> None:
        key = self._review.key(index)
        self.settings.review_step = index
        if key == "reports":
            self._on_view_selected({"kind": "reports", "title": t("review.step.reports")})
            return
        from jtask.gtd import review_step, stuck_projects

        if key == "stuck_projects":
            # the dock lists the *stuck* projects; the table shows the pickable
            # work (next actions) so you can see which projects have none.
            self._on_view_selected({
                "kind": "filter", "key": "review_stuck",
                "title": t("review.step.stuck_projects"),
                "filter": review_step("next_actions").filter() or [],
            })
            submit(stuck_projects, self._review.show_stuck, lambda _e: None)
            return

        self._on_view_selected({
            "kind": "filter", "key": f"review_{key}",
            "title": t(f"review.step.{key}"),
            "filter": review_step(key).filter() or [],
        })

    def _exit_review(self) -> None:
        if not self._review_active:
            return
        self._review_active = False
        self.settings.review_step = 0
        self.settings.review_started = ""
        self._review_dock.setVisible(False)
        if self._pre_review_spec is not None:
            self._on_view_selected(self._pre_review_spec)
        self._toast.show_message(t("msg.review_closed"))

