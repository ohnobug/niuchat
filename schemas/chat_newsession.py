from pydantic import BaseModel, Field
from .base_response import BaseResponse

class ChatNewsessionIn(BaseModel):
    title: str = Field(...)

class ChatNewsession(BaseModel):
    chat_session_id: int

class ChatNewsessionOut(BaseResponse):
    data: ChatNewsession = Field(...)
