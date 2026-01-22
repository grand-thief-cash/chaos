from typing import Dict, Any

from pydantic import BaseModel, Field, field_validator

from artemis.consts import TaskCode


class CallbackEndpoints(BaseModel):
    progress: str | None = None
    callback: str | None = None
    callback_ip: str | None = None
    callback_port: int | None = None


class TaskMeta(BaseModel):
    """Transport-level metadata schema."""

    run_id: int | str = Field(..., description="Run identifier")
    task_id: int | str = Field(..., description="Task identifier")
    exec_type: str = Field(..., description="SYNC|ASYNC")
    task_code: TaskCode = Field(..., description="Task code")
    callback_endpoints: CallbackEndpoints = None

    @field_validator("exec_type")
    @classmethod
    def _normalize_exec_type(cls, v: str) -> str:
        value = str(v).upper().strip() if v is not None else None
        if value is None or value not in ["SYNC", "ASYNC"]:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="exec_type in meta required")
        return value

    @field_validator("run_id", "task_id", "task_code")
    @classmethod
    def _validate_required_fields(cls, v, info):
        if v is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=422,detail=f"{info.field_name} in meta required")
        return v

# class TaskBody(BaseModel):
#     pass


class TaskRunReq(BaseModel):
    """Task run request schema."""
    task_meta: TaskMeta = Field(..., alias="meta")
    task_body: Dict[str, Any] = Field(default={}, alias="body")
