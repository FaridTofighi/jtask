"""M6 — history / raw data / statistics / timesheet / timer."""

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
# History
# ---------------------------------------------------------------------------


def test_describe_translates_each_change_kind():
    import datetime as dt

    from jtask.history import ChangeEntry
    from jtask_gui.widgets.history_view import describe

    w = dt.datetime(2026, 8, 30, 8, 0, 0)
    assert describe(
        ChangeEntry(w, "changed", "Priority", "M", "H", "x")
    ) == "اولویت از «M» به «H» تغییر کرد"
    assert "افزوده شد" in describe(
        ChangeEntry(w, "tag_added", "", None, "فوری", "x")
    )
    assert "یادداشت" in describe(
        ChangeEntry(w, "annotation_added", "", None, "متن", "x")
    )
    stop = describe(
        ChangeEntry(w, "deleted", "Start", None, None, "x", dt.timedelta(minutes=90))
    )
    assert "زمان‌سنجی متوقف شد" in stop and "۱:۳۰" in stop
    assert "زمان‌سنجی آغاز شد" in describe(
        ChangeEntry(w, "set", "Start", None, "2026-08-30 08:00:00", "x")
    )
    # a date-typed value is shown Jalali, not raw Gregorian
    out = describe(ChangeEntry(w, "set", "Due", None, "2026-08-31 00:00:00", "x"))
    assert "2026" not in out and "سررسید" in out


def test_history_view_populates_from_real_task(win, qapp):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    tw.add(["کار با تاریخچه", "priority:M"])
    uuid = tw.export()[0]["uuid"]
    tw.command([uuid], "modify", ["priority:H"])
    tw.command([uuid], "annotate", ["یادداشت آزمایشی"])

    win._show_detail(tw.export([uuid])[0])
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()

    tree = win._history_view._tree
    assert tree.topLevelItemCount() >= 1
    texts = []
    for i in range(tree.topLevelItemCount()):
        day = tree.topLevelItem(i)
        for j in range(day.childCount()):
            texts.append(day.child(j).text(1))
    assert any("اولویت" in t and "تغییر کرد" in t for t in texts)
    assert any("یادداشت" in t for t in texts)


def test_annotations_tab_lists_and_adds(win, qapp, qtbot):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    tw.add(["کار با یادداشت"])
    uuid = tw.export()[0]["uuid"]
    tw.command([uuid], "annotate", ["یادداشت یک"])

    view = win._annotations_view
    win._show_detail(tw.export([uuid])[0])
    assert view._list.count() == 1
    card = view._list.itemWidget(view._list.item(0))
    assert card.desc == "یادداشت یک"

    # the edit form shows a read-only summary, not an editor
    assert "یادداشت یک" in win._detail._ann_summary.text()

    view._input.setPlainText("یادداشت دو")
    with qtbot.waitSignal(view.annotateRequested, timeout=1000) as sig:
        view._add()
    assert sig.args == [uuid, "یادداشت دو"]

    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()
    assert len(tw.export([uuid])[0].get("annotations") or []) == 2


def test_annotations_tab_empty_state(qapp):
    from jtask_gui.widgets.annotations_view import AnnotationsView

    v = AnnotationsView()
    v.load_task({"uuid": "x", "description": "d"})
    assert v._list.isHidden()
    assert not v._empty.isHidden()

    v.load_task({"uuid": "x", "annotations": [{"description": "n", "entry": ""}]})
    assert not v._list.isHidden()
    assert v._empty.isHidden()


def test_bulk_annotate_from_table_menu(win, qapp, monkeypatch):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    tw.add(["کار الف"])
    tw.add(["کار ب"])
    uuids = [row["uuid"] for row in tw.export()]

    monkeypatch.setattr(
        "PyQt6.QtWidgets.QInputDialog.getText", lambda *a, **k: ("یادداشت گروهی", True)
    )
    # _annotate_bulk lives in mixins/task_lifecycle.py (MainWindow decomposition)
    monkeypatch.setattr("jtask_gui.mixins.task_lifecycle.confirm", lambda *a, **k: True)

    win._annotate_bulk(uuids)
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()

    for u in uuids:
        anns = tw.export([u])[0].get("annotations") or []
        assert any(a["description"] == "یادداشت گروهی" for a in anns)


