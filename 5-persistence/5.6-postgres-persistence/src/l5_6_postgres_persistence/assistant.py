"""A reading-list assistant with two kinds of memory.

The checkpointer keeps each thread's messages (short-term memory, one
conversation). The store keeps each user's genres across all threads
(long-term memory, one user). No LLM: the assistant is rule-based, so the run
is offline and the output is always the same. The store also has an
embedding index, so recommend finds memories by meaning, not only by key.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.messages import AIMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore, IndexConfig

# region catalog
# One book per genre keeps the output short. Alphabetical order on purpose:
# mentioned_genres walks this dict, so its results come in this order.
CATALOG: dict[str, str] = {
    "fantasy": "The Hobbit",
    "history": "SPQR",
    "mystery": "The Hound of the Baskervilles",
    "sci-fi": "Dune",
}
# endregion


# region fake_embedding
# Each vector dimension is a THEME. Words with a similar meaning share a theme,
# so "spaceship" and "planets" land on the same axis. That is a hand-made,
# very small version of what a real embedding model learns from data (with
# hundreds or thousands of dimensions). This one has six that we can read:
# [space, robots, crime, magic, past, other].
THEMES: dict[str, set[str]] = {
    "space": {"sci-fi", "space", "spaceship", "planet", "star", "alien"},
    "robots": {"robot", "android", "machine", "computer"},
    "crime": {"mystery", "detective", "crime", "murder", "clue", "whodunit"},
    "magic": {"fantasy", "magic", "wizard", "dragon", "spell", "quest"},
    "past": {"history", "ancient", "empire", "rome", "king", "war"},
}


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Turn each text into a vector: one count per theme, plus an "other" axis.

    This is an embedding function: texts in, vectors out. The store calls it
    with a batch of texts, both for the memories it indexes on put and for
    the query on search, and expects one vector of the same length per text.
    Similar meaning gives vectors pointing the same way, and so a higher
    cosine similarity.
    """
    vectors: list[list[float]] = []
    for text in texts:
        # A naive plural strip ("planets" -> "planet"); the hyphen in the
        # pattern keeps "sci-fi" one word.
        words = [w.removesuffix("s") for w in re.findall(r"[a-z-]+", text.lower())]
        # A text's value on a theme is how many of its words belong to it.
        vector = [float(sum(w in theme_words for w in words)) for theme_words in THEMES.values()]
        # The "other" axis is 1.0 only when no theme word appears, so no vector
        # is ever all zeros. Cosine similarity divides by the vector length,
        # and a zero vector has no direction (the score would be nan). Real
        # models never return zero vectors; this guard exists only because
        # the fake is so small.
        vector.append(0.0 if any(vector) else 1.0)
        vectors.append(vector)
    return vectors


# endregion


# region memory_index
# The store's embedding index. A plain function is enough for "embed": the
# store wraps it itself (no Embeddings subclass needed).
# - dims: the vector length. InMemoryStore does not check it, but stores that
#   keep vectors in a database column use it to size that column.
# - embed: how text becomes a vector.
# - fields: WHICH part of a value is embedded. Only "note" (what the user
#   said), not "genre" or "stance". The default is ["$"], the whole value as
#   JSON.
# A real model plugs in here without other changes, for example
#   {"dims": 1536, "embed": init_embeddings("openai:text-embedding-3-small"),
#    "fields": ["note"]}
# with `from langchain.embeddings import init_embeddings` (needs the
# langchain and langchain-openai packages and an API key), or
# "embed": "openai:text-embedding-3-small" as a string, which the store
# resolves through the same init_embeddings.
# The config lives here, not in __main__, so lesson 5.6 can pass the same
# MEMORY_INDEX to PostgresStore.
MEMORY_INDEX: IndexConfig = {"dims": len(THEMES) + 1, "embed": embed_texts, "fields": ["note"]}

# search always returns the nearest memories, even unrelated ones (score 0.00
# here, a low but non-zero number with real models), so the caller decides
# what counts as relevant. The value has to be tuned for each embedding model.
MIN_SCORE = 0.5
# endregion


# region user_context
@dataclass(frozen=True)
class UserContext:
    """Who is talking, for one run: the store namespace is built from it."""

    # The user id comes from the caller (the app's login), not from the
    # messages, so a user cannot read another user's memory by typing a name.
    user_id: str


# endregion


# region namespace
def genres_namespace(user_id: str) -> tuple[str, ...]:
    """Return the store namespace that holds one user's genres."""
    # A namespace is a tuple of strings, like a folder path. Putting the user
    # id first gives every user their own folder; "genres" leaves room for
    # other kinds of memory per user later (("ada", "profile"), ...).
    # Labels must be non-empty strings without periods, and the root cannot
    # be "langgraph": the store raises InvalidNamespaceError otherwise.
    return (user_id, "genres")


