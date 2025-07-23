from .base_response import BaseResponse
from pydantic import BaseModel, Field

class UserLoginRequestIn(BaseModel):
    phone_number: str = Field(..., example="")
    password: str = Field(..., example="")
    
class UserLoginToken(BaseModel):
    token: str = Field(...)

class UserLoginRequestOut(BaseResponse):
    data: UserLoginToken = Field(...)