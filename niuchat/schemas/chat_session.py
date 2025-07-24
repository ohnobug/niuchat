from pydantic import BaseModel, Field
from typing import Dict
from .base_response import BaseResponse

class ChatSessionIn(BaseModel):
    pass

class ChatSession(BaseModel):
    id: int
    title: str

class ChatSessionOut(BaseResponse):
    data: Dict[int, ChatSession] = Field(...)