# 6 Human-in-the-Loop and Time Travel

Pausing a run for a person with interrupt(), resuming it with Command(resume=...), the common approval and editing patterns, the rules that keep resumes correct, and going back in a thread's history.

## Lessons

- [6.1 Pausing with interrupt() and Resuming with Command](6.1-interrupt-and-resume/README.md) — A refund request above a limit pauses for a manager's decision. Shows interrupt() with a payload, why a checkpointer and thread_id are required, reading the pending interrupt (v1 __interrupt__ and v2 GraphOutput.interrupts), and resuming with Command(resume=...).
- [6.2 Approve, Edit and Validate: Interrupt Patterns](6.2-interrupt-patterns/README.md) — Extends the refund flow with the three standard patterns: approve or reject with Command routing, let the manager edit the refund amount before it is applied, and re-ask in a loop until the human input is valid.
- [6.3 The Rules of Interrupts](6.3-rules-of-interrupts/README.md) — Shows, with counters in the refund flow, that a resumed node re-runs from its start: side effects before interrupt() run twice unless made idempotent, several interrupts in one node are matched by order, and parallel interrupts are resumed with a map keyed by Interrupt.id.
- [6.4 Approving Tool Calls Inside an Agent](6.4-interrupts-in-tools/README.md) — A to-do agent may add tasks freely but must ask before deleting one: the delete tool calls interrupt() itself, so the agent loop pauses inside ToolNode and the human's answer becomes the tool result.
- [6.5 Time Travel: History, Replay and Forks](6.5-time-travel/README.md) — Walks back through the refund thread with get_state_history, replays from an earlier checkpoint, and forks it with update_state (including as_node) to try a different decision, comparing replay with fork.

[Home](../README.md)
