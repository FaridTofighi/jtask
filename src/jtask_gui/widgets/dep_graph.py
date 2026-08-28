"""A small dependency graph: blockers → this task → dependents."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from ..theme import palette

_W, _H, _GAP_X, _GAP_Y = 150, 44, 24, 70


class DependencyGraph(QGraphicsView):
    def __init__(self, theme_name: str = "شب", parent=None) -> None:
        super().__init__(parent)
        self._theme = theme_name
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(self.renderHints())
        self.setMinimumHeight(150)
        self.setMaximumHeight(280)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def set_theme(self, name: str) -> None:
        self._theme = name

    def show_task(self, task: dict, all_tasks: list[dict]) -> None:
        scene = self.scene()
        scene.clear()
        pal = palette(self._theme)
        by_uuid = {t.get("uuid"): t for t in all_tasks}

        deps = task.get("depends") or []
        if isinstance(deps, str):
            deps = [d for d in deps.split(",") if d]
        blockers = [by_uuid[d] for d in deps if d in by_uuid]
        dependents = [
            t for t in all_tasks
            if task.get("uuid") in _dep_list(t)
        ]

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
                self._node(scene, t, x, y, colour, pal, big=(row == 0))
                centres[t.get("uuid")] = QPointF(x + _W / 2, y + _H / 2)

        pen = QPen(QColor(pal["text_muted"]))
        pen.setWidth(2)
        for b in blockers:
            self._edge(scene, centres[b["uuid"]], centres[task["uuid"]], pen)
        for d in dependents:
            self._edge(scene, centres[task["uuid"]], centres[d["uuid"]], pen)

        if not blockers and not dependents:
            note = QGraphicsSimpleTextItem("این کار وابستگی‌ای ندارد.")
            note.setBrush(QBrush(QColor(pal["text_muted"])))
            scene.addItem(note)

        rect = scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
        scene.setSceneRect(rect)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    # --- drawing ------------------------------------------------

    def _node(self, scene, task, x, y, colour, pal, big=False):
        rect = QRectF(x, y, _W, _H)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        item = QGraphicsPathItem(path)
        item.setBrush(QBrush(QColor(pal["surface"])))
        pen = QPen(QColor(colour))
        pen.setWidth(3 if task.get("status") == "pending" else 1)
        item.setPen(pen)
        scene.addItem(item)

        desc = (task.get("description") or "")[:22]
        label = QGraphicsSimpleTextItem(f"#{task.get('id', '?')}  {desc}")
        label.setBrush(QBrush(QColor(pal["text"])))
        label.setPos(x + 8, y + _H / 2 - 8)
        scene.addItem(label)

    def _edge(self, scene, a: QPointF, b: QPointF, pen: QPen):
        path = QPainterPath(a)
        mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
        path.quadTo(mid, b)
        line = QGraphicsPathItem(path)
        line.setPen(pen)
        scene.addItem(line)


def _dep_list(task: dict) -> list[str]:
    deps = task.get("depends") or []
    if isinstance(deps, str):
        return [d for d in deps.split(",") if d]
    return [str(d) for d in deps]
