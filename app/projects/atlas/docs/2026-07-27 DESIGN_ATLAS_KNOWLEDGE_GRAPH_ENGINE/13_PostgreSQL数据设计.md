## 十三、PostgreSQL 数据设计

### 13.1 命名原则

phoenixA 中表数量较多，Atlas 表必须具有清晰业务归属。

使用独立 PostgreSQL schema：

```text
atlas_kg
```

禁止使用无业务前缀的全局名称：

```text
entities
entity_aliases
claims
events
```

使用：

```text
atlas_kg.knowledge_entity
atlas_kg.knowledge_entity_alias
atlas_kg.relation_claim
```

API 路径统一使用：

```text
/api/v1/atlas-kg/...
```

### 13.2 Phase 1 表清单

```text
atlas_kg.document_extraction_run
atlas_kg.knowledge_entity
atlas_kg.knowledge_entity_alias
atlas_kg.knowledge_entity_identifier
atlas_kg.security_entity_link
atlas_kg.relation_claim
atlas_kg.quantified_claim
atlas_kg.analyst_view
atlas_kg.semantic_discovery_run
atlas_kg.semantic_discovery_sample
atlas_kg.semantic_discovery_candidate
atlas_kg.semantic_proposal
atlas_kg.semantic_version
atlas_kg.semantic_version_entry
atlas_kg.semantic_environment_activation
atlas_kg.industry_taxonomy_scheme
atlas_kg.industry_taxonomy_concept
atlas_kg.industry_crosswalk_run
atlas_kg.industry_crosswalk_mapping
atlas_kg.graph_projection_run
```

不创建：

```text
normalized_document
document_chunk
llm_raw_response
claim_evidence
event
event_revision
embedding
```

说明：

- 不创建独立 `claim_evidence` 表。
- `evidence_quote` 和 `page_number` 直接放在 Relation/Quantified/View 表中。
- Semantic Proposal 现在属于 Phase 1，需要可视化审核，因此必须持久化。
- Published YAML 是 `semantic_version` 的发布 artifact，不替代数据库中的审核记录。

### 13.3 document_extraction_run

用途：

- 跟踪哪些 PDF 已处理。
- 保证幂等。
- 记录模型、prompt 和 schema 版本。
- 记录成功、失败和重跑。

核心字段：

```text
id
source_document_id
source_content_hash
source_report_type
pipeline_version
run_generation
input_mode
pdf_size_bytes
pdf_page_count
pdf_unlock_status
pdf_unlocker_version
model_id
model_quantization
system_prompt_version
report_type_prompt_version
prompt_signature
extraction_schema_version
semantic_version
status
warning_code
error_code
error_summary
request_attempt_count
validation_error_codes JSONB
possible_truncation
last_page_referenced
relation_claim_count
quantified_claim_count
analyst_view_count
started_at
completed_at
created_at
```

唯一约束：

```text
UNIQUE(
  source_document_id,
  source_content_hash,
  pipeline_version,
  prompt_signature,
  run_generation
)
```

关键字段说明：

| 字段 | 含义 |
|---|---|
| `input_mode` | Phase 1 固定为 `PDF_DIRECT` |
| `run_generation` | 同一文档和相同 Prompt 的受控强制重跑序号；普通重试不增加 |
| `pdf_unlock_status` | `UNLOCKED_IN_MEMORY` 或 `UNLOCK_FAILED`；不保存任何解保护副本路径 |
| `pdf_unlocker_version` | pikepdf 内存解保护适配器版本 |
| `prompt_signature` | System Prompt、Schema、Semantic Version、Report Prompt 和模型的组合签名 |
| `semantic_version` | 实际注入模型的 Published/Draft Semantic Version |
| `request_attempt_count` | 初始请求和打回重生成的总次数 |
| `validation_error_codes` | 每次失败的结构化错误码，不保存模型 raw response |
| `error_code` | 运行最终失败码，例如 `PDF_UNLOCK_FAILED`、`MODEL_PDF_UNREADABLE` 或 `MODEL_TIMEOUT` |
| `possible_truncation` | 模型是否声明可能未完整读取 PDF |
| `last_page_referenced` | 模型输出中引用到的最大页码 |

幂等规则：

- 默认请求先查询相同 document/hash/prompt signature 的最新 `SUCCEEDED` run，存在则跳过。
- 格式错误重生成属于同一个 run，只增加 `request_attempt_count`。
- 用户显式 `force=true` 时创建新的 `run_generation`，并在成功后 supersede 旧 run。

状态：

```text
PENDING
PROCESSING
SUCCEEDED
FAILED_RETRYABLE
FAILED_PERMANENT
SUPERSEDED
```

### 13.4 knowledge_entity

核心字段：

