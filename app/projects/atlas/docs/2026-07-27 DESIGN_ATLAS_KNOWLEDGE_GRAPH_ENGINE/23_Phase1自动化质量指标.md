## 二十三、Phase 1 自动化质量指标

由于人力有限，第一期以自动统计和少量抽查为主。

质量目标优先级：

```text
错误事实进入 Graph 的风险
    >
事实/观点混淆
    >
实体错误合并
    >
Predicate 方向错误
    >
信息漏抽取
```

即：

> Phase 1 优先 Precision，不为了提高 Recall 允许模型猜测。

### 23.1 文档处理指标

```text
PDF bytes 读取成功率
pikepdf 内存解保护成功率
PDF unlock status 分布
MODEL_PDF_UNREADABLE 比例
Whole-PDF 模型处理成功率
context exceeded / OOM / timeout 比例
possible truncation 比例
last_page_referenced / total_page_count 分布
文档抽取成功率
LLM schema 首次通过率
LLM 重试后通过率
平均 regeneration 次数
平均每文档 Claim 数
平均处理时间
平均峰值显存
```

### 23.2 实体解析指标

```text
VERIFIED entity 匹配率
PROVISIONAL entity 创建率
AMBIGUOUS mention 比例
UNRESOLVED mention 比例
alias 自动学习数量
```

### 23.3 语义指标

```text
canonical predicate 映射率
unknown raw predicate 数量
unknown raw predicate 跨文档重复率
各 predicate 的文档覆盖率
OTHER 占比
semantic proposal 待审核数量
sample → proposal 转换率
published semantic version 数量
draft/base 抽取差异
各候选 report type 可读率
各候选 report type 平均 Claim 产出
各候选 report type Evidence 完整率
各候选 report type ENABLE/DISABLE/NEEDS_MORE_SAMPLE 结论
申万 mapping coverage
东财 mapping coverage
券商已发现术语 mapping coverage
crosswalk conflict 数量
crosswalk validation failure 数量
crosswalk human override 数量
```

### 23.4 Graph 指标

```text
Company/Product/Material/Technology 节点数
各关系类型边数
有两个以上来源支持的关系数
只有 PROVISIONAL entity 的关系比例
孤立节点比例
```

### 23.5 少量人工抽查

不建设大规模人工标注系统。

建议每次模型或 prompt 版本升级时：

- 随机抽查 10–20 份报告。
- 每种报告类型至少覆盖若干样本。
- 优先抽查：
  - 模型重生成过的 PDF。
  - possible truncation。
  - 新 Predicate。
  - 新 Provisional Entity。
  - 非 EXACT Crosswalk。
- 重点检查：
  - 事实和观点是否混淆。
  - 公司是否错误合并。
  - 供应方向是否反了。
  - 计划是否被当成已完成事实。
  - 产能百分比是否被错误转换。
  - evidence quote 是否真的支持 Claim。
  - PDF 没有提及的信息是否被模型补写。

发现幻觉时：

1. 对应 Claim 标记 `REJECTED`。
2. 检查是否是 Prompt 约束缺失。
3. 检查是否是 Semantic YAML 定义诱导错误。
4. 修改 Prompt/YAML 后创建新版本。
5. 使用相同 PDF 回归测试。
6. 不直接在数据库中手工修正模型 Claim 后假装抽取正确。

---
