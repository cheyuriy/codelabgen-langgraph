"""Live run: a two-turn offline chat, then add_messages called by hand."""

import operator

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage
from langgraph.graph import add_messages

from l4_1_messages_state.chatbot import build_graph, make_model


def show(messages: list[AnyMessage], indent: str = "  ") -> None:
    """Print one line per message: its class name and content."""
    for m in messages:
        print(f"{indent}{type(m).__name__}: {m.content}")


def show_ids(messages: list[AnyMessage]) -> None:
    """Print one line per message with its id (only for fixed, short ids)."""
    for m in messages:
        print(f"    {m.id} {m.type}: {m.content}")


def main() -> None:
    """Run both sections of the lesson."""
    # region two_turn_chat
    print("== A two-turn chat with a scripted model ==")
    model = make_model(["2 + 3 is 5.", "5 times 4 is 20."])
    graph = build_graph(model)

    print("turn 1:")
    # add_messages coerces the ("user", ...) tuple into a HumanMessage and gives
    # it a uuid id; the fake reply gets an id like "lc_run--..." from
    # langchain-core. Ids change every run, so we print booleans, not ids.
    result = graph.invoke({"messages": [("user", "What is 2 + 3?")]})
    show(result["messages"])
    print("  every message has an id:", all(m.id for m in result["messages"]))

    print("turn 2:")
    # No checkpointer: pass the whole history back in, plus the new question.
    result2 = graph.invoke({"messages": result["messages"] + [("user", "And times 4?")]})
    show(result2["messages"])
    kept = [m.id for m in result2["messages"][:2]] == [m.id for m in result["messages"]]
    print("  ids from turn 1 kept:", kept)
    # endregion

    # region reducer_calls
    print()
    print("== add_messages is a plain function ==")
    # A scripted wrong answer that we will correct by id.
    history = [HumanMessage("What is 2 + 3?", id="q1"), AIMessage("2 + 3 is 6.", id="a1")]

    print("append q2:")  # a new id goes to the end
    show_ids(add_messages(history, [HumanMessage("And times 4?", id="q2")]))

    print("replace a1:")  # an existing id is replaced in place
    show_ids(add_messages(history, [AIMessage("2 + 3 is 5.", id="a1")]))

    print("remove q1:")  # RemoveMessage deletes the message with that id
    show_ids(add_messages(history, [RemoveMessage(id="q1")]))

    print("operator.add with the same fix:")  # plain concatenation: a1 twice
    show_ids(operator.add(history, [AIMessage("2 + 3 is 5.", id="a1")]))

    # add_messages returns a new list; the input is left untouched.
    print("history itself still has", len(history), "messages")
    # endregion


if __name__ == "__main__":
    main()
