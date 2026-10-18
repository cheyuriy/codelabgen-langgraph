"""The "map" task: price one order line. It knows nothing about orders."""

import time
from typing import TypedDict

PRICES: dict[str, float] = {"PEN": 1.5, "NOTEBOOK": 4.0, "MUG": 8.0}

# Simulates a slow call to a price service. The pause is what makes
# max_concurrency visible: with a limit, the lookups queue up.
PRICE_LOOKUP_S = 0.2


# region price_task
class PriceTask(TypedDict):
    """The payload of one Send: a single line, not the whole order.

    Its shape differs from the order state on purpose. Each price_line task
    receives exactly this dict as its input.
    """

    sku: str
    qty: int


class LinePrice(TypedDict):
    """One priced line, as stored in the order's ``lines`` list."""

    sku: str
    qty: int
    amount: float


# endregion


# region price_line
# For a Send target the type hint of the first parameter is the payload type
# (lesson 2.3: a node's hint is its input schema). The task sees only the
# payload it was sent, never the order state.
def price_line(task: PriceTask) -> dict:
    """Look up the price of one line and return it for the ``lines`` reducer."""
    time.sleep(PRICE_LOOKUP_S)
    amount = PRICES[task["sku"]] * task["qty"]
    line: LinePrice = {"sku": task["sku"], "qty": task["qty"], "amount": amount}
    # A one-element list: the reducer concatenates the lists of all the tasks.
    return {"lines": [line]}


# endregion
