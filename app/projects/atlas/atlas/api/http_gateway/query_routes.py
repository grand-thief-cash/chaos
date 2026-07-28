from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/v1/atlas-kg", tags=["atlas-query"])


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=2, max_length=2000)


class CompanyReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str = Field(min_length=1, max_length=256)


@router.post("/query")
async def query_knowledge(payload: QueryRequest, request: Request):
    if request.app.state.runtime.query_orchestrator is None:
        raise HTTPException(status_code=503, detail="query model adapter is not configured")
    try:
        result = await request.app.state.runtime.query_orchestrator.run(
            payload.question
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.post("/company-reviews")
async def create_company_review(payload: CompanyReviewRequest, request: Request):
    if request.app.state.runtime.company_review_agent is None:
        raise HTTPException(
            status_code=503,
            detail="company review model adapter is not configured",
        )
    try:
        result = await request.app.state.runtime.company_review_agent.review(
            payload.company_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.model_dump(mode="json")
