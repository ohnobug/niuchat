from pydantic import BaseModel, Field

# 响应基类
class BaseResponse(BaseModel):
    code: int = Field(..., example=200)
    message: str = Field(..., example="Success")
