"""The entry point the server loads: langgraph.json names make_graph in this file."""

from langgraph.graph.state import CompiledStateGraph

from l10_6_local_server.desk import build_desk


# region make_graph
def make_graph() -> CompiledStateGraph:
    """Build the support desk for the server, without a checkpointer."""
    # 1. No checkpointer: the server brings its own persistence and gives
    #    every run a checkpointer and a store. A compiled graph exported with
    #    a checkpointer of its own is refused at startup (experiment 1).
    # 2. This is a factory: the server calls it for each run and for each
    #    state read, so any build-time work belongs inside the graph, not at
    #    import time.
    # 3. The server looks at the factory's parameters: none (as here), one
    #    (it receives the run's config, or a runtime when the parameter is
    #    annotated `ServerRuntime` from langgraph_sdk.runtime), or two
    #    (config and runtime). That is why build_desk cannot be the entry
    #    point itself: its one parameter would receive the config dict
    #    (experiment 2).
    return build_desk(checkpointer=None)


# endregion
