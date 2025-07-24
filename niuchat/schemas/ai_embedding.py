from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EmbeddingItem(BaseModel):
    # 'id' 将由 Milvus 自动生成，因此在插入时是可选的
    question: str = Field(..., description="问题")
    answer: str = Field(..., description="答案")
    category: str = Field(..., description="分类")
    embedding: List[float] = Field(..., description="向量")

class EmbeddingInsertIn(BaseModel):
    collection_name: str = "me_knowledge_base"
    data: List[EmbeddingItem]

class EmbeddingInsertOut(BaseModel):
    code: int = 200
    message: str = "success"
    data: Dict[str, Any] = Field(..., description="返回插入数据的ID列表, e.g., {'inserted_ids': [1, 2, 3]}")

class EmbeddingSearchIn(BaseModel):
    collection_name: str = "demo_collection"
    data: List[List[float]] = Field(..., description="用于搜索的查询向量列表")
    filter: Optional[str] = Field(None, description="过滤条件, e.g., \"subject == 'history'\"")
    limit: int = Field(5, description="返回最相似结果的数量")
    output_fields: Optional[List[str]] = Field(["text", "subject"], description="需要返回的字段列表")

class EmbeddingQueryIn(BaseModel):
    collection_name: str = "demo_collection"
    filter: str = Field(..., description="过滤条件, e.g., \"id in [1, 2]\"")
    output_fields: Optional[List[str]] = Field(["text", "subject"], description="需要返回的字段列表")

class EmbeddingDeleteIn(BaseModel):
    collection_name: str = "demo_collection"
    filter: str = Field(..., description="用于删除的过滤条件, e.g., \"subject == 'history'\"")

class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any
