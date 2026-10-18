"""Live run: a shipment fails half-way, is fixed and resumed from its last checkpoint."""

import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.memory import InMemorySaver

from l10_4_recover_failed_run.graph import build_graph
from l10_4_recover_failed_run.service import LabelPrinterOffline, ParcelTooHeavy, ShippingApi


# region main
async def show_quote(graph: Any, request: dict[str, Any] | None, config: RunnableConfig) -> None:
    """Run one quote on the config's thread and print every node update as it arrives.

    `request` None means "resume": continue the thread from its last
    checkpoint instead of starting a new run.
    """
    # "updates" yields one dict per finished node. A node answered from the
    # cache also carries {'__metadata__': {'cached': True}}, and so does a
    # replayed pending write: a node that finished before the failure and
    # is not run again on resume.
    async for update in graph.astream(request, config, stream_mode="updates"):
        print(update)


# region show_saved
async def show_saved(graph: Any, config: RunnableConfig) -> None:
    """Print what the checkpointer kept for the thread in `config`."""
    # get_state reads the latest checkpoint of the thread. `next` is the
    # tasks still to run.
    snapshot = await graph.aget_state(config)
    print(f"saved: next={snapshot.next}")
    # `tasks` are the tasks of that step. A failed task has the error it
    # raised, as the saved repr string (it went through the serializer). A
    # task whose writes were saved has them in `result`. A task with neither
    # has nothing saved: under durability="exit" a cancelled sibling's error
    # is never written, yet it is still in `next` and runs again.
    for task in snapshot.tasks:
        if task.error is not None:
            print(f"  {task.name}: failed with {task.error}")
        elif task.result is not None:
            print(f"  {task.name}: finished, kept {task.result}")
        else:
            print(f"  {task.name}: nothing saved, runs again")


# endregion


async def main() -> None:
    """Run the five sections against one API, one cache and one checkpointer."""
    api = ShippingApi()
    # One checkpointer for every thread, and each shipment is its own
    # thread_id.
    checkpointer = InMemorySaver()
    # A sync invoke() still fails, now with TypeError: No synchronous
    # function provided to "__error_handler__lookup_zone".
    graph = build_graph(api, cache=InMemoryCache(), checkpointer=checkpointer)

    print("== 1. A healthy shipment: book_pickup and print_label run in parallel ==")
    config: RunnableConfig = {"configurable": {"thread_id": "shipment-1"}}
    await show_quote(graph, {"address": "12 Baker Street, London", "weight_kg": 2.0}, config)

    print()
    # region failed_run
    print("== 2. The label printer is offline: the run fails after book_pickup has finished ==")
    config = {"configurable": {"thread_id": "shipment-2"}}
    api.printer_online = False
    try:
        await show_quote(graph, {"address": "1 Rue de Rivoli, Paris", "weight_kg": 1.0}, config)
    except LabelPrinterOffline as error:
        # No handler caught it, so the error reaches the caller.
        print(f"run failed: {error}")
    # The checkpointer kept the checkpoint before this step and
    # book_pickup's finished write.
    await show_saved(graph, config)
    # endregion

    print()
    # region resume
    print("== 3. The printer is back: resume with None on the same thread ==")
    # Fix the cause first. A resume while the printer is still offline fails
    # the same way.
    api.printer_online = True
    calls_before = api.rate_calls
    pickups_before = api.pickups_booked
    labels_before = api.labels_printed
    # None means "no new input: continue this thread from its last
    # checkpoint". The original input would start the run over.
    await show_quote(graph, None, config)
    print(
        f"during the resume: rate calls {api.rate_calls - calls_before}, "
        f"pickups booked {api.pickups_booked - pickups_before}, "
        f"labels printed {api.labels_printed - labels_before}"
    )
    # endregion

    print()
    # region durability_modes
    print("== 4. Durability modes: what a failed run leaves in the checkpointer ==")
    # Durability is chosen per call. On an ordinary exception every mode
    # keeps the failed step and its finished writes; "exit" just writes them
    # once, on the way out. The difference is a hard crash: "sync" has every
    # finished step and write saved, "async" may lose the newest ones, and
    # "exit" loses the whole run (lesson 5.2 measured it). An in-memory
    # saver survives no crash at all.
    for mode in ("sync", "async", "exit"):
        config = {"configurable": {"thread_id": f"durability-{mode}"}}
        api.printer_online = False
        try:
            await graph.ainvoke(
                {"address": "5 Market Street, Manchester", "weight_kg": 3.0},
                config,
                durability=mode,
            )
        except LabelPrinterOffline:
            pass
        # checkpointer.list(config) lists this thread's checkpoints, newest
        # first.
        saved = len(list(checkpointer.list(config)))
        snapshot = await graph.aget_state(config)
        # Kept means "has a saved result". A missing error is not enough:
        # under "exit" a cancelled sibling has neither and runs again.
        kept = [task.name for task in snapshot.tasks if task.result is not None]
        api.printer_online = True
        pickups_before = api.pickups_booked
        await graph.ainvoke(None, config, durability=mode)
        print(
            f"{mode:<5} checkpoints: {saved}  next: {snapshot.next}  kept: {kept}  "
            f"pickups booked on resume: {api.pickups_booked - pickups_before}"
        )
    # endregion

    print()
    # region closed_thread
    print("== 5. A failure an error handler re-raised: the thread is closed ==")
    config = {"configurable": {"thread_id": "shipment-3"}}
    try:
        await show_quote(
            graph, {"address": "10 Unter den Linden, Berlin", "weight_kg": 40.0}, config
        )
    except ParcelTooHeavy as error:
        print(f"run failed: {error}")
    # fallback_quote re-raised the original error. LangGraph 1.2.16 then
    # records the step as finished, so next is empty and the resume runs
    # nothing: it only returns the saved values. A node with an error
    # handler cannot be fixed and resumed, which is why the shipment nodes
    # have none.
    await show_saved(graph, config)
    calls_before = api.rate_calls
    await graph.ainvoke(None, config)
    print(f"rate service calls during the resume: {api.rate_calls - calls_before}")
    # endregion


if __name__ == "__main__":
    asyncio.run(main())
# endregion
