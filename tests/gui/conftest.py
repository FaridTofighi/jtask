"""Shared fixtures for the GUI test suite (headless)."""

from __future__ import annotations

import datetime
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import jdatetime  # noqa: E402
import pytest  # noqa: E402

from jtask import jalali, taskwarrior  # noqa: E402

TEHRAN = datetime.timezone(datetime.timedelta(hours=3, minutes=30))


@pytest.fixture(autouse=True)
def _tz(monkeypatch):
    monkeypatch.setattr(jalali, "LOCAL_TZ", TEHRAN)


@pytest.fixture
def tw_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKDATA", str(tmp_path / "td"))
    rc = tmp_path / "rc"
    rc.write_text("", encoding="utf-8")
    monkeypatch.setenv("TASKRC", str(rc))
    monkeypatch.setenv("JTASK_CONFIG_DIR", str(tmp_path / "cfg"))
    taskwarrior.refresh_lookups()
    yield
    taskwarrior.refresh_lookups()


@pytest.fixture
def today_1403_07_10():
    return jdatetime.date(1403, 7, 10)
