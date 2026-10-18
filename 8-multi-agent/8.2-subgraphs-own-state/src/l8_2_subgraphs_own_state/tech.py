"""The tech team as its own graph, with a state that has nothing in common with the desk's."""

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

# The devices the tech team knows how to help with.
DEVICES = ("laptop", "phone", "router")

# One standard fix per device.
FIXES = {
    "laptop": "restart it and install the latest updates",
    "phone": "reinstall the app",
    "router": "unplug it for 30 seconds",
}


# region tech_state
class TechState(TypedDict):
    """State of the tech subgraph: its own keys, none shared with the desk."""

    # No key has the same name as a DeskState key (no messages, no category),
    # so the desk cannot hand its state to this graph directly. A node of the
    # desk translates instead (desk.py, region tech_node). That also means
    # the tech team can be built and tested without knowing anything about
    # the desk (test 2).
    #
    # problem is the input: the ticket text.
    problem: str
    # device and fix are filled in by the nodes below.
    device: NotRequired[str]
    fix: NotRequired[str]


# endregion


# region tech_nodes
def identify_device(state: TechState) -> dict:
    """Find the device in the problem text, or ask the customer for it."""
    text = state["problem"].lower()
    device = next((name for name in DEVICES if name in text), None)
    if device is None:
        # An interrupt inside a subgraph pauses the WHOLE desk, and its
        # question comes out of the parent's invoke (out.interrupts).
        # Pausing needs saved progress: the tech graph has no checkpointer of
        # its own, it uses the one the parent lends it on every run (8.1,
        # section 4). On resume, interrupt() returns the resume value.
        device = interrupt("Which device are you using: laptop, phone or router?")
    return {"device": device}


def suggest_fix(state: TechState) -> dict:
    """Look up the standard fix for the device."""
    return {"fix": FIXES[state["device"]]}


# endregion


# region build_tech
def build_tech() -> CompiledStateGraph:
    """Build and compile the tech subgraph: identify_device -> suggest_fix."""
    builder = StateGraph(TechState)
    builder.add_node("identify_device", identify_device)
    builder.add_node("suggest_fix", suggest_fix)
    builder.add_edge(START, "identify_device")
    builder.add_edge("identify_device", "suggest_fix")
    builder.add_edge("suggest_fix", END)
    # Compiled without a checkpointer, like billing. That is the default
    # per-invocation mode: every call starts a fresh history, and inside a
    # run its progress is saved under the parent's thread.
    return builder.compile()


# endregion
