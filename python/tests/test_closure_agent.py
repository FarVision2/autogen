

from dataclasses import dataclass

import pytest
from agnext.application import SingleThreadedAgentRuntime

from agnext.core import AgentRuntime, AgentId

from agnext.components import ClosureAgent


import asyncio

from agnext.core import MessageContext

@dataclass
class Message:
    content: str



@pytest.mark.asyncio
async def test_register_receives_publish() -> None:
    runtime = SingleThreadedAgentRuntime()

    queue = asyncio.Queue[tuple[str, str]]()

    async def log_message(_runtime: AgentRuntime, id: AgentId, message: Message, ctx: MessageContext) -> None:
        key = id.key
        await queue.put((key, message.content))

    await runtime.register("name", lambda: ClosureAgent("My agent", log_message))
    run_context = runtime.start()
    await runtime.publish_message(Message("first message"), namespace="default")
    await runtime.publish_message(Message("second message"), namespace="default")
    await runtime.publish_message(Message("third message"), namespace="default")

    await run_context.stop_when_idle()

    assert queue.qsize() == 3
    assert queue.get_nowait() == ("default", "first message")
    assert queue.get_nowait() == ("default", "second message")
    assert queue.get_nowait() == ("default", "third message")
    assert queue.empty()
