# 5.4 Long-Term Memory with a Store — code walkthrough

The program is a rule-based reading-list assistant with no LLM. Ada tells it which genres she likes on one thread and asks for books on another. Bob then talks to the same graph. At the end the program prints what the store holds. Messages are kept per thread by the checkpointer, and genres are kept per user by the store. Run it with `./run.sh 5.4` from the course root.
The concept itself is explained in the [notes](notes.md).

This lesson starts a new example, the reading-list assistant. Lesson 5.5 extends it with semantic search, and 5.6 moves it to Postgres.

## [assistant.py](../src/l5_4_long_term_memory_store/assistant.py)

All the graph code is here: the data, the two nodes and `build_graph`. Read it top to bottom.

### Data and the user

- [`CATALOG`](../src/l5_4_long_term_memory_store/assistant.py#L22-L27) is a plain dict, so it is iterated in insertion order. `mentioned_genres` walks it, which is why the bot always says "mystery, sci-fi" and never "sci-fi, mystery", whatever order the user typed them in. Keys double as store keys later, so a genre must exist here to be recommended: `recommend` looks up `CATALOG[genre]` for every liked key.
- [`UserContext`](../src/l5_4_long_term_memory_store/assistant.py#L32-L38) is the run context from lesson 2.4. `build_graph` names it as `context_schema`, the caller passes an instance with `context=` on every `invoke`, and each node reads it as `runtime.context`. It is `frozen=True` ([line 32](../src/l5_4_long_term_memory_store/assistant.py#L32)) because the context belongs to the whole run and nodes are not supposed to change it. `user_id` on [line 38](../src/l5_4_long_term_memory_store/assistant.py#L38) has no default, so you cannot build a context without saying who the user is.
- [`genres_namespace`](../src/l5_4_long_term_memory_store/assistant.py#L45-L52) is the only place that decides where a user's memory lives. Both nodes and `__main__.py` call it, so they cannot drift apart. The store checks the labels on `get`, `search` and `put`: an empty label or a label with a period raises `InvalidNamespaceError`. `put` also refuses an empty tuple and `"langgraph"` as the first label. A user id such as `ada.lovelace` would therefore fail on the first turn.

### Routing

- [`mentioned_genres`](../src/l5_4_long_term_memory_store/assistant.py#L59-L62) is a substring check on the lower-cased text. It is deliberately crude: the lesson is about memory, not language understanding.
- [`route`](../src/l5_4_long_term_memory_store/assistant.py#L65-L68) is used as `add_conditional_edges(START, route)`, so it runs before any node. It reads only the newest message, `state["messages"][-1]`, which is the `HumanMessage` the caller just sent. The returned string is the name of the next node. The `Literal["remember", "recommend"]` return type tells LangGraph the possible targets, so it can draw both edges without a path map in `add_conditional_edges`.

### [`remember`](../src/l5_4_long_term_memory_store/assistant.py#L75-L101)

The node that writes long-term memory.

- The parameter `runtime: Runtime[UserContext]` is injected by name: when LangGraph sees a node parameter called `runtime`, it passes a `Runtime` object holding this run's `context` and the `store` given to `compile`. `Runtime[UserContext]` only tells the type checker what `runtime.context` is.
- [Line 78](../src/l5_4_long_term_memory_store/assistant.py#L78) decides the stance once for the whole message, so "skip mystery and fantasy" marks both as avoided.
- [Line 80](../src/l5_4_long_term_memory_store/assistant.py#L80) builds the namespace from `runtime.context.user_id`. Without `context=` on `invoke`, `runtime.context` is `None` and this line raises `AttributeError: ... 'user_id'` (the last test checks it).
- [Line 86](../src/l5_4_long_term_memory_store/assistant.py#L86) reads the old value before writing, only to produce the "already like" and "like -> avoid" notes in [lines 87-92](../src/l5_4_long_term_memory_store/assistant.py#L87-L92). The store does not need it: `put` would replace the value anyway. If the graph was compiled without a store, `runtime.store` is `None` and this line is where it fails, with `AttributeError: ... 'get'`.
- [Line 97](../src/l5_4_long_term_memory_store/assistant.py#L97) is the write. The key is the genre name, so a second mention of the same genre overwrites one item instead of adding a new one, and Ada ends with exactly two items. The value repeats the genre inside the dict: the key is the item's address, and the value is what a `filter=` can match on.
- The write goes to the store at once, while the node is still running. It is not returned to the graph, so no reducer sees it and no checkpoint contains it. Rewinding a thread to an older checkpoint would not undo it.
- [Line 101](../src/l5_4_long_term_memory_store/assistant.py#L101) returns only the reply. `MessagesState`'s `add_messages` reducer appends it to the thread, and the checkpointer saves it under the current `thread_id`.

### [`recommend`](../src/l5_4_long_term_memory_store/assistant.py#L108-L124)

The node that reads long-term memory.

- [Lines 115-117](../src/l5_4_long_term_memory_store/assistant.py#L115-L117) call `search` with the namespace as a prefix: `("ada", "genres")` matches that namespace and anything nested below it. `filter={"stance": "like"}` is checked against each item's `value`, so Ada's avoided mystery is dropped after Tuesday's skip. No `query=` is passed, so this is a plain lookup with no ranking and every `score` is `None`. Lesson 5.5 adds the query.
- `search` returns at most 10 items by default. With four genres in the catalog that never matters here, but a real memory list would need `limit=` or paging with `offset=`.
- [Line 120](../src/l5_4_long_term_memory_store/assistant.py#L120) sorts the keys in the code. The output order comes from this `sorted`, not from the store, so the reply looks the same whichever store you use.
- [Lines 121-122](../src/l5_4_long_term_memory_store/assistant.py#L121-L122) are the reply for an empty namespace: Bob's first request lands here, because nothing has been written under `("bob", "genres")` yet.
- [Line 123](../src/l5_4_long_term_memory_store/assistant.py#L123) turns each key back into a book through `CATALOG`.

### [`build_graph`](../src/l5_4_long_term_memory_store/assistant.py#L131-L145)

- [Line 136](../src/l5_4_long_term_memory_store/assistant.py#L136) uses the built-in `MessagesState` and declares `UserContext` as the context type. With a dataclass schema, a plain dict such as `context={"user_id": "ada"}` is also turned into a `UserContext`.
- [Lines 137-138](../src/l5_4_long_term_memory_store/assistant.py#L137-L138) register the functions under their own names, `"remember"` and `"recommend"`. These are exactly the strings `route` returns.
- [Line 145](../src/l5_4_long_term_memory_store/assistant.py#L145) is where the store enters the graph. `compile(store=...)` is the only way a node gets `runtime.store`. A checkpointer alone does not provide one: they are separate objects that hold different things. Either argument can be `None`. With a store and no checkpointer the genres would still be remembered, but each `invoke` would start with an empty message history.

## [\_\_main\_\_.py](../src/l5_4_long_term_memory_store/__main__.py)

The live run: three conversations on one graph, then a look into the store from outside.

- [`chat`](../src/l5_4_long_term_memory_store/__main__.py#L17-L26) sends one message. [Line 21](../src/l5_4_long_term_memory_store/__main__.py#L21) puts `thread_id` into the config, and [line 23](../src/l5_4_long_term_memory_store/__main__.py#L23) puts `user_id` into `context=`. The checkpointer only looks at `thread_id`, and the store only sees the namespace the nodes build from `user_id`. That is why Ada can open a new thread and keep her genres. Putting `user_id` into `configurable` instead would not reach `runtime.context`, and `remember` would fail.
- [`message_count`](../src/l5_4_long_term_memory_store/__main__.py#L29-L32) asks the checkpointer for a thread's latest state. For a thread that was never used, `get_state` returns empty `values`, hence `.get("messages", [])` and the 0 printed for `tuesday`.
- [Lines 40-43](../src/l5_4_long_term_memory_store/__main__.py#L40-L43) create the two memories and one graph. Both are in-memory objects that live only as long as this Python process. These are the lines lesson 5.6 replaces with Postgres.
- [Monday](../src/l5_4_long_term_memory_store/__main__.py#L45-L49): the first message goes to `remember`, the second has no genre and goes to `recommend`.
- [Tuesday](../src/l5_4_long_term_memory_store/__main__.py#L52-L63): [lines 56-59](../src/l5_4_long_term_memory_store/__main__.py#L56-L59) show that the new thread starts with 0 messages. The first recommendation still names both genres, because the store is keyed by Ada, not by the thread. The skip turn prints `like -> avoid`, which comes from the `get` on line 86 of `assistant.py` finding Monday's item.
- [Bob](../src/l5_4_long_term_memory_store/__main__.py#L66-L71) uses the same graph and the same store, but his namespace starts empty, so Ada's genres never reach him.
- [What the store holds](../src/l5_4_long_term_memory_store/__main__.py#L74-L91) uses the `store` object directly, with no graph involved. The nodes and the caller share it. [Line 79](../src/l5_4_long_term_memory_store/__main__.py#L79) lists the namespaces: one per user. [Line 81](../src/l5_4_long_term_memory_store/__main__.py#L81) searches each user's namespace without a filter and sorts by key, for the same reason as in `recommend`. [Line 85](../src/l5_4_long_term_memory_store/__main__.py#L85) shows that `get` returns an `Item`, so you read `.value`, and [line 86](../src/l5_4_long_term_memory_store/__main__.py#L86) that a missing key gives `None`, not an error. [Lines 87-90](../src/l5_4_long_term_memory_store/__main__.py#L87-L90) count the messages per thread: 4, 6 and 6. The checkpointer kept each conversation separately, while the store kept one small set of genres per user.

## [test_memory_store.py](../tests/test_memory_store.py)

Each test builds a fresh graph with its own `InMemorySaver` and `InMemoryStore`, so no test sees another's memory.

- [`test_memory_crosses_threads`](../tests/test_memory_store.py#L25-L35): the genres reach thread `t2`, but its result holds only 2 messages, so `t1`'s history did not come along.
- [`test_namespaces_isolate_users`](../tests/test_memory_store.py#L38-L51): Bob gets the empty-namespace reply, and the store ends with one namespace per user.
- [`test_put_is_an_upsert_and_get_sees_it`](../tests/test_memory_store.py#L54-L67): after the skip, Ada still has 2 items, not 3, and `filter=` leaves only sci-fi.
- [`test_caller_and_nodes_share_one_store`](../tests/test_memory_store.py#L70-L77): an item written with `store.put` before any run is read by the node, and a second graph with a different checkpointer but the same store sees it too.
- [`test_misuse_errors`](../tests/test_memory_store.py#L80-L91): the two `AttributeError`s you get without `store=` or without `context=`.
