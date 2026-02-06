"""ConstraintValidator: checks options against user constraints."""

from __future__ import annotations

from maestro.models import Constraint, ConstraintStatus, Option, Violation


class ConstraintValidator:
    """Validates options against user-defined constraints and attaches violations."""

    def validate(self, options: list[Option], constraint: Constraint) -> list[Option]:
        """Check each option against constraints. Mutates options in place, also returns them."""
        for option in options:
            option.violations = []
            option.status = ConstraintStatus.PASS
            self._check_budget(option, constraint)
            self._check_quality(option, constraint)
            self._check_time(option, constraint)
            option.status = self._overall_status(option.violations)
        return options

    def _check_budget(self, option: Option, constraint: Constraint) -> None:
        if constraint.budget_max is None:
            return
        if option.cost > constraint.budget_max:
            delta_pct = ((option.cost / constraint.budget_max) - 1) * 100
            option.violations.append(Violation(
                constraint="budget",
                limit=constraint.budget_max,
                actual=option.cost,
                delta_pct=round(delta_pct, 1),
            ))

    def _check_quality(self, option: Option, constraint: Constraint) -> None:
        if constraint.quality_min is None:
            return
        if option.quality < constraint.quality_min:
            delta_pct = ((constraint.quality_min / max(option.quality, 0.01)) - 1) * 100
            option.violations.append(Violation(
                constraint="quality",
                limit=constraint.quality_min,
                actual=option.quality,
                delta_pct=round(delta_pct, 1),
            ))

    def _check_time(self, option: Option, constraint: Constraint) -> None:
        if constraint.time_max is None:
            return
        if option.time_seconds > constraint.time_max:
            delta_pct = ((option.time_seconds / constraint.time_max) - 1) * 100
            option.violations.append(Violation(
                constraint="time",
                limit=float(constraint.time_max),
                actual=float(option.time_seconds),
                delta_pct=round(delta_pct, 1),
            ))

    def _overall_status(self, violations: list[Violation]) -> ConstraintStatus:
        if not violations:
            return ConstraintStatus.PASS
        if all(v.delta_pct < 10 for v in violations):
            return ConstraintStatus.PARTIAL
        return ConstraintStatus.FAIL
