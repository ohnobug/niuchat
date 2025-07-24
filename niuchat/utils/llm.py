
from enum import Enum
from typing import AsyncGenerator, List
import openai
from pydantic import BaseModel
import config

async def get_embedding(text: str):
    """得到词嵌入

    Args:
        text: 文本
    """
    client_openai = openai.AsyncOpenAI(
        base_url=config.EMBEDDING_BASE_URL,
        api_key=config.EMBEDDING_API_KEY,
    )

    response_embedding = await client_openai.embeddings.create(
        model=config.EMBEDDING_MODEL_NAME,
        input=[text]
    )

    return response_embedding.data[0].embedding


class RoleEnum(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"

class Message(BaseModel):
    role: RoleEnum
    content: str

async def llmchat(messages: List[Message]) -> AsyncGenerator[str, None]:
    client = openai.AsyncOpenAI(
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL
    )

    stream = await client.chat.completions.create(
        model=config.LLM_MODEL_NAME,
        stream=True,
        messages=messages
    )

    async for event in stream:
        content = event.choices[0].delta.content if event.choices and event.choices[0].delta else None

        if content:
            yield content
