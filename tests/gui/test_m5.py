"""M5 — task-lifecycle command parity + cross-cutting error handling."""

from __future__ import annotations

import pytest


@pytest.fixture
def win(qapp, qtbot, tw_env):
    from PyQt6.QtCore import QSettings

    QSettings("jtask", "jtask-gui").clear()
    from jtask_gui.main_window import MainWindow
    from jtask_gui.settings import Settings
    from jtask_gui.workers import wait_for_done

    w = MainWindow(Settings())
    w.resize(1200, 780)
    qtbot.addWidget(w)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()
    yield w
    wait_for_done(4000)


# ---------------------------------------------------------------------------
# Feature 1 — real error surfacing (exit code + stderr), no crash
# ---------------------------------------------------------------------------


def test_worker_failed_emits_the_exception_object(qapp):
    from jtask.errors import TaskCommandError
    from jtask_gui.workers import submit, wait_for_done

    got: list = []

    def boom():
        raise TaskCommandError(
            "اجرای Taskwarrior ناموفق بود (کد 1).",
            returncode=1,
            stderr="No tasks specified.",
            cmd=["task", "999", "modify"],
        )

    submit(boom, lambda r: None, got.append)
    wait_for_done(3000)
    qapp.processEvents()

    assert len(got) == 1
    assert isinstance(got[0], TaskCommandError)
    assert "No tasks specified." in got[0].details()


def test_worker_failed_still_delivers_plain_jtask_errors(qapp):
    from jtask.errors import JtaskError
    from jtask_gui.workers import submit, wait_for_done

    got: list = []
    submit(
        lambda: (_ for _ in ()).throw(JtaskError("خطای ساده")),
        lambda r: None,
        got.append,
    )
    wait_for_done(3000)
    qapp.processEvents()
    assert len(got) == 1
    assert str(got[0]) == "خطای ساده"


def test_error_dialog_renders_message_and_hidden_details(qapp):
    from jtask_gui.widgets.error_dialog import ErrorDialog

    dlg = ErrorDialog(
        "اجرای Taskwarrior ناموفق بود (کد 1).",
        details="$ task 999 modify\nexit code: 1\n\nNo tasks specified.",
    )
    assert "کد 1" in dlg.message_text()
    assert not dlg.details_visible()
    dlg.set_details_visible(True)
    assert dlg.details_visible()
    assert "No tasks specified." in dlg.details_text()


def test_error_dialog_copies_details_to_clipboard(qapp):
    from jtask_gui.widgets.error_dialog import ErrorDialog

    dlg = ErrorDialog("خطا", details="DETAIL-BLOB-123")
    dlg.copy_details()
    assert "DETAIL-BLOB-123" in qapp.clipboard().text()


def test_error_dialog_open_console_invokes_callback_and_closes(qapp):
    from jtask_gui.widgets.error_dialog import ErrorDialog

    fired: list = []
    dlg = ErrorDialog("خطا", details="d", on_open_console=lambda: fired.append(1))
    dlg.open_console()
    assert fired == [1]
    assert not dlg.isVisible()


def test_error_dialog_without_details_is_plain(qapp):
    from jtask_gui.widgets.error_dialog import ErrorDialog

    dlg = ErrorDialog("فقط پیام")
    assert dlg.copy_button() is None
    assert dlg.details_toggle() is None


def test_main_window_routes_task_command_error_to_rich_dialog(win, monkeypatch):
    import jtask_gui.main_window as mw
    from jtask.errors import TaskCommandError

    captured: dict = {}

    class FakeDialog:
        def __init__(self, message, details=None, parent=None, on_open_console=None):
            captured["message"] = message
            captured["details"] = details
            captured["has_console_cb"] = on_open_console is not None

        def exec(self):
            return 0

    monkeypatch.setattr(mw, "ErrorDialog", FakeDialog)
    win._error(
        TaskCommandError(
            "اجرای Taskwarrior ناموفق بود (کد 2).",
            returncode=2,
            stderr="The expression could not be evaluated.",
            cmd=["task", "rc.x=y", "bad"],
        )
    )
    assert "کد 2" in captured["message"]
    assert "could not be evaluated" in captured["details"]
    assert captured["has_console_cb"] is True


def test_failed_write_surfaces_real_taskwarrior_error(win, qapp):
    """A modify against a non-existent id must show TW's own message, not crash."""
    import jtask_gui.main_window as mw

    seen: list = []
    monkeypatch_target = mw.ErrorDialog

    class Capture(monkeypatch_target):  # type: ignore[misc, valid-type]
        def __init__(self, message, details=None, **kw):
            seen.append((message, details))

        def exec(self):
            return 0

    mw.ErrorDialog = Capture
    try:
        from jtask_gui.workers import wait_for_done

        win._write(
            lambda: __import__("jtask").taskwarrior.command(["999999"], "modify", ["project:x"]),
            "نباید موفق شود",
        )
        wait_for_done(4000)
        qapp.processEvents()
    finally:
        mw.ErrorDialog = monkeypatch_target

    assert seen, "error dialog was never shown"
    msg, details = seen[0]
    assert details and "No tasks specified." in details


