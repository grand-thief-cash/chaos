from pydantic import BaseModel

class Record(BaseModel):
    symbol: str
    price: float
    timestamp: str

