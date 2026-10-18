# 6.2 Approve, Edit and Validate: Interrupt Patterns

Extends the refund flow with the three standard patterns: approve or reject with Command routing, let the manager edit the refund amount before it is applied, and re-ask in a loop until the human input is valid.

> [!NOTE]
> This lesson continues the example from [6.1 Pausing with interrupt() and Resuming with Command](../6.1-interrupt-and-resume/README.md).

## What you will learn

- Route on a human decision by returning Command(goto=...) after interrupt()
- Let a human edit a proposed value and apply the edited version
- Validate human input and interrupt again until it is acceptable

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l6_2_interrupt_patterns/__main__.py), [refunds.py](src/l6_2_interrupt_patterns/refunds.py)

## How to run

From the course root:

```bash
./run.sh 6.2
```

Or by hand:

```bash
cd 6-human-in-the-loop && uv sync --all-packages --quiet
cd 6.2-interrupt-patterns
uv run --package l6-2-interrupt-patterns python -m l6_2_interrupt_patterns
```

Run the tests:

```bash
./run.sh test 6.2
```

← Previous: [6.1 Pausing with interrupt() and Resuming with Command](../6.1-interrupt-and-resume/README.md) · Next: [6.3 The Rules of Interrupts](../6.3-rules-of-interrupts/README.md) →
