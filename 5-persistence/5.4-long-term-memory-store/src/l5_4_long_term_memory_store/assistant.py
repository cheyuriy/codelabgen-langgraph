"""A reading-list assistant with two kinds of memory.

The checkpointer keeps each thread's messages (short-term memory, one
conversation). The store keeps each user's genres across all threads
(long-term memory, one user). No LLM: the assistant is rule-based, so the run
is offline and the output is always the same.
"""

from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.messages import AIMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore

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
        runtime.store.put(namespace, genre, {"genre": genre, "stance": stance})
    # A node may also declare a parameter named `store: BaseStore` (the older
    # style, still injected in 1.2.16). runtime.store is the current way and
    # gives context and store from one object.
    return {"messages": [AIMessage("Noted: " + ", ".join(notes) + ".")]}


# endregion


# region recommend_node
def recommend(state: MessagesState, runtime: Runtime[UserContext]) -> dict[str, Any]:
    """Recommend one book for every genre the user likes."""
    # search takes a namespace PREFIX (positional) and returns SearchItem
    # objects: an Item plus .score, which is None here because no query was
    # given. filter= keeps items whose value matches every key exactly
    # (operators such as $ne and $gt exist too). The default limit is 10.
    # Lesson 5.5 adds query= here for semantic search.
    liked = runtime.store.search(
        genres_namespace(runtime.context.user_id), filter={"stance": "like"}
    )
    # Without a query the order of results is not something to rely on, so
    # sort the keys yourself.
    genres = sorted(item.key for item in liked)
    if not genres:
        return {"messages": [AIMessage("Tell me a genre you like and I will pick a book.")]}
    picks = "; ".join(f"{CATALOG[genre]} ({genre})" for genre in genres)
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
