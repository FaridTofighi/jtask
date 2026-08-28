"""Themed 'coming soon' panel for the Reports & Charts area (M1)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ReportsPlaceholder(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Placeholder")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        title = QLabel("گزارش‌ها و نمودارها")
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel("به‌زودی")
        badge.setObjectName("Badge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setMaximumWidth(120)

        body = QLabel(
            "در گام بعدی این بخش شامل نمودارهای تعاملی می‌شود:\n\n"
            "• نمودار سوختن (روزانه/هفتگی/ماهانه)\n"
            "• تاریخچه و گراف تاریخچه (افزوده/تکمیل/حذف)\n"
            "• خلاصهٔ پیشرفت پروژه‌ها\n"
            "• تقویم جلالی تعاملی با نمای تراکم روزها\n\n"
            "همهٔ محورها و برچسب‌ها جلالی و متناسب با پوستهٔ فعال خواهند بود."
        )
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)

        lay.addStretch(1)
        lay.addWidget(title)
        lay.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(body)
        lay.addStretch(2)
