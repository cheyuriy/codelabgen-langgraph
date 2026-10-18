"""Live run for lesson 7.3: stream the confirm node's chat-model tokens five ways.

The same pick -> pack -> ship -> confirm run is streamed with
stream_mode="messages": all the tokens, the tokens next to the updates in
version="v2", the tokens filtered by node, filtered by tag, and finally with
the nostream call left out of the stream although its text is in the state.
"""

from l7_3_streaming_llm_tokens.orders import OrderState, build_graph
from l7_3_streaming_llm_tokens.render import describe

# The input: only order_id and items. The nodes fill in status, box and tracking.
ORDER: OrderState = {"order_id": "A-1001", "items": ["PEN", "NOTEBOOK"]}


def main() -> None:
    """Stream the confirm node's tokens in five ways and print what arrives."""
    graph = build_graph()

    # region messages_mode
    print("== stream_mode='messages': one (chunk, metadata) pair per token ==")
    # In v1 every item is a tuple (AIMessageChunk, metadata). The metadata says
    # where the token came from: langgraph_node, langgraph_step,
    # langgraph_triggers, ... and "tags" (only the tags you set; the key is
    # MISSING for a call without tags, hence .get, see experiment 4).
    # Only confirm calls a model, so pick, pack and ship add nothing, and the
    # warehouse note is absent because its call is tagged nostream.
    # The fake model sends each space as its own chunk. A real provider chunks
    # differently, so never rely on chunk boundaries, only on the joined text.
    for chunk, metadata in graph.stream(ORDER, stream_mode="messages"):
        print(f"  {metadata['langgraph_node']} {metadata.get('tags', [])} {chunk.content!r}")
    print()
    # endregion

    # region messages_with_updates
    print("== stream_mode=['updates', 'messages'], version='v2': tokens while confirm runs ==")
    # A messages part is {"type": "messages", "ns": ..., "data": (chunk, metadata)}.
    # The tokens arrive between ship's update and confirm's update, i.e. while
    # confirm is still running: requesting "messages" turns on eager streaming,
    # like "custom" did in lesson 7.2.
    for part in graph.stream(ORDER, stream_mode=["updates", "messages"], version="v2"):
        print(f"  {describe(part)}")
    print()
    # endregion

    # region filter_by_node
    print("== filtered by node 'confirm': both replies run together ==")
    # This is how a UI prints a reply live: end="" and flush=True.
    # langgraph_node is always in the metadata, so indexing it is safe. The
    # filter picks one node, but confirm calls the model three times (one of
    # them silent), so the email and the SMS are glued together. Filter by
    # node when each node makes one model call.
    print("  ", end="")
    for chunk, metadata in graph.stream(ORDER, stream_mode="messages"):
        if metadata["langgraph_node"] == "confirm":
            print(chunk.content, end="", flush=True)
    print()
    print()
    # endregion

    # region filter_by_tag
    print("== filtered by tag 'email': only the customer email ==")
    # Tags select single model calls, whichever node makes them. Use `in` (a
    # call can carry several tags) and .get (untagged calls have no "tags" key).
    print("  ", end="")
    for chunk, metadata in graph.stream(ORDER, stream_mode="messages"):
        if "email" in metadata.get("tags", []):
            print(chunk.content, end="", flush=True)
    print()
    print()
    # endregion

    # region nostream_call
    print("== tags=[TAG_NOSTREAM]: the note is written but never streamed ==")
    # The note call ran (its text is in the state), but none of its tokens
    # reached the stream: "nostream" hides a model call from
    # stream_mode="messages" only, it does not skip the call. Typical use: a
    # classifier, a router or a summary the user should not see typed out.
    streamed_tags: set[str] = set()
    for _chunk, metadata in graph.stream(ORDER, stream_mode="messages"):
        streamed_tags.update(metadata.get("tags", []))
    print(f"  tags in the token stream: {sorted(streamed_tags)}")
    print(f"  note in the final state: {graph.invoke(ORDER)['note']!r}")
    # endregion


if __name__ == "__main__":
    main()
