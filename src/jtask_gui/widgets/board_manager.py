"""Create / edit / delete / reorder boards and their columns."""

from __future__ import annotations

import copy

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from jtask import taskwarrior

from .. import boards as B
from .. import tokens as tok
from ..i18n import t
from ..theme import palette
from .filter_builder import FilterBuilder


def _arrow(text: str, slot) -> QToolButton:
    b = QToolButton()
    b.setText(text)
    b.clicked.connect(slot)
    return b


def _tags_str(xs: list[str]) -> str:
    return " ".join(xs)


def _tags_list(s: str) -> list[str]:
    return [x.lstrip("+-#") for x in s.split() if x.strip()]


class _ColorPicker(QWidget):
    """A row of swatches — "no colour" + one per ``boards.COLUMN_ACCENT_ROLES`` —
    each painted with the given theme's hue. Stores only the *role name*."""

    changed = pyqtSignal()

    def __init__(self, theme_name: str, parent=None) -> None:
        super().__init__(parent)
        pal = palette(theme_name)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tok.SP_4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QToolButton] = {}

        options = [("", t("board.color.none"), pal["field"])]
        options += [(r, t(f"board.color.{r}"), pal[r]) for r in B.COLUMN_ACCENT_ROLES]
        for role, label, hue in options:
            b = QToolButton()
            b.setCheckable(True)
            b.setToolTip(label)
            b.setFixedSize(20, 20)
            b.setStyleSheet(
                f"QToolButton {{ background:{hue}; border:1px solid {pal['border']};"
                f" border-radius:{tok.R_SM}px; }}"
                f"QToolButton:checked {{ border:2px solid {pal['text']}; }}"
            )
            self._buttons[role] = b
            self._group.addButton(b)
            lay.addWidget(b)
        lay.addStretch(1)
        self._group.buttonToggled.connect(self._on_toggle)

    def _on_toggle(self, _btn, checked: bool) -> None:
        if checked:
            self.changed.emit()

    def value(self) -> str | None:
        for role, b in self._buttons.items():
            if b.isChecked():
                return role or None
        return None

    def set_value(self, role: str | None) -> None:
        self._buttons.get(role or "", self._buttons[""]).setChecked(True)