```text
entity_id UUID
entity_type
canonical_name
country_code
status
parent_entity_id
created_from_document_id
created_by_run_id
merged_into_entity_id
attributes JSONB
created_at
updated_at
```

说明：

- `canonical_name` 不作为全局唯一键。
- `entity_id` 是 Claim 和 Graph 的稳定身份。
- 不同国家允许出现相同 canonical name。
- 产品、材料、技术和市场也使用同一知识实体表。

### 13.5 knowledge_entity_alias

核心字段：

```text
id
entity_id
alias
normalized_alias
language
alias_status
source_document_id
created_by_run_id
created_at
```

索引：

```text
normalized_alias
entity_id
alias_status
```

### 13.6 knowledge_entity_identifier

核心字段：

```text
id
entity_id
identifier_type
identifier_value
issuer
valid_from
valid_to
source
```

标识类型示例：

```text
TICKER
EXCHANGE_CODE
ISIN
LEI
UNIFIED_SOCIAL_CREDIT_CODE
INTERNAL_SECURITY_ID
```

### 13.7 security_entity_link

连接 Atlas Knowledge Entity 与 phoenixA Security：

```text
id
entity_id
security_id
link_type
valid_from
valid_to
source
created_at
```

`link_type`：

```text
ISSUER
PARENT_COMPANY
OPERATING_COMPANY
```

### 13.8 relation_claim

核心字段：

```text
claim_id UUID
extraction_run_id
source_document_id
subject_entity_id
object_entity_id
raw_subject_text
raw_object_text
predicate_family
raw_predicate
canonical_predicate_key
assertion_type
claim_status
valid_from
valid_to
qualifiers JSONB
evidence_quote
page_number
extraction_confidence
created_at
updated_at
```

`claim_status`：

```text
CANDIDATE_ENTITY
CANDIDATE_SEMANTIC
ACCEPTED
REJECTED
SUPERSEDED
```

Phase 1 最小来源追踪：

- 必须保存 `source_document_id`。
- 不建立独立 Evidence 表。
- 不要求 bbox。
- 不要求 chunk ID。
- 必须保存模型返回的最短 `evidence_quote`。
- `page_number` 允许为 null，但非空时必须在 PDF 页数范围内。
- Evidence 直接嵌入 Claim，支持 cthulhu 审核，不形成独立检索子系统。

### 13.9 quantified_claim

核心字段：

```text
claim_id UUID
extraction_run_id
source_document_id
subject_entity_id
product_entity_id
metric_key
metric_raw_name
absolute_value
relative_change
unit
currency
baseline_period
target_period
measurement_status
assertion_type
claim_status
qualifiers JSONB
evidence_quote
page_number
extraction_confidence
created_at
updated_at
```

`measurement_status`：

```text
CURRENT
HISTORICAL
PLANNED
UNDER_CONSTRUCTION
COMPLETED
ANALYST_ESTIMATE
FORECAST
```

### 13.10 analyst_view

核心字段：

```text
view_id UUID
extraction_run_id
source_document_id
subject_entity_id
view_type
topic
direction
summary
horizon
view_status
attributes JSONB
evidence_quote
page_number
extraction_confidence
created_at
updated_at
```

`view_type`：

```text
OPPORTUNITY
RISK
COMPETITIVE_ADVANTAGE
COMPETITIVE_WEAKNESS
INDUSTRY_TREND
INVESTMENT_THESIS
OTHER
```

### 13.11 semantic_discovery_run

记录用户从 cthulhu 发起的一次 Sample Discovery。

核心字段：

```text
id UUID
run_type
base_semantic_version
sampling_strategy
random_seed
requested_sample_size
actual_sample_size
filters JSONB
discover_options JSONB
report_type_assessment_summary JSONB
status
documents_succeeded
documents_failed
proposal_count
error_summary
created_by
started_at
completed_at
created_at
```

状态：

```text
DRAFT
SAMPLING
RUNNING
AGGREGATING
AWAITING_REVIEW
COMPLETED
FAILED
CANCELLED
```

补充字段说明：

| 字段 | 含义 |
|---|---|
| `report_type_assessment_summary` | 按 Artemis report type 聚合的可读率、Claim 产出、Evidence 完整率、数据重复度和 ENABLE/DISABLE/NEEDS_MORE_SAMPLE 建议 |

### 13.12 semantic_discovery_sample

冻结 Discovery Run 实际选择的 PDF。

核心字段：

```text
id
discovery_run_id
source_document_id
report_type
institution
page_count
stratum_key
sample_order
status
attempt_count
candidate_count
error_summary
document_utility_assessment JSONB
created_at
completed_at
```

不保存单次 LLM raw response；校验通过的候选转换成标准化 `semantic_discovery_candidate`。

