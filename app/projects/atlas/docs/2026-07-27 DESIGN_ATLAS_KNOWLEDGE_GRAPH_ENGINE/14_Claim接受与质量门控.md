## 十四、Claim 接受与质量门控

### 14.1 不能只看模型 Confidence

模型输出 `0.82` 不等于真实世界中 82% 正确。

Phase 1 中必须区分两种“接受”：

```text
STRUCTURALLY_VALID
    程序确认格式、枚举、引用、类型和数值约束有效。

SEMANTICALLY_ACCEPTED
    使用模型给出的 Assertion Type、Evidence 和实体/语义解析结果，
    根据发布规则决定是否可以进入事实 Graph。
```

程序不能证明 PDF 中的陈述是真实世界事实，也不能独立判断一句话是观点还是事实。Assertion Type 由模型判断；程序只检查该判断是否是合法枚举、是否与其他字段自洽。

Relation Claim 进入 `ACCEPTED` 至少要求：

- Whole-PDF JSON 通过所有结构和约束校验。
- subject 已解析为 entity。
- object 已解析为 entity。
- subject 与 object 不违反类型约束。
- canonical predicate 已确定。
- assertion type 是合法值。
- polarity 不是 `NEGATED`。
- evidence quote 非空。
- page number 为空或在合法范围内。
- document 没有被标记为 `possible_truncation`，或者已经人工复核。

“模型是否胡编”不能仅靠程序判断，因此通过以下方式降低风险：

- Prompt 明确禁止补充常识。
- 每个 Claim 强制输出 evidence quote。
- 低频新 Predicate、新实体和疑似截断结果进入 Review。
- cthulhu 显示 Claim、页码和原文。
- Semantic Version 升级使用固定 sample 回归。

### 14.2 Assertion Type 与 Graph

默认可进入事实 Graph：

```text
OBSERVED_FACT
COMPANY_DISCLOSURE
```

默认不进入事实 Graph：

```text
MANAGEMENT_GUIDANCE
ANALYST_ESTIMATE
ANALYST_OPINION
FORECAST
SCENARIO
```

例外：

- 管理层计划可以投影为明确带 `assertion_type=MANAGEMENT_GUIDANCE` 的计划关系，但不能与当前事实关系合并。
- Phase 1 可暂时不投影计划关系，只通过 Claim API 查询。

### 14.3 单次 Whole-PDF 输出内去重

同一关系可能在摘要、正文和结论中重复出现，模型可能输出多条相同 Candidate。

程序化合并键：

```text
source_document_id
subject_entity_id
canonical_predicate_key
object_entity_id
assertion_type
关键 qualifiers
```

保留：

- 最高 extraction confidence。
- qualifiers 的非冲突并集。
- 冲突时保留多条 Claim，不强制覆盖。

### 14.4 跨文档关系

不同文档中相同关系保留为不同 Claim，因为：

- 来源不同。
- 发布时间不同。
- Assertion Type 可能不同。
- 有效期可能不同。
- 后续需要判断支持数量和冲突。

Graph Projection 可以聚合这些 Claim。

---

