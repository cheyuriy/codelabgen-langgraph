"""Live run: one four-turn thread on a SQLite checkpointer.

It prints what the model receives on every call and what the thread saved
after every turn, then how the thread's checkpoints look. Fully offline: both
the chat model and the summarizer are scripted fakes.
"""

import tempfile
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver

from l5_3_message_history.chatbot import (
    SUMMARY_PREFIX,
    ToolCallingFakeModel,
    build_graph,
    tool_call,
)


# region peeking_model
class PeekingModel(ToolCallingFakeModel):
    """A scripted fake that prints the message types of every input it gets.

    The scripted fake ignores its input; this subclass prints it, so the run
    can show what trimming sent. A real model receives the same list. Build it
    as ``PeekingModel(messages=iter(replies), label=...)``, the same thing
    make_model does.
    """

    # A pydantic field (chat models are pydantic models), shown in the output.
    label: str = "model"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Print the type of every input message, then return the next scripted reply."""
        kinds = [
            # A system message that carries the summary is marked as such.
            "system+summary"
            if isinstance(m, SystemMessage) and SUMMARY_PREFIX in m.content
            else m.type
            for m in messages
        ]
        print(f"    {self.label} gets: {' '.join(kinds)}")
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


# endregion


def main() -> None:
    """Run four turns on one thread and print what the models saw and what was saved."""
    # The scripts are built here, fresh for this run: the fake sets ids on them.
    script = [
        tool_call("add", "call_1", a=3, b=4),  # turn 1
        AIMessage("3 + 4 is 7."),
        tool_call("multiply", "call_2", a=7, b=2),  # turn 2
        AIMessage("7 * 2 is 14."),
        AIMessage("So far: 3 + 4 = 7, then 7 * 2 = 14."),  # turn 3
        tool_call("divide", "call_3", a=14, b=7),  # turn 4
        AIMessage("14 / 7 is 2.0."),
    ]
    # The summarizer is a scripted fake too, not a plain function: the
    # summarize node then has its production shape (prompt in, AIMessage out),
    # and switching to a real model changes one argument. The texts are what a
    # model would write about the messages it is given: turn 1 at the first
    # summary; turns 2 and 3 plus the old summary at the second.
    summaries = [
        AIMessage("The user asked for 3 + 4 (7)."),
        AIMessage("The user asked for 3 + 4 (7), multiplied it by 2 (14) and asked for a recap."),
    ]
    questions = [
        "What is 3 + 4?",
        "Now multiply that by 2.",
        "What have we computed so far?",
        "Divide that by 7.",
    ]

    # The same durable checkpointer as 5.2, now in one process. The deletions
    # below are written to the file like any other update. A fresh temp file
    # keeps the output reproducible.
    with (
        tempfile.TemporaryDirectory() as tmp,
        SqliteSaver.from_conn_string(str(Path(tmp) / "checkpoints.sqlite")) as checkpointer,
    ):
        graph = build_graph(
            PeekingModel(messages=iter(script)),
            checkpointer,
            PeekingModel(messages=iter(summaries), label="summarizer"),
        )
        config: RunnableConfig = {"configurable": {"thread_id": "chat-1"}}

        # region conversation
        # What to look for:
        # - turn 2's second call gets only "human ai tool" although 5 messages
        #   were allowed: start_on cut the window back to the turn's HumanMessage;
        # - after turn 2 the state passes 6 messages, so summarize deletes
        #   turn 1 and writes the first summary;
        # - turn 3 stays at 6, below the threshold: no summary;
        # - turn 4 summarizes again and extends the summary.
        # The summarizer's last "human" is the instruction, not a user question.
        for i, question in enumerate(questions, 1):
            print(f"== turn {i}: {question} ==")
            result = graph.invoke({"messages": [HumanMessage(question)]}, config)
            print(f"  answer: {result['messages'][-1].content}")
            print(
                f"  saved: {len(result['messages'])} messages "
                f"({' '.join(m.type for m in result['messages'])})"
            )
            print(f"  summary: {result.get('summary', '(none yet)')}")
            print()
        # endregion

        # region checkpoint_history
        # RemoveMessage changes the state from this checkpoint on; it does not
        # rewrite history. Earlier checkpoints of the thread still hold the
        # deleted messages (time travel, lesson 6.5, relies on that). To really
        # erase a conversation, delete the thread (checkpointer.delete_thread).
        # checkpoint["channel_values"] is the raw saved state.
        print("== the thread's checkpoints ==")
        checkpoints = list(checkpointer.list(config))  # newest first
        latest = len(checkpoints[0].checkpoint["channel_values"]["messages"])
        most = max(len(c.checkpoint["channel_values"].get("messages", [])) for c in checkpoints)
        print(
            f"  latest: {latest} messages; most in any checkpoint: {most}; "
            f"checkpoints: {len(checkpoints)}"
        )
        # endregion


if __name__ == "__main__":
    main()