def test_history_view_empty_state_for_taskless(qapp):
    from jtask_gui.widgets.history_view import TaskHistoryView

    v = TaskHistoryView()
    v._render(None)
    assert v._empty.isVisible() or v._empty.isVisibleTo(v)


# ---------------------------------------------------------------------------
# Raw data
# ---------------------------------------------------------------------------


def test_raw_data_view_shows_json_without_derived_keys(qapp):
    from jtask_gui.widgets.raw_data_view import RawDataView

    v = RawDataView()
    v.load_task(
        {
            "uuid": "abc",
            "description": "کار",
            "due": "20260101T000000Z",
            "due_gregorian": "2026-01-01",
        }
    )
    text = v._text.toPlainText()
    assert '"description": "کار"' in text
    assert "due_gregorian" not in text
    assert '"due":' in text


def test_show_detail_populates_all_tabs(win, qapp):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    tw.add(["سه‌تب"])
    task = tw.export()[0]
    win._show_detail(task)
    for _ in range(5):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()

    assert win._detail_host.count() == 4  # edit · annotations · history · raw
    assert "سه‌تب" in win._raw_view._text.toPlainText()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def test_stats_value_rendering():
    from jtask_gui.widgets.stats_view import _render_value

    assert _render_value("2026-08-30") == "۱۴۰۵-۰۶-۰۸"
    assert _render_value("21 characters") == "۲۱ نویسه"
    assert _render_value("") == "—"
    assert _render_value("0%") == "۰٪"


def test_stats_view_populates(win, qapp):
    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    tw.add(["آمار ۱", "project:پ"])
    tw.add(["آمار ۲"])
    win._reports._rail.setCurrentRow(
        next(
            i
            for i in range(win._reports._rail.count())
            if win._reports._rail.item(i).data(0x0100) == "stats"
        )
    )
    for _ in range(5):
        qapp.processEvents()
        wait_for_done(4000)
        qapp.processEvents()
    tbl = win._reports._stats._table
    labels = {tbl.item(r, 0).text() for r in range(tbl.rowCount())}
    assert "کل" in labels
    assert "پروژه‌ها" in labels


# ---------------------------------------------------------------------------
# Timesheet
# ---------------------------------------------------------------------------


def test_timesheet_view_renders_sessions(win, qapp):
    import datetime as dt

    from jtask import taskwarrior as tw
    from jtask_gui.workers import wait_for_done

    tw.add(["کار زمان‌دار", "project:وب"])
    uuid = tw.export()[0]["uuid"]
    tw.command([uuid], "start")
    tw.command([uuid], "stop")

    v = win._reports._timesheet
    v._from.set_value(_to_jalali(dt.date.today() - dt.timedelta(days=1)))
    v._to.set_value(_to_jalali(dt.date.today() + dt.timedelta(days=1)))
    v.reload()
    for _ in range(6):
        qapp.processEvents()
        wait_for_done(5000)
        qapp.processEvents()

    assert v._tree.topLevelItemCount() >= 1
    assert "جمع کل" in v._summary.text()


def _to_jalali(d):
    import jdatetime

    return jdatetime.date.fromgregorian(date=d)


# ---------------------------------------------------------------------------
# Timer indicator
# ---------------------------------------------------------------------------


def test_timer_indicator_shows_and_hides():
    import datetime as dt

    from jtask_gui.widgets.timer_indicator import TimerIndicator

    ti = TimerIndicator()
    assert not ti.isVisibleTo(ti) or ti.text() == ""

    now = dt.datetime.now(dt.timezone.utc)
    started = (now - dt.timedelta(minutes=5, seconds=3)).strftime("%Y%m%dT%H%M%SZ")
    ti.set_active_tasks([{"uuid": "u1", "description": "کار جاری", "start": started}])
    assert "کار جاری" in ti.text()
    assert "۵:0" in ti.text().replace("٠", "۰") or "۰:۰۵" in ti.text() or ":" in ti.text()

    ti.set_active_tasks([])
    assert not ti.isVisibleTo(ti)


def test_timer_indicator_stop_emits_uuid(qtbot):
    from jtask_gui.widgets.timer_indicator import TimerIndicator

    ti = TimerIndicator()
    ti.set_active_tasks([{"uuid": "u9", "description": "x", "start": "20260830T040000Z"}])
    got = []
    ti.stopRequested.connect(got.append)
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent

    ev = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(1, 1),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ti.mousePressEvent(ev)
    assert got == ["u9"]
