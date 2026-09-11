"""engine.inventory
===================

Models and utilities for tracking Antarctic station resource inventories.

The module is deliberately independent of navigation, cost, or optimisation
logic.  It provides a single ``ResourceInventory`` data‑class that can be used
to model any resource (diesel, food, medical supplies, etc.) and to answer the
following questions:

* How many days remain before the resource falls below its safety threshold.
* The exact UTC datetime when that threshold will be reached.
* The projected inventory level on an arbitrary future date.
* How much of the resource must be resupplied.
* What the inventory will look like after the resupply.

All calculations are deterministic, type‑annotated and validated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Final, Optional


# ---------------------------------------------------------------------------
# Helper validation functions
# ---------------------------------------------------------------------------

def _require_non_negative(value: float, name: str) -> float:
    """Raise ``ValueError`` if *value* is negative."""
    if value < 0:
        raise ValueError(f"{name} must be non‑negative (got {value!r})")
    return value


def _require_positive(value: float, name: str) -> float:
    """Raise ``ValueError`` if *value* is not strictly positive."""
    if value <= 0:
        raise ValueError(f"{name} must be > 0 (got {value!r})")
    return value


def _require_aware_utc(dt: datetime, name: str) -> datetime:
    """Ensure *dt* is timezone‑aware and expressed in UTC."""
    if dt.tzinfo is None:
        raise ValueError(f"{name} must be timezone‑aware")
    # Normalise to UTC for internal calculations
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Core model
# ---------------------------------------------------------------------------

@dataclass
class ResourceInventory:
    """
    Represents the inventory state of a single resource at an Antarctic station.

    Attributes
    ----------
    resource_name : str
        Human‑readable name of the resource (e.g. ``\"diesel\"``).
    current_quantity : float
        Current amount available (in ``unit``). Must be ≥ 0.
    unit : str
        Unit of measurement (e.g. ``\"litres\"`` or ``\"tonnes\"``).
    daily_consumption : float
        Expected consumption per UTC day. Zero indicates a non‑depleting resource.
    minimum_safety_threshold : float
        Quantity below which the resource is considered **critical**.
    required_resupply_quantity : float
        Amount that the planning process wishes to deliver on the next voyage.
        Must be ≥ 0.
    """

    resource_name: str
    current_quantity: float = field(metadata={"ge": 0})
    unit: str
    daily_consumption: float = field(metadata={"ge": 0})
    minimum_safety_threshold: float = field(metadata={"ge": 0})
    required_resupply_quantity: float = field(default=0.0, metadata={"ge": 0})

    def __post_init__(self) -> None:
        # Validate numeric fields
        _require_non_negative(self.current_quantity, "current_quantity")
        _require_non_negative(self.daily_consumption, "daily_consumption")
        _require_non_negative(self.minimum_safety_threshold, "minimum_safety_threshold")
        _require_non_negative(self.required_resupply_quantity, "required_resupply_quantity")

    # -----------------------------------------------------------------------
    # Public calculation methods
    # -----------------------------------------------------------------------

    def calculate_days_until_threshold(self) -> float:
        """
        Days remaining before the inventory reaches the safety threshold.

        Returns
        -------
        float
            Number of days (may be fractional).  ``0`` if the resource is already
            at or below the safety threshold. ``float('inf')`` if the daily
            consumption is zero and the quantity is above the threshold.
        """
        if self.current_quantity <= self.minimum_safety_threshold:
            return 0.0

        if self.daily_consumption == 0:
            # Never depletes
            return float("inf")

        delta = self.current_quantity - self.minimum_safety_threshold
        return delta / self.daily_consumption

    def calculate_critical_date(self, current_datetime: datetime) -> Optional[datetime]:
        """
        UTC datetime when the resource will first be **critical**.

        Parameters
        ----------
        current_datetime : datetime
            Current UTC, timezone‑aware datetime.

        Returns
        -------
        datetime | None
            Critical datetime in UTC, or ``None`` if the resource never reaches the
            threshold (zero consumption and quantity above threshold).
        """
        now_utc = _require_aware_utc(current_datetime, "current_datetime")
        days = self.calculate_days_until_threshold()

        if days == float("inf"):
            return None
        return now_utc + timedelta(days=days)

    def calculate_inventory_on_date(
        self,
        current_datetime: datetime,
        target_datetime: datetime,
    ) -> float:
        """
        Project the inventory level on ``target_datetime``.

        Parameters
        ----------
        current_datetime : datetime
            Current UTC, timezone‑aware datetime.
        target_datetime : datetime
            Future UTC, timezone‑aware datetime for which the projection is required.

        Returns
        -------
        float
            Projected quantity (never negative).  If the resource would deplete
            before the target date, the result is clamped at ``0``.
        """
        now_utc = _require_aware_utc(current_datetime, "current_datetime")
        tgt_utc = _require_aware_utc(target_datetime, "target_datetime")

        if tgt_utc <= now_utc:
            # No forward projection needed
            return max(0.0, self.current_quantity)

        elapsed_days = (tgt_utc - now_utc).total_seconds() / 86400.0

        if self.daily_consumption == 0:
            return self.current_quantity

        projected = self.current_quantity - self.daily_consumption * elapsed_days
        return max(0.0, projected)

    def calculate_required_resupply(self) -> float:
        """
        Determine how much of the resource must be delivered to satisfy the
        planned resupply request.

        Returns
        -------
        float
            ``required_resupply_quantity`` (always ≥ 0).
        """
        return self.required_resupply_quantity

    def calculate_inventory_after_resupply(self) -> float:
        """
        Compute the inventory level immediately after applying the planned
        resupply quantity.

        Returns
        -------
        float
            New inventory quantity (never negative).
        """
        new_quantity = self.current_quantity + self.required_resupply_quantity
        return max(0.0, new_quantity)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__: Final = ["ResourceInventory"]