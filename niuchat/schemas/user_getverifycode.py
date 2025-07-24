from pydantic import BaseModel, Field
from .base_response import BaseResponse
import enum

class UserGetVerifyCodePurposeEnum(str, enum.Enum):
    """
    验证码用途枚举
    """
    REGISTER = "register"
    FORGOT_PASSWORD = "forgot_password"
    LOGIN = "login"
    BIND_PHONE = "bind_phone"


class UserGetVerifyCodeRequestIn(BaseModel):
    phone_number: str = Field(...)
    purpose: UserGetVerifyCodePurposeEnum = Field(..., description="验证码用途")


class UserGetVerifyCodeRequestOut(BaseResponse):
    pass

