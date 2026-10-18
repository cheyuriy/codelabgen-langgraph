# 6.3 The Rules of Interrupts

Shows, with counters in the refund flow, that a resumed node re-runs from its start: side effects before interrupt() run twice unless made idempotent, several interrupts in one node are matched by order, and parallel interrupts are resumed with a map keyed by Interrupt.id.

> [!NOTE]
> This lesson continues the example from [6.2 Approve, Edit and Validate: Interrupt Patterns](../6.2-interrupt-patterns/README.md).

## What you will learn

- Explain that a node restarts from the beginning on resume and keep side effects before interrupt() idempotent
- Use several interrupt() calls in one node in a stable order and avoid wrapping them in a bare try/except
- Resume several pending interrupts at once with Command(resume={interrupt_id: value})

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l6_3_rules_of_interrupts/__main__.py), [refunds.py](src/l6_3_rules_of_interrupts/refunds.py), [signoff.py](src/l6_3_rules_of_interrupts/signoff.py)

## How to run

From the course root:

```bash
./run.sh 6.3
```

Or by hand:

```bash
cd 6-human-in-the-loop && uv sync --all-packages --quiet
cd 6.3-rules-of-interrupts
uv run --package l6-3-rules-of-interrupts python -m l6_3_rules_of_interrupts
```

Run the tests:

```bash
./run.sh test 6.3
```

← Previous: [6.2 Approve, Edit and Validate: Interrupt Patterns](../6.2-interrupt-patterns/README.md) · Next: [6.4 Approving Tool Calls Inside an Agent](../6.4-interrupts-in-tools/README.md) →
