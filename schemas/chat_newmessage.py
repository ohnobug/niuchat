from pydantic import BaseModel, Field
from .base_response import BaseResponse

class ChatNewmessageIn(BaseModel):
    chat_session_id: int = Field(...)
    text: str

class ChatNewmessage(BaseModel):
    chat_message_id: int
    ai_message_id: int

class ChatNewmessageOut(BaseResponse):
    data: ChatNewmessage = Field(...)