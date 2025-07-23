from .base_response import BaseResponse
from pydantic import BaseModel, Field
from typing import Dict

class ChatHistoryIn(BaseModel):
    chat_session_id: int = Field(..., example=1)

class ChatHistory(BaseModel):
    id: int
    sender: str
    text: str
    created_at: int
    
class ChatHistoryOut(BaseResponse):
    data: Dict[int, ChatHistory] = Field(...)
