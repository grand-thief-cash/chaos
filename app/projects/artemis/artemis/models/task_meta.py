from pydantic import BaseModel, Field, field_validator

from artemis.models.callback_endpoints import CallbackEndpoints


class TaskMeta(BaseModel):
    """Transport-level metadata schema."""

    run_id: int | str = Field(..., description="Run identifier")
    task_id: int | str = Field(..., description="Task identifier")
    exec_type: str = Field(..., description="SYNC|ASYNC")
    callback_endpoints: CallbackEndpoints | dict | None = None

    model_config = {"extra": "allow"}

    @field_validator("exec_type")
    @classmethod
    def _normalize_exec_type(cls, v: str) -> str:
        return str(v).upper().strip()

    def normalized_exec_type(self) -> str:
        return str(self.exec_type).upper()
