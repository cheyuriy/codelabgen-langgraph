"""What every team uses to hand a ticket to another team, and to find the ticket after a handoff."""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.types import Command

# This module imports nothing from desk.py, billing.py or tech.py: the desk
# imports the teams, and the teams import this module.


# region hand_off
def hand_off(source: str, target: str, reason: str) -> Command:
    """Send the ticket from the team `source` to the desk node `target`."""
    # A short note for the customer, signed by the team that hands off.
    note = AIMessage(f"{reason} Passing you to the {target} team.", name=source)
    # How it travels: when a node returns this Command, LangGraph raises
    # ParentCommand (langgraph.errors) inside the subgraph. The exception
    # unwinds the subgraph run and is caught by the desk's task for the team
    # node, which applies the update and the goto as if that node had
    # returned them (section 4 of the run shows the exception).
    return Command(
        # graph=Command.PARENT: this command is not for the graph the node
        # runs in (the team's subgraph) but for the closest parent graph, the
        # desk. So goto names a DESK node ("tech", "billing"), a sibling of
        # the team that hands off; the team's own graph has no such node.
        graph=Command.PARENT,
        goto=target,
        # The update is applied to the DESK's state, with the desk's keys and
        # the desk's reducers, not to the subgraph's state. That is why it may
        # write category and handoffs, keys billing does not have and tech
        # does not know at all (TechState has no desk key). messages goes
        # through add_messages and handoffs through operator.add (DeskState);
        # category is a plain key, so the last write wins.
        #
        # What a handoff passes is a choice ("context engineering" in the
        # docs): here a short note for the customer, the new category and one
        # log entry. Nothing the team computed inside its subgraph reaches the
        # desk unless it is put into this update.
        update={
            "messages": [note],
            "category": target,
            "handoffs": [f"{source} -> {target}"],
        },
    )


# endregion


# region ticket_text
def ticket_text(messages: Sequence[AnyMessage]) -> str:
    """The customer's latest ticket: the last human message."""
    # After a handoff the last message is the other team's note, not the
    # ticket, so a team that read messages[-1] would answer the note
    # (experiment 3). Every team finds the ticket with this function.
    return next(m.content for m in reversed(messages) if m.type == "human")


# endregion
