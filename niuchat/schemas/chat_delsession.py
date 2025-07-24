from pydantic import BaseModel, Field
from .base_response import BaseResponse

class ChatDelsessionIn(BaseModel):
    chat_session_id: int = Field(...)

class ChatDelsessionOut(BaseResponse):
    pass