# ---------------------------------------------------------------------------
# Feature 2 — GUI-enforced confirmation layer + operation status
# ---------------------------------------------------------------------------


def test_confirm_dialog_shows_affected_count_in_persian(qapp):
    from jtask_gui.widgets.confirm import ConfirmDialog

    d = ConfirmDialog(title="حذف", body="کارهای انتخاب‌شده حذف شوند؟", count=3)
    assert "۳" in d.body_text()
    assert d._confirm_btn.isEnabled()


def test_hard_confirm_requires_typing_the_exact_phrase(qapp):
    from jtask_gui.widgets.confirm import ConfirmDialog

    d = ConfirmDialog(
        title="پاک‌سازی",
        body="کارهای حذف‌شده برای همیشه پاک می‌شوند.",
        count=5,
        destructive=True,
        require_phrase="پاک‌سازی",
    )
    assert not d._confirm_btn.isEnabled()
    d._phrase_edit.setText("پاک‌ساز")
    assert not d._confirm_btn.isEnabled()
    d._phrase_edit.setText("پاک‌سازی")
    assert d._confirm_btn.isEnabled()
    d._phrase_edit.setText("چیز دیگر")
    assert not d._confirm_btn.isEnabled()


def test_confirm_helper_maps_dialog_result_to_bool(qapp, monkeypatch):
    from jtask_gui.widgets import confirm

    monkeypatch.setattr(confirm.ConfirmDialog, "exec", lambda self: 1)
    assert confirm.confirm(None, title="t", body="b") is True
    monkeypatch.setattr(confirm.ConfirmDialog, "exec", lambda self: 0)
    assert confirm.confirm(None, title="t", body="b") is False


def test_operation_status_transitions(qapp):
    from jtask_gui.widgets.op_status import OperationStatus

    w = OperationStatus()
    assert w.state == "idle"
    w.running("در حال حذف…")
    assert w.state == "running" and "حذف" in w.text()
    w.failed("شکست خورد")
    assert w.state == "failed" and "شکست" in w.text()
    w.success("انجام شد")
    assert w.state == "success"
    w.idle()
    assert w.state == "idle" and w.text() == ""


def test_write_shows_failed_state_and_never_crashes(win, qapp, monkeypatch):
    import jtask_gui.main_window as mw
    from jtask_gui.workers import wait_for_done

    monkeypatch.setattr(mw, "ErrorDialog", lambda *a, **k: type("D", (), {"exec": lambda s: 0})())
    win._write(
        lambda: __import__("jtask").taskwarrior.command(["424242"], "modify", ["+x"]),
        "نباید",
    )
    wait_for_done(4000)
    qapp.processEvents()
    assert win._op_status.state == "failed"


# ---------------------------------------------------------------------------
# Feature 3 — undo with preview (broad, not only after bulk)
# ---------------------------------------------------------------------------


def test_undo_preview_reports_count_and_leaves_state_untouched(tw_env):
    from jtask import taskwarrior as tw

    assert tw.undo_preview()["empty"] is True

    tw.add(["کار الف"])
    tw.command(["1"], "modify", ["priority:H"])
    prev = tw.undo_preview()
    assert prev["empty"] is False
    assert prev["count"] >= 1
    assert "would be reverted" in prev["text"]
    # answering 'no' must not have applied anything
    assert tw.export()[0]["priority"] == "H"


