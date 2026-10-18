"""Shared pytest fixtures: a recording fake chat model, a checkpointer, a config."""

from collections.abc import Callable
from typing import Any

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field


# region recording_model
class RecordingChatModel(GenericFakeChatModel):
    """A fake chat model that also remembers every prompt it received.

    GenericFakeChatModel returns the scripted AIMessages one per call and
    ignores its input. Recording the prompts lets a test check what the node
    sent to the model.
    """

    # Field(default_factory=list): pydantic gives every instance its own list.
    prompts: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record the prompt, then return the next scripted reply."""
        self.prompts.append(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


# endregion


# region fixtures
# All fixtures are function-scoped (the pytest default), and that is the
# point: every test gets its own model, checkpointer and config.


@pytest.fixture
def make_model() -> Callable[..., RecordingChatModel]:
    """Return a factory that builds a fake model with the given replies."""

    def _make(*replies: str) -> RecordingChatModel:
        # The script is an iterator that gets used up, so every test makes its
        # own model with exactly the replies its run needs.
        return RecordingChatModel(messages=iter([AIMessage(r) for r in replies]))

    return _make


@pytest.fixture
def checkpointer() -> InMemorySaver:
    """Return a fresh in-memory checkpointer for one test."""
    return InMemorySaver()


@pytest.fixture
def config() -> RunnableConfig:
    """Return the run config with the thread to save checkpoints under."""
    # Every test may use the same thread_id only because every test gets a
    # fresh checkpointer.
    return {"configurable": {"thread_id": "ticket-1"}}


# endregion
