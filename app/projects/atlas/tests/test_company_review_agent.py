import pytest

from atlas.intelligence import CompanyReviewAgent
from atlas.models import QueryAnswer


class Query:
    def __init__(self):
        self.question = ""

    async def run(self, question):
        self.question = question
        return QueryAnswer(answer="review")


@pytest.mark.asyncio
async def test_company_review_requires_fact_opinion_separation_and_evidence():
    query = Query()
    result = await CompanyReviewAgent(query).review("Company A")
    assert result.answer == "review"
    assert "Company A" in query.question
    assert "不得把分析师观点或预测改写成事实" in query.question
    assert "evidence_quote" in query.question
