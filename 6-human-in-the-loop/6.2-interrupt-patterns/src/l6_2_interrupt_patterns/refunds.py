"""Refund requests above a limit wait for a manager, who decides what happens.

Small refunds are approved by policy. Larger ones pause inside
``manager_review`` with ``interrupt()``. The manager approves, rejects or
lowers the amount, and that answer picks the next node. Invalid answers are
asked again until the manager sends one that makes sense.
"""

from typing import Any, Literal, NotRequired, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

# region refund_state
REFUND_LIMIT = 100
"""Refunds up to this many whole dollars are approved without a human."""


class RefundState(TypedDict):
    """The state of one refund request.

    The caller only sends ``request_id`` and ``amount``. ``amount`` is what
    the customer asked for and is never overwritten. ``decided_by`` and
    ``approved_amount`` are written by the deciding node (auto_approve or
    manager_review), ``status`` by pay_refund / reject_refund at the end.
    """

    request_id: str
    amount: int
    status: NotRequired[str]
    decided_by: NotRequired[str]
    # The amount actually paid; may be lower than `amount` when the manager
    # edits it.
    approved_amount: NotRequired[int]
    # The last validation error, stored so that the next run of manager_review
    # can show it to the manager; set back to None once an answer is accepted.
    review_error: NotRequired[str | None]


# endregion


# region route_by_amount
def route_by_amount(state: RefundState) -> Literal["auto_approve", "manager_review"]:
    """Send refunds above REFUND_LIMIT to a manager, approve the rest by policy."""
    # The Literal return type tells LangGraph (and the graph drawing) which
    # nodes this conditional edge can lead to.
    if state["amount"] > REFUND_LIMIT:
        return "manager_review"
    return "auto_approve"


# endregion


# region auto_approve
def auto_approve(state: RefundState) -> dict[str, Any]:
    """Approve a small refund for the full amount.

    It goes on to pay_refund like any approved refund.
    """
    return {"decided_by": "policy", "approved_amount": state["amount"]}


# endregion


# region check_answer
def check_answer(answer: Any, requested: int) -> str | None:
    """Check the manager's answer and return an error message, or None if it is fine.

    The answer looks like ``{"decision": "approve"}``, ``{"decision": "reject"}``
    or ``{"decision": "approve", "amount": 120}`` (an edited, lower amount).
    A manager may lower a refund but never raise it above what was requested.
    The amount of a reject is ignored.
    """
    # The resume value comes from outside (a web form, a chat message), so it
    # can be anything; check it before acting on it.
    if not isinstance(answer, dict) or answer.get("decision") not in ("approve", "reject"):
        return "decision must be 'approve' or 'reject'"
    amount = answer.get("amount", requested)
    if not isinstance(amount, int) or not 1 <= amount <= requested:
        return f"amount must be a whole number from 1 to {requested}"
    return None


# endregion


# region manager_review
# Command[Literal[...]] tells compile() and the graph drawing where this node
# can go (as in 3.3), including back to itself. There is no add_edge out of
# manager_review any more: the Command picks the next node from the human's
# answer.
def manager_review(
    state: RefundState,
) -> Command[Literal["pay_refund", "reject_refund", "manager_review"]]:
    """Ask a manager to approve, reject or lower the refund, and route on the answer.

    First run: ``interrupt()`` pauses the graph here, saves a checkpoint and
    hands the payload to the caller. Resume: the caller invokes the same
    thread with ``Command(resume=...)``; the node runs again from its first
    line and this time ``interrupt()`` returns the resume value.
    """
    # Runs on the first run AND on every resume: the node restarts from the top.
    print(f"  [manager_review] started for {state['request_id']}")
    request = {
        "request_id": state["request_id"],
        "amount": state["amount"],
        "question": f"Approve a refund of ${state['amount']} for {state['request_id']}?",
    }
    # A stored error from the previous run is shown to the manager together
    # with the same question, so they see why they are asked again.
    if state.get("review_error"):
        request["error"] = state["review_error"]
    answer = interrupt(request)
    error = check_answer(answer, state["amount"])
    if error is not None:
        # An invalid answer is not acted on. It is stored in review_error and
        # the Command sends the graph back into manager_review, whose new run
        # pauses again with the error. This follows the Interrupts guide:
        # call interrupt() once per node run and loop through the graph, so
        # each answer is checked exactly once. The guide loops with a
        # conditional edge; Command(goto=...) is used here because this node
        # already routes with Command, which keeps one routing mechanism.
        return Command(update={"review_error": error}, goto="manager_review")
    print(f"  [manager_review] accepted {answer!r}")
    # Both success branches clear review_error, so a decided request carries
    # no stale error.
    if answer["decision"] == "reject":
        return Command(
            update={"decided_by": "manager", "review_error": None},
            goto="reject_refund",
        )
    # The edited amount goes into approved_amount; the requested amount stays
    # in `amount`, so both are visible later.
    return Command(
        update={
            "decided_by": "manager",
            "approved_amount": answer.get("amount", state["amount"]),
            "review_error": None,
        },
        goto="pay_refund",
    )


# endregion


# region outcome_nodes
def pay_refund(state: RefundState) -> dict[str, str]:
    """Pay approved_amount (never amount), so an edited value is what gets applied."""
    print(f"  [pay_refund] paying ${state['approved_amount']} for {state['request_id']}")
    return {"status": "approved"}


def reject_refund(state: RefundState) -> dict[str, str]:
    """Close the request without paying anything."""
    print(f"  [reject_refund] no refund for {state['request_id']}")
    return {"status": "rejected"}


# endregion


# region build_graph
def build_graph(checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    """Build the refund graph: route by amount, decide, then pay or reject.

    interrupt() needs a checkpointer: the pause *is* a saved checkpoint, and
    resuming means loading that checkpoint again by thread_id. Without one the
    first run still returns the interrupt to the caller, but nothing is saved,
    so nothing can resume it. manager_review has no outgoing edge here because
    its Command chooses the next node.
    """
    builder = StateGraph(RefundState)
    builder.add_node("auto_approve", auto_approve)
    builder.add_node("manager_review", manager_review)
    builder.add_node("pay_refund", pay_refund)
    builder.add_node("reject_refund", reject_refund)
    builder.add_conditional_edges(START, route_by_amount)
    builder.add_edge("auto_approve", "pay_refund")
    builder.add_edge("pay_refund", END)
    builder.add_edge("reject_refund", END)
    return builder.compile(checkpointer=checkpointer)


# endregion
