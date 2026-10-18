"""A simulated shipping service: an address lookup and a flaky rate service.

Nothing here talks to the network. The failures are scripted, so every run
of the lesson behaves the same way and finishes in well under a second.
"""


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


# region shipping_api
class ShippingApi:
    """A stand-in for two external APIs, with counters to see how often they run."""

    def __init__(self, rate_failures: int = 0) -> None:
        """Create the API; `rate_failures` scripts an outage of the rate service.

        The next `rate_failures` calls to `get_rate` fail with
        RateServiceUnavailable, then the service recovers.
        """
        self.rate_failures = rate_failures
        self.zone_lookups = 0  # how many times the "expensive" lookup really ran
        self.rate_calls = 0  # how many times the rate service was called

    def lookup_zone(self, address: str) -> str:
        """Turn an address into a shipping zone (think of a geocoding API)."""
        self.zone_lookups += 1
        # The city is the text after the last comma: "12 Baker Street, London".
        city = address.rsplit(",", 1)[-1].strip().lower()
        return ZONES[city]

    async def get_rate(self, zone: str, weight_kg: float) -> float:
        """Ask the rate service for the price of a parcel (a network call)."""
        self.rate_calls += 1
        # The weight check comes first, so a too-heavy parcel fails the same
        # way whether or not the service is "down".
        if weight_kg > MAX_WEIGHT_KG:
            raise ParcelTooHeavy(f"parcel too heavy: {weight_kg} kg")
        if self.rate_failures > 0:
            self.rate_failures -= 1
            raise RateServiceUnavailable("rate service unavailable (503)")
        return RATES_PER_KG[zone] * weight_kg


# endregion
