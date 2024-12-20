import os
from enum import Enum
from typing import List, Literal, Optional, Union

import pytest
from autogen_agentchat.agents import OpenAIAssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core.base import CancellationToken
from autogen_core.components.tools._base import BaseTool, Tool
from openai import AsyncAzureOpenAI
from pydantic import BaseModel


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    FREE_RESPONSE = "FREE_RESPONSE"


class Question(BaseModel):
    question_text: str
    question_type: QuestionType
    choices: Optional[List[str]] = None


class DisplayQuizArgs(BaseModel):
    title: str
    questions: List[Question]


class QuizResponses(BaseModel):
    responses: List[str]


class DisplayQuizTool(BaseTool[DisplayQuizArgs, QuizResponses]):
    def __init__(self) -> None:
        super().__init__(
            args_type=DisplayQuizArgs,
            return_type=QuizResponses,
            name="display_quiz",
            description=(
                "Displays a quiz to the student and returns the student's responses. "
                "A single quiz can have multiple questions."
            ),
        )

    async def run(self, args: DisplayQuizArgs, cancellation_token: CancellationToken) -> QuizResponses:
        responses: List[str] = []
        for q in args.questions:
            if q.question_type == QuestionType.MULTIPLE_CHOICE:
                response = q.choices[0] if q.choices else ""
            elif q.question_type == QuestionType.FREE_RESPONSE:
                response = "Sample free response"
            else:
                response = ""
            responses.append(response)
        return QuizResponses(responses=responses)


@pytest.fixture
def client() -> AsyncAzureOpenAI:
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not all([azure_endpoint, api_key]):
        pytest.skip("Azure OpenAI credentials not found in environment variables")

    assert azure_endpoint is not None
    assert api_key is not None
    return AsyncAzureOpenAI(azure_endpoint=azure_endpoint, api_version=api_version, api_key=api_key)


@pytest.fixture
def agent(client: AsyncAzureOpenAI) -> OpenAIAssistantAgent:
    tools: List[Union[Literal["code_interpreter", "file_search"], Tool]] = [
        "code_interpreter",
        "file_search",
        DisplayQuizTool(),
    ]

    return OpenAIAssistantAgent(
        name="assistant",
        instructions="Help the user with their task.",
        model="gpt-4o-mini",
        description="OpenAI Assistant Agent",
        client=client,
        tools=tools,
    )


@pytest.fixture
def cancellation_token() -> CancellationToken:
    return CancellationToken()


@pytest.mark.asyncio
async def test_file_retrieval(agent: OpenAIAssistantAgent, cancellation_token: CancellationToken) -> None:
    file_path = r"C:\Users\lpinheiro\Github\autogen-test\data\SampleBooks\jungle_book.txt"
    await agent.on_upload_for_file_search(file_path, cancellation_token)

    message = TextMessage(source="user", content="What is the first sentence of the jungle scout book?")
    response = await agent.on_messages([message], cancellation_token)

    assert response.chat_message.content is not None
    assert isinstance(response.chat_message.content, str)
    assert len(response.chat_message.content) > 0

    await agent.delete_uploaded_files(cancellation_token)
    await agent.delete_vector_store(cancellation_token)
    await agent.delete_assistant(cancellation_token)


@pytest.mark.asyncio
async def test_code_interpreter(agent: OpenAIAssistantAgent, cancellation_token: CancellationToken) -> None:
    message = TextMessage(source="user", content="I need to solve the equation `3x + 11 = 14`. Can you help me?")
    response = await agent.on_messages([message], cancellation_token)

    assert response.chat_message.content is not None
    assert isinstance(response.chat_message.content, str)
    assert len(response.chat_message.content) > 0
    assert "x = 1" in response.chat_message.content.lower()

    await agent.delete_assistant(cancellation_token)


@pytest.mark.asyncio
async def test_quiz_creation(agent: OpenAIAssistantAgent, cancellation_token: CancellationToken) -> None:
    message = TextMessage(
        source="user",
        content="Create a short quiz about basic math with one multiple choice question and one free response question.",
    )
    response = await agent.on_messages([message], cancellation_token)

    assert response.chat_message.content is not None
    assert isinstance(response.chat_message.content, str)
    assert len(response.chat_message.content) > 0
    assert isinstance(response.inner_messages, list)
    assert any(tool_msg.content for tool_msg in response.inner_messages if hasattr(tool_msg, "content"))

    await agent.delete_assistant(cancellation_token)
