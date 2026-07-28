import pytest

from atlas.intelligence import QueryOrchestrator
from atlas.models import QueryAnswer, QueryPlan, QueryToolCall


class Model:
    def __init__(self, tool):
        self.tool = tool
    async def plan(self, question, allowed_tools):
        return QueryPlan(question=question, calls=[QueryToolCall(tool=self.tool)], answer_instruction="grounded")
    async def answer(self, question, observations):
        return QueryAnswer(answer="基于图谱结果", citations=[])


class Tools:
    async def execute(self, tool, arguments):
        return {
            "ok": True,
            "source_document_id": "report:1",
            "page_number": 2,
        }


@pytest.mark.asyncio
async def test_query_orchestrator_rejects_arbitrary_tool():
    with pytest.raises(ValueError, match="forbidden"):
        await QueryOrchestrator(Model("run_cypher"), Tools()).run("测试")
    answer = await QueryOrchestrator(Model("get_claims"), Tools()).run("测试")
    assert answer.tool_trace[0]["tool"] == "get_claims"


@pytest.mark.asyncio
async def test_query_orchestrator_rejects_invented_citation():
    class CitationModel(Model):
        async def answer(self, question, observations):
            return QueryAnswer(
                answer="unsupported",
                citations=[{
                    "source_document_id": "invented:1",
                    "page_number": 99,
                }],
            )

    with pytest.raises(ValueError, match="unsupported citations"):
        await QueryOrchestrator(
            CitationModel("get_claims"),
            Tools(),
        ).run("测试")
