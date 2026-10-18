"""Turns one v2 stream part into a line of text."""

from langgraph.types import StreamPart


# region describe
def describe(part: StreamPart) -> str:
    """Return a one-line description of a v2 stream part.

    StreamPart is a union of TypedDicts discriminated by the "type" key
    (ValuesStreamPart, UpdatesStreamPart, MessagesStreamPart,
    CustomStreamPart, CheckpointStreamPart, TasksStreamPart and
    DebugStreamPart, all in langgraph.types). Matching on part["type"] lets a
    type checker narrow part["data"] to the right shape in each case.

    Every part has "ns": the subgraph path that produced it, () for the
    top-level graph. It is only non-empty when you stream with subgraphs=True.
    """
    match part["type"]:
        case "values":
            # data is the full state. Only values parts carry "interrupts": a
            # tuple of Interrupt objects, empty unless the run paused.
            return (
                f"[values]  ns={part['ns']} status={part['data'].get('status', '-')} "
                f"interrupts={len(part['interrupts'])}"
            )
        case "updates":
            # data maps node name -> what that node returned. An updates chunk
            # normally holds one node; the join keeps this correct if a chunk
            # ever holds more.
            return "; ".join(
                f"[updates] ns={part['ns']} {node} -> {update}"
                for node, update in part["data"].items()
            )
        case "custom":
            # data is exactly what the node passed to the writer, untouched.
            return f"[custom]  ns={part['ns']} {part['data']}"
        case "messages":
            # data is a (message chunk, metadata) pair: one part per token.
            chunk, metadata = part["data"]
            return f"[messages] ns={part['ns']} {metadata['langgraph_node']} {chunk.content!r}"
        case other:
            # Every other part type (checkpoints, tasks, debug) lands here.
            return f"[{other}] (not shown in this lesson)"


# endregion