def test_undo_flow_shows_confirm_with_preview_then_applies(win, qapp, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui import main_window as mw
    from jtask_gui.workers import wait_for_done

    tw.add(["کار واگرد"])
    tw.command(["1"], "modify", ["priority:H"])

    seen: dict = {}

    def fake_confirm(parent, **kw):
        seen.update(kw)
        return True

    monkeypatch.setattr(mw, "confirm", fake_confirm)
    win._undo()
    wait_for_done(4000)
    qapp.processEvents()
    wait_for_done(4000)
    qapp.processEvents()

    assert seen.get("count", 0) >= 1
    assert "would be reverted" in (seen.get("details") or "")
    # undo actually ran → priority modification reverted
    assert "priority" not in tw.export()[0]


def test_undo_flow_noop_when_nothing_to_undo(win, qapp, monkeypatch):
    from jtask_gui import main_window as mw
    from jtask_gui.workers import wait_for_done

    called = []
    monkeypatch.setattr(mw, "confirm", lambda *a, **k: called.append(1) or True)
    win._undo()
    wait_for_done(4000)
    qapp.processEvents()
    assert called == []


# ---------------------------------------------------------------------------
# Feature 4 — lifecycle verbs: append / prepend / duplicate / purge + delete
# ---------------------------------------------------------------------------


def test_taskwarrior_purge_returns_count(tw_env):
    from jtask import taskwarrior as tw

    tw.add(["دور ریختنی"])
    uuid = tw.export()[0]["uuid"]
    tw.command([uuid], "delete")
    assert tw.purge([uuid]) == 1
    assert tw.export(["status:deleted"]) == []


def test_taskwarrior_duplicate_reports_new_identifier(tw_env):
    from jtask import taskwarrior as tw

    tw.add(["اصل", "priority:H"])
    uuid = tw.export()[0]["uuid"]
    res = tw.duplicate([uuid], ["project:کپی"])
    assert res["id"] or res["uuid"]
    rows = tw.export(["project:کپی"])
    assert len(rows) == 1 and rows[0]["priority"] == "H"


def test_bulk_edit_dialog_emits_only_touched_fields(qapp):
    from jtask_gui.widgets.bulk_edit import BulkEditDialog

    d = BulkEditDialog(3, ["خانه", "کار"], ["مهم"])
    assert d.mods() == []

    d._priority.set_value("H")
    d._project.setCurrentText("خانه")
    d._add_tags.setText("خرید فوری")
    d._del_tags.setText("مهم")
    mods = d.mods()
    assert "priority:H" in mods
    assert "project:خانه" in mods
    assert "+خرید" in mods and "+فوری" in mods
    assert "-مهم" in mods


def test_bulk_edit_dialog_clear_priority_and_date(qapp):
    from jtask_gui.widgets.bulk_edit import BulkEditDialog

    d = BulkEditDialog(1)
    d._priority.set_value("__clear__")
    d._due._clear.setChecked(True)
    mods = d.mods()
    assert "priority:" in mods
    assert "due:" in mods


def test_bulk_edit_dialog_until_row(qapp):
    import datetime

    from jtask_gui.widgets.bulk_edit import BulkEditDialog

    d = BulkEditDialog(2)
    d._until._clear.setChecked(True)
    assert "until:" in d.mods()

    d2 = BulkEditDialog(2)
    d2._until._picker.set_value(datetime.date(2026, 9, 4))
    tok = [m for m in d2.mods() if m.startswith("until:")]
    assert tok == ["until:2026-09-04"]


def test_delete_flow_confirms_then_deletes(win, qapp, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui import main_window as mw
    from jtask_gui.workers import wait_for_done

    tw.add(["حذف‌شونده"])
    uuid = tw.export()[0]["uuid"]

    monkeypatch.setattr(mw, "confirm", lambda *a, **k: False)
    win._delete([uuid])
    wait_for_done(3000)
    qapp.processEvents()
    assert tw.export([uuid])[0]["status"] == "pending"

    monkeypatch.setattr(mw, "confirm", lambda *a, **k: True)
    win._delete([uuid])
    wait_for_done(3000)
    qapp.processEvents()
    assert tw.export([uuid])[0]["status"] == "deleted"


def test_duplicate_flow_creates_a_second_task(win, qapp):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    tw.add(["یگانه"])
    uuid = tw.export()[0]["uuid"]
    win._duplicate([uuid])
    wait_for_done(4000)
    qapp.processEvents()
    assert len(tw.export(["description:یگانه"])) == 2


def test_append_flow_updates_description(win, qapp, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    tw.add(["پایه"])
    uuid = tw.export()[0]["uuid"]
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QInputDialog.getText", lambda *a, **k: ("دنباله", True)
    )
    win._append_like([uuid], "append", "افزودن به شرح")
    wait_for_done(4000)
    qapp.processEvents()
    assert tw.export([uuid])[0]["description"] == "پایه دنباله"


def test_purge_flow_requires_confirm_and_removes_deleted_task(win, qapp, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui import main_window as mw
    from jtask_gui.workers import wait_for_done

    tw.add(["رفتنی"])
    uuid = tw.export()[0]["uuid"]
    tw.command([uuid], "delete")

    monkeypatch.setattr(mw, "confirm", lambda *a, **k: False)
    win._purge([uuid])
    wait_for_done(3000)
    qapp.processEvents()
    assert len(tw.export(["status:deleted"])) == 1

    monkeypatch.setattr(mw, "confirm", lambda *a, **k: True)
    win._purge([uuid])
    wait_for_done(3000)
    qapp.processEvents()
    assert tw.export(["status:deleted"]) == []


def test_bulk_edit_flow_applies_mods_to_all_selected(win, qapp, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui import main_window as mw
    from jtask_gui.workers import wait_for_done

    tw.add(["گروهی الف"])
    tw.add(["گروهی ب"])
    uuids = [t["uuid"] for t in tw.export()]

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def mods(self):
            return ["priority:M", "+بازبینی"]

    monkeypatch.setattr("jtask_gui.widgets.bulk_edit.BulkEditDialog", FakeDialog)
    monkeypatch.setattr(mw, "confirm", lambda *a, **k: True)
    win._bulk_edit(uuids)
    wait_for_done(4000)
    qapp.processEvents()
    for t in tw.export():
        assert t["priority"] == "M"
        assert "بازبینی" in t.get("tags", [])


# ---------------------------------------------------------------------------
# Feature 5 — full Add Task dialog + Log completed task
# ---------------------------------------------------------------------------


def test_task_form_builds_tokens_from_fields(qapp, today_1403_07_10, monkeypatch):
    import jdatetime

    from jtask_gui.widgets.task_form import TaskFormDialog

    monkeypatch.setattr(jdatetime.date, "today", staticmethod(lambda: today_1403_07_10))
    d = TaskFormDialog("add", ["خانه"], ["مهم"])
    d._description.setText("تعمیر شیر آب")
    d._project.setCurrentText("خانه")
    d._tags.set_tags(["فوری"])
    d._priority.set_value("H")
    d._dates["due"].set_value(jdatetime.date(1403, 7, 12))

    args = d.args()
    assert args[0] == "تعمیر شیر آب"
    assert "project:خانه" in args
    assert "+فوری" in args
    assert "priority:H" in args
    assert "due:2024-10-03" in args  # 1403-07-12 → Gregorian


def test_task_form_requires_description(qapp):
    from jtask_gui.widgets.task_form import TaskFormDialog

    d = TaskFormDialog("add")
    assert not d._ok.isEnabled()
    d._description.setText("یک کار")
    assert d._ok.isEnabled()


def test_task_form_recur_requires_due(qapp):
    from jtask_gui.widgets.task_form import TaskFormDialog

    d = TaskFormDialog("add")
    d._description.setText("جلسهٔ هفتگی")
    d._recur.set_value("weekly")
    d._revalidate()
    assert not d._ok.isEnabled()
    import jdatetime

    d._dates["due"].set_value(jdatetime.date(1403, 7, 20))
    d._revalidate()
    assert d._ok.isEnabled()


def test_task_form_recur_template_fills_fields(qapp, qtbot, monkeypatch):
    from jtask_gui.widgets.task_form import TaskFormDialog
    from jtask_gui.workers import wait_for_done

    d = TaskFormDialog("add")
    qtbot.addWidget(d)

    monkeypatch.setattr(
        "jtask.reports.recurring_templates",
        lambda *a, **k: [
            {"description": "آبیاری", "recur": "weekly", "project": "خانه",
             "tags": ["گیاه"], "due": "", "due_gregorian": "", "uuid": "u1"}
        ],
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QInputDialog.getItem",
        lambda *a, **k: ("آبیاری  ·  weekly", True),
    )

    d._pick_recur_template()
    for _ in range(5):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()

    assert d._description.text() == "آبیاری"
    assert d._project.currentText() == "خانه"
    assert "گیاه" in d._tags.tags()
    assert d._recur.value() == "weekly"


def test_task_form_log_mode_runs_log(qapp, monkeypatch):
    from jtask_gui.widgets.task_form import TaskFormDialog

    d = TaskFormDialog("log")
    assert "انجام‌شده" in d.windowTitle()
    d._description.setText("کاری که کردم")
    calls = {}
    monkeypatch.setattr(
        "jtask.taskwarrior.log", lambda args: calls.setdefault("args", args) or "ok"
    )
    d.run()
    assert calls["args"][0] == "کاری که کردم"


def test_add_form_flow_creates_task_with_gregorian_due(win, qapp, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    class FakeForm:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def args(self):
            return ["کار فرم", "priority:M", "due:2024-10-01"]

    monkeypatch.setattr("jtask_gui.widgets.task_form.TaskFormDialog", FakeForm)
    win._open_task_form("add")
    wait_for_done(4000)
    qapp.processEvents()

    rows = tw.export(["description:کار فرم"])
    assert len(rows) == 1
    assert rows[0]["priority"] == "M"
    # due:2024-10-01 reached Taskwarrior verbatim (local midnight → UTC)
    from jtask import jalali

    assert jalali.from_taskwarrior(rows[0]["due"], fmt="short") == "۱۴۰۳-۰۷-۱۰"


def test_log_form_flow_creates_completed_task(win, qapp, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    class FakeForm:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def args(self):
            return ["ثبت‌شده", "project:بایگانی"]

    monkeypatch.setattr("jtask_gui.widgets.task_form.TaskFormDialog", FakeForm)
    win._open_task_form("log")
    wait_for_done(4000)
    qapp.processEvents()

    rows = tw.export(["description:ثبت‌شده"])
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
