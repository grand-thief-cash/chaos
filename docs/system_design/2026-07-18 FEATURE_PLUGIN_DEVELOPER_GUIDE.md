# FeaturePlugin 开发者指南

> 状态：Phase 5 交付版
>
> 目标：在不破坏版本、PIT、身份和审计边界的前提下新增 Artemis FeaturePlugin

## 1. 开发原则

1. Feature 是有业务语义和版本的治理对象，不是任意 Python 函数的别名。
2. Definition 描述稳定身份；业务含义、输入、公式或输出契约改变时发布新 Version。
3. Published Version 不可修改。即使只改 description、config 或 entrypoint，也必须创建新版本。
4. 所有证券输入和输出使用 PhoenixA `security_id`，不得使用 symbol 作为主键。
5. 插件只能读取 `data_cutoff_time` 时已可用的数据。`as_of_time` 不是数据可用时间。
6. missing 必须显式输出 `value=null,value_status=missing`，不得填 0。
7. 插件必须确定性执行；相同 Manifest、code revision、Run request 和输入应产生相同输出。
8. 密码、token、secret、DSN 不得进入 Manifest config、runtime parameters、quality flags 或日志。

## 2. 文件布局

```text
app/projects/artemis/
├── config/feature_catalog/
│   ├── manifest.yaml
│   └── features/<domain>/<feature-version>.yaml
├── artemis/feature_platform/plugins/<domain>/<plugin>.py
└── tests/
    ├── test_feature_platform_manifests.py
    └── test_feature_platform_planning_execution.py
```

每个版本使用独立 Manifest 文件，并在 `config/feature_catalog/manifest.yaml` 的 `manifests` 列表中注册。一个 Definition 的 V1、V2 可以指向不同 entrypoint，但 code 必须相同、version number 必须不同。

## 3. Manifest 契约

最小示例：

```yaml
api_version: chaos.feature/v1

feature:
  code: research.security.example_metric
  display_name: Example Metric
  description: Precise business meaning and intended use.
  kind: metric
  entity_type: security
  value_type: number
  unit: scalar
  category: research
  owner: research-platform
  tags: [research]

version:
  number: 1
  status: draft
  frequency: on_demand
  as_of_semantics: snapshot
  missing_policy: explicit_missing
  description: Initial formula and input contract.

implementation:
  kind: python
  producer_service: artemis
  backend: python
  entrypoint: artemis.feature_platform.plugins.research.example_metric:ExampleMetricFeature
  implementation_revision: 1
  config: {}
  status: active

dependencies: []

materialization:
  store: numeric
  mode: snapshot

quality:
  min_coverage_ratio: 0.95
  allow_nan: false
  allow_infinite: false
  allow_duplicates: false
```

### 3.1 Feature code

- 使用小写点分命名，例如 `research.security.net_margin_ttm`。
- code 是永久身份，不在 code 中编码日期、环境、owner 或实现语言。
- 禁止复用已存在 code 表达不同业务含义。

### 3.2 状态生命周期

- `draft`：允许同步更新，适合开发和审查。
- `published`：可执行且不可变。
- `deprecated`：不再作为默认最新版本，但显式历史查询仍可读取。

推荐流程：Draft validate -> sync -> review -> publish -> compute。不要把未经审查的本地文件直接声明为 published。

### 3.3 implementation revision

实现内容变化但业务 Version 尚在 Draft 时递增 `implementation_revision`。Published 后任何实现变化都创建新的 FeatureVersion；revision 不能作为绕过版本不可变的后门。

## 4. 依赖声明

### 4.1 Feature 依赖

```yaml
dependencies:
  - kind: feature
    feature_code: research.security.upstream_metric
    feature_version: 2
```

必须固定上游 version。规划器会构建稳定拓扑序、拒绝环，并把依赖计划 checksum 冻结进 Run。

### 4.2 DataField 依赖

```yaml
dependencies:
  - kind: data_field
    source: amazing_data
    dataset: financial_statement
    data_type: income
    raw_field: NET_PRO_EXCL_MIN_INT_INC
    contract_version: "2026-06-27"
```

必须精确到 `source + dataset + data_type + raw_field + contract_version`。禁止使用模糊字段名、label、SQL 字符串或 latest contract。Registry sync 会解析到 PhoenixA `govern.data_field_dictionary` 并冻结 lineage。

## 5. Plugin 协议

插件实现四个方法：

```python
from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureNumericOutput, NumericValue
from artemis.feature_platform.execution.context import FeatureExecutionContext


class ExampleMetricFeature:
    def validate(self, definition: dict, version: dict, implementation: dict) -> None:
        if definition.get("value_type") != "number":
            raise FeaturePlatformError("INPUT_SCHEMA_INVALID", "example metric requires number output")

    def load_inputs(self, ctx: FeatureExecutionContext, provider, dependencies: list[dict]):
        if len(dependencies) != 1:
            raise FeaturePlatformError("DEPENDENCY_REFERENCE_INVALID", "one dependency is required")
        return provider.load_data_field(ctx, dependencies[0])

    def compute(self, ctx: FeatureExecutionContext, inputs) -> FeatureNumericOutput:
        rows = []
        for security_id in ctx.security_ids:
            rows.append(
                NumericValue(
                    security_id=security_id,
                    value=None,
                    value_status="missing",
                    quality_flags={"reason": "example_only"},
                    source_max_available_at=ctx.data_cutoff_time,
                )
            )
        return FeatureNumericOutput(
            feature_version_id=ctx.feature_version_id,
            observed_at=ctx.as_of_time,
            rows=rows,
        )

    def validate_output(self, ctx: FeatureExecutionContext, output: FeatureNumericOutput) -> None:
        if len(output.rows) != len(ctx.security_ids):
            raise FeaturePlatformError("OUTPUT_SCHEMA_INVALID", "one output per RunSubject is required")
```

