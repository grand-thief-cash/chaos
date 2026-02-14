from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TaskYamlGetResp(BaseModel):
    path: str = Field(..., description="Resolved task.yaml path")
    content: str = Field(..., description="Raw yaml content")


class TaskYamlPutReq(BaseModel):
    content: str = Field(..., description="Raw yaml content")


class TaskUnitTreeNode(BaseModel):
    name: str
    type: Literal["dir", "file"]
    children: Optional[List["TaskUnitTreeNode"]] = None


TaskUnitTreeNode.model_rebuild()


class TaskUnitsTreeResp(BaseModel):
    root: str
    items: List[TaskUnitTreeNode]


class TaskUnitFileGetResp(BaseModel):
    path: str
    content: str


class TaskUnitFilePutReq(BaseModel):
    path: str
    content: str


class TaskUnitFileCreateReq(BaseModel):
    path: str
    content: str


class TaskUnitRegisterReq(BaseModel):
    task_code: str = Field(..., description="Task code to register")
    module: str = Field(..., description="Python module path, e.g. artemis.task_units.zh.stock_zh_a_list")
    class_name: str = Field(..., description="Task class name")


class TaskUnitRegisterResp(BaseModel):
    task_code: str
    module: str
    class_name: str
