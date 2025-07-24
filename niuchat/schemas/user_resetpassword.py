from pydantic import BaseModel, Field
from .base_response import BaseResponse

class UserResetPasswordRequestIn(BaseModel):
    phone_number: str
    verify_code: str
    new_password: str = Field()

class UserResetPasswordRequestOut(BaseResponse):
    pass