职责划分：

| 方法 | 允许做什么 | 禁止做什么 |
|---|---|---|
| `validate` | 校验 Definition/Version/Implementation 契约 | 网络请求、加载大数据 |
| `load_inputs` | 通过 provider 读取声明过的依赖 | 直接连接数据库、读取未声明字段 |
| `compute` | 纯计算并构造 typed output | 写 PhoenixA、改变 Run 状态 |
| `validate_output` | 业务级输出断言 | 修补或静默丢弃坏输出 |

平台 runner 会负责超时、通用 schema、重复 subject、NaN/Inf、universe、coverage 和 batch sink 校验。

## 6. ExecutionContext

可使用字段：

| 字段 | 含义 |
|---|---|
| `run_id` | PhoenixA 权威 Run UUID |
| `feature_version_id` | Registry 内冻结的版本 ID |
| `as_of_time` | 输出观察时间 |
| `data_cutoff_time` | 输入数据允许的最晚可用时间 |
| `security_ids` | 冻结且去重的 RunSubject 集合 |
| `source_profile` | PhoenixA 数据源配置 |
| `market` | 请求市场上下文 |
| `parameters` | 已通过敏感 key 校验的运行参数 |
| `dependency_outputs` | 当前 DAG 中已完成的上游 Feature 输出 |
| `implementation_config` | 当前 Manifest 的非敏感 config 副本 |

插件不得根据当前时间、进程随机数或外部可变全局状态改变结果。需要随机过程时必须在 Version 契约中定义 seed，并将 seed 冻结在 parameters 中。

## 7. PIT 与 source availability

DataField provider 返回的每条记录必须包含实际 `available_at`。财务报表场景优先使用 `actual_ann_date`，否则使用 `ann_date`；不能只按 reporting period 判断可见性。

插件输出要求：

- 使用了源记录时，`source_max_available_at` 是所有实际输入记录可用时间的最大值；
- 未找到源记录时，输出 explicit missing，并写入负查询边界；
- `source_max_available_at > data_cutoff_time` 会被 PhoenixA 服务层和数据库 trigger 拒绝；
- 修订公告只有在修订记录实际可用后才能替换旧记录；
- 禁止通过把 availability 设置为 cutoff 来掩盖真实晚到数据。

## 8. 输出与质量

每个 RunSubject 必须且只能有一条输出：

```text
valid   -> value 是有限 JSON number
missing -> value 必须是 null，quality_flags 给出原因
invalid -> value 必须是 null，quality_flags 给出校验失败原因
```

质量配置不是文档备注，而是执行 Gate。`min_coverage_ratio` 未达到、重复 security、universe 外输出、NaN/Inf 或输出计数不匹配都会使 RunItem 失败。

`quality_flags` 只放低基数、可审计原因。禁止放完整源记录、凭证、用户数据或超大调试对象。

## 9. 版本发布流程

1. 新建 Draft Manifest 和插件文件。
2. 在 catalog `manifest.yaml` 注册路径。
3. 为 Manifest schema、entrypoint、插件计算、missing/invalid 和 PIT 边界添加测试。
4. 执行本地 validate，确认 canonical checksum 稳定。
5. Sync Draft 到 PhoenixA，检查 lineage 和 availability。
6. Code review 同时审核业务定义、数据可用时间和质量阈值。
7. 调用 PhoenixA publish action 发布版本。
8. 发布后重新 validate/sync，应返回 unchanged。
9. 用小 universe 运行 smoke，再进行容量和全量回填。
10. 公式或依赖变化时创建下一版本，禁止编辑 Published 文件。

## 10. 测试要求

Artemis 定向测试：

```bash
export PATH=/usr/local/go/bin:/usr/bin:/bin
source /home/machine/projects/chaos/venv/bin/activate
cd /home/machine/projects/chaos/app/projects/artemis
PYTHONPATH=. python -m pytest -q \
  tests/test_feature_platform_openapi.py \
  tests/test_feature_platform_manifests.py \
  tests/test_feature_platform_planning_execution.py \
  tests/test_feature_platform_service_task.py
```

PhoenixA 门禁：

```bash
cd /home/machine/projects/chaos/app/projects/phoenixA
go test ./...
go vet ./...
python scripts/verify_openapi_routes.py
```

最终必须执行运维手册中的 managed acceptance。单元测试不能替代 Sync -> Compute -> Persist -> Query -> Restart E2E。

最低测试矩阵：

- Manifest unknown field、敏感 key、重复 identity、坏 entrypoint；
- Feature dependency 稳定拓扑和 cycle；
- DataField 精确 contract 和 deprecated field；
- 正常 valid、explicit missing、invalid、duplicate、universe 外输出；
- NaN、Inf、coverage 不足和 plugin timeout；
- cutoff 前、cutoff 后、修订公告；
- source outage、PhoenixA write conflict 和 state conflict；
- 同请求幂等、失败 retry 和服务重启持久化；
- V1/V2 coexistence、latest 与显式历史查询。

## 11. Review 检查表

- code 和业务定义是否稳定且唯一；
- 新版本是否真的需要，或是否错误修改了 Published 文件；
- 每个依赖是否在 Manifest 中精确声明；
- provider 是否执行 availability cutoff；
- 输出是否覆盖冻结 universe 且 missing 不填 0；
- quality threshold 是否有业务依据；
- parameters/config/log 是否可能泄露敏感信息；
- 计算是否确定、可重试、可复现；
- OpenAPI、测试、运维说明是否同步；
- 是否已在当前 PhoenixA/Artemis 版本上运行 E2E。
