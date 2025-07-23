from .base_response import BaseResponse
from pydantic import BaseModel, Field

class UserInfoRequestIn(BaseModel):
    pass

class UserInfo(BaseModel):
    phone_number: str = Field(...)

class UserInfoRequestOut(BaseResponse):
    data: UserInfo = Field(...)
