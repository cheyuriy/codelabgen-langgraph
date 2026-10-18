"""Live run of lesson 8.2: a subgraph with its own state, called inside a node."""

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from l8_2_subgraphs_own_state.desk import build_desk
from l8_2_subgraphs_own_state.show import brief, label, node_path

BILLING_TICKET = "Please refund invoice INV-1042, I was charged twice."
# Used by the tests and the experiments, not by the run below.
GENERAL_TICKET = "Do you have a dark mode?"
TECH_TICKET = "My laptop shows an error after the update."
# No device named, so the tech graph has to ask.
VAGUE_TECH_TICKET = "The app crashes when I log in."


def main() -> None:
    """Run tech tickets through the desk and show the tech subgraph at work."""
    checkpointer = InMemorySaver()
    desk = build_desk(checkpointer)
    ticket_1 = {"configurable": {"thread_id": "ticket-1"}}
    ticket_2 = {"configurable": {"thread_id": "ticket-2"}}
    ticket_3 = {"configurable": {"thread_id": "ticket-3"}}
    ticket_4 = {"configurable": {"thread_id": "ticket-4"}}

    # region run_tech_ticket
    print("== 1. A tech ticket: the tech node maps the state in and out ==")
    result = desk.invoke({"messages": [HumanMessage(TECH_TICKET)]}, ticket_1)
    for m in result["messages"]:
        print(f"  {label(m)}: {m.content}")
    # problem, device and fix stayed inside the subgraph; the desk only got
    # the message the tech node built.
    print(f"  state keys: {sorted(result)}")
    print()
    # endregion

    # region two_ways
    print("== 2. Subgraph as a node vs subgraph inside a node ==")
    # get_subgraphs() finds tech too, although "tech" is a plain function
    # node (see the TECH_TEAM comment in desk.py).
    print(f"  subgraphs the desk can see: {[name for name, _ in desk.get_subgraphs()]}")
    # Both subgraphs stream their inner steps under their own namespace,
    # whichever way they are attached. The difference is the last root line
    # of each: billing (added as a node) writes the subgraph's whole shared
    # messages list, ['human', 'billing']; tech (called inside a node) writes
    # only what the wrapper returned, ['tech'].
    for ticket, config in ((BILLING_TICKET, ticket_2), (TECH_TICKET, ticket_3)):
        for part in desk.stream(
            {"messages": [HumanMessage(ticket)]},
            config,
            stream_mode="updates",
            subgraphs=True,
            version="v2",
        ):
            for node, update in part["data"].items():
                print(f"  {node_path(part['ns']):<8} {node} -> {brief(update)}")
    print()
    # endregion

    # region paused_state
    print("== 3. A vague tech ticket pauses inside the tech subgraph ==")
    out = desk.invoke({"messages": [HumanMessage(VAGUE_TECH_TICKET)]}, ticket_4, version="v2")
    print(f"  interrupt: {out.interrupts[0].value}")
    # The parent is paused in front of its tech node; parent.tasks has one
    # task per pending node.
    parent = desk.get_state(ticket_4)
    print(f"  parent next: {parent.next}")
    # Without subgraphs=True the task's state is only a config pointing at
    # the subgraph's checkpoints (thread_id and checkpoint_ns): a hint that
    # saved subgraph state exists.
    pointer_keys = sorted(parent.tasks[0].state["configurable"])
    print(f"  get_state():                tasks[0].state keys {pointer_keys}")
    # With subgraphs=True LangGraph loads it, and the task's state is the
    # subgraph's own StateSnapshot: TechState values (problem only; device is
    # what it is waiting for) and the subgraph's next node. This only exists
    # while the subgraph is paused: after a finished run there is no pending
    # task, so tasks is empty (section 4). It also needs a parent
    # checkpointer and a subgraph LangGraph can find statically
    # (experiment 3).
    tech_state = desk.get_state(ticket_4, subgraphs=True).tasks[0].state
    print(f"  get_state(subgraphs=True):  tasks[0].state is a {type(tech_state).__name__}")
    where = node_path(tech_state.config["configurable"]["checkpoint_ns"].split("|"))
    print(f"  {where} values: {tech_state.values}")
    print(f"  {where} next:   {tech_state.next}")
    print()
    # endregion

    # region resume_ticket
    print("== 4. Resume: the answer travels back through the tech node ==")
    # The resume value reaches interrupt() inside the subgraph. The tech node
    # ran again from its top, invoked the subgraph, which continued from its
    # checkpoint, and mapped the result out as before. Resume values follow
    # module 6: Command(resume=None) does not resume; use a real value.
    out = desk.invoke(Command(resume="phone"), ticket_4, version="v2")
    for m in out.value["messages"]:
        print(f"  {label(m)}: {m.content}")
    print(f"  pending tasks: {len(desk.get_state(ticket_4, subgraphs=True).tasks)}")
    # endregion


if __name__ == "__main__":
    main()
