"""Editable description fields follow their content's direction, not the app's."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit

from jtask_gui.bidi import bind_auto_direction

LTR = Qt.LayoutDirection.LeftToRight
RTL = Qt.LayoutDirection.RightToLeft


@pytest.fixture
def _rtl_app(qapp):
    prev = qapp.layoutDirection()
    qapp.setLayoutDirection(RTL)          # simulate the Persian UI
    yield qapp
    qapp.setLayoutDirection(prev)


def test_line_edit_flips_with_content(_rtl_app):
    e = QLineEdit()
    bind_auto_direction(e)
    assert e.layoutDirection() == RTL     # empty → follow the app (fa = RTL)

    e.setText("Meeting with Arash")
    assert e.layoutDirection() == LTR

    e.setText("جلسه با آرش")
    assert e.layoutDirection() == RTL

    e.clear()
    assert e.layoutDirection() == RTL     # back to the app default


def test_ltr_app_empty_field_is_ltr(qapp):
    prev = qapp.layoutDirection()
    qapp.setLayoutDirection(LTR)
    try:
        e = QLineEdit()
        bind_auto_direction(e)
        assert e.layoutDirection() == LTR
        e.setText("خرید نان")
        assert e.layoutDirection() == RTL
    finally:
        qapp.setLayoutDirection(prev)


def test_wired_into_the_description_fields(_rtl_app, qtbot):
    from jtask_gui.widgets.task_form import TaskFormDialog

    d = TaskFormDialog("add")
    qtbot.addWidget(d)
    d._description.setText("Buy groceries")
    assert d._description.layoutDirection() == LTR
    d._description.setText("خرید مایحتاج")
    assert d._description.layoutDirection() == RTL
