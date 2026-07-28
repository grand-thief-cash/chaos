## 二十五、TODO：Event 与市场信号

> 本章只记录后续设计方向，不进入 Phase 1 数据表、API 和实现。

### 25.1 为什么 Event 暂缓

事件处理涉及：

- 同一现实事件被多篇新闻重复报道。
- 传闻、公告、批准、完成和取消等阶段变化。
- 同一个事件随时间新增事实。
- 连续市场价格变化与离散事件的区别。
- 新信息是否应该重新触发影响分析。

这些问题会显著扩大第一期范围，因此先完成稳定知识图谱。

### 25.2 后续 Event 三层对象

#### EventMention

某个文档对事件的一次描述。

示例：

```text
新闻A：“公司X计划收购公司Y”
新闻B：“公司X就收购公司Y签署协议”
公告C：“公司X收购公司Y获得监管批准”
```

每一条都是独立 EventMention。

#### CanonicalEvent

Atlas 判断多个 EventMention 是否描述同一现实世界事件后形成的内部聚合对象。

它不是外部数据源提供的对象，而是 Atlas 的事件聚类结果。

示例：

```text
CanonicalEvent: 公司X收购公司Y
  ├── EventMention A
  ├── EventMention B
  └── EventMention C
```

#### EventRevision

同一 CanonicalEvent 的状态或核心事实发生变化。

示例：

```text
Revision 1: rumored
Revision 2: announced
Revision 3: signed
Revision 4: approved
Revision 5: completed
```

EventRevision 不是对 EventMention 做归因，而是记录同一现实事件的演进版本。

### 25.3 Fingerprint 的后续定位

Fingerprint 只用于候选召回，不作为事件唯一身份。

可能字段：

```text
event family
canonical participants
target/object
time window
location
stage
metric
```

最终是否合并需要规则、语义匹配和必要的模型判断。

### 25.4 商品和期货价格

油价、金价、期货等不使用 Event 去重。

后续模型：

```text
MarketInstrument
DailyObservation
TrendEpisode
```

`DailyObservation` 来自结构化行情数据。

`TrendEpisode` 由程序规则生成：

- N 日涨跌幅。
- 波动率变化。
- 突破。
- 连续上涨或下跌。
- 成交量异常。

新闻中的“油价上涨”只作为市场信号的解释来源，不作为唯一价格事实。

---

