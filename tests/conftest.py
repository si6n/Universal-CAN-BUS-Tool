"""Shared pytest fixtures for the Universal CAN-Bus Diagnostic test suite.

H-29 (KOD_REVIEW_RAPORU-1, sec. 4.5 / 6 FAZ 2): time-dependent assertions must
not depend on the granularity of the host's real monotonic clock.

Why this exists
--------------
GitHub Actions ``windows-latest`` runners are Hyper-V guests whose
``QueryPerformanceCounter`` is emulated at the legacy timer tick (~15.625 ms).
On such a host two ``time.monotonic_ns()`` reads separated by a real
``time.sleep(0.01)`` can return the *identical* value, so a duration assertion
like ``assert duration_ns >= 5_000_000`` fails with ``assert 0 >= 5000000``.
That is precisely how CI run 33187380425 (commit d205a85) broke two tests that
pass on developer workstations.

Tests that assert *durations* therefore drive an explicit virtual clock via the
``monotonic_clock`` fixture instead of sleeping for real.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

# Observed monotonic granularity on Hyper-V emulated-QPC CI runners.
CI_MONOTONIC_GRANULARITY_NS = 15_625_000

_NS_PER_SECOND = 1_000_000_000


class VirtualMonotonicClock:
    """A monotonic nanosecond source the test can advance on demand.

    The clock is *clamped* to the real monotonic source, so it can only ever
    run ahead of wall progress, never behind it. That keeps every blocking
    primitive that observes ``time.monotonic`` (queue timeouts, condition
    waits, I/O loops) making real progress while the fixture is installed,
    which makes the patch safe to apply process-wide.
    """

    def __init__(self, real_monotonic_ns: Callable[[], int]) -> None:
        self._real_monotonic_ns = real_monotonic_ns
        self._virtual_ns = real_monotonic_ns()
        self.reads = 0

    @property
    def now_ns(self) -> int:
        """Current virtual time, never behind real monotonic time."""
        real = self._real_monotonic_ns()
        if real > self._virtual_ns:
            self._virtual_ns = real
        return self._virtual_ns

    def read_ns(self) -> int:
        """Drop-in replacement for ``time.monotonic_ns``."""
        self.reads += 1
        return self.now_ns

    def read_s(self) -> float:
        """Drop-in replacement for ``time.monotonic``."""
        return self.now_ns / _NS_PER_SECOND

    def advance_ns(self, delta_ns: int) -> None:
        """Move the virtual clock forward by ``delta_ns`` nanoseconds."""
        if delta_ns < 0:
            raise ValueError("virtual clock cannot move backwards")
        self._virtual_ns = self.now_ns + delta_ns

    def sleep(self, seconds: float) -> None:
        """Deterministic stand-in for ``time.sleep``: jumps the clock forward."""
        if seconds < 0:
            raise ValueError("virtual clock cannot move backwards")
        self.advance_ns(int(seconds * _NS_PER_SECOND))


@pytest.fixture
def monotonic_clock(monkeypatch: pytest.MonkeyPatch) -> VirtualMonotonicClock:
    """Patch ``time.monotonic_ns``/``time.monotonic`` with a controllable clock.

    Use ``monotonic_clock.sleep(0.01)`` wherever the test previously slept for
    real; duration assertions then hold on any host clock granularity.
    """
    clock = VirtualMonotonicClock(real_monotonic_ns=time.monotonic_ns)
    monkeypatch.setattr(time, "monotonic_ns", clock.read_ns)
    monkeypatch.setattr(time, "monotonic", clock.read_s)
    return clock
