from __future__ import annotations

from typing import Protocol

from atlas.models import QueryAnswer


class KnowledgeQuery(Protocol):
    async def run(self, question: str) -> QueryAnswer: ...


class CompanyReviewAgent:
    """A read-only, evidence-bound specialization of the Atlas query agent."""

    def __init__(self, query: KnowledgeQuery) -> None:
        self.query = query

    async def review(self, company_name: str) -> QueryAnswer:
        return await self.query.run(
            f"""
为公司“{company_name}”生成产业知识综述。只允许使用 Atlas 工具返回的数据。
必须按以下结构组织：
1. 实体识别结果与歧义；
2. 已观察事实与公司披露；
3. 产品、上游投入、供应商、客户及产业链位置；
4. 量化信息；
5. 分析师观点、预测和管理层计划（必须与事实分开）；
6. 信息缺口。
每项结论必须保留 source_document_id、page_number 和 evidence_quote（若工具结果提供）。
不得把分析师观点或预测改写成事实；证据不足时明确说明。
""".strip()
        )
