"""A simulated shipping service: an address lookup and a flaky rate service.

Nothing here talks to the network. Failures, hangs and slowness are all
scripted, so every run of the lesson behaves the same way and finishes in
about two seconds.
"""

import asyncio
from collections.abc import Callable


# region errors
class RateServiceUnavailable(ConnectionError):
    """A transient failure: the rate service is down for a moment.

    Trying again a little later can succeed, so this error is worth retrying.
    """


class ParcelTooHeavy(ValueError):
    """A bad request: the parcel is over the weight limit.

    The same request fails the same way every time, so retrying never helps.
    """


# endregion

ZONES = {"london": "UK", "manchester": "UK", "paris": "EU", "berlin": "EU"}
RATES_PER_KG = {"UK": 4.0, "EU": 7.5}
MAX_WEIGHT_KG = 30.0
# One step of the slow tariff calculation, in seconds.
STEP_S = 0.025
# How long a "hung" call sleeps. A timeout cancels it long before that. It is
# bounded so that a missing timeout shows up as a 5 s stall, not a frozen run.
HANG_S = 5.0


# region shipping_api
class ShippingApi:
    """A stand-in for two external APIs, with counters to see how often they run."""

    def __init__(self, rate_failures: int = 0, rate_hangs: int = 0, rate_steps: int = 0) -> None:
        """Create the API; the arguments script how the rate service misbehaves.

        The next `rate_failures` calls to `get_rate` fail with
        RateServiceUnavailable, then the service recovers.
        """
        self.rate_failures = rate_failures
        # rate_hangs scripts the next N calls to hang (never answer), like
        # rate_failures does for outages.
        self.rate_hangs = rate_hangs
        # rate_steps is how many STEP_S steps every call works through before
        # answering (0 = instant).
        self.rate_steps = rate_steps
        self.zone_lookups = 0  # how many times the "expensive" lookup really ran
        self.rate_calls = 0  # how many times the rate service was called

    def lookup_zone(self, address: str) -> str:
        """Turn an address into a shipping zone (think of a geocoding API)."""
        self.zone_lookups += 1
        # The city is the text after the last comma: "12 Baker Street, London".
        city = address.rsplit(",", 1)[-1].strip().lower()
        return ZONES[city]

    async def get_rate(
        self,
        zone: str,
        weight_kg: float,
        on_progress: Callable[[], None] | None = None,
    ) -> float:
        """Ask the rate service for the price of a parcel (a network call).

        Many SDKs take a progress callback like `on_progress`. The service
        calls it after every finished step of the calculation. The service
        knows nothing about LangGraph.
        """
        self.rate_calls += 1
        # The weight check comes first, so a too-heavy parcel fails the same
        # way whether or not the service is "down".
        if weight_kg > MAX_WEIGHT_KG:
            raise ParcelTooHeavy(f"parcel too heavy: {weight_kg} kg")
        if self.rate_failures > 0:
            self.rate_failures -= 1
            raise RateServiceUnavailable("rate service unavailable (503)")
        if self.rate_hangs > 0:
            self.rate_hangs -= 1
            # A hang: the call never answers. Only a timeout that cancels
            # this await gets the caller out of here early.
            await asyncio.sleep(HANG_S)
        # The slow path: work through the tariff step by step and report
        # progress after every step.
        for _ in range(self.rate_steps):
            await asyncio.sleep(STEP_S)
            if on_progress is not None:
                on_progress()
        return RATES_PER_KG[zone] * weight_kg


# endregion
