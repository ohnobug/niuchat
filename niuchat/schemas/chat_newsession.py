from pydantic import BaseModel, Field
from .base_response import BaseResponse

class ChatNewsessionIn(BaseModel):
    title: str = Field(...)

class ChatNewsession(BaseModel):
    chat_session_id: int
    llm_model_name: str
    me_smart_customer_service_version: str

class ChatNewsessionOut(BaseResponse):
    data: ChatNewsession = Field(...)
