"""Offline tests for lesson 5.6: the Postgres demo, run on in-memory stand-ins.

verify runs these before Postgres starts, so nothing here opens a connection.
The in-memory saver and store behave like the Postgres ones for everything
the scenes and reset_demo use.
"""

import importlib

import pytest
from l5_6_postgres_persistence.__main__ import (
    STEPS,
    THREADS,
    USERS,
    chat,
    message_count,
    open_postgres,
    play_scene,
    reset_demo,
)
from l5_6_postgres_persistence.assistant import (
    MEMORY_INDEX,
    build_graph,
    embed_texts,
    genres_namespace,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

# The conversation lines of the live run, without the '== process' headers.
EXPECTED_CONVERSATION = """\
  thread monday starts with 0 messages
  ada> I love sci-fi: robots and distant planets.
  bot> Noted: sci-fi (like).
  ada> I like mystery too, a detective in ancient Rome.
  bot> Noted: mystery (like).
  thread monday starts with 4 messages
  ada> Any book for tonight?
  bot> Try: The Hound of the Baskervilles (mystery); Dune (sci-fi).
  thread tuesday starts with 0 messages; thread monday holds 6
  ada> Something with a spaceship, please.
  bot> Try: Dune (sci-fi, score 0.89).
  ada> I am in the mood for a whodunit.
  bot> Try: The Hound of the Baskervilles (mystery, score 0.71).
  ada> Please skip mystery for now.
  bot> Noted: mystery (like -> avoid).
  ada> I am in the mood for a whodunit.
  bot> Try: Dune (sci-fi).
  bob> Recommend something.
  bot> Tell me a genre you like and I will pick a book.
  bob> I love fantasy: dragons, wizards and an old king.
  bot> Noted: fantasy (like).
  bob> Anything with a wizard?
  bot> Try: The Hobbit (fantasy, score 0.95).
"""


def play_all(saver: InMemorySaver, store: InMemoryStore) -> None:
    """Play every step on the shared backends, with a NEW graph per step (like a new process)."""
    for step in STEPS:
        play_scene(step, build_graph(saver, store))


def test_no_database_at_import_and_url_read_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing needs no environment; open_postgres reads POSTGRES_URL only when entered."""
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    module = importlib.import_module("l5_6_postgres_persistence.__main__")
    importlib.reload(module)
    with pytest.raises(KeyError, match="POSTGRES_URL"):
        with open_postgres():
            pass
    # pgvector rejects vectors of any length other than the column's dims.
    vector = embed_texts(["Something with a spaceship, please."])[0]
    assert len(vector) == MEMORY_INDEX["dims"] == 6


def test_state_lives_in_the_backend(capsys: pytest.CaptureFixture[str]) -> None:
    """A fresh graph per step still continues the threads, because the backends hold them."""
    saver = InMemorySaver()
    store = InMemoryStore(index=MEMORY_INDEX)
    play_all(saver, store)
    assert capsys.readouterr().out == EXPECTED_CONVERSATION


def test_a_process_with_its_own_backend_sees_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """Empty backends mean an empty thread and no memories: what Postgres removes."""
    graph = build_graph(InMemorySaver(), InMemoryStore(index=MEMORY_INDEX))
    play_scene("monday-evening", graph)
    out = capsys.readouterr().out.splitlines()
    assert "  thread monday starts with 0 messages" in out
    assert "  bot> Tell me a genre you like and I will pick a book." in out


def test_reset_demo_deletes_only_the_demo_data(capsys: pytest.CaptureFixture[str]) -> None:
    """reset_demo removes the demo's threads and memories, keeps the rest, and can run twice."""
    saver = InMemorySaver()
    store = InMemoryStore(index=MEMORY_INDEX)
    play_all(saver, store)
    graph = build_graph(saver, store)
    chat(graph, "other", "cy", "I love history.")
    capsys.readouterr()

    reset_demo(saver, store)

    for thread_id in THREADS:
        assert message_count(graph, thread_id) == 0
    # Check search(), not list_namespaces(): InMemoryStore keeps emptied namespaces.
    for user_id in USERS:
        assert store.search(genres_namespace(user_id)) == []
    assert message_count(graph, "other") == 2
    assert store.get(("cy", "genres"), "history") is not None
    # Deleting what is already gone is fine.
    reset_demo(saver, store)


def test_play_scene_rejects_unknown_steps() -> None:
    """An unknown step name is an error, not a silent no-op."""
    graph = build_graph(InMemorySaver(), InMemoryStore(index=MEMORY_INDEX))
    with pytest.raises(ValueError, match="unknown step 'nope'"):
        play_scene("nope", graph)
