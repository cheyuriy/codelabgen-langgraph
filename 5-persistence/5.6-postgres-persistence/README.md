# 5.6 Postgres Checkpointer and Store for Production

Runs the reading-list assistant on PostgresSaver and PostgresStore against a real Postgres server: connection strings from the environment, setup(), and sharing state between two separate processes.

> [!NOTE]
> This lesson continues the example from [5.5 Semantic Search over Memories](../5.5-semantic-memory-search/README.md).

## What you will learn

- Connect PostgresSaver and PostgresStore from a connection string and create their tables with setup()
- Run the same thread from two processes and show that state is shared through the database
- List the operational concerns of production persistence (connections, thread ids, checkpoint growth)

## Lesson materials

- [Notes](docs/notes.md) — the concept, explained
- [Code walkthrough](docs/readalong.md) — the example's code, step by step
- Code: [__main__.py](src/l5_6_postgres_persistence/__main__.py), [assistant.py](src/l5_6_postgres_persistence/assistant.py)

## How to run

From the course root:

```bash
./run.sh 5.6
```

Or by hand:

```bash
docker compose up -d --wait postgres
cd 5-persistence && uv sync --all-packages --quiet
cd 5.6-postgres-persistence
uv run --package l5-6-postgres-persistence python -m l5_6_postgres_persistence
```

Run the tests:

```bash
./run.sh test 5.6
```

← Previous: [5.5 Semantic Search over Memories](../5.5-semantic-memory-search/README.md) · Next: [6.1 Pausing with interrupt() and Resuming with Command](../../6-human-in-the-loop/6.1-interrupt-and-resume/README.md) →
