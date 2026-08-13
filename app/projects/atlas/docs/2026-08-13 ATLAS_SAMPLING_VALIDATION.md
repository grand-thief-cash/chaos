# Atlas Sampling 真实数据验收（2026-08-13）

## 结论

本轮不是“生产字段已经定稿”，而是验证开发期 sampling 是否能用有限资源持续发现字段。两组不同 seed 覆盖六种生产文档类型，每类 4+4 篇，共 48 个逐 PDF 自由 JSON；第二轮六个 profile 均通过自动业务审计。最终目录为 `2026-08-13 ATLAS_SAMPLING_CANDIDATE_FIELD_CATALOG_V1.json`，状态是 **candidate / not approved for production**。

现行总体设计、环境边界、Harness 和生产交接规则见 `2026-08-13 ARCHITECTURE_DESIGN_FOR_ATLAS_V3.md`。

结果说明当前方案可用：逐 PDF JSON 保持模型自由结构，跨文档 review 才做通用字段归并；HTTP 200 但 schema/证据不合格会触发 provider failover；最终 catalog 可确定性地从已审计字段构建，避免再花数分钟让免费模型决定是否遗漏已有证据。

## 样本与 run

| 类型 | seed / run | 第二组 seed / run | 第二组可读性 |
| --- | --- | --- | ---: |
| `stock` | 211 / `45d74665-1def-4d61-a63d-e12fd2fe0f15` | 311 / `ec8a8220-3acb-4461-92aa-a2bbca76ed0a` | 4/4 |
| `industry` | 223 / `1060c969-632e-4253-8398-76cc54fd0f63` | 313 / `878e44de-5db9-4cba-9638-f1b92c6ec053` | 4/4 |
| `macro` | 227 / `7294fd87-7726-40b3-a470-9ba51f520928` | 317 / `e7674f17-e5b4-4880-8fc9-0e049bdc9754` | 4/4 |
| `strategy` | 229 / `b8757cfe-7692-45e0-8db8-b17458603608` | 319 / `badb16ca-4d8f-4277-912c-46f3964082a1` | 4/4 |
| `morning_report` | 233 / `5f1a5b56-e31b-48de-89eb-bc1874fa8c3f` | 323 / `5e428757-ac3e-4306-ab82-5940bcff46a2` | 4/4 |
| `new_stock` | 239 / `4ea1ed8a-4f85-4a8e-92df-799104a6d129` | 331 / `69d49b93-3f99-4a14-bd7b-b9fedc2c99a5` | 4/4 |

`morning_report` 第二组最初有一篇无文本层扫描件失败。启用受门控的 RapidOCR 后，同一 seed 重跑得到 4/4：`万和财富早班车` 记录 `LAYOUT_SIDECAR_USED`，自由 JSON 为 1,795 字符。OCR 单页 canary 约 7.1 秒、峰值 RSS 约 566 MiB；因此只用于扫描/稀疏页补救，不用于所有 PDF。

## 候选 profile

以下是两轮字段并集经同义归一、证据路径校验和类型噪声过滤后的候选。`CORE` 表示该类型建图时优先请求，并不要求每篇 PDF 强制非空；`CONDITIONAL` 仅在内容存在时抽取。

| 类型 | 当前候选字段 |
| --- | --- |
| `stock` | 上下游关系；产能与项目布局；关键经营指标；关键风险与传导；投资建议与评级；政策事件及影响；财务与盈利预测 |
| `industry` | 核心技术与研发能力；供需格局与驱动；关键风险与传导；投资建议与评级；政策事件及影响；竞争格局 |
| `macro` | 宏观经济指标；政策事件及影响；关键风险与传导 |
| `strategy` | 市场表现与市场信号；供需格局与驱动；投资建议与评级；政策事件及影响；关键风险与传导 |
| `morning_report` | 研究对象；业务板块与主营产品/服务；核心技术与研发能力；上下游关系；供需格局与驱动；关键风险与传导 |
| `new_stock` | 业务板块与主营产品/服务；核心技术与研发能力；产业链定位；上下游关系；供需格局与驱动；关键经营指标 |

跨类型目录共有 15 个字段族。11 个具有两篇以上独立文档证据；`产业链定位`、`产能与项目布局`、`研究对象`、`竞争格局` 当前只有单文档证据，保持 `PROVISIONAL/CONDITIONAL`。

## 人工业务 review

本轮明确修正了下列问题，而不是只接受“流程成功”：

- `污泥处理量`、具体产品出货量等只留在逐 PDF JSON，终审归入 `关键经营指标[{metric_name,period,value,unit,business_segment}]`；
- `每股收益-最新股本摊薄_E`、具体年份利润不得成为字段名，归入 `财务与盈利预测`；
- `技术进展`、`产品分类与技术特点` 归入 `核心技术与研发能力`；
- `主要产品或服务` 归入 `业务板块与主营产品/服务`；
- `市场预测` 归入 `供需格局与驱动`；
- 删除 industry 的偶发 `估值/宏观指标/市场表现`、strategy 的栏目名 `行业重点新闻`、new_stock 的 `市场表现与估值`；
- 所有推荐字段必须引用真实 document id 和该文档实际存在的 JSON path；单文档证据不能晋升 `CORE`。

## 已知缺口与下一轮计划

- 两轮 `stock` 仍偏财报点评，主营产品、技术、客户和产业链定位覆盖不足；下一轮应按报告子类型/标题分层，定向增加公司深度、首次覆盖和产业链专题。
- `morning_report` 内容天然混合，本轮不同 seed 差异较大。它应保持条件字段 profile，不应被误用为公司主档 schema。
- 尚未形成跨行业、可审计的 `产品/技术/应用关系` 三元字段证据；下一轮定向选择半导体、机器人、医药、材料、能源等行业各 1–2 篇。
- 免费 provider 输出仍常截断或返回错误 schema。最终 catalog 默认使用 `--deterministic`；模型只参与逐 PDF 自由理解与同类 review，且必须经过业务 validator。
- 当前开发读取生产 MinIO 的 key 仍应替换为服务端只读策略 key。Atlas 的 `read_only` 配置和 reader-only 代码不能替代 MinIO IAM 权限。

## 验证

- Atlas：最终完整测试 `131 passed`（包含生产 sampling 路由缺失、provider business failover、OCR 门控、字段证据与 catalog 回归），仅有 FastAPI 既有 `on_event` 弃用警告。
- PhoenixA：`go test ./internal/... ./cmd/dbtool` 通过。
- Cthulhu：`development-home` 与 `production` 构建通过；生产构建仅保留既有 bundle budget/CommonJS warning。
- 第二轮六类 `audit_sampling_run.py` 全部 `passed: true`；人工 review 仍按上面的 gap 将目录标记为候选，而非批准生产。
