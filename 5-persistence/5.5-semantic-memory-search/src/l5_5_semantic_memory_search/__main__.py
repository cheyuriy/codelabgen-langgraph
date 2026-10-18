"""Live run: Ada on two threads, Bob on his own, then a look into the store.

Fully offline: the assistant is rule-based and both memories live in this
Python process (InMemorySaver and InMemoryStore). The store has an embedding
index (a tiny offline fake), so the assistant finds memories by meaning.
"""

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.memory import InMemoryStore

from l5_5_semantic_memory_search.assistant import (
    MEMORY_INDEX,
    UserContext,
    build_graph,
    genres_namespace,
)


# region chat_helper
def chat(graph: CompiledStateGraph, thread_id: str, user_id: str, text: str) -> None:
    """Send one user message on a thread and print the exchange."""
    # thread_id goes in config (which conversation); user_id goes in context
    # (whose memory). They are different keys on purpose.
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(
        {"messages": [HumanMessage(text)]}, config, context=UserContext(user_id=user_id)
    )
    print(f"  {user_id}> {text}")
    print(f"  bot> {result['messages'][-1].content}")


def message_count(graph: CompiledStateGraph, thread_id: str) -> int:
    """Return how many messages the checkpointer holds for a thread."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    return len(graph.get_state(config).values.get("messages", []))


# endregion


def main() -> None:
    """Run the three conversations and print what the store holds."""
    checkpointer = InMemorySaver()
    # The index is fixed when the store is created. A store created without
    # one keeps working, but silently ignores query= in search.
    store = InMemoryStore(index=MEMORY_INDEX)
    # Built once: every thread and every user goes through this one graph.
    graph = build_graph(checkpointer, store)

    # region monday
    print("== Monday: Ada shares her taste (thread monday) ==")
    chat(graph, "monday", "ada", "I love sci-fi: robots and distant planets.")
    chat(graph, "monday", "ada", "I like mystery too, a detective in ancient Rome.")
    chat(graph, "monday", "ada", "Any book for tonight?")
    # endregion

    print()
    # region tuesday
    print("== Tuesday: a new thread, the same user (thread tuesday) ==")
    # The checkpointer gives tuesday an empty history, but the store still has
    # Monday's genres: the namespace depends on the user, not the thread.
    print(
        f"  thread tuesday starts with {message_count(graph, 'tuesday')} messages;"
        f" thread monday holds {message_count(graph, 'monday')}"
    )
    # The requests name no genre. The query finds the memory whose note means
    # the same thing, and after the skip the filter keeps mystery out even
    # though it matches best.
    chat(graph, "tuesday", "ada", "Something with a spaceship, please.")
    chat(graph, "tuesday", "ada", "I am in the mood for a whodunit.")
    chat(graph, "tuesday", "ada", "Please skip mystery for now.")
    chat(graph, "tuesday", "ada", "I am in the mood for a whodunit.")
    # endregion

    print()
    # region bob
    print("== Bob: his own namespace (thread bob-1) ==")
    chat(graph, "bob-1", "bob", "Recommend something.")
    chat(graph, "bob-1", "bob", "I love fantasy: dragons, wizards and an old king.")
    chat(graph, "bob-1", "bob", "Anything with a wizard?")
    # endregion

    print()
    # region inspect_store
    print("== What the store holds ==")
    # The caller can read and write the same store outside the graph (seeding
    # a profile, an admin view). Timestamps (created_at, updated_at) are left
    # out because they change on every run.
    print(f"  namespaces: {store.list_namespaces()}")
    for user_id in ["ada", "bob"]:
        items = sorted(store.search(genres_namespace(user_id)), key=lambda i: i.key)
        for item in items:
            print(f"  {item.namespace} {item.key!r}: {item.value}")
    ns = genres_namespace("ada")
    print(f"  get({ns}, 'sci-fi').value = {store.get(ns, 'sci-fi').value}")
    print(f"  get({ns}, 'fantasy') = {store.get(ns, 'fantasy')}")
    counts = ", ".join(
        f"{thread}={message_count(graph, thread)}" for thread in ["monday", "tuesday", "bob-1"]
    )
    print(f"  messages per thread: {counts}")
    # endregion

    print()
    # region keys_vs_meaning
    print("== Keys versus meaning ==")
    # get needs the exact key, while search with a query ranks every memory in
    # the namespace prefix by meaning. No filter here, so the avoided mystery
    # memory is listed too, with score 0.00.
    print(f"  get({ns}, 'space') = {store.get(ns, 'space')}")
    hits = store.search(ns, query="space robots")
    print(
        f"  search({ns}, query='space robots'): "
        + ", ".join(f"{i.key}={i.score:.2f}" for i in hits)
    )
    # endregion


if __name__ == "__main__":
    main()
