## 八、抽取对象：Claim，而不是直接的 Graph Edge

### 8.1 为什么需要 Claim

研报中的句子可能是：

- 已经发生的事实。
- 公司自己的披露。
- 管理层计划。
- 券商估计。
- 分析师观点。
- 条件情景。

如果模型抽取后直接写成 Neo4j 关系，这些语义会被压平为“事实”。

因此 LLM 的标准产出是 Claim，Graph Edge 只是已接受 Claim 的投影视图。

### 8.2 Assertion Type

```text
OBSERVED_FACT
    文档直接陈述已经发生或当前存在的事实。

COMPANY_DISCLOSURE
    来自公司公告、财报或管理层披露，但 Atlas 尚未独立验证。

MANAGEMENT_GUIDANCE
    公司对未来的计划、目标或指引。

ANALYST_ESTIMATE
    分析师对数值、产能、份额等做出的估计。

ANALYST_OPINION
    分析师的定性判断、风险、机会或投资观点。

FORECAST
    明确面向未来的预测结果。

SCENARIO
    在特定假设成立时的情景推演。
```

### 8.3 第一阶段 Claim 分类

Phase 1 持久化三类标准对象：

1. Relation Claim
   - 公司与公司之间的关系。
   - 公司与产品、材料、技术、市场之间的关系。
   - 产品、材料、技术之间的关系。

2. Quantified Claim
   - 产能、产量、销量、市占率、利用率等运营数据。
   - 变化比例。
   - 管理层目标和券商预测。

3. Analyst View
   - 风险、机会、优势、竞争判断。
   - 推荐逻辑。
   - 未来趋势观点。

标准化历史财务数据不进入 Atlas Claim：

- 收入。
- 净利润。
- ROE。
- 标准毛利率。
- 每股收益历史值。

这些数据优先从 phoenixA 的结构化财务数据读取。

以下财务相关内容可以进入 Analyst View 或 Quantified Claim：

- 券商盈利预测。
- 估值假设。
- 目标价。
- 未来毛利率预测。
- 与产能、产品和市场份额相关的运营假设。

---

