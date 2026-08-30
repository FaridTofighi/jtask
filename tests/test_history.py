"""Parsing ``task <id> information`` — change log + time-tracking sessions."""

from __future__ import annotations

import datetime as dt

from jtask import history

SAMPLE = """
Name          Value
------------- ----------------------------------------
ID            1
Description   طراحی صفحه
                2026-08-30 08:15:00 با آرش هماهنگ شد
Status        Pending
Project       وب
Due           2026-08-31 00:00:00
UUID          b8d480bf-16ff-4a8c-8b18-bf0f32ce0da0
Urgency       21.1

Date                Modification
------------------- ---------------------------------------
2026-08-30 08:17:14 Description set to 'طراحی صفحه'.
                    Entry set to '2026-08-30 08:17:14'.
                    Status set to 'pending'.
2026-08-30 08:17:16 Priority set to 'L'.
2026-08-30 08:17:18 Priority changed from 'L' to 'H'.
2026-08-30 09:00:00 Annotation of 'با آرش هماهنگ شد' added.
2026-08-30 09:05:00 Tag 'فوری' added.
2026-08-30 10:00:00 Start set to '2026-08-30 10:00:00'.
2026-08-30 10:30:00 Start deleted (duration: 0:30:00).
2026-08-30 11:00:00 Start set to '2026-08-30 11:00:00'.
"""


def test_parses_attribute_table():
    rep = history.parse_information(SAMPLE)
    assert rep.attributes["Description"] == "طراحی صفحه"
    assert rep.attributes["Project"] == "وب"
    assert rep.attributes["UUID"].startswith("b8d480bf")


def test_change_log_is_chronological_with_per_transaction_time():
    rep = history.parse_information(SAMPLE)
    kinds = [(c.attr, c.kind) for c in rep.changes]
    assert ("Description", "set") in kinds
    assert ("Priority", "changed") in kinds
    first = rep.changes[0]
    assert first.when == dt.datetime(2026, 8, 30, 8, 17, 14)
    # the two 08:17:14 lines share the transaction timestamp
    assert rep.changes[1].when == dt.datetime(2026, 8, 30, 8, 17, 14)
    assert rep.changes[3].when == dt.datetime(2026, 8, 30, 8, 17, 16)


def test_priority_change_captures_old_and_new():
    rep = history.parse_information(SAMPLE)
    ch = next(c for c in rep.changes if c.kind == "changed" and c.attr == "Priority")
    assert ch.old == "L"
    assert ch.new == "H"
    assert ch.raw == "Priority changed from 'L' to 'H'."


def test_tag_and_annotation_changes():
    rep = history.parse_information(SAMPLE)
    tag = next(c for c in rep.changes if c.kind == "tag_added")
    assert tag.new == "فوری"
    ann = next(c for c in rep.changes if c.kind == "annotation_added")
    assert ann.new == "با آرش هماهنگ شد"


def test_sessions_from_start_stop_pairs():
    rep = history.parse_information(SAMPLE)
    assert len(rep.sessions) == 2
    s0 = rep.sessions[0]
    assert s0.start == dt.datetime(2026, 8, 30, 10, 0, 0)
    assert s0.end == dt.datetime(2026, 8, 30, 10, 30, 0)
    assert s0.duration == dt.timedelta(minutes=30)
    # the last 'Start set' has no matching delete → still running
    assert rep.sessions[1].end is None
    assert rep.sessions[1].running is True


def test_multi_day_duration_parses():
    text = """
Date                Modification
------------------- ------------------------
2026-08-28 09:00:00 Start set to '2026-08-28 09:00:00'.
2026-08-30 10:00:00 Start deleted (duration: 2 days, 1:00:00).
"""
    rep = history.parse_information(text)
    assert rep.sessions[0].duration == dt.timedelta(days=2, hours=1)
    assert rep.sessions[0].end == dt.datetime(2026, 8, 30, 10, 0, 0)


def test_no_modification_section_is_safe():
    rep = history.parse_information("Name  Value\nID  1\nDescription  x\n")
    assert rep.changes == []
    assert rep.sessions == []
    assert rep.attributes["Description"] == "x"
