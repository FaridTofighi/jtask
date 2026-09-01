"""Filter bar: raw-string translation + shared autocomplete source."""

from jtask_gui.widgets.autocomplete import build_vocabulary
from jtask_gui.widgets.filter_bar import FilterBar


def test_current_filter_rewrites_jalali_dates(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar.set_text("project:وب due.before:1403.08.01")
    assert bar.current_filter() == ["project:وب", "due.before:2024-10-22"]


def test_empty_filter_is_empty_list(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    assert bar.current_filter() == []


def test_filter_changed_signal(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    got = []
    bar.filterChanged.connect(got.append)
    bar.set_text("+مهم")
    bar._apply()
    assert got == [["+مهم"]]


def test_emptying_the_field_resets_the_view(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    got = []
    bar.filterChanged.connect(got.append)

    bar.set_text("meeting")
    bar._apply()
    assert got[-1] == ["meeting"]

    # user deletes what they typed → back to the unfiltered view, no Enter needed
    bar._edit.setText("")
    assert got[-1] == []

    bar._edit.setText("   ")   # whitespace-only counts as empty too
    assert got[-1] == []


def test_vocabulary_comes_from_shared_lists():
    vocab = build_vocabulary(["وب", "خانه"], ["مهم", "بعدی"], uda_names=["reviewed"])
    assert "project:وب" in vocab
    assert "+مهم" in vocab and "-بعدی" in vocab
    assert "reviewed:" in vocab
    assert "due.before:" in vocab


def test_widget_autocomplete_uses_taskwarrior_lookups(qtbot, tw_env, monkeypatch):
    from jtask import taskwarrior

    monkeypatch.setattr(taskwarrior, "list_projects", lambda: ["Alpha"])
    monkeypatch.setattr(taskwarrior, "list_tags", lambda: ["beta"])
    monkeypatch.setattr(taskwarrior, "uda_definitions", lambda: {})
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar.refresh_completions()
    model = bar._edit.completer().model()
    entries = {model.data(model.index(i, 0)) for i in range(model.rowCount())}
    assert "project:Alpha" in entries
    assert "+beta" in entries
