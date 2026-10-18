"""Live run for lesson 7.4: consume the same order run through stream_events(version="v3").

The graph is unchanged from 7.3. Each section starts a new run and reads it
through a different projection of the run stream: values and the final
output, the chat-model messages, both interleaved, opt-in updates and custom
projections, and the raw protocol events.
"""

import warnings
from collections import Counter

from langgraph.stream import CustomTransformer, UpdatesTransformer

from l7_4_event_streaming.orders import OrderState, build_graph

# The input: only order_id and items. The nodes fill in status, box and tracking.
ORDER: OrderState = {"order_id": "A-1001", "items": ["PEN", "NOTEBOOK"]}


def main() -> None:
    """Read one order run through the projections of stream_events(version="v3")."""
    # region beta_warning
    # stream_events(version="v3") is experimental in langgraph 1.2.16: each call
    # emits a LangChainBetaWarning ("The v3 streaming protocol on Pregel is
    # experimental."). LangChainBetaWarning subclasses DeprecationWarning, so
    # filtering on that category plus the start of the message silences exactly
    # this warning without importing the private langchain_core._api module.
    # The filter must be set AFTER langchain_core has been imported (it is, by
    # the `from langgraph.stream import ...` line above): importing it calls
    # surface_langchain_beta_warnings(), which puts its own "default" filter in
    # front of any filter set earlier (experiment 5).
    # In an app you would leave the warning visible while you evaluate the API;
    # the lesson hides it so the output stays readable.
    warnings.filterwarnings(
        "ignore", message="The v3 streaming protocol", category=DeprecationWarning
    )
    # endregion
    graph = build_graph()

    # region values_projection
    print("== run.values and run.output: state snapshots, then the final state ==")
    # stream_events(version="v3") does not start the run. It returns a
    # GraphRunStream, and the caller's for loop is what drives the graph forward
    # (there is no background thread). stream_mode= and subgraphs= are refused
    # with a TypeError (experiment 3): v3 decides which modes it needs.
    run = graph.stream_events(ORDER, version="v3")
    # run.values yields the full state after each step, like
    # stream_mode="values", starting with the input.
    for snapshot in run.values:
        print(f"  status={snapshot.get('status', '-')} keys={len(snapshot)}")
    # run.output is a property that runs the graph to the end (if it has not
    # finished yet) and returns the final state. Here the loop already finished
    # the run, so it returns at once. The note is in the output although it was
    # never streamed (nostream, lesson 7.3). run.interrupted and run.interrupts
    # work the same way (lesson 6; not used here, there is no checkpointer).
    print(f"  output: email={run.output['email']!r} note={run.output['note']!r}")
    print()
    # endregion

    # region messages_projection
    print("== run.messages: one stream per model call, tokens in message.text ==")
    # Each item is a ChatModelStream (langchain_core.language_models.
    # chat_model_stream) for ONE model call, not one token: compare 7.3, where
    # the node filter glued the email and the SMS together.
    # message.node is the node that made the call. Iterating message.text yields
    # the text deltas as they arrive; str(message.text) gives the whole text,
    # message.output the assembled AIMessage, and message.reasoning and
    # message.tool_calls the other parts of a reply.
    # A ChatModelStream carries no tags, so here the email and the SMS are told
    # apart by their order; the raw events in the last section still carry the
    # metadata with the tags. The note call is absent: nostream works in v3 too.
    run = graph.stream_events(ORDER, version="v3")
    for message in run.messages:
        print(f"  {message.node}: ", end="")
        for token in message.text:
            print(token, end="", flush=True)
        print()
    print()
    # endregion

    # region interleave_projections
    print("== run.interleave('values', 'messages'): both projections in arrival order ==")
    # A projection only buffers items once something subscribes to it, and each
    # one can be subscribed only once (experiments 1 and 2). Reading two
    # projections one after the other therefore loses the second one.
    # interleave(*names) subscribes to all the named projections and yields
    # (name, item) pairs in the order they were produced.
    # The two messages arrive after ship's snapshot and before confirm's, while
    # confirm is still running: the v3 counterpart of 7.3's updates-plus-messages
    # section. str(item.text) pulls the rest of that reply before the loop goes on.
    run = graph.stream_events(ORDER, version="v3")
    for name, item in run.interleave("values", "messages"):
        if name == "values":
            print(f"  [values]   status={item.get('status', '-')}")
        else:
            print(f"  [messages] {item.node} {str(item.text)!r}")
    print()
    # endregion

    # region opt_in_transformers
    print("== transformers=[UpdatesTransformer, CustomTransformer]: opt-in projections ==")
    # By default a v3 run has only the values, messages, lifecycle and subgraphs
    # projections, and the graph streams only the modes some transformer asks
    # for (each transformer declares required_stream_modes). So pack's and
    # ship's writer events from 7.2 were not even produced in the sections above.
    # Passing transformer CLASSES (not instances: v3 builds one per scope) adds
    # run.updates and run.custom. run.extensions maps every projection name to
    # its channel. Reading run.updates without UpdatesTransformer raises
    # AttributeError (experiment 3). Your own projections are StreamTransformer
    # subclasses (the docs' "custom transformers"; not in this lesson).
    run = graph.stream_events(
        ORDER, version="v3", transformers=[UpdatesTransformer, CustomTransformer]
    )
    print(f"  projections: {sorted(run.extensions)}")
    for name, item in run.interleave("updates", "custom"):
        print(f"  [{name}] {item}")
    print()
    # endregion

    # region raw_events
    print("== iter(run): the raw protocol events behind the projections ==")
    # Iterating the run itself yields protocol events: dicts with "type", "seq"
    # (strictly increasing, use it for ordering), "method" (the channel name)
    # and "params" (namespace [] for the root graph, timestamp, data).
    # A model call becomes message-start, a content block start / deltas /
    # finish, and message-finish. The projections are built from these events,
    # and ChatModelStream assembles them for you. The metadata next to each
    # messages payload is the same as in 7.3 (langgraph_node, tags).
    run = graph.stream_events(ORDER, version="v3")
    counts: Counter[str] = Counter()
    for event in run:
        method = event["method"]
        if method == "messages":
            payload, _metadata = event["params"]["data"]
            method = f"messages/{payload['event']}"
        counts[method] += 1
    for method, n in counts.items():
        print(f"  {method}: {n}")
    # The same run through stream(): 12 bare token chunks instead of 2 message
    # objects. stream() with stream_mode is the stable, low-level API: its
    # values/updates/custom parts are plain dicts, but messages parts hold
    # AIMessageChunk objects you convert before sending them over SSE. v3 is the
    # higher-level, in-process API, experimental in 1.2.16 (the beta warning).
    parts = Counter(
        part["type"]
        for part in graph.stream(ORDER, stream_mode=["values", "messages"], version="v2")
    )
    print(f"  stream(..., version='v2') with the same modes: {dict(parts)}")
    # endregion


if __name__ == "__main__":
    main()
