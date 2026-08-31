# Development / runtime environment

The GUI, its test suite, and the shipped screenshots assume the following. A
machine that drifts from this still *runs* jtask-gui, but the test numbers and
the chart-text rendering can differ — which historically read as "features not
implemented" when it was really an environment gap.

## Required

| Component | Expected | Why it matters |
|---|---|---|
| Python | ≥ 3.10 (`requires-python`) | — |
| Taskwarrior (`task`) | **≥ 3.5.0** | `docs/taskwarrior-feature-matrix.md` is written against 3.5.0 (libshared 14.2.0). Older versions mostly work; `tests/test_environment.py` skips (not fails) with a pointer here when it sees < 3.5. |
| PyQt6 | ≥ 6.6, **and no PyQt5 in the same interpreter** | Both bindings loaded together is an import-order / Qt-plugin hazard. |
| matplotlib | ≥ 3.8, **built against libraqm** | Without libraqm matplotlib does not shape/bidi-reorder Arabic script itself, so `charts/mpl_text.fa()` falls back to `arabic-reshaper` + `python-bidi`. Both code paths are covered by `tests/gui/test_chart_text.py`; only the *screenshots* assume the raqm path. Check with `python -c "from matplotlib import ft2font; print(ft2font.__libraqm_version__)"`. |
| qtawesome | ≥ 1.3 | toolbar / sidebar icons |
| jdatetime | ≥ 5.0 | Jalali math |
| arabic-reshaper, python-bidi | any recent | CLI terminal output + the no-libraqm chart path |

## Test dependencies

`pytest`, `ruff`, `mypy` — and **`pytest-qt`** for the GUI suite.

If `pytest-qt` is missing, `tests/gui/conftest.py` supplies minimal `qapp` /
`qtbot` stand-ins so the ~270 GUI tests still run headless. The stand-ins cover
only the sliver of the `qtbot` API the suite uses (`addWidget`, `wait`,
`waitSignal`, `waitUntil`); install `pytest-qt` for the real thing when you can.

Historically, a missing `pytest-qt` did **not** just skip the GUI tests — one
test (`test_m4.py::test_app_icon_loads`) built a `QIcon` with no live
`QGuiApplication` and Qt called `abort()`, killing the whole `pytest` process
mid-run. That test now requests the `qapp` fixture.

## Running everything

```
pip install -e ".[gui,dev]"          # or ensure the table above is satisfied
QT_QPA_PLATFORM=offscreen python -m pytest -q      # expect: 431 passed
ruff check .
mypy                                  # core only (src/jtask); see pyproject.toml
QT_QPA_PLATFORM=offscreen python -m jtask_gui      # headless smoke launch
```

`mypy` may report `Library stubs not installed for "yaml"` — install
`types-PyYAML` to silence it; it does not indicate a code problem.
