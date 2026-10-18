"""Live run: a support supervisor that calls billing and shipping agents as tools.

Run with: python -m l8_4_supervisor_agents
"""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from l8_4_supervisor_agents.fake_model import make_model
from l8_4_supervisor_agents.scripts import (
    SHIPPING_QUESTION,
    TWO_PART_QUESTION,
    billing_script,
    shipping_script,
    supervisor_one_script,
    supervisor_two_script,
)
from l8_4_supervisor_agents.show import describe, node_path
from l8_4_supervisor_agents.specialists import build_billing_agent, build_shipping_agent
from l8_4_supervisor_agents.supervisor import build_supervisor

CONFIG: RunnableConfig = {"recursion_limit": 10}


def main() -> None:
    """Run the three sections. Each builds fresh models and agents (scripts run once)."""
    # region trace_one
    print("== 1. One question through two levels ==")
    print("question:", SHIPPING_QUESTION)
    supervisor = build_supervisor(
        make_model(supervisor_one_script()),
        build_billing_agent(make_model([])),  # never called in this section
        build_shipping_agent(make_model(shipping_script())),
    )
    # With subgraphs=True each item is (namespace, update). () is the
    # supervisor; ("tools:<id>",) is the specialist run started inside the
    # supervisor's tools node. The inner run's input HumanMessage is not an
    # update, so it is not printed. Only one specialist runs, so the order
    # of the lines is the same every time.
    for ns, update in supervisor.stream(
        {"messages": [HumanMessage(SHIPPING_QUESTION)]},
        CONFIG,
        stream_mode="updates",
        subgraphs=True,
    ):
        for node, node_update in update.items():
            for m in node_update["messages"]:
                print(f"  {node_path(ns):<7} {node:<6} {describe(m)}")
    # endregion
    print()

    # region two_specialists
    print("== 2. Two specialists in one step ==")
    print("question:", TWO_PART_QUESTION)
    supervisor = build_supervisor(
        make_model(supervisor_two_script()),
        build_billing_agent(make_model(billing_script())),
        build_shipping_agent(make_model(shipping_script())),
    )
    # Do NOT print the nested trace here: the two specialist runs are
    # concurrent, and their lines interleave differently from run to run.
    # The final state keeps the call order (call_1, call_2), and both
    # "tools" updates have the same node name, so these summaries are stable.
    steps: list[str] = []  # node names of the supervisor's own updates
    counts: dict[tuple[str, ...], int] = {}  # messages per nested run
    names: dict[tuple[str, ...], str] = {}  # agent name per nested run
    final_state: dict = {}
    for ns, mode, data in supervisor.stream(
        {"messages": [HumanMessage(TWO_PART_QUESTION)]},
        CONFIG,
        stream_mode=["updates", "values"],
        subgraphs=True,
    ):
        if mode == "values":
            if not ns:
                final_state = data  # the last one is the final state
            continue
        for node, node_update in data.items():
            if not ns:
                steps.append(node)
                continue
            for m in node_update["messages"]:
                counts[ns] = counts.get(ns, 0) + 1
                if isinstance(m, AIMessage) and m.name and ns not in names:
                    names[ns] = m.name
    print("  supervisor steps: " + " -> ".join(steps))
    runs = sorted(f"{names[ns]} ({n} messages)" for ns, n in counts.items())
    print("  specialist runs: " + ", ".join(runs))
    print("  the supervisor's history:")
    for m in final_state["messages"]:
        print(f"    {describe(m)}")
    # endregion
    print()

    # region on_its_own
    print("== 3. A specialist on its own ==")
    # The specialist does not know it is used as a tool and needs no parent.
    # Contrast 8.3: a team run on its own raised ParentCommand when it handed off.
    result = build_billing_agent(make_model(billing_script())).invoke(
        {"messages": [HumanMessage("Why was INV-2077 charged twice?")]}, CONFIG
    )
    for m in result["messages"]:
        print(f"  {describe(m)}")
    # endregion


if __name__ == "__main__":
    main()
