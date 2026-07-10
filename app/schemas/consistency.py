from pydantic import BaseModel


class ConsistencyCheckItem(BaseModel):
    level: str
    code: str
    message: str
    source: str


class ConsistencyCheckResponse(BaseModel):
    status: str
    items: list[ConsistencyCheckItem]