`document_utility_assessment` 保存该样本文档通过 Schema 的结构化价值判断，包括 readability、knowledge yield、useful dimensions、是否主要重复 phoenixA 已有数据以及 report type 建议；不保存模型解释性聊天内容。

### 13.13 semantic_discovery_candidate

保存通过 Schema 校验的发现候选，不保存模型完整响应。

```text
id UUID
discovery_run_id
discovery_sample_id
semantic_kind
raw_term
suggested_key
display_name
description
field_class
target_object
target_path
value_type
candidate_payload JSONB
evidence_page_number
evidence_quote
created_at
```

用途：

- 大 sample size 时支持分批聚合。
- Discovery Run 中断后不必重跑成功 PDF。
- Proposal 可以追溯到多个标准化 Candidate。
- 只保存与语义发现相关的结构化结果，不保存聊天文字或模型推理。

### 13.14 semantic_proposal

cthulhu 中用于确认语义定义和生产 report type 的核心对象。

```text
proposal_id UUID
discovery_run_id
semantic_kind
report_type_key
enabled_for_production
prompt_profile_key
suggested_key
display_name
description
family
field_class
target_object
target_path
value_type
nullable
subject_entity_types JSONB
object_entity_types JSONB
aliases JSONB
applicable_report_types JSONB
statistics JSONB
evidence_examples JSONB
llm_rationale
proposal_priority
review_status
merged_into_semantic_key
reviewed_definition JSONB
reviewed_by
reviewed_at
created_at
updated_at
```

字段说明：

| 字段 | 含义 |
|---|---|
| `semantic_kind` | FIELD、PREDICATE、METRIC、VIEW_TYPE、CONCEPT 或 REPORT_TYPE_PROFILE；行业映射使用独立 Crosswalk 表 |
| `report_type_key` | 仅 `REPORT_TYPE_PROFILE` 使用；必须等于 Artemis 元数据中的 report type |
| `enabled_for_production` | 仅 `REPORT_TYPE_PROFILE` 使用；发布后决定 Report Consumer 是否消费该类型 |
| `prompt_profile_key` | 仅 `REPORT_TYPE_PROFILE` 使用；指向该类型生产抽取 Prompt Profile |
| `suggested_key` | LLM 建议的稳定英文 key，人工可编辑 |
| `field_class` | CORE_SCHEMA_FIELD 或 SEMANTIC_ATTRIBUTE |
| `target_object/target_path` | 字段生效的 JSON 对象和 qualifiers/attributes 路径 |
| `reviewed_definition` | 人工修改后的最终定义；发布时优先使用 |
| `statistics` | 文档频次、报告类型覆盖、机构覆盖、冲突数等 |
| `evidence_examples` | 用于 UI Review 的少量文档 ID、页码和原文 |
| `merged_into_semantic_key` | Proposal 合并到已有定义时使用 |

### 13.15 semantic_version

```text
id UUID
version
base_version
status
schema_version
change_summary
yaml_object_uri
yaml_sha256
entry_count
created_by
published_by
created_at
tested_at
published_at
retired_at
```

状态：

```text
DRAFT
TESTED
PUBLISHED
RETIRED
```

唯一约束：

```text
UNIQUE(version)
UNIQUE(yaml_sha256)
```

### 13.16 semantic_version_entry

保存某个版本中实际生效的定义。

```text
id
semantic_version_id
semantic_kind
semantic_key
definition JSONB
origin
source_proposal_id
created_at
```

唯一约束：

```text
UNIQUE(
  semantic_version_id,
  semantic_kind,
  semantic_key
)
```

YAML 由这些 version entries 确定性生成，不能让 LLM直接自由写最终 YAML。

### 13.17 semantic_environment_activation

记录不同环境实际使用哪个 Published Version：

```text
id
environment
semantic_version_id
yaml_object_uri
yaml_sha256
activated_by
activated_at
```

环境示例：

```text
LOCAL
TEST
PRODUCTION
```

唯一约束：

```text
UNIQUE(environment)
```

激活操作必须确认 version 为 `PUBLISHED` 且 YAML hash 校验成功。

### 13.18 industry_taxonomy_scheme

```text
id UUID
scheme_key
display_name
version
source_system
snapshot_date
status
created_at
updated_at
```

唯一约束：

```text
UNIQUE(scheme_key, version)
```

### 13.19 industry_taxonomy_concept

```text
concept_id UUID
taxonomy_scheme_id
external_code
name
normalized_name
description
parent_concept_id
level
status
source_document_id
created_at
updated_at
```

对于券商术语：

- `external_code` 可以为 null。
- `source_document_id` 记录首次发现该术语的 PDF。
- `taxonomy_scheme_id` 指向 `BROKER:{institution}`。

### 13.20 industry_crosswalk_run

记录一次模型自动 Crosswalk 构建或指定范围重跑，不保存模型原始响应。

