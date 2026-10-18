# 5.5 Semantic Search over Memories — code walkthrough

This is the reading-list assistant from lesson 5.4, with one addition: the store now has an embedding index. Each genre memory keeps the sentence the user said, and `recommend` finds memories by what that sentence means, so "Something with a spaceship, please." finds sci-fi even though it never names the genre. The run prints the similarity scores, and at the end it compares a keyed `get` with a semantic `search`. Run it with `./run.sh 5.5` from the course root.
The concept itself is explained in the [notes](notes.md).

## What changed since lesson 5.4

- [`THEMES` and `embed_texts`](../src/l5_5_semantic_memory_search/assistant.py#L35-L72) are new. Together they are a small offline embedding function that turns text into vectors.
- [`MEMORY_INDEX` and `MIN_SCORE`](../src/l5_5_semantic_memory_search/assistant.py#L79-L101) are new. The first is the index configuration for the store, the second is the relevance threshold.
- `remember` stores one more field, `note`, on [line 176](../src/l5_5_semantic_memory_search/assistant.py#L176).
- [`recommend`](../src/l5_5_semantic_memory_search/assistant.py#L187-L213) searches with `query=` and keeps only the memories that score at least `MIN_SCORE`. When none does, it falls back to the 5.4 reply.
- `__main__.py` creates the store with `index=MEMORY_INDEX` on [line 49](../src/l5_5_semantic_memory_search/__main__.py#L49). The scripted messages now describe books instead of naming genres, and a new [keys versus meaning](../src/l5_5_semantic_memory_search/__main__.py#L107-L118) section is printed at the end.
- [test_semantic_search.py](../tests/test_semantic_search.py) replaces 5.4's `test_memory_store.py`.
- [pyproject.toml](../pyproject.toml#L10) adds `numpy`.

Unchanged: `CATALOG`, `UserContext`, `genres_namespace`, the routing, `build_graph` and the `chat` helper. They are explained in the [5.4 walkthrough](../../5.4-long-term-memory-store/docs/readalong.md).

## [assistant.py](../src/l5_5_semantic_memory_search/assistant.py)

### The fake embedding

An embedding function turns each text into a list of numbers, a vector, so that texts with similar meaning get vectors that point in a similar direction. Real models learn this from data. The course runs offline, so the lesson writes a tiny one by hand, with axes you can read.

- [`THEMES`](../src/l5_5_semantic_memory_search/assistant.py#L40-L46) defines one axis per theme. Words that mean related things share an axis: "spaceship", "planet" and "sci-fi" all count toward `space`. This shared axis is the whole trick. "spaceship" and "planets" are different words, but they push the vector the same way. The dict order fixes the axis order, `[space, robots, crime, magic, past]`, and `other` is added last.
- [`embed_texts`](../src/l5_5_semantic_memory_search/assistant.py#L49-L72) takes a batch of texts and returns one vector per text, all of the same length. The store calls it in two places. On `put`, it embeds the indexed field of the new value. On `search(query=...)`, it embeds the query, calling the function with a one-item list. A plain function is enough here. The store wraps it in its own `Embeddings` adapter, so you don't need to subclass anything.
- [Line 62](../src/l5_5_semantic_memory_search/assistant.py#L62) splits the text into lower-case words. The pattern keeps hyphens, so `sci-fi` stays one word. `removesuffix("s")` is a crude plural strip that turns "planets" into "planet" and "wizards" into "wizard". It also damages words like "this", but those are not in any theme, so the result is unchanged.
- [Line 64](../src/l5_5_semantic_memory_search/assistant.py#L64) counts, for each theme, how many words belong to it. The sci-fi note "I love sci-fi: robots and distant planets." gives `[2, 1, 0, 0, 0, 0]`: "sci-fi" and "planet" count toward space, "robot" toward robots. The first test checks exactly this vector.
- [Line 70](../src/l5_5_semantic_memory_search/assistant.py#L70) adds the `other` axis. It is 1.0 only when no theme word was found. Without it, "Any book for tonight?" would be all zeros. Cosine similarity divides by the vector's length, so a zero query vector would give the score `nan`, and numpy would print a `RuntimeWarning`. The comparison with `MIN_SCORE` would then be quietly false. Real models don't return zero vectors, so this guard is needed only because the fake is so small.

### The index configuration

- [`MEMORY_INDEX`](../src/l5_5_semantic_memory_search/assistant.py#L96) is an `IndexConfig`, a plain `TypedDict`, with three keys:
  - `dims` is `len(THEMES) + 1` = 6, computed from the themes, so it stays right if you add a theme. `InMemoryStore` never reads it, so a wrong value would not fail here. The first test therefore checks that every vector has this length. Stores that keep vectors in a database column use `dims` to size that column, and that is where a mismatch would fail.
  - `embed` is the function itself, not a call to it.
  - `fields=["note"]` decides which part of each value is embedded. The genre and stance are not embedded, only the user's own sentence. When `fields` is left out, the whole value is embedded as JSON. The fourth test shows how much this choice matters.
- The comment in [lines 87-93](../src/l5_5_semantic_memory_search/assistant.py#L87-L93) shows how a real model would plug in: only the `embed` and `dims` values change, and the nodes stay the same. The string form needs the `langchain` package, which this course does not install. With the string, `InMemoryStore(...)` raises a `ValueError` when the store is built, not later on a search.
- The config lives in `assistant.py` rather than in `__main__.py` so that lesson 5.6 can pass the same `MEMORY_INDEX` to a different store.
- [`MIN_SCORE`](../src/l5_5_semantic_memory_search/assistant.py#L101) exists because `search` with a query never returns nothing just because nothing matches. It returns the nearest items it has, up to `limit`. Here an unrelated memory scores exactly 0.00, because it shares no axis with the query. With a real model unrelated texts still get some lower positive number, so 0.5 is a value for this fake and has to be tuned for each model.

### [`remember`](../src/l5_5_semantic_memory_search/assistant.py#L149-L180)

The only change is the value written on [line 176](../src/l5_5_semantic_memory_search/assistant.py#L176): it now includes `"note": text`, the whole sentence. Because the store was built with an index, the same `put` also calls `embed_texts` on that note and keeps the vector next to the item. The node does nothing extra for this.

- The key is still the genre, so `put` is still an upsert. When Ada says "Please skip mystery for now.", the mystery item gets the new note and a new vector, and the vector for "a detective in ancient Rome" is gone. The third test shows the query "ancient Rome" dropping from 0.71 to 0.00 for mystery after the skip.
- Each message writes its whole sentence as the note of every genre it mentions. That is why the `monday` script uses one genre per sentence: each memory gets a note about its own genre only.
- The `index` argument of `put`, described in the comment in [lines 171-175](../src/l5_5_semantic_memory_search/assistant.py#L171-L175), overrides `fields` for a single item. The node doesn't use it, but the fourth test does.

### [`recommend`](../src/l5_5_semantic_memory_search/assistant.py#L187-L213)

- [Line 189](../src/l5_5_semantic_memory_search/assistant.py#L189) reads the request text, and [lines 196-198](../src/l5_5_semantic_memory_search/assistant.py#L196-L198) pass it as `query=`. The store embeds the query and computes the cosine similarity with every candidate's vector: 1.0 means the same direction, 0.0 means no shared axis. It returns `SearchItem`s sorted by `.score`, highest first.
- `filter={"stance": "like"}` chooses the candidates *before* ranking. That is why, after the skip, the whodunit request answers "Dune": mystery would score best, but it never reaches the ranking.
- [Lines 199-200](../src/l5_5_semantic_memory_search/assistant.py#L199-L200): an empty result now means "no liked memories at all", not "nothing relevant". `search` with a query still returns every liked item (up to `limit`), however far it is. Bob's first message lands here.
- [Line 203](../src/l5_5_semantic_memory_search/assistant.py#L203) applies the threshold. The `is not None` check matters, because `score` is `None` when the store has no index (the last test) and for an item stored without a vector (the fourth test).
- [Lines 204-208](../src/l5_5_semantic_memory_search/assistant.py#L204-L208) keep the store's order, which is the ranking, and print each score. Where the numbers in the run come from:
  - The spaceship request embeds to `[1, 0, 0, 0, 0, 0]`. Against the sci-fi note `[2, 1, 0, 0, 0, 0]` that gives 2/√5 ≈ 0.89.
  - "whodunit" is `[0, 0, 1, 0, 0, 0]`. Against the mystery note `[0, 0, 2, 0, 2, 0]` that gives 2/√8 ≈ 0.71.
  - "wizard" against Bob's note `[0, 0, 0, 3, 1, 0]` gives 3/√10 ≈ 0.95.
- [Lines 209-212](../src/l5_5_semantic_memory_search/assistant.py#L209-L212) are the fallback when nothing reaches `MIN_SCORE`. Then the reply is the 5.4 one: every liked genre, sorted by key in the code. "Any book for tonight?" lands here, because its vector lies only on the `other` axis, so every memory scores 0.00. Equal scores say nothing about which item should come first, so the code does its own sorting instead of using the store's order.

`build_graph` is unchanged. The index belongs to the store, and the graph only passes the store through to the nodes.

## [\_\_main\_\_.py](../src/l5_5_semantic_memory_search/__main__.py)

- [Line 49](../src/l5_5_semantic_memory_search/__main__.py#L49) creates the store with the index. That's the only place the index is set: the store is created once with it, and every `put` and `search` uses it. Leave `index=` out and the store raises no error: `search` silently ignores `query=` and returns items with `score=None`. Only code that formats the score breaks, which is why the keys-versus-meaning section then crashes with a `TypeError` (see line 116 below).
- [Monday](../src/l5_5_semantic_memory_search/__main__.py#L53-L58): two sentences, one genre each, so each memory gets a note that describes it. "Any book for tonight?" has no theme words and gets the fallback reply with both books.
- [Tuesday](../src/l5_5_semantic_memory_search/__main__.py#L61-L76): the requests describe a book instead of naming a genre, so `route` sends them to `recommend`. The first finds sci-fi, the second finds mystery. After the skip, the same whodunit request can only see sci-fi, which scores 0.00, so the fallback answers "Try: Dune (sci-fi)." without a score.
- [Bob](../src/l5_5_semantic_memory_search/__main__.py#L79-L84): the namespace still separates users. His wizard request is compared only with his own fantasy memory.
- [What the store holds](../src/l5_5_semantic_memory_search/__main__.py#L87-L104) is the same as in 5.4. The printed values now include the `note`. Mystery's note is the skip sentence, which shows that the upsert replaced it. The vectors themselves are not part of `item.value`, so they are not printed.
- [Keys versus meaning](../src/l5_5_semantic_memory_search/__main__.py#L107-L118) reuses `ns` from the section above. [Line 112](../src/l5_5_semantic_memory_search/__main__.py#L112) asks for the key `'space'` and gets `None`, because `get` matches the key exactly and there is no such key. [Line 113](../src/l5_5_semantic_memory_search/__main__.py#L113) searches the same namespace by meaning, with no filter, so both of Ada's memories come back, ranked: sci-fi 0.95, because the query hits both its space and robots axes, and the avoided mystery memory at 0.00. Line 116 formats `i.score` with `:.2f`, which only works because this store has an index. Without one, `score` would be `None` and this line would raise a `TypeError`.

## [test_semantic_search.py](../tests/test_semantic_search.py)

Each test builds its own store. The helper [`ada_graph`](../tests/test_semantic_search.py#L30-L35) replays Ada's two Monday sentences, and [`scores`](../tests/test_semantic_search.py#L38-L41) turns a search into `(key, rounded score)` pairs. When two scores are equal, the tests compare dicts instead of lists, so they don't rely on the order of tied items.

- [`test_fake_embedding_is_readable_and_never_zero`](../tests/test_semantic_search.py#L44-L48): the exact vectors for a text with no theme words and for the sci-fi note, and their length against `MEMORY_INDEX["dims"]`.
- [`test_search_finds_memories_by_meaning`](../tests/test_semantic_search.py#L51-L72): search ranks sci-fi at 0.89 for the spaceship request, while `get` with the key `'spaceship'` finds nothing. The rest checks the replies: a scored pick on a new thread, the fallback for a vague request, and Bob's empty namespace.
- [`test_filter_and_query_together_and_upsert_reembeds`](../tests/test_semantic_search.py#L75-L85): the skip removes mystery from the liked candidates and replaces its vector. [Line 85](../tests/test_semantic_search.py#L85) turns the filter around, to `stance` `avoid`: mystery is the only candidate, and its new note, which contains "mystery", scores exactly 1.0 against "whodunit".
- [`test_fields_and_index_false_choose_what_is_embedded`](../tests/test_semantic_search.py#L88-L114):
  - Part (a) embeds `genre` instead of `note`. "space robots" scores sci-fi 0.71 instead of 0.95, because the word "sci-fi" carries no robots signal.
  - Part (b) stores a history item with `index=False`. `InMemoryStore` returns it after the scored items, with `score=None`, and only while fewer than `limit` results have been collected, so `limit=1` drops it. `get` still finds it. This placement is how `InMemoryStore` handles items without a vector. The documentation only says such items are not searchable, so other stores may treat them differently. The reply on [lines 112-114](../tests/test_semantic_search.py#L112-L114) shows the `is not None` check in `recommend`: the unscored history item can't pass the threshold, so the fallback lists it.
- [`test_store_without_index_ignores_query`](../tests/test_semantic_search.py#L117-L126): with a plain `InMemoryStore()`, nothing fails. `query=` is ignored, every score is `None`, and the spaceship request gets the fallback with both books.

## [pyproject.toml](../pyproject.toml)

[Line 10](../pyproject.toml#L10) adds `numpy`. `InMemoryStore` computes cosine similarity with numpy when it is installed. Without numpy the scores are the same, but the store logs a one-time "NumPy not found" message to stderr, which would clutter the live run.