class _ColumnHeaderPreview(QFrame):
    """A live thumbnail of the column header — accent strip + title — so the
    colour choice is visible before saving."""

    def __init__(self, theme_name: str, parent=None) -> None:
        super().__init__(parent)
        self._pal = palette(theme_name)
        self.setObjectName("ColHeaderPreview")
        self.setStyleSheet(
            f"QFrame#ColHeaderPreview {{ background:{self._pal['bg_alt']};"
            f" border:1px solid {self._pal['border_soft']};"
            f" border-radius:{tok.R_MD}px; }}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(tok.SP_6, tok.SP_6, tok.SP_6, tok.SP_6)
        v.setSpacing(tok.SP_4)
        self._strip = QFrame()
        self._strip.setFixedHeight(3)
        self._title = QLabel("")
        self._title.setStyleSheet(
            f"color:{self._pal['text_muted']}; font-weight:700;"
        )
        v.addWidget(self._strip)
        v.addWidget(self._title)
        self.show_header("", None)

    def show_header(self, title: str, role: str | None) -> None:
        self._title.setText(title or t("board.col.title"))
        hue = self._pal[role] if role in B.COLUMN_ACCENT_ROLES else "transparent"
        self._strip.setStyleSheet(f"background:{hue}; border-radius:2px;")


class _DropEditor(QWidget):
    """Edits one column's drop-action dict, from the bounded vocabulary."""

    changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tok.SP_6)

        self._type = QComboBox()
        for key in B.DROP_TYPES:
            self._type.addItem(t(f"board.drop.type.{key}"), key)
        self._type.currentIndexChanged.connect(self._on_type)
        lay.addWidget(self._type)

        self._stack = QStackedWidget()
        lay.addWidget(self._stack)

        # none
        self._stack.addWidget(QWidget())
        # tags
        w = QWidget()
        f = QVBoxLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self._add = QLineEdit()
        self._add.setPlaceholderText(t("board.drop.tags.add"))
        self._remove = QLineEdit()
        self._remove.setPlaceholderText(t("board.drop.tags.remove"))
        f.addWidget(self._add)
        f.addWidget(self._remove)
        self._stack.addWidget(w)
        # attr
        w = QWidget()
        f = QHBoxLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self._attr_field = QComboBox()
        for k in B.ATTR_FIELDS:
            self._attr_field.addItem(t(f"word.{k}"), k)
        self._attr_value = QLineEdit()
        self._attr_value.setPlaceholderText(t("word.name"))
        f.addWidget(self._attr_field)
        f.addWidget(self._attr_value, 1)
        self._stack.addWidget(w)
        # uda
        w = QWidget()
        f = QHBoxLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self._uda_name = QComboBox()
        try:
            for name in sorted(taskwarrior.uda_definitions()):
                self._uda_name.addItem(name, name)
        except Exception:  # noqa: BLE001
            pass
        self._uda_value = QLineEdit()
        f.addWidget(self._uda_name)
        f.addWidget(self._uda_value, 1)
        self._stack.addWidget(w)
        # verb
        w = QWidget()
        f = QHBoxLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self._verb = QComboBox()
        for v in B.VERBS:
            self._verb.addItem(t(f"board.verb.{v}"), v)
        f.addWidget(self._verb)
        f.addStretch(1)
        self._stack.addWidget(w)

        for widget in (self._add, self._remove, self._attr_value, self._uda_value):
            widget.textChanged.connect(lambda *_: self.changed.emit())
        for combo in (self._attr_field, self._uda_name, self._verb):
            combo.currentIndexChanged.connect(lambda *_: self.changed.emit())

    def _on_type(self) -> None:
        self._stack.setCurrentIndex(self._type.currentIndex())
        self.changed.emit()

    def load(self, drop: dict) -> None:
        dt = drop.get("type", "none")
        self._type.setCurrentIndex(max(0, self._type.findData(dt)))
        self._stack.setCurrentIndex(self._type.currentIndex())
        self._add.setText(_tags_str(drop.get("add", [])))
        self._remove.setText(_tags_str(drop.get("remove", [])))
        self._attr_field.setCurrentIndex(
            max(0, self._attr_field.findData(drop.get("field", "project")))
        )
        self._attr_value.setText(str(drop.get("value", "")) if dt == "attr" else "")
        self._uda_name.setCurrentIndex(max(0, self._uda_name.findData(drop.get("name", ""))))
        self._uda_value.setText(str(drop.get("value", "")) if dt == "uda" else "")
        self._verb.setCurrentIndex(max(0, self._verb.findData(drop.get("verb", "done"))))

    def value(self) -> dict:
        dt = self._type.currentData()
        if dt == "tags":
            return {"type": "tags", "add": _tags_list(self._add.text()),
                    "remove": _tags_list(self._remove.text())}
        if dt == "attr":
            return {"type": "attr", "field": self._attr_field.currentData(),
                    "value": self._attr_value.text().strip()}
        if dt == "uda":
            return {"type": "uda", "name": self._uda_name.currentData() or "",
                    "value": self._uda_value.text().strip()}
        if dt == "verb":
            return {"type": "verb", "verb": self._verb.currentData()}
        return {"type": "none"}


