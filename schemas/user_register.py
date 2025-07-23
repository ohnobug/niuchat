from .base_response import BaseResponse
from pydantic import BaseModel, Field

class UserRegisterRequestIn(BaseModel):
    phone_number: str = Field(...)
    password: str = Field(...)
    verify_code: str = Field(...)

class UserRegisterRequestOut(BaseResponse):
    pass
