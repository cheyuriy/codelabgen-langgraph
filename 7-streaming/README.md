# 7 Streaming

Showing progress while a graph runs: state and update streams, typed v2 stream parts, custom progress events, LLM tokens, and the newer event streaming API.

## Lessons

- [7.1 Stream Modes: values, updates and Typed v2 Parts](7.1-stream-modes/README.md) — Streams an order-fulfilment graph (pick, pack, ship) with stream_mode values and updates, then several modes at once, and switches to version="v2" so every chunk is a typed StreamPart with type, ns and data.
- [7.2 Custom Progress Events with get_stream_writer](7.2-custom-stream-data/README.md) — The packing node reports per-item progress with get_stream_writer, and the caller prints it from stream_mode="custom" next to the regular updates.
- [7.3 Streaming LLM Tokens](7.3-streaming-llm-tokens/README.md) — Adds a node that writes a shipping confirmation with a fake chat model that streams chunk by chunk. Uses stream_mode="messages", filters tokens by node via metadata and by tags, and keeps a model silent with nostream.
- [7.4 Event Streaming with stream_events v3](7.4-event-streaming/README.md) — Consumes the same run through stream_events(version="v3"): a run stream object with typed projections for values, messages and the final output, compared with the stream-mode API.

[Home](../README.md)
