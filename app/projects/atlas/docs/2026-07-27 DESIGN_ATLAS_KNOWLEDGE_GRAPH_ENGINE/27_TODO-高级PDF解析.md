## 二十七、TODO：高级 PDF 解析

以下情况达到一定比例后，再评估 Docling/Marker/OCR：

- 大量扫描 PDF。
- 文本提取乱码。
- 多栏阅读顺序严重错误。
- 关键知识集中在表格中。
- 关键产业关系主要存在于图表中。
- Query Agent 需要精确页码或原文引用。

候选能力：

- 标题层级恢复。
- 页眉页脚识别。
- 表格结构恢复。
- 图片和图表理解。
- page/bbox evidence。
- 原文精确引用。

Phase 1 的 `DocumentModelInput` 接口必须允许以后增加 `TEXT_EXTRACTED`、`PAGE_BATCH` 和 `TEXT_CHUNKED` 实现，但当前只实现 `PDF_DIRECT`。

---

