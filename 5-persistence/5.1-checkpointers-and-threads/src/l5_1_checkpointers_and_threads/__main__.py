"""Live run: one agent with an InMemorySaver, two threads, and the saved state."""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

# InMemorySaver lives in the langgraph-checkpoint package (4.3.0). MemorySaver
# is only a backwards-compatible alias of the same class.
from langgraph.checkpoint.memory import InMemorySaver

from l5_1_checkpointers_and_threads.chatbot import build_graph, make_model, tool_call


def describe(m: AnyMessage) -> str:
    """Return a one-line description of a message (never its id: ids change per run)."""
    if isinstance(m, AIMessage) and m.tool_calls:
        calls = []
        for tc in m.tool_calls:
            args = ", ".join(f"{k}={v}" for k, v in tc["args"].items())
            calls.append(f"{tc['name']}({args}) [{tc['id']}]")
        return "AIMessage asks for " + ", ".join(calls)
    if isinstance(m, ToolMessage):
        return f"ToolMessage [{m.tool_call_id}] {m.name} = {m.content}"
    return f"{type(m).__name__}: {m.content}"


def main() -> None:
    """Run the four sections of the lesson."""
    # One saver for the whole process. InMemorySaver keeps every checkpoint in
    # this Python object, so it is gone when the process exits (5.2 fixes that).
    checkpointer = InMemorySaver()

    # One model serves every invoke, so the script holds the replies of all
    # turns, in call order. Built fresh here: the fake sets ids on these objects.
    script = [
        # Turn 1 in chat-1: "What is 3 + 4?"
        tool_call("add", "call_1", a=3, b=4),
        AIMessage("3 + 4 is 7."),
        # Turn 2 in chat-1: "Now multiply that by 2."
        tool_call("multiply", "call_2", a=7, b=2),
        AIMessage("7 * 2 is 14."),
        # The same follow-up in chat-2, a thread with no history.
        AIMessage("Multiply what? This conversation has no earlier result."),
    ]
    graph = build_graph(make_model(script), checkpointer)

    # The thread_id is the conversation's key: runs with the same thread_id
    # share their state. The same graph object serves every thread.
    chat1: RunnableConfig = {"configurable": {"thread_id": "chat-1"}}
    chat2: RunnableConfig = {"configurable": {"thread_id": "chat-2"}}

    # region checkpoint_stream
    print("== Turn 1 in thread chat-1, one checkpoint at a time ==")
    # stream_mode="checkpoints" emits one event each time a checkpoint is
    # saved, in the same shape as get_state() (a dict here, with next as a
    # list). The run writes an "input" checkpoint first (step -1: the input is
    # not applied yet, next is ['__start__']), then one "loop" checkpoint at
    # the end of every super-step: step 0 after the input is written into
    # state, then one after each node run. A checkpoint = channel values +
    # what runs next + metadata, saved under the thread.
    last = None
    for cp in graph.stream(
        {"messages": [HumanMessage("What is 3 + 4?")]}, chat1, stream_mode="checkpoints"
    ):
        md = cp["metadata"]
        n_messages = len(cp["values"].get("messages", []))
        print(
            f"  step {md['step']:>2}  {md['source']:<5}  messages={n_messages}  next={cp['next']}"
        )
        last = cp
    # Without a checkpointer the stream emits no checkpoint events at all.
    if last is not None:
        print("answer:", last["values"]["messages"][-1].content)
    # endregion
    print()

    # region same_thread
    print("== Turn 2 in the same thread ==")
    # The input holds one message. The checkpointer loads the 4 messages of
    # turn 1 first and add_messages appends the new one, so the model
    # (call_model sends the whole state) sees the earlier turn. The fake model
    # ignores its input; the state is what a real model would receive.
    result = graph.invoke({"messages": [HumanMessage("Now multiply that by 2.")]}, chat1)
    for m in result["messages"]:
        print(f"  {describe(m)}")
    print(f"sent 1 message, the thread now holds {len(result['messages'])}")
    # endregion
    print()

    # region new_thread
    print("== The same follow-up in a new thread chat-2 ==")
    # A new thread_id starts from empty state: nothing from chat-1 is visible.
    result = graph.invoke({"messages": [HumanMessage("Now multiply that by 2.")]}, chat2)
    for m in result["messages"]:
        print(f"  {describe(m)}")
    # endregion
    print()

    # region inspect_state
    print("== get_state(chat-1) ==")
    # get_state reads the latest checkpoint of the thread as a StateSnapshot.
    snap = graph.get_state(chat1)
    print(f"  type: {type(snap).__name__}")
    messages = snap.values["messages"]
    print(f"  values: {len(messages)} messages, last: {messages[-1].content!r}")
    # next == () means the run finished: no node is waiting to run.
    print(f"  next: {snap.next}")
    # The config points at this exact checkpoint. checkpoint_id is a
    # time-based uuid, so print only whether it is set.
    conf = snap.config["configurable"]
    print(
        f"  config: thread_id={conf['thread_id']!r} checkpoint_ns={conf['checkpoint_ns']!r}"
        f" checkpoint_id set: {bool(conf['checkpoint_id'])}"
    )
    # step continues across turns: turn 2 wrote steps 4..8, with step 4 as its
    # "input" checkpoint. (metadata also holds parents; the snapshot has a
    # created_at timestamp, which changes per run, so it is not printed.)
    print(f"  metadata: step={snap.metadata['step']} source={snap.metadata['source']!r}")
    # parent_config points at the checkpoint saved just before this one.
    print(f"  has parent checkpoint: {snap.parent_config is not None}")
    # checkpointer.list is the saver's own read API, newest first.
    # graph.get_state_history reads the same data (lesson 6.5).
    n1 = len(list(checkpointer.list(chat1)))
    n2 = len(list(checkpointer.list(chat2)))
    print(f"  checkpoints saved: chat-1 = {n1}  chat-2 = {n2}")
    # A thread that never ran has no checkpoint: empty values, nothing next.
    unused = graph.get_state({"configurable": {"thread_id": "chat-3"}})
    print(f"  unused thread chat-3: values = {unused.values}  next = {unused.next}")
    # endregion


if __name__ == "__main__":
    main()
