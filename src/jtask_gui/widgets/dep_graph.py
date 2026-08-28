"""A small dependency graph: blockers → this task → dependents."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QLabel,
)

from ..theme import palette

_W, _H, _GAP_X, _GAP_Y = 150, 44, 24, 70


class DependencyGraph(QGraphicsView):
    def __init__(self, theme_name: str = "شب", parent=None) -> None:
        super().__init__(parent)
        self._theme = theme_name
        self._task: dict | None = None
        self._all: list[dict] = []
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMinimumHeight(140)
        self.setMaximumHeight(260)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # empty state is a plain overlay label sized to the viewport — never a
        # scene item scaled by fitInView()
        self._empty = QLabel("این کار وابستگی‌ای ندارد.", self.viewport())
        self._empty.setObjectName("DepEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.hide()

    # --- API -------------------------------------------------------

    def set_theme(self, name: str) -> None:
        self._theme = name
        if self._task is not None:
            self.show_task(self._task, self._all)

    def show_task(self, task: dict, all_tasks: list[dict]) -> None:
        self._task = task
        self._all = all_tasks
        self._relayout()

    # --- events ---------------------------------------------------

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._empty.setGeometry(self.viewport().rect())
        if self._task is not None:
            self._fit()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._empty.setGeometry(self.viewport().rect())
        if self._task is not None:
            self._fit()

    # --- layout -------------------------------------------------

    def _relayout(self) -> None:
        scene = self.scene()
        scene.clear()
        pal = palette(self._theme)
        task = self._task
        by_uuid = {t.get("uuid"): t for t in self._all}

        deps = _dep_list(task)
        blockers = [by_uuid[d] for d in deps if d in by_uuid]
        dependents = [t for t in self._all if task.get("uuid") in _dep_list(t)]

        if not blockers and not dependents:
            scene.setSceneRect(QRectF(0, 0, 10, 10))
            self._empty.setGeometry(self.viewport().rect())
            self._empty.raise_()
            self._empty.show()
            return
        self._empty.hide()

        rows = [
            (blockers, -1, pal["overdue"]),
            ([task], 0, pal["primary"]),
            (dependents, 1, pal["waiting"]),
        ]
        centres: dict[str, QPointF] = {}
        for items, row, colour in rows:
            total = len(items)
            for i, t in enumerate(items):
                x = (i - (total - 1) / 2) * (_W + _GAP_X)
                y = row * (_H + _GAP_Y)
                self._node(scene, t, x, y, colour, pal)
                centres[t.get("uuid")] = QPointF(x + _W / 2, y + _H / 2)

        pen = QPen(QColor(pal["text_muted"]))
        pen.setWidth(2)
        for b in blockers:
            self._edge(scene, centres[b["uuid"]], centres[task["uuid"]], pen)
        for d in dependents:
            self._edge(scene, centres[task["uuid"]], centres[d["uuid"]], pen)

        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-16, -16, 16, 16))
        self._fit()

    def _fit(self) -> None:
        rect = self.scene().sceneRect()
        if rect.isEmpty():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        # fitInView scales both ways — never magnify a small graph
        if self.transform().m11() > 1.0:
            self.resetTransform()

    # --- drawing ------------------------------------------------

    def _node(self, scene, task, x, y, colour, pal):
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, _W, _H), 8, 8)
        item = QGraphicsPathItem(path)
        item.setBrush(QBrush(QColor(pal["surface"])))
        pen = QPen(QColor(colour))
        pen.setWidth(3 if task.get("status") == "pending" else 1)
        item.setPen(pen)
        scene.addItem(item)

        desc = (task.get("description") or "")[:24]
        label = QGraphicsTextItem(f"#{task.get('id', '?')}  {desc}")
        label.setDefaultTextColor(QColor(pal["text"]))
        label.setTextWidth(_W - 14)
        label.setPos(x + 7, y + 5)
        scene.addItem(label)

    def _edge(self, scene, a: QPointF, b: QPointF, pen: QPen):
        path = QPainterPath(a)
        mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
        path.quadTo(mid, b)
        line = QGraphicsPathItem(path)
        line.setPen(pen)
        scene.addItem(line)


def _dep_list(task: dict | None) -> list[str]:
    deps = (task or {}).get("depends") or []
    if isinstance(deps, str):
        return [d for d in deps.split(",") if d]
    return [str(d) for d in deps]