# endregion


# region route
def mentioned_genres(text: str) -> list[str]:
    """Return the catalog genres that appear in the text, in catalog order."""
    text = text.lower()
    return [genre for genre in CATALOG if genre in text]


def route(state: MessagesState) -> Literal["remember", "recommend"]:
    """Send messages that name a genre to remember, everything else to recommend."""
    text = state["messages"][-1].content
    return "remember" if mentioned_genres(text) else "recommend"


# endregion


# region remember_node
def remember(state: MessagesState, runtime: Runtime[UserContext]) -> dict[str, Any]:
    """Save each mentioned genre as liked or avoided in the user's namespace."""
    text = state["messages"][-1].content
    stance = "avoid" if "skip" in text.lower() else "like"
    # runtime.context is the UserContext the caller passed with context=...
    namespace = genres_namespace(runtime.context.user_id)
    notes: list[str] = []
    for genre in mentioned_genres(text):
        # runtime.store is the store passed to compile(store=...): the same
        # object for every thread and every run. get returns an Item (with
        # .namespace, .key, .value, .created_at, .updated_at) or None.
        old = runtime.store.get(namespace, genre)
        if old is None:
            notes.append(f"{genre} ({stance})")
        elif old.value["stance"] == stance:
            notes.append(f"{genre} (already {stance})")
        else:
            notes.append(f"{genre} ({old.value['stance']} -> {stance})")
        # put(namespace, key, value) is an upsert: the same namespace + key
        # replaces the value. The value must be a dict of JSON-serialisable
        # values. The write happens right now, inside the node: it is not a
        # state update and is not part of any checkpoint.
        # Because the store has an index, put also embeds the "note" field
        # (fields=["note"]). An upsert embeds the new note again, so the old
        # sentence no longer matches. put(..., index=False) would store an
        # item without a vector, and put(..., index=["genre"]) would embed
        # other fields for this one item.
        runtime.store.put(namespace, genre, {"genre": genre, "stance": stance, "note": text})
    # A node may also declare a parameter named `store: BaseStore` (the older
    # style, still injected in 1.2.16). runtime.store is the current way and
    # gives context and store from one object.
    return {"messages": [AIMessage("Noted: " + ", ".join(notes) + ".")]}


# endregion


# region recommend_node
def recommend(state: MessagesState, runtime: Runtime[UserContext]) -> dict[str, Any]:
    """Recommend the liked genres that match the request, or all of them."""
    text = state["messages"][-1].content
    # search takes a namespace PREFIX (positional). With query= the store
    # embeds the request, compares it with each memory's vector and returns
    # SearchItems sorted by .score (cosine similarity, 1.0 = same direction),
    # highest first. filter= is applied BEFORE ranking, so an avoided genre
    # never comes back however close it is. limit (default 10) caps how many
    # come back.
    liked = runtime.store.search(
        genres_namespace(runtime.context.user_id), query=text, filter={"stance": "like"}
    )
    if not liked:
        return {"messages": [AIMessage("Tell me a genre you like and I will pick a book.")]}
    # score is None when the store has no index (then query= is ignored) or
    # for an item put with index=False, hence the `is not None` check.
    relevant = [item for item in liked if item.score is not None and item.score >= MIN_SCORE]
    if relevant:
        # Keep the store's order: highest score first.
        picks = "; ".join(
            f"{CATALOG[item.key]} ({item.key}, score {item.score:.2f})" for item in relevant
        )
    else:
        # Nothing is relevant: fall back to every liked genre. Tied or None
        # scores give no useful order, so sort the keys yourself.
        picks = "; ".join(f"{CATALOG[genre]} ({genre})" for genre in sorted(i.key for i in liked))
    return {"messages": [AIMessage(f"Try: {picks}.")]}


# endregion


# region build_graph
def build_graph(
    checkpointer: BaseCheckpointSaver | None, store: BaseStore | None
) -> CompiledStateGraph:
    """Build the assistant: START routes to remember or recommend, both end."""
    # context_schema tells LangGraph what context= holds (as in lesson 2.4).
    builder = StateGraph(MessagesState, context_schema=UserContext)
    builder.add_node(remember)
    builder.add_node(recommend)
    builder.add_conditional_edges(START, route)
    builder.add_edge("remember", END)
    builder.add_edge("recommend", END)
    # The two arguments are independent: the checkpointer is keyed by
    # thread_id (from config), the store by namespace (built by your code).
    # __main__ creates both, so lesson 5.6 only changes those lines.
    return builder.compile(checkpointer=checkpointer, store=store)


# endregion
