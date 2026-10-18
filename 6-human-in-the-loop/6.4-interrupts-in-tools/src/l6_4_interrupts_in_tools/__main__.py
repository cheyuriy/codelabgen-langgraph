"""Live run for lesson 6.4: one to-do conversation in which deleting needs the user's approval."""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, GraphOutput

from l6_4_interrupts_in_tools.agent import asks_for, build_agent, make_model
from l6_4_interrupts_in_tools.todos import TODO_LIST, TOOL_RUNS

# One thread for the whole conversation: the checkpoint carries the messages
# from turn to turn, and the pause and the resume find each other by it.
CONFIG = {"configurable": {"thread_id": "todo-chat"}}


# region script
def script() -> list[AIMessage]:
    """Return a fresh list of the fake model's replies for the four turns.

    The replies are fixed, so the model says the same thing whatever the tool
    returned; a real model would read the ToolMessage and answer accordingly.
    Eight replies for four turns: the model is called twice per turn, never
    again on resume.
    """
    return [
        # Turn 1: add a task, then confirm.
        asks_for(("add_task", "call_1", {"title": "pay rent"})),
        AIMessage("Added 'pay rent' as task 3."),
        # Turn 2: delete a task (the user approves), then confirm.
        asks_for(("delete_task", "call_2", {"task_id": 1})),
        AIMessage("Done, 'buy milk' is off your list."),
        # Turn 3: delete a task (the user rejects), then acknowledge.
        asks_for(("delete_task", "call_3", {"task_id": 2})),
        AIMessage("OK, I kept 'call the bank'."),
        # Turn 4: add and delete in ONE reply (add_task first), then confirm.
        asks_for(
            ("add_task", "call_4", {"title": "water the plants"}),
            ("delete_task", "call_5", {"task_id": 3}),
        ),
        AIMessage("Added 'water the plants' and removed 'pay rent'."),
    ]


# endregion


# region show_steps
def describe(message: AnyMessage) -> str:
    """Return a one-line description of a message for the output."""
    if isinstance(message, AIMessage) and message.tool_calls:
        calls = ", ".join(
            f"{tc['name']}({', '.join(f'{k}={v!r}' for k, v in tc['args'].items())}) [{tc['id']}]"
            for tc in message.tool_calls
        )
        return f"ai asks for {calls}"
    if isinstance(message, ToolMessage):
        return f"tool [{message.tool_call_id}] {message.name}: {message.content}"
    return f"{message.type}: {message.content}"


def step(graph: CompiledStateGraph, value: dict | Command) -> GraphOutput:
    """Run one invoke (a new user message or a resume) and print only the messages it added.

    version="v2" keeps the state (out.value) and the pending interrupts
    (out.interrupts) apart (6.1).
    """
    # Count the saved messages before the invoke (values is {} before the first turn).
    seen = len(graph.get_state(CONFIG).values.get("messages", []))
    out = graph.invoke(value, CONFIG, version="v2")
    for message in out.value["messages"][seen:]:
        print(f"  {describe(message)}")
    for item in out.interrupts:
        print(f"  paused, asking: {item.value['question']!r}")
    return out


# endregion


def main() -> None:
    """Run the four turns of the to-do conversation."""
    graph = build_agent(make_model(script()), InMemorySaver())

    # region add_freely
    print("== Turn 1: adding needs no approval ==")
    # add_task has no interrupt(), so the loop runs model -> tools -> model
    # without stopping.
    step(graph, {"messages": [HumanMessage("Add 'pay rent' to my list.")]})
    print(f"  to-do list: {TODO_LIST}")
    # endregion
    print()

    # region approve_delete
    print("== Turn 2: deleting pauses inside the tool ==")
    step(graph, {"messages": [HumanMessage("Delete 'buy milk'.")]})
    # The pause happened inside delete_task, inside the "tools" node. The
    # checkpoint holds the AIMessage with the tool call and the pending
    # "tools" task, but no answer to call_2 yet: 4.2's pairing rule is only
    # fulfilled after the resume.
    snap = graph.get_state(CONFIG)
    last = snap.values["messages"][-1]
    print(f"  saved: next={snap.next} tasks={[task.name for task in snap.tasks]}")
    print(
        f"  last saved message: {last.type}, asks for {[tc['id'] for tc in last.tool_calls]}, "
        "no ToolMessage yet"
    )
    # "yes" is what interrupt() returns inside the tool. The tool runs twice
    # (once to pause, once to finish), and the string it returns is the ToolMessage.
    step(graph, Command(resume="yes"))
    print(f"  delete_task runs: {TOOL_RUNS['delete_task']}")
    print(f"  to-do list: {TODO_LIST}")
    # endregion
    print()

    # region reject_delete
    print("== Turn 3: a rejection becomes the tool result ==")
    step(graph, {"messages": [HumanMessage("Delete 'call the bank'.")]})
    # The tool does not delete and returns the human's answer as its result;
    # the loop goes on to the model as after any tool call, nothing raises.
    step(graph, Command(resume="no, I still need to do it"))
    print(f"  to-do list: {TODO_LIST}")
    # endregion
    print()

    # region add_and_delete
    print("== Turn 4: one reply adds and deletes ==")
    before = TOOL_RUNS["add_task"]
    step(graph, {"messages": [HumanMessage("Add 'water the plants' and delete 'pay rent'.")]})
    # Both calls run in the same "tools" task. add_task finished and changed
    # the list, but its ToolMessage was not saved because the task paused.
    print(f"  saved: tasks={[task.name for task in graph.get_state(CONFIG).tasks]}")
    print(f"  add_task ran {TOOL_RUNS['add_task'] - before}x, to-do list: {TODO_LIST}")
    # On resume the node runs both calls again: add_task runs a second time,
    # and only its tool-call-id check keeps 'water the plants' from being
    # added twice. add_task is FIRST in the reply on purpose: with delete_task
    # first, whether add_task starts before the pause depends on thread timing.
    step(graph, Command(resume="yes"))
    print(f"  add_task ran {TOOL_RUNS['add_task'] - before}x, to-do list: {TODO_LIST}")
    # endregion


if __name__ == "__main__":
    main()
