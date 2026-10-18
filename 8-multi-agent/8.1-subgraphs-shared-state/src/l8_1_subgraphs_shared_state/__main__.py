"""Live run of lesson 8.1: a compiled subgraph as a node with shared state."""

from collections import Counter

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from l8_1_subgraphs_shared_state.desk import build_desk
from l8_1_subgraphs_shared_state.show import brief, label, node_path

BILLING_TICKET = "Please refund invoice INV-1042, I was charged twice."
# Used by the tests and the experiments, not by the run below.
GENERAL_TICKET = "Do you have a dark mode?"


def main() -> None:
    """Run a billing ticket through the desk and show the subgraph at work."""
    checkpointer = InMemorySaver()
    desk = build_desk(checkpointer)
    ticket_1 = {"configurable": {"thread_id": "ticket-1"}}
    ticket_2 = {"configurable": {"thread_id": "ticket-2"}}

    # region run_ticket
    print("== 1. A billing ticket runs through the billing subgraph ==")
    result = desk.invoke({"messages": [HumanMessage(BILLING_TICKET)]}, ticket_1)
    for m in result["messages"]:
        print(f"  {label(m)}: {m.content}")
    # invoice_id is not in the result: only shared keys come back from the
    # subgraph. category is: it is the parent's own key, untouched by it.
    print(f"  state keys: {sorted(result)}")
    print()
    # endregion

    # region xray
    print("== 2. get_graph() vs get_graph(xray=True) ==")
    # Without xray the subgraph is one box named "billing". With xray=True it
    # is drawn as a Mermaid `subgraph billing ... end` block and its nodes get
    # ids like "billing:find_invoice" (":" is escaped as \3a in the Mermaid
    # ids). xray also accepts an int: the number of levels to expand.
    print(f"  nodes:      {list(desk.get_graph().nodes)}")
    print(f"  xray nodes: {list(desk.get_graph(xray=True).nodes)}")
    print("  xray Mermaid:")
    print(desk.get_graph(xray=True).draw_mermaid())
    # endregion

    # region stream_subgraphs
    print("== 3. stream(subgraphs=True, version='v2'): updates from both levels ==")
    # subgraphs=True adds the subgraph's own updates, and each part's ns says
    # where it came from (the promise of lesson 7.1). Without it only the two
    # root lines appear (experiment 3). In v1 (no version="v2") every chunk
    # becomes a (ns, chunk) tuple instead of a dict.
    # A fresh thread, so the message count below is not mixed with section 1.
    for part in desk.stream(
        {"messages": [HumanMessage(BILLING_TICKET)]},
        ticket_2,
        stream_mode="updates",
        subgraphs=True,
        version="v2",
    ):
        for node, update in part["data"].items():
            print(f"  {node_path(part['ns']):<8} {node} -> {brief(update)}")
    # The last root line is the merge described in desk.py: the billing
    # node's update holds both messages, yet the thread holds 2, not 3,
    # because add_messages matched the ticket by its id.
    count = len(desk.get_state(ticket_2).values["messages"])
    print(f"  messages in thread ticket-2: {count}")
    print()
    # endregion

    # region checkpoints
    print("== 4. One checkpointer, checkpoints in two namespaces ==")
    # The subgraph has no saver of its own (None), yet the parent's
    # InMemorySaver holds checkpoints of both graphs under thread ticket-1.
    # The parent puts its checkpointer into the config of every task it runs
    # (pregel/_algo.py) and the subgraph uses the lent one
    # (Pregel._resolve_checkpointer in pregel/main.py). The subgraph's
    # checkpoints are stored under checkpoint_ns "billing:<task_id>".
    billing = dict(desk.get_subgraphs())["billing"]
    print(f"  billing subgraph compiled with checkpointer={billing.checkpointer}")
    # Each graph saved 4: the input checkpoint (step -1) and one per
    # super-step (lesson 5.1). With the default checkpointer=None the
    # namespace contains the task id, so every run of the subgraph starts a
    # fresh history (per invocation); that is what lets an interrupt inside
    # the subgraph resume (lesson 8.2 reads that saved subgraph state).
    counts = Counter(
        node_path(saved.config["configurable"]["checkpoint_ns"].split("|"))
        for saved in checkpointer.list(ticket_1)
    )
    for name, n in sorted(counts.items()):
        print(f"  {name:<8} {n} checkpoints")
    # endregion


if __name__ == "__main__":
    main()
