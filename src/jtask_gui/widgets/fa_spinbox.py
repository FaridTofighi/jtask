"""QSpinBox that shows Persian digits when the digit mode is on."""

from __future__ import annotations

from PyQt6.QtWidgets import QSpinBox

from jtask import jalali

from .. import fmt


class FaSpinBox(QSpinBox):
    def textFromValue(self, value: int) -> str:  # noqa: N802
        return fmt.digits(str(value))

    def valueFromText(self, text: str) -> int:  # noqa: N802
        digits = "".join(c for c in jalali.normalize_digits(text) if c.isdigit() or c == "-")
        try:
            return int(digits)
        except ValueError:
            return self.value()

    def validate(self, text, pos):  # noqa: N802
        from PyQt6.QtGui import QValidator

        norm = jalali.normalize_digits(text)
        stripped = norm.replace(self.prefix(), "").replace(self.suffix(), "").strip()
        if stripped in ("", "-"):
            return QValidator.State.Intermediate, text, pos
        return (QValidator.State.Acceptable
                if stripped.lstrip("-").isdigit()
                else QValidator.State.Invalid), text, pos