class BoardManagerDialog(QDialog):
    changed = pyqtSignal()

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BoardManager")
        self.setWindowTitle(t("board.manage.title"))
        self.setMinimumWidth(720)
        self._settings = settings
        self._user: dict[str, dict] = copy.deepcopy(settings.boards())
        self._order: list[str] = list(settings.board_order())
        self._current: str | None = None
        self._loading = False

        root = QHBoxLayout(self)
        root.setContentsMargins(*tok.INSET_DIALOG)
        root.setSpacing(tok.SP_12)

        # -- left: board list --
        left = QVBoxLayout()
        self._boards = QListWidget()
        self._boards.currentRowChanged.connect(self._select_board)
        left.addWidget(self._boards, 1)
        brow = QHBoxLayout()
        new_btn = QToolButton()
        new_btn.setText(t("board.manage.new"))
        new_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m = QMenu(new_btn)
        m.addAction(t("board.manage.new_blank")).triggered.connect(self._new_blank)
        for b in B.all_builtins():
            m.addAction(t("board.manage.from_preset", name=b.name)).triggered.connect(
                lambda _c=False, key=b.name: self._from_preset(key)
            )
        new_btn.setMenu(m)
        self._del_btn = QPushButton(t("btn.delete"))
        self._del_btn.clicked.connect(self._delete)
        self._up = _arrow("↑", lambda: self._move_board(-1))
        self._dn = _arrow("↓", lambda: self._move_board(1))
        for wdg in (new_btn, self._del_btn, self._up, self._dn):
            brow.addWidget(wdg)
        left.addLayout(brow)

        io_row = QHBoxLayout()
        self._export_btn = QPushButton(t("board.manage.export"))
        self._export_btn.clicked.connect(self._export)
        imp = QPushButton(t("board.manage.import"))
        imp.clicked.connect(self._import)
        io_row.addWidget(self._export_btn)
        io_row.addWidget(imp)
        left.addLayout(io_row)
        root.addLayout(left, 0)

        # -- right: columns of the selected board --
        right = QVBoxLayout()
        self._board_note = QLabel("")
        self._board_note.setObjectName("Muted")
        self._board_note.setWordWrap(True)
        right.addWidget(self._board_note)

        mid = QHBoxLayout()
        self._cols = QListWidget()
        self._cols.currentRowChanged.connect(self._select_col)
        self._cols.setMaximumWidth(200)
        mid.addWidget(self._cols)

        editor = QVBoxLayout()
        editor.setSpacing(tok.SP_6)
        self._col_title = QLineEdit()
        self._col_title.setPlaceholderText(t("board.col.title"))
        self._col_title.textChanged.connect(self._col_edited)
        editor.addWidget(QLabel(t("board.col.title")))
        editor.addWidget(self._col_title)
        editor.addWidget(QLabel(t("board.col.filter")))
        frow = QHBoxLayout()
        self._col_filter = QLineEdit()
        self._col_filter.setReadOnly(True)
        self._col_filter.textChanged.connect(self._col_edited)
        fbtn = QPushButton(t("board.col.filter.edit"))
        fbtn.clicked.connect(self._edit_filter)
        frow.addWidget(self._col_filter, 1)
        frow.addWidget(fbtn)
        editor.addLayout(frow)
        editor.addWidget(QLabel(t("board.col.drop")))
        self._drop = _DropEditor()
        self._drop.changed.connect(self._col_edited)
        editor.addWidget(self._drop)

        editor.addWidget(QLabel(t("board.col.color")))
        self._color = _ColorPicker(settings.theme)
        self._color.changed.connect(self._col_edited)
        editor.addWidget(self._color)

        self._preview = _ColumnHeaderPreview(settings.theme)
        editor.addWidget(self._preview)
        editor.addStretch(1)
        crow = QHBoxLayout()
        add_c = QPushButton(t("board.col.add"))
        add_c.clicked.connect(self._add_col)
        rm_c = QPushButton(t("board.col.remove"))
        rm_c.clicked.connect(self._remove_col)
        cu = _arrow("↑", lambda: self._move_col(-1))
        cd = _arrow("↓", lambda: self._move_col(1))
        for wdg in (add_c, rm_c, cu, cd):
            crow.addWidget(wdg)
        editor.addLayout(crow)
        mid.addLayout(editor, 1)
        right.addLayout(mid, 1)
        root.addLayout(right, 1)

        # NB-4 slot: export / import buttons are added here.
        self._button_row = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._button_row.button(QDialogButtonBox.StandardButton.Close).setText(t("btn.close"))
        self._button_row.rejected.connect(self.accept)
        right.addWidget(self._button_row)

        self._reload_board_list()
        self.resize(760, 480)

    # --- board list -------------------------------------------

    def _all_board_names(self) -> list[str]:
        builtins = [b.name for b in B.all_builtins()]
        return builtins + [n for n in self._order if n in self._user]

    def _is_builtin(self, name: str | None) -> bool:
        return name in {b.name for b in B.all_builtins()}

    def _reload_board_list(self, select: str | None = None) -> None:
        self._boards.blockSignals(True)
        self._boards.clear()
        names = self._all_board_names()
        for n in names:
            it = QListWidgetItem(n)
            if self._is_builtin(n):
                f = it.font()
                f.setItalic(True)
                it.setFont(f)
            self._boards.addItem(it)
        self._boards.blockSignals(False)
        target = select or (names[0] if names else None)
        if target in names:
            self._boards.setCurrentRow(names.index(target))

    def _select_board(self, row: int) -> None:
        names = self._all_board_names()
        if not (0 <= row < len(names)):
            self._current = None
            return
        self._current = names[row]
        builtin = self._is_builtin(self._current)
        self._del_btn.setEnabled(not builtin)
        self._up.setEnabled(not builtin)
        self._dn.setEnabled(not builtin)
        self._board_note.setText(
            t("board.manage.builtin_note") if builtin else t("board.manage.user_note")
        )
        self._load_columns()

    def _current_board_dict(self) -> dict | None:
        if self._current is None:
            return None
        if self._is_builtin(self._current):
            b = next(b for b in B.all_builtins() if b.name == self._current)
            return b.to_dict()
        return {"name": self._current, **self._user.get(self._current, {"columns": []})}

    def _new_blank(self) -> None:
        name, ok = QInputDialog.getText(self, t("board.manage.new_blank"), t("word.name"))
        name = name.strip()
        if not ok or not name or name in self._all_board_names():
            return
        self._user[name] = {"columns": [
            {"title": t("board.col.new"), "filter": "status:pending",
             "drop": {"type": "none"}}
        ]}
        self._order.append(name)
        self._persist()
        self._reload_board_list(name)

    def _from_preset(self, preset_name: str) -> None:
        src = next(b for b in B.all_builtins() if b.name == preset_name)
        name = preset_name
        i = 2
        while name in self._all_board_names():
            name = f"{preset_name} {i}"
            i += 1
        self._user[name] = {"columns": [c.to_dict() for c in src.columns]}
        self._order.append(name)
        self._persist()
        self._reload_board_list(name)

    def _delete(self) -> None:
        if self._current is None or self._is_builtin(self._current):
            return
        self._user.pop(self._current, None)
        self._order = [n for n in self._order if n != self._current]
        self._persist()
        self._reload_board_list()

    def _move_board(self, delta: int) -> None:
        if self._current is None or self._current not in self._order:
            return
        i = self._order.index(self._current)
        j = i + delta
        if 0 <= j < len(self._order):
            self._order[i], self._order[j] = self._order[j], self._order[i]
            self._persist()
            self._reload_board_list(self._current)

    # --- columns ---------------------------------------------

    def _load_columns(self) -> None:
        self._loading = True
        self._cols.clear()
        d = self._current_board_dict() or {"columns": []}
        for c in d["columns"]:
            self._cols.addItem(c.get("title", ""))
        self._loading = False
        if d["columns"]:
            self._cols.setCurrentRow(0)
        else:
            self._select_col(-1)

    def _select_col(self, row: int) -> None:
        d = self._current_board_dict()
        editable = self._current is not None and not self._is_builtin(self._current)
        cols = (d or {}).get("columns", [])
        active = editable and 0 <= row < len(cols)
        for w in (self._col_title, self._col_filter, self._drop, self._color):
            w.setEnabled(active)
        if not (0 <= row < len(cols)):
            self._loading = True
            self._col_title.clear()
            self._col_filter.clear()
            self._drop.load({"type": "none"})
            self._color.set_value(None)
            self._loading = False
            self._preview.show_header("", None)
            return
        self._loading = True
        col = cols[row]
        self._col_title.setText(col.get("title", ""))
        self._col_filter.setText(col.get("filter", ""))
        self._drop.load(col.get("drop") or {"type": "none"})
        self._color.set_value(col.get("color"))
        self._loading = False
        self._preview.show_header(col.get("title", ""), col.get("color"))

    def _col_edited(self, *_a) -> None:
        if self._loading or self._current is None or self._is_builtin(self._current):
            return
        row = self._cols.currentRow()
        cols = self._user[self._current]["columns"]
        if not (0 <= row < len(cols)):
            return
        cols[row] = {
            "title": self._col_title.text().strip() or t("board.col.new"),
            "filter": self._col_filter.text().strip(),
            "drop": self._drop.value(),
        }
        color = self._color.value()
        if color:
            cols[row]["color"] = color
        it = self._cols.item(row)
        if it is not None:
            it.setText(cols[row]["title"])
        self._preview.show_header(cols[row]["title"], color)
        self._persist()

    def _edit_filter(self) -> None:
        dlg = FilterBuilder(self._col_filter.text().strip(), self)
        dlg.applied.connect(lambda _tok, raw: self._col_filter.setText(raw))
        dlg.exec()

    def _add_col(self) -> None:
        if self._current is None or self._is_builtin(self._current):
            return
        self._user[self._current]["columns"].append(
            {"title": t("board.col.new"), "filter": "status:pending",
             "drop": {"type": "none"}}
        )
        self._persist()
        self._load_columns()
        self._cols.setCurrentRow(self._cols.count() - 1)

    def _remove_col(self) -> None:
        if self._current is None or self._is_builtin(self._current):
            return
        row = self._cols.currentRow()
        cols = self._user[self._current]["columns"]
        if 0 <= row < len(cols) and len(cols) > 1:
            cols.pop(row)
            self._persist()
            self._load_columns()

    def _move_col(self, delta: int) -> None:
        if self._current is None or self._is_builtin(self._current):
            return
        row = self._cols.currentRow()
        cols = self._user[self._current]["columns"]
        j = row + delta
        if 0 <= row < len(cols) and 0 <= j < len(cols):
            cols[row], cols[j] = cols[j], cols[row]
            self._persist()
            self._load_columns()
            self._cols.setCurrentRow(j)

    # --- export / import -----------------------------------

    def _export(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        d = self._current_board_dict()
        if d is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, t("board.manage.export"), f"{self._current}.json",
            "JSON (*.json)",
        )
        if not path:
            return
        board = B.Board.from_dict(d)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(B.to_json(board))

    def _import(self) -> None:
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        path, _ = QFileDialog.getOpenFileName(
            self, t("board.manage.import"), "", "JSON (*.json)",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                board = B.from_json(fh.read())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, t("board.manage.import"),
                                t("board.manage.import.bad", err=str(exc)))
            return
        name = board.name or t("board.col.new")
        i = 2
        while name in self._all_board_names():
            name = f"{board.name} {i}"
            i += 1
        self._user[name] = {"columns": [c.to_dict() for c in board.columns]}
        self._order.append(name)
        self._persist()
        self._reload_board_list(name)

    # --- persistence ----------------------------------------

    def _persist(self) -> None:
        for name, spec in self._user.items():
            self._settings.save_board(name, spec)
        for name in list(self._settings.boards()):
            if name not in self._user:
                self._settings.delete_board(name)
        self._settings.set_board_order([n for n in self._order if n in self._user])
        self.changed.emit()