```text
run_id UUID
base_semantic_version_id
source_taxonomy_snapshots JSONB
target_atlas_scheme_version
scope JSONB
model_id
prompt_version
status
source_concept_count
resolved_mapping_count
no_mapping_count
validation_failure_count
repair_attempt_count
relation_distribution JSONB
quality_summary JSONB
error_summary
created_by
started_at
completed_at
created_at
```

字段说明：

| 字段 | 含义 |
|---|---|
| `source_taxonomy_snapshots` | 本次从 phoenixA 读取的申万、东财、券商 Scheme/Version/Snapshot 标识 |
| `scope` | 全量或限定 Scheme、父节点、概念 ID、失败批次的重跑范围 |
| `status` | `RUNNING`、`VALIDATING`、`READY_FOR_VERSION`、`FAILED` 或 `CANCELLED` |
| `relation_distribution` | EXACT/CLOSE/BROADER/NARROWER/RELATED/NO_CANONICAL_MAPPING 数量 |
| `quality_summary` | 覆盖率、冲突、循环、低 confidence 和抽样结果摘要，供 cthulhu 结果级观察 |

### 13.21 industry_crosswalk_mapping

```text
mapping_id UUID
crosswalk_run_id
source_concept_id
target_atlas_concept_id
mapping_relation
confidence
proposal_origin
resolution_status
semantic_version_id
llm_rationale
notes
model_result JSONB
override_target_atlas_concept_id
override_mapping_relation
override_reason
overridden_by
overridden_at
created_at
updated_at
```

`mapping_relation`：

```text
EXACT
CLOSE
BROADER
NARROWER
RELATED
NO_CANONICAL_MAPPING
```

`NO_CANONICAL_MAPPING` 时 `target_atlas_concept_id` 可以为 null，其他关系必须非空。

`resolution_status`：

```text
MODEL_RESOLVED
VALIDATED
VALIDATION_FAILED
HUMAN_OVERRIDE
```

说明：

- 通过程序检查的模型结果从 `MODEL_RESOLVED` 进入 `VALIDATED`，不要求逐条人工 Approve。
- `model_result` 保存标准化后的模型映射结果和理由，不保存完整 LLM raw response。
- 人工只在结果异常时填写 override 字段；有效值优先使用 override，同时保留原模型结果。
- `VALIDATION_FAILED` mapping 不能进入 Draft Semantic Version。

### 13.22 graph_projection_run

核心字段：

```text
id
mode
status
claim_updated_after
entities_created
entities_updated
relationships_created
relationships_updated
relationships_removed
error_summary
started_at
completed_at
```

### 13.23 数据库字段命名约定

| 形式 | 含义 |
|---|---|
| `*_id` | 数据库或领域稳定 ID |
| `*_key` | 可放入配置/YAML 的稳定英文 key |
| `raw_*` | PDF 或模型原始表达，尚未 canonicalize |
| `canonical_*` | 已映射到 Published Semantic Version 的定义 |
| `source_*` | 原始数据来源或 phoenixA 文档引用 |
| `suggested_*` | 模型 Proposal，不代表已经生效 |
| `reviewed_*` | 人工审核普通 Semantic Proposal 后的值 |
| `override_*` | 人工在异常介入时覆盖 Crosswalk 模型结果的值；必须保留原因和操作者 |
| `*_version` | 不可变定义、Schema、Prompt 或数据 Snapshot 版本 |
| `*_status` | 对象生命周期状态，不代表模型置信度 |
| `extraction_confidence` | 模型对抽取动作的自评，不是真实概率 |
| `valid_from/valid_to` | 现实世界关系或分类的有效时间 |
| `created_at/updated_at` | 数据库记录时间，不是现实事件时间 |

模型输出到数据库的映射：

| 模型字段 | PostgreSQL 字段 | 说明 |
|---|---|---|
| `subject_mention` | `raw_subject_text` | 保留 PDF 原始名称 |
| resolved subject | `subject_entity_id` | Entity Resolver 写入 |
| `raw_predicate` | `raw_predicate` | 保留原始关系短语 |
| `canonical_predicate_hint` | `canonical_predicate_key` | Semantic Resolver 校验后写入 |
| `evidence_quote` | `evidence_quote` | 最小审核原文 |
| `page_number` | `page_number` | PDF 页码 |
| `confidence`/`extraction_confidence` | `extraction_confidence` | 统一使用后者 |
| `qualifiers` | `qualifiers` JSONB | 只允许 Published YAML 定义字段 |
| `attributes` | 对应 `attributes` JSONB | 只允许 Published YAML 定义字段 |

任何字段在代码、API、数据库和 YAML 中必须使用同一含义。不能出现同名字段在不同模块表达不同语义。

---
