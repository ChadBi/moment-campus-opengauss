from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List
from math import ceil

T = TypeVar("T")


class MessageResponse(BaseModel):
    code: int = Field(default=0, description="业务状态码，0表示成功")
    message: str = Field(default="success", description="响应消息")
    data: Optional[dict] = Field(default=None, description="响应数据")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list, description="数据列表")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    total: int = Field(default=0, ge=0, description="总记录数")
    total_pages: int = Field(default=0, ge=0, description="总页数")
    has_more: bool = Field(default=False, description="是否还有更多数据（page < total_pages）")

    @classmethod
    def create(cls, items: List[T], page: int, page_size: int, total: int) -> "PaginatedResponse[T]":
        total_pages = ceil(total / page_size) if page_size > 0 else 0
        has_more = page < total_pages
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_more=has_more,
        )
