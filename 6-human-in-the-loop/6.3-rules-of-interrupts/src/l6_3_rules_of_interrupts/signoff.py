"""Large refunds need two sign-offs: a manager AND finance.

Refunds above $1000 are signed off by a manager and by finance. Both are asked
in parallel, so two interrupts are pending at once, and the caller resumes
them by ``Interrupt.id``. The manager answers two questions in one node (the
decision, then a reason for the audit log), and those answers are matched to
the ``interrupt()`` calls by their order.

This flow is separate from ``refunds.py``, whose ``manager_review`` stays at
one ``interrupt()`` per run and re-asks through the graph. Several interrupts
in one node is a rule to know, used here for two different questions that are
always asked in the same order; it is not a replacement for 6.2's validation
loop.
"""

from collections import Counter
from typing import NotRequired, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

# region signoff_state
NODE_RUNS: Counter[str] = Counter()
"""How many times each sign-off node has started.

The parallel nodes do not print, because their print order varies from run
to run, so the main script prints these counts instead.
"""


class SignoffState(TypedDict):
    """One large refund.

    Each sign-off node writes its own keys, so the parallel writes never
    collide and no reducer is needed.
    """

    request_id: str
    amount: int
    manager_decision: NotRequired[str]
    manager_reason: NotRequired[str]
    finance_decision: NotRequired[str]
    status: NotRequired[str]


# endregion


# region manager_signoff
def manager_signoff(state: SignoffState) -> dict[str, str]:
    """Ask the manager two questions in one node: the decision, then a reason."""
    NODE_RUNS["manager_signoff"] += 1
    # On resume the node restarts, so the first interrupt() returns the stored
    # first answer and the second one pauses or returns the next answer.
    # Resume values are matched to interrupt() calls strictly by their index
    # in the node: always call them in the same order and never skip one
    # conditionally.
    # Both pauses of this node have the SAME Interrupt.id (the id belongs to
    # the node's task, not to the question), which is why LangGraph matches
    # by order inside a node.
    # Do not wrap interrupt() in a bare try/except: it pauses by raising
    # GraphInterrupt, an Exception subclass, and catching it would swallow
    # the pause.
    # The "role" key lets the caller tell the pending interrupts apart.
    decision = interrupt(
        {
            "role": "manager",
            "question": f"Approve a refund of ${state['amount']} for {state['request_id']}?",
        }
    )
    reason = interrupt(
        {
            "role": "manager",
            "question": f"You chose {decision!r}. Why? (kept in the audit log)",
        }
    )
    return {"manager_decision": decision, "manager_reason": reason}


# endregion


# region finance_signoff
def finance_signoff(state: SignoffState) -> dict[str, str]:
    """Ask finance one question, in parallel with manager_signoff."""
    NODE_RUNS["finance_signoff"] += 1
    answer = interrupt({"role": "finance", "question": f"Is there budget for ${state['amount']}?"})
    return {"finance_decision": answer}


# endregion


# region settle
def settle(state: SignoffState) -> dict[str, str]:
    """Join the two sign-offs; runs once, after both have finished.

    settle is the only node here that prints, because it runs alone in its
    step, so its line has a stable place in the output.
    """
    approved = state["manager_decision"] == "approve" and state["finance_decision"] == "approve"
    status = "approved" if approved else "rejected"
    print(f"  [settle] {state['request_id']} {status}")
    return {"status": status}


# endregion


# region build_signoff_graph
def build_signoff_graph(checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    """Build the sign-off graph: two parallel sign-offs joined by settle.

    The two sign-offs run in the same step, so when both pause the thread has
    two pending interrupts.
    """
    builder = StateGraph(SignoffState)
    builder.add_node("manager_signoff", manager_signoff)
    builder.add_node("finance_signoff", finance_signoff)
    builder.add_node("settle", settle)
    # Two edges from START: both sign-offs run in the first step (as in 3.1).
    builder.add_edge(START, "manager_signoff")
    builder.add_edge(START, "finance_signoff")
    # The waiting edge: settle runs only once BOTH sign-offs have finished.
    builder.add_edge(["manager_signoff", "finance_signoff"], "settle")
    builder.add_edge("settle", END)
    return builder.compile(checkpointer=checkpointer)


# endregion
