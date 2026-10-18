"""Offline tests for lesson 5.5: semantic search over the user's memories."""

from l5_5_semantic_memory_search.assistant import (
    MEMORY_INDEX,
    UserContext,
    build_graph,
    embed_texts,
)
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

ADA = ("ada", "genres")
SCI_FI_NOTE = "I love sci-fi: robots and distant planets."
MYSTERY_NOTE = "I like mystery too, a detective in ancient Rome."


def reply(graph: CompiledStateGraph, thread_id: str, user_id: str, text: str) -> str:
    """Invoke the graph with one message and return the assistant's reply text."""
    result = graph.invoke(
        {"messages": [HumanMessage(text)]},
        {"configurable": {"thread_id": thread_id}},
        context=UserContext(user_id=user_id),
    )
    return result["messages"][-1].content


def ada_graph(store: BaseStore) -> CompiledStateGraph:
    """Build a graph on the store and let Ada share her two genres on thread 'm'."""
    graph = build_graph(InMemorySaver(), store)
    reply(graph, "m", "ada", SCI_FI_NOTE)
    reply(graph, "m", "ada", MYSTERY_NOTE)
    return graph


def scores(store: BaseStore, query: str, **kwargs: object) -> list[tuple[str, float | None]]:
    """Return (key, rounded score) pairs of a search in Ada's namespace, in store order."""
    hits = store.search(ADA, query=query, **kwargs)
    return [(i.key, None if i.score is None else round(i.score, 2)) for i in hits]


def test_fake_embedding_is_readable_and_never_zero() -> None:
    """Each axis counts theme words; a text without any lands on the 'other' axis."""
    vectors = embed_texts(["Any book for tonight?", SCI_FI_NOTE])
    assert vectors == [[0.0, 0.0, 0.0, 0.0, 0.0, 1.0], [2.0, 1.0, 0.0, 0.0, 0.0, 0.0]]
    assert all(len(vector) == MEMORY_INDEX["dims"] for vector in vectors)


def test_search_finds_memories_by_meaning() -> None:
    """A request that names no genre still finds the memory with the same meaning."""
    store = InMemoryStore(index=MEMORY_INDEX)
    graph = ada_graph(store)
    assert scores(store, "Something with a spaceship, please.") == [
        ("sci-fi", 0.89),
        ("mystery", 0.0),
    ]
    # A keyed lookup only finds exact keys.
    assert store.get(ADA, "spaceship") is None
    # The memory crosses threads, as in 5.4.
    assert reply(graph, "t", "ada", "Something with a spaceship, please.") == (
        "Try: Dune (sci-fi, score 0.89)."
    )
    # Nothing scores above MIN_SCORE: the 5.4 fallback lists every liked genre.
    assert reply(graph, "t", "ada", "Any book for tonight?") == (
        "Try: The Hound of the Baskervilles (mystery); Dune (sci-fi)."
    )
    # Namespaces still isolate users.
    assert reply(graph, "b", "bob", "Anything with a wizard?") == (
        "Tell me a genre you like and I will pick a book."
    )


def test_filter_and_query_together_and_upsert_reembeds() -> None:
    """The filter runs before ranking, and a new note replaces the old vector."""
    store = InMemoryStore(index=MEMORY_INDEX)
    graph = ada_graph(store)
    assert dict(scores(store, "ancient Rome")) == {"mystery": 0.71, "sci-fi": 0.0}
    reply(graph, "m", "ada", "Please skip mystery for now.")
    # Mystery would match best, but filter={"stance": "like"} removes it first.
    assert reply(graph, "m", "ada", "I am in the mood for a whodunit.") == "Try: Dune (sci-fi)."
    # The upsert embedded the new note, so the old sentence no longer matches.
    assert dict(scores(store, "ancient Rome")) == {"mystery": 0.0, "sci-fi": 0.0}
    assert scores(store, "whodunit", filter={"stance": "avoid"}) == [("mystery", 1.0)]


def test_fields_and_index_false_choose_what_is_embedded() -> None:
    """fields picks the embedded part of a value; index=False stores no vector."""
    sci_fi = {"genre": "sci-fi", "stance": "like", "note": SCI_FI_NOTE}
    mystery = {"genre": "mystery", "stance": "like", "note": MYSTERY_NOTE}

    # (a) Embedding the genre instead of the note: "robots" no longer counts.
    by_genre = InMemoryStore(index={**MEMORY_INDEX, "fields": ["genre"]})
    by_note = InMemoryStore(index=MEMORY_INDEX)
    for store in (by_genre, by_note):
        store.put(ADA, "sci-fi", sci_fi)
        store.put(ADA, "mystery", mystery)
    assert dict(scores(by_genre, "space robots"))["sci-fi"] == 0.71
    assert dict(scores(by_note, "space robots"))["sci-fi"] == 0.95

    # (b) An item put with index=False has no vector: InMemoryStore lists it
    # after the scored items, with score None, and get still finds it.
    store = InMemoryStore(index=MEMORY_INDEX)
    store.put(ADA, "sci-fi", sci_fi)
    history = {"genre": "history", "stance": "like", "note": "Wars and empires of ancient Rome."}
    store.put(ADA, "history", history, index=False)
    assert scores(store, "ancient Rome") == [("sci-fi", 0.0), ("history", None)]
    assert scores(store, "ancient Rome", limit=1) == [("sci-fi", 0.0)]
    assert store.get(ADA, "history").value == history
    graph = build_graph(InMemorySaver(), store)
    assert reply(graph, "t", "ada", "Tell me about ancient Rome.") == (
        "Try: SPQR (history); Dune (sci-fi)."
    )


def test_store_without_index_ignores_query() -> None:
    """Without an index, query= is silently ignored and every score is None."""
    store = InMemoryStore()
    graph = ada_graph(store)
    assert reply(graph, "t", "ada", "Something with a spaceship, please.") == (
        "Try: The Hound of the Baskervilles (mystery); Dune (sci-fi)."
    )
    hits = store.search(ADA, query="space")
    assert hits
    assert all(item.score is None for item in hits)
