from pydantic import BaseModel

class CallbackEndpoints(BaseModel):
    progress: str | None = None
    callback: str | None = None
