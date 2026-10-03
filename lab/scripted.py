"""Scripted agent turns for Inspect's mockllm provider.

The "model" is a fixed list of ModelOutputs. The react() agent sends each
scripted tool call to a real sandbox, so the tool results in the log are
genuine output from the container. See spike/SPIKE-NOTES.md for why turns
with reasoning are built by hand.
"""

import time

from inspect_ai.model import (
    ChatMessageAssistant,
    ContentReasoning,
    ContentText,
    Model,
    ModelOutput,
    get_model,
)
from inspect_ai.tool import ToolCall

MODEL = "mockllm/model"


def turn(
    function: str,
    arguments: dict,
    call_id: str,
    text: str | None = None,
    reasoning: str | None = None,
) -> ModelOutput:
    """One assistant turn: optional reasoning, optional visible text, one tool call."""
    content: list = []
    if reasoning:
        content.append(ContentReasoning(reasoning=reasoning))
    if text:
        content.append(ContentText(text=text))
    message = ChatMessageAssistant(
        content=content or "",
        tool_calls=[ToolCall(id=call_id, function=function, arguments=arguments)],
        model=MODEL,
        source="generate",
    )
    return ModelOutput.from_message(message, stop_reason="tool_calls")


def scripted(outputs: list[ModelOutput], think_seconds: list[float] | None = None) -> Model:
    """A model that replays `outputs` in order.

    `think_seconds`, if given, pauses before each output so the log's timing
    looks like a real model's (seconds per turn, not milliseconds). The pause
    blocks the event loop, which is fine for a single-sample run.
    """
    if not think_seconds:
        return get_model(MODEL, custom_outputs=outputs)

    def paced():
        for output, delay in zip(outputs, think_seconds, strict=True):
            time.sleep(delay)
            yield output

    return get_model(MODEL, custom_outputs=paced())
