"""Live run of lesson 8.3: agents hand a ticket to each other with Command.PARENT."""

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import ParentCommand
from langgraph.graph.state import CompiledStateGraph

from l8_3_agent_handoffs.billing import build_billing
from l8_3_agent_handoffs.desk import build_desk
from l8_3_agent_handoffs.show import brief, label, node_path

# The four 8.2 tickets: used by the tests, not by the run below.
BILLING_TICKET = "Please refund invoice INV-1042, I was charged twice."
GENERAL_TICKET = "Do you have a dark mode?"
TECH_TICKET = "My laptop shows an error after the update."
# No device named, so the tech graph has to ask.
VAGUE_TECH_TICKET = "The app crashes when I log in."

# Classified billing ("payment"), but it names no invoice: a tech problem.
BILLING_TO_TECH_TICKET = "The payment page shows an error on my phone."
# Classified tech ("login"), but it names an invoice: a billing question.
TECH_TO_BILLING_TICKET = "I paid INV-2077 twice and now my login fails."


# region stream_ticket
def stream_ticket(desk: CompiledStateGraph, ticket: str, config: dict) -> None:
    """Send one ticket through the desk and print every node update, inner ones too."""
    # subgraphs=True also streams the steps inside billing and tech, each
    # under its own namespace; version="v2" yields dicts with "ns" and "data".
    for part in desk.stream(
        {"messages": [HumanMessage(ticket)]},
        config,
        stream_mode="updates",
        subgraphs=True,
        version="v2",
    ):
        for node, update in part["data"].items():
            print(f"  {node_path(part['ns']):<8} {node} -> {brief(update)}")


# endregion


def main() -> None:
    """Hand tickets between the billing and tech teams and show what the desk keeps."""
    desk = build_desk(InMemorySaver())
    # ONE thread for sections 1-3: the same customer sends both tickets.
    customer = {"configurable": {"thread_id": "customer-7"}}

    # region billing_to_tech
    print("== 1. Billing hands a ticket to tech ==")
    # There is no "billing find_invoice" line: the node handed off instead of
    # returning an update, and the subgraph stopped there. The root billing
    # line is the handoff's update (note, new category, log entry); then the
    # desk runs its tech node, which runs the tech subgraph as in 8.2.
    stream_ticket(desk, BILLING_TO_TECH_TICKET, customer)
    print()
    # endregion

    # region tech_to_billing
    print("== 2. Tech hands a ticket back to billing ==")
    # The same from a subgraph with its own schema, called inside a node: the
    # root tech line is the handoff's update, not the tech reply. Then billing
    # finds the invoice in the ticket (not in tech's note) and, being added
    # as a node, writes back its whole shared messages list as in 8.1.
    stream_ticket(desk, TECH_TO_BILLING_TICKET, customer)
    print()
    # endregion

    # region thread_state
    print("== 3. What the desk kept on the thread ==")
    values = desk.get_state(customer).values
    for m in values["messages"]:
        print(f"  {label(m)}: {m.content}")
    # The log holds both handoffs because handoffs has a reducer
    # (operator.add); category is a plain key and shows the last team the
    # ticket was handed to.
    print(f"  handoffs: {values['handoffs']}")
    print(f"  category: {values['category']}")
    print()
    # endregion

    # region on_its_own
    print("== 4. A team on its own has no parent to hand off to ==")
    # This is how a handoff travels: as an exception that unwinds the
    # subgraph until a parent graph catches it. Run as a top-level graph,
    # nobody catches it, so it reaches the caller with the Command inside.
    # A team built for handoffs only works inside a parent that has the goto
    # targets.
    try:
        build_billing().invoke({"messages": [HumanMessage(BILLING_TO_TECH_TICKET)]})
    except ParentCommand as exc:
        command = exc.args[0]
        print(f"  build_billing().invoke(...) raised {type(exc).__name__}")
        print(f"  goto: {command.goto!r}, update keys: {sorted(command.update)}")
    # endregion


if __name__ == "__main__":
    main()
