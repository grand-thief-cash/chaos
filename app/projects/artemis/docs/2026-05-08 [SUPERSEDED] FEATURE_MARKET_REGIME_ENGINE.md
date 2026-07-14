# 2026-05-08 Market Regime Engine（市场状态引擎）设计

> **Status: Superseded（2026-07-14）**
>
> 本文仅保留作历史记录，已由 `docs/system_design/2026-07-14 FEATURE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md` 替代，不得再作为新开发或验收依据。

> 更新日期：2026-05-08 (rev.2 — 架构重构: 离散分类 → 连续状态空间)  
> 关联文档：`2026-05-08 [PLANNING] FEATURE_FUNDAMENTAL_FACTOR_ENGINE.md`, `2026-04-15 REVIEW_STRATEGY_ENGINE_ARCHITECTURE.md`  
> 影响范围：Artemis (Python), PhoenixA (Go), PostgreSQL, Cronjob (Go)

---

## 一、背景与目标

### 1.1 为什么需要 Market Regime Engine？

量化系统中最常见的失败模式：

```
回测年化收益 35% → 实盘亏 20%

核心原因：
  回测数据 = 2020-2024（牛市为主）
  实盘上线 = 2025（震荡/熊市）
  
  趋势策略在震荡市中被反复打脸
  均值回归策略在单边市中被碾压
```

**Market Regime Engine 的本质不是"预测市场"，而是"识别当前市场环境"，然后路由到最合适的策略组合。**

它是整个系统的**"策略调度器"**——决定当前应该激活哪些因子、启用哪些策略、控制多大仓位。

### 1.2 在平台中的位置

```
                    Chaos 量化平台 — 决策链路
                    
                    ┌─────────────────────┐
                    │   Data Layer         │
                    │   (PhoenixA)         │
                    │                     │
                    │ bars_* (OHLCV)      │
                    │ financial_statement  │
                    │ industry_*          │
                    │ security_registry   │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐ ┌───────────────┐ ┌──────────────────┐
    │ Factor Engine    │ │ Regime Engine │ │ Atlas            │
    │ (因子引擎)       │ │ (状态引擎)    │ │ (知识图谱/事件)   │
    │                 │ │               │ │                  │
    │ 输出:           │ │ 输出:         │ │ 输出:            │
    │ 标准化因子值     │ │ 当前 regime   │ │ 事件影响评分      │
    │ (横截面)        │ │ 策略权重      │ │ 产业链映射        │
    └────────┬────────┘ │ 仓位限制      │ └────────┬─────────┘
             │          │ 持仓周期      │          │
             │          └───────┬───────┘          │
             │                  │                  │
             └──────────────────┼──────────────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Strategy Engine     │
                     │  (策略引擎)          │
                     │                     │
                     │  根据 regime 动态:   │
                     │  - 选择策略组合      │
                     │  - 调整因子权重      │
                     │  - 控制风险敞口      │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Backtest/Execution  │
                     │  (回测/实盘)         │
                     └─────────────────────┘
```

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **State-space thinking（连续状态空间）** | ⚠️ 核心变更：不输出离散分类(BULL/BEAR)，而是输出**连续状态向量**。策略层消费连续分数做平滑分配，避免 regime flip noise |
| **Rule-based 起步** | MVP 用规则计算连续分数，不上 ML。原因：1) 没有标注数据 2) 可解释性强 3) 迭代快 |
| **MVP 极简特征** | 第一版只用 **5-8 个核心特征**，不做 feature addiction。每个新特征必须有明确 IC 验证才引入 |
| **A 股优先** | 先做 A 股 regime，美股/港股后续扩展。A 股有独特指标（北向资金、涨跌停、融资余额） |
| **输出面向策略** | 输出 `{trend_strength: 0.72, risk_appetite: 0.81, ...}`，策略引擎直接乘权重 |
| **包含前瞻信号** | 不只描述"当前状态"，还要捕捉"状态变化前兆"（regime transition features） |
| **可回测** | Regime 判定必须可回溯验证——在历史任意一天都能重算出当时的 regime state |
| **延迟容忍** | Regime 是日频计算（收盘后），不要求实时（分钟级 regime 是后续升级） |

### 1.4 架构核心变更：从 Classification 到 State Estimation

> **rev.2 最重要的修正。**

```
❌ 原版 (Classification Thinking):
  market_features → classifier → "BULL" → strategy_weights["BULL"]
  
  问题:
    1. 硬切换: 今天 BULL, 明天 SIDEWAYS → 策略权重剧烈跳变
    2. 后验性: "PANIC" 被识别时已经跌完了
    3. 信息丢失: "BULL with confidence 0.61" 和 "BULL with confidence 0.99" 不应该一样处理
    4. 过拟合阈值: 每个 threshold 都是潜在过拟合点

✅ 新版 (State-Space Thinking):
  market_features → state_estimator → continuous_state_vector → strategy_allocation
  
  优势:
    1. 平滑: trend_strength 从 0.8 → 0.7 → 0.6 是渐变的
    2. 前瞻: transition_features 可以捕捉状态变化前兆
    3. 无信息丢失: 所有维度都是连续值 (0.0-1.0)
    4. 无阈值过拟合: 策略权重用线性/非线性映射而非 if-else
```

**核心输出结构变更**：

```python
# ❌ 旧版
regime_result = {
    "market_regime": "BULL_TREND",    # enum
    "volatility_regime": "LOW_VOL",   # enum
    "style_regime": "GROWTH",         # enum
}

# ✅ 新版
regime_state = {
    # ── 核心状态维度（0.0 - 1.0 连续值）──
    "trend_strength": 0.72,           # 0=强空头, 0.5=无趋势, 1=强多头
    "risk_appetite": 0.81,            # 0=极度避险, 1=极度冒险
    "volatility_stress": 0.22,        # 0=平静, 1=极端波动
    "market_breadth": 0.64,           # 0=全市场下跌, 1=全市场上涨
    "liquidity": 0.71,                # 0=流动性枯竭, 1=流动性泛滥
    "sector_concentration": 0.31,     # 0=均匀, 1=极端集中(少数行业主导)
    
    # ── 前瞻/转换信号 ──
    "breadth_momentum": -0.12,        # 广度变化速度 (可以为负)
    "vol_acceleration": 0.05,         # 波动率变化加速度
    
    # ── 便利层: 离散标签 (仅用于日志/报告, 策略不直接消费) ──
    "label_market": "BULL_TREND",
    "label_confidence": 0.72,
}
```

> **策略引擎消费连续分数**，不消费离散标签。
> 离散标签仅用于：人类查看、日志记录、cthulhu 前端展示。

---

## 二、数据需求

### 2.1 数据源清单

#### 2.1.1 核心指数数据（现有 bars_* 表）

| 指数 | 代码 | 用途 | 数据状态 |
|------|------|------|---------|
| 上证指数 | 000001 | 大盘趋势 | ✅ 已有 |
| 沪深300 | 000300 | 大盘+蓝筹代表 | ✅ 已有 |
| 中证500 | 000905 | 中盘代表 | ✅ 已有 |
| 中证1000 | 000852 | 小盘代表 | ⬜ 需新增 |
| 创业板指 | 399006 | 成长/科技代表 | ⬜ 需新增 |
| 科创50 | 000688 | 科技硬核 | ⬜ 需新增 |
| 上证50 | 000016 | 超大盘/价值 | ⬜ 需新增 |
| 红利指数 | 000015 | 防御/红利 | ⬜ 需新增 |
| 国证2000 | 399303 | 微盘代表 | ⬜ 可选 |

> **新增指数来源**：通过 Artemis 现有 task_engine 下载 → PhoenixA bars_index_* 表存储。

#### 2.1.2 行业指数数据（现有 industry_daily 表）

| 数据 | 说明 | 数据状态 |
|------|------|---------|
| 申万一级行业指数（31 个） | 行业轮动分析 | ✅ 已有 |
| 申万二级行业指数 | 更细粒度行业动量 | ⬜ 可选 |

#### 2.1.3 全市场广度数据（需从个股行情聚合计算）

| 特征 | 计算方式 | 数据来源 |
|------|---------|---------|
| 上涨家数占比 | `count(close > pre_close) / total` | bars_stock_zh_a_daily_* |
| 涨停家数 | `count(pct_change >= 9.8%)` | bars_stock_zh_a_daily_* |
| 跌停家数 | `count(pct_change <= -9.8%)` | bars_stock_zh_a_daily_* |
| 站上 MA20 占比 | `count(close > ma20) / total` | bars_stock_zh_a_daily_* + 计算 |
| 站上 MA60 占比 | `count(close > ma60) / total` | bars_stock_zh_a_daily_* + 计算 |
| 创 20 日新高占比 | `count(close == max20) / total` | bars_stock_zh_a_daily_* + 计算 |
| 创 20 日新低占比 | `count(close == min20) / total` | bars_stock_zh_a_daily_* + 计算 |

> **关键**：这些「广度指标」是 Regime Engine 独有的，**不是传统 TA 指标**。
> 它描述的是"全市场参与度"——一个沪深300涨2%但只有30%个股上涨的市场，和一个沪深300涨2%但80%个股上涨的市场，regime 完全不同。

#### 2.1.4 流动性与资金流向（A 股特有，需新增数据源）

| 数据 | 来源 | 优先级 | 说明 |
|------|------|--------|------|
| 全市场成交额 | bars_* 聚合 | P0 | 日成交总额，流动性核心指标 |
| 全市场换手率均值 | bars_ext_* 聚合 | P0 | 市场活跃度 |
| 融资余额 | 新增数据源（AmazingData/东方财富） | P1 | 杠杆资金情绪 |
| 北向资金净流入 | 新增数据源 | P1 | 外资情绪风向标 |
| ETF 申赎（上证50/沪深300ETF） | 新增数据源 | P2 | 机构配置方向 |

> **融资余额 + 北向资金**是 A 股独有的 alpha 信号，GPT 的建议中完全遗漏了这两个。
> 在 A 股，北向资金的单日大幅流入/流出对短期市场情绪有显著预测力。

#### 2.1.5 波动率数据（需计算）

| 指标 | 计算方式 | 说明 |
|------|---------|------|
| 沪深300 20 日滚动波动率 | `std(daily_return, 20) * sqrt(250)` | 年化波动率 |
| 沪深300 60 日滚动波动率 | `std(daily_return, 60) * sqrt(250)` | 中期波动率 |
| 波动率变化率 | `vol_20d / vol_60d` | 波动率扩张/收缩 |
| ATR（沪深300） | `SMA(TR, 14)` | 绝对波动幅度 |
| 市场日内振幅均值 | `mean((high-low)/close)` 全市场 | 日内波动结构 |

> **A 股没有官方 VIX**。中国波指（iVX）数据不连续且获取困难。
> 替代方案：用沪深300日收益率的滚动标准差 + 全市场日内振幅构造"隐含波动率代理"。

#### 2.1.6 风格因子数据（部分依赖 Factor Engine）

| 特征 | 计算方式 | 说明 |
|------|---------|------|
| 小盘/大盘相对强弱 | `中证1000收益 / 沪深300收益` 滚动 | 风格轮动核心 |
| 成长/价值相对强弱 | `创业板指收益 / 上证50收益` 滚动 | 成长 vs 价值 |
| 高beta/低beta比值 | 按 beta 分组的组间收益差 | 风险偏好 |
| 红利/成长比值 | `红利指数收益 / 创业板指收益` | 防御 vs 进攻 |

### 2.2 数据获取策略

```
┌──────────────────────────────────────────────────────────────┐
│                    数据获取层次                                │
│                                                              │
│  Layer 1: 已有数据（直接使用）                                │
│    - bars_stock_zh_a_daily_* (个股日线)                       │
│    - bars_index_* (指数日线，部分已有)                         │
│    - industry_daily (申万行业日线)                             │
│    - bars_ext_* (换手率等扩展指标)                             │
│                                                              │
│  Layer 2: 需聚合计算（从已有数据派生）                         │
│    - 全市场广度指标 (从个股行情聚合)                            │
│    - 波动率系列 (从指数收益率计算)                              │
│    - 风格因子 (从指数/行业收益率计算)                           │
│    - 成交额/换手率聚合                                        │
│                                                              │
│  Layer 3: 需新增数据源（新增 task_engine 下载任务）             │
│    - 北向资金净流入                                           │
│    - 融资融券余额                                             │
│    - 新增指数 (中证1000/创业板指/科创50/红利 等)               │
│    - ETF 申赎数据 (P2)                                       │
│                                                              │
│  ※ Layer 1 + Layer 2 足以支撑 MVP                            │
│  ※ Layer 3 在 Phase 2 逐步接入                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、状态空间设计（State-Space）

> **rev.2 核心重构**：从"三层离散分类"改为"连续状态向量"。

### 3.1 状态维度定义

Regime Engine 输出一个 **6 维连续状态向量 + 2 维转换信号**，每个维度 ∈ [0.0, 1.0]：

```
┌─────────────────────────────────────────────────────────────────┐
│                   Regime State Vector (核心输出)                  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Dimension 1: trend_strength         [0.0 ─── 0.5 ─── 1.0]│   │
│  │              强空头        无趋势        强多头              │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Dimension 2: risk_appetite          [0.0 ─── 0.5 ─── 1.0]│   │
│  │              极度避险       中性          极度冒险           │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Dimension 3: volatility_stress      [0.0 ─── 0.5 ─── 1.0]│   │
│  │              极低波动率     正常          极端波动           │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Dimension 4: market_breadth         [0.0 ─── 0.5 ─── 1.0]│   │
│  │              全面下跌       均衡          全面上涨           │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Dimension 5: liquidity              [0.0 ─── 0.5 ─── 1.0]│   │
│  │              枯竭          正常          泛滥               │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Dimension 6: sector_concentration   [0.0 ─── 0.5 ─── 1.0]│   │
│  │              均匀分散       正常          极端集中           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Transition Signals (前瞻/变化速度, 可以为负)               │   │
│  │                                                           │   │
│  │ breadth_momentum:   市场广度变化速度 [-1.0 ~ +1.0]         │   │
│  │ vol_acceleration:   波动率变化加速度 [-1.0 ~ +1.0]         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Convenience Labels (仅供人类阅读/日志，策略不消费)           │   │
│  │                                                           │   │
│  │ label_market: "BULL_TREND" / "BEAR_TREND" / "SIDEWAYS"    │   │
│  │ label_vol:    "LOW" / "NORMAL" / "HIGH" / "SPIKE"         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 每个维度的含义与计算逻辑

#### Dimension 1: `trend_strength`（趋势强度）

```python
def compute_trend_strength(index_data: pd.DataFrame) -> float:
    """
    趋势强度: 0 = 强空头, 0.5 = 无趋势, 1.0 = 强多头
    
    输入信号:
      - 指数 vs MA120 的偏离度 (核心)
      - MA20 斜率
      - MA20 vs MA60 的关系
    
    计算:
      score = 0.5  # 基准: 无趋势
      score += clip(distance_from_ma120 / 0.15, -0.3, 0.3)  # 偏离度贡献 ±0.3
      score += 0.1 if ma20 > ma60 else -0.1                  # 均线排列贡献 ±0.1
      score += clip(ma20_slope * 100, -0.1, 0.1)             # 斜率贡献 ±0.1
      return clip(score, 0.0, 1.0)
    """
```

#### Dimension 2: `risk_appetite`（风险偏好）

```python
def compute_risk_appetite(features: dict) -> float:
    """
    风险偏好: 0 = 极度避险, 1.0 = 极度冒险
    
    输入信号:
      - 市场广度 (breadth_above_ma20_pct)
      - 小盘 vs 大盘相对强弱
      - 涨停/跌停比例
    
    高 risk_appetite 特征: 小盘股暴涨、涨停多、全面上涨
    低 risk_appetite 特征: 大盘股/红利强、跌停多、缩量
    """
```

#### Dimension 3: `volatility_stress`（波动率压力）

```python
def compute_volatility_stress(features: dict) -> float:
    """
    波动率压力: 0 = 极低波动(平静), 1.0 = 极端波动(恐慌)
    
    输入信号:
      - vol_20d 在历史分位数中的位置 (核心)
      - vol_ratio (短期/长期波动率比)
    
    计算:
      # 使用历史分位数映射到 0-1
      percentile = rank_in_history(vol_20d, lookback=500)
      stress = percentile
      
      # vol_ratio 加速信号
      if vol_ratio > 1.5:
          stress = min(stress + 0.2, 1.0)
      
      return stress
    """
```

#### Dimension 4: `market_breadth`（市场广度）

```python
def compute_market_breadth(features: dict) -> float:
    """
    市场广度: 0 = 全面下跌, 1.0 = 全面上涨
    
    输入信号:
      - 站上 MA20 占比 (核心, 最稳定的广度指标)
      - 上涨家数占比 (辅助, 日内噪声较大)
    
    计算:
      # 站上MA20占比直接映射 (已经在 0-1 范围)
      breadth = pct_above_ma20 * 0.7 + advance_pct * 0.3
      return breadth
    """
```

#### Dimension 5: `liquidity`（流动性）

```python
def compute_liquidity(features: dict) -> float:
    """
    流动性: 0 = 枯竭, 1.0 = 泛滥
    
    输入信号:
      - turnover_ratio: 今日成交额 / 20日均值
    
    计算:
      # turnover_ratio 映射: 0.5x → 0.0, 1.0x → 0.5, 2.0x → 1.0
      liquidity = clip((turnover_ratio - 0.5) / 1.5, 0.0, 1.0)
      return liquidity
    """
```

#### Dimension 6: `sector_concentration`（行业集中度）

> **新增维度**：GPT review 指出的"cross-sectional information"的具体实现。

```python
def compute_sector_concentration(industry_data: pd.DataFrame) -> float:
    """
    行业集中度: 0 = 全行业均匀涨跌, 1.0 = 收益极端集中在少数行业
    
    为什么重要:
      - concentration 高 = 少数行业主导（主题行情）→ 适合行业动量
      - concentration 低 = 全面行情 → 适合选股策略
      - concentration 高 + 趋势弱 = 危险（指数靠权重股撑着，实际大多数在跌）
    
    计算:
      # 31个申万一级行业的20d收益率
      returns = industry_20d_returns  # shape: (31,)
      
      # 使用 Herfindahl Index 的变体
      abs_returns = abs(returns)
      if abs_returns.sum() < 1e-8:
          return 0.0
      
      weights = abs_returns / abs_returns.sum()
      hhi = (weights ** 2).sum()
      
      # HHI 映射到 0-1: 1/31 ≈ 0.03 (完全均匀) → 0.0, 0.3+ (极度集中) → 1.0
      concentration = clip((hhi - 0.03) / 0.27, 0.0, 1.0)
      return concentration
    """
```

### 3.3 Transition Signals（状态转换前兆）

> **新增**：GPT review 强调的原版设计是"后验"的。Transition signals 是前瞻性的。

```python
def compute_breadth_momentum(features_today: dict, features_5d_ago: dict) -> float:
    """
    广度动量: 市场广度正在改善还是恶化
    
    范围: [-1.0, +1.0]
      +1.0 = 广度快速改善 (从 0.3 → 0.7)
      -1.0 = 广度快速恶化 (从 0.7 → 0.3)
      0.0  = 广度稳定
    
    ⚠️ 这是最重要的前瞻信号：
      - 广度恶化往往领先指数下跌 3-5 天
      - 指数创新高但广度创新低 = "bearish divergence"
    
    计算:
      delta = breadth_today - breadth_5d_ago
      momentum = clip(delta / 0.20, -1.0, 1.0)  # ±20% 的广度变化映射到 ±1
      return momentum
    """


def compute_vol_acceleration(vol_today: float, vol_5d_ago: float, vol_20d_ago: float) -> float:
    """
    波动率加速度: 波动率变化的变化
    
    范围: [-1.0, +1.0]
      +1.0 = 波动率正在加速上升（即将进入高波环境）
      -1.0 = 波动率正在加速下降（市场正在冷静）
    
    计算:
      speed_now = (vol_today - vol_5d_ago) / vol_5d_ago  # 短期变化率
      speed_prev = (vol_5d_ago - vol_20d_ago) / vol_20d_ago  # 之前的变化率
      acceleration = speed_now - speed_prev  # 加速度 = 变化率的变化
      return clip(acceleration / 0.5, -1.0, 1.0)
    """
```

### 3.4 Cross-Sectional Features（截面结构, Phase 2）

> **新增**：GPT review 强调的"不只看指数层面，要看个股分布结构"。

```python
@dataclass
class CrossSectionalFeatures:
    """
    截面结构特征 — 描述"市场内部的结构性信息"
    
    这些特征比指数本身更早暴露市场的真实状态。
    """
    
    return_dispersion: float
    # 个股日收益率的标准差
    # 高 = 选股 alpha 机会多（分散度高）
    # 低 = 市场同步性高（系统性行情或恐慌）
    # 极低 + 下跌 = PANIC (correlation → 1)
    
    top10_contribution: float
    # 前10大权重股贡献了多少指数涨幅（百分比）
    # > 80% = 极度集中（指数失真，实际是个股熊市）
    # < 30% = 健康的广基行情
    
    avg_pairwise_correlation: float
    # 随机抽样 200 只股票，计算平均 pairwise correlation (20d rolling)
    # 接近 1 = 恐慌（高系统性风险）
    # 低 = 正常市场（特质性主导）
    
    return_skewness: float
    # 个股收益率分布的偏度
    # 正偏 = 少数暴涨（牛市涨停行情）
    # 负偏 = 少数暴跌（地雷股出清）
```

> Phase 2 实现。这些特征需要拉取全市场个股数据，计算成本高（同广度特征），
> 可以复用 PhoenixA 的 `/api/v2/market/breadth` 接口扩展。

### 3.5 Convenience Labels（便利层：离散标签）

> 离散标签从连续分数**推导**而来，仅用于日志/报告/前端展示，策略引擎**不消费**。

```python
def derive_labels(state: RegimeState) -> dict:
    """从连续状态向量推导离散标签（仅用于人类可读性）"""
    
    # Market trend label
    if state.trend_strength > 0.65:
        label_market = "BULL_TREND"
    elif state.trend_strength < 0.35:
        label_market = "BEAR_TREND"
    elif state.volatility_stress > 0.8:
        label_market = "PANIC"
    else:
        label_market = "SIDEWAYS"
    
    # Volatility label
    if state.volatility_stress > 0.75:
        label_vol = "SPIKE" if state.vol_acceleration > 0.3 else "HIGH"
    elif state.volatility_stress < 0.25:
        label_vol = "LOW"
    else:
        label_vol = "NORMAL"
    
    return {
        "label_market": label_market,
        "label_vol": label_vol,
        "label_confidence": abs(state.trend_strength - 0.5) * 2,  # 0-1, 离0.5越远越确定
    }
```

---

## 四、Regime Features（特征工程）

### 4.1 MVP 特征集（严格精简）

> ⚠️ **rev.2 关键修正**：从原版 30+ 个特征砍到 **8 个核心特征**。
> 
> 原则："每新增 1 个特征，必须证明它的 IC > 0.03 且不与已有特征高度相关(|corr| < 0.7)"

```python
@dataclass
class RegimeFeatures:
    """
    MVP 特征向量 — 仅 8 个核心特征
    
    选择标准:
      1. 每个维度选 1 个最强代理变量
      2. 互相低相关
      3. 数据已有或容易计算
      4. 物理含义清晰
    """
    trade_date: str
    
    # ──── 趋势 (1 个) ────
    hs300_distance_from_ma120: float   # (close - ma120) / ma120
    # 为什么选这个: 比 bool(close > ma120) 信息量更大，连续值，含偏离幅度
    
    # ──── 趋势斜率 (1 个) ────
    hs300_ma20_slope: float            # MA20 的 5 日变化率
    # 为什么选这个: 趋势方向 + 强度都包含了
    
    # ──── 广度 (1 个) ────
    breadth_above_ma20_pct: float      # 全市场站上 MA20 占比
    # 为什么选这个: 最稳定的广度指标，日内噪声小，比 advance_pct 好
    
    # ──── 波动率 (1 个) ────
    vol_20d: float                     # 沪深300 20日年化波动率
    # 为什么选这个: 最基础的风险度量
    
    # ──── 波动率结构 (1 个) ────
    vol_ratio: float                   # vol_20d / vol_60d
    # 为什么选这个: 波动率是在扩张还是收缩，regime transition 的领先信号
    
    # ──── 流动性 (1 个) ────
    turnover_ratio: float              # 今日成交额 / 20日均值
    # 为什么选这个: 放量/缩量是最直觉的流动性指标
    
    # ──── 风格 (1 个) ────
    style_small_vs_large: float        # 中证1000 20d收益 - 沪深300 20d收益
    # 为什么选这个: 风格轮动的最简表达
    
    # ──── 行业集中度 (1 个) ────
    industry_concentration: float      # 行业 HHI 变体 (见 3.2)
    # 为什么选这个: GPT review 强调的 cross-sectional 信息
```

### 4.2 Phase 2+ 扩展特征（需 IC 验证后引入）

| 特征 | Phase | 前置条件 | 预期价值 |
|------|-------|---------|---------|
| 涨停/跌停家数 | P2 | MVP IC 验证完成 | A 股情绪极端值检测 |
| 北向资金 5d 净流入 | P2 | 新增数据源 | 外资情绪风向标 |
| 融资余额变化率 | P2 | 新增数据源 | 杠杆资金情绪 |
| return_dispersion (截面离散度) | P2 | PhoenixA 聚合 API | 选股 alpha 可行性 |
| top10_contribution | P3 | PhoenixA 聚合 API | 指数失真检测 |
| avg_pairwise_correlation | P3 | 计算密集 | 恐慌检测（correlation → 1）|
| 创新高/新低占比 | P3 | IC 验证 | 趋势确认 |

> **引入新特征的门控条件**：
> 1. Historical IC > 0.03（对 future 20d return）
> 2. 与已有特征 |corr| < 0.7
> 3. Regime stability: 该特征加入后不导致 state vector 日间抖动率 > 20%

---

## 五、State Estimator（状态估计器）

> **rev.2 重构**：从 "Rule-based Classifier" 改为 "Continuous State Estimator"。
> 不再有 if/else 离散跳变，每个状态维度都是连续值。

### 5.1 核心计算逻辑

```python
class RegimeStateEstimator:
    """
    连续状态估计器
    
    核心设计:
      - 每个维度独立计算 (0.0 - 1.0)
      - 使用 EMA 平滑避免日间抖动 (替代旧版 Regime Inertia)
      - 无阈值 = 无过拟合点
      - 策略层直接乘以状态值做加权
    """
    
    def __init__(self, config: RegimeConfig):
        self.config = config
        self.smoothing_alpha = 0.3  # EMA 平滑系数 (0.3 ≈ 5天半衰期)
        self._prev_state: Optional[RegimeState] = None
    
    def estimate(self, features: RegimeFeatures) -> RegimeState:
        """从 8 个特征计算 6+2 维状态向量"""
        
        # 1. 计算原始状态 (连续映射, 无 if-else)
        raw = RegimeState(
            trade_date=features.trade_date,
            trend_strength=self._compute_trend(features),
            risk_appetite=self._compute_risk(features),
            volatility_stress=self._compute_vol_stress(features),
            market_breadth=features.breadth_above_ma20_pct,
            liquidity=clip((features.turnover_ratio - 0.5) / 1.5, 0.0, 1.0),
            sector_concentration=features.industry_concentration,
            breadth_momentum=0.0,  # 需要前几天数据
            vol_acceleration=0.0,
        )
        
        # 2. EMA 平滑 (替代旧版 Regime Inertia)
        if self._prev_state is not None:
            raw = self._ema_smooth(raw, self._prev_state)
        
        # 3. 推导便利标签 (仅供日志/前端)
        raw.labels = derive_labels(raw)
        
        self._prev_state = raw
        return raw
    
    def _compute_trend(self, f: RegimeFeatures) -> float:
        """趋势强度: sigmoid 映射, 0.5=无趋势, >0.5=多头, <0.5=空头"""
        score = 0.5
        score += sigmoid_clip(f.hs300_distance_from_ma120 / 0.15) * 0.4
        score += clip(f.hs300_ma20_slope * 50, -0.1, 0.1)
        return clip(score, 0.0, 1.0)
    
    def _compute_risk(self, f: RegimeFeatures) -> float:
        """风险偏好: 广度 + 风格"""
        base = f.breadth_above_ma20_pct
        style_adj = clip(f.style_small_vs_large / 0.10, -0.15, 0.15)
        return clip(base + style_adj, 0.0, 1.0)
    
    def _compute_vol_stress(self, f: RegimeFeatures) -> float:
        """波动率压力: vol_ratio 映射"""
        return clip((f.vol_ratio - 0.7) / 1.3, 0.0, 1.0)
    
    def _ema_smooth(self, raw: RegimeState, prev: RegimeState) -> RegimeState:
        """
        EMA 平滑: alpha=0.3
        ⚠️ vol_stress 上行不平滑(快速响应风险), 下行才平滑
        """
        a = self.smoothing_alpha
        smoothed = RegimeState(trade_date=raw.trade_date)
        
        for dim in ["trend_strength", "risk_appetite", "market_breadth",
                    "liquidity", "sector_concentration"]:
            setattr(smoothed, dim, a * getattr(raw, dim) + (1-a) * getattr(prev, dim))
        
        # vol_stress: 只平滑下行
        if raw.volatility_stress > prev.volatility_stress:
            smoothed.volatility_stress = raw.volatility_stress
        else:
            smoothed.volatility_stress = a * raw.volatility_stress + (1-a) * prev.volatility_stress
        
        # Transition signals 不平滑
        smoothed.breadth_momentum = raw.breadth_momentum
        smoothed.vol_acceleration = raw.vol_acceleration
        return smoothed
```

### 5.2 策略权重的连续映射

```python
class StrategyAllocator:
    """
    从连续状态向量 → 策略权重 (连续函数, 无 if-else)
    
    每种策略有一个"亲和力函数": f(state) → weight
    """
    
    def allocate(self, state: RegimeState) -> StrategyAllocation:
        # Momentum: 趋势强 + 广度好 + 低波 → 强
        momentum_w = (
            state.trend_strength * 0.4 +
            state.market_breadth * 0.3 +
            (1 - state.volatility_stress) * 0.2 +
            state.liquidity * 0.1
        )
        
        # Mean Reversion: 无趋势(trend≈0.5) + 适度波动 → 强
        trend_neutrality = 1.0 - abs(state.trend_strength - 0.5) * 2
        mean_rev_w = (
            trend_neutrality * 0.5 +
            state.volatility_stress * 0.2 +
            (1 - state.sector_concentration) * 0.3
        )
        
        # Factor Selection: 基础策略, 大多数时候都有效
        factor_w = (
            state.market_breadth * 0.3 +
            (1 - state.volatility_stress) * 0.3 +
            0.4
        )
        
        # Event Driven: 高集中度 + 高风险偏好 → 主题行情
        event_w = (
            state.sector_concentration * 0.4 +
            state.risk_appetite * 0.3 +
            state.liquidity * 0.3
        )
        
        # 归一化
        total = momentum_w + mean_rev_w + factor_w + event_w
        weights = {k: v/total for k, v in {
            "momentum": momentum_w,
            "mean_reversion": mean_rev_w,
            "factor_select": factor_w,
            "event_driven": event_w,
        }.items()}
        
        # 仓位上限
        position_limit = self._position_limit(state)
        
        return StrategyAllocation(weights=weights, position_limit=position_limit)
    
    def _position_limit(self, state: RegimeState) -> float:
        """仓位 = 0.9 - 风险惩罚"""
        penalty = (
            state.volatility_stress * 0.6 +
            max(0, -state.breadth_momentum) * 0.3 +
            max(0, 0.3 - state.trend_strength) * 0.5
        )
        return clip(0.9 - penalty, 0.05, 1.0)
```

### 5.3 因子权重的连续调整

```python
class FactorWeightAdjuster:
    """
    ❌ 旧版: if BULL → growth × 1.5
    ✅ 新版: growth_weight = 1.0 + (trend - 0.5) * 1.0
    """
    
    def adjust(self, state: RegimeState) -> Dict[str, float]:
        t = state.trend_strength
        v = state.volatility_stress
        r = state.risk_appetite
        
        return {
            "growth_revenue_yoy": 1.0 + (t - 0.5) * 1.0 + (r - 0.5) * 0.5,
            "quality_cash_conversion": 1.0 + v * 0.8,
            "profitability_roe": 1.0 + (t - 0.5) * 0.3,
            "valuation_pe_ttm": 1.0 + (0.5 - t) * 0.8 + v * 0.3,
            "per_share_dps": 1.0 + (0.5 - r) * 1.2 + v * 0.5,
            "solvency_debt_ratio": 1.0 + v * 0.6,
        }
```

---

## 六、架构设计

### 6.1 模块结构

```
artemis/
├── engines/
│   ├── factor_engine/                     ← 因子引擎（已设计）
│   ├── strategy_engine/                   ← 策略引擎（已有）
│   ├── indicator_engine/                  ← 指标引擎（已有）
│   ├── cache_engine/                      ← 缓存引擎（已有）
│   │
│   └── regime_engine/                     ← 新增：市场状态引擎
│       ├── __init__.py
│       ├── pipeline.py                    # Regime 计算 Pipeline 协调器
│       ├── config.py                      # Regime 阈值/权重配置
│       │
│       ├── features/                      # 特征计算
│       │   ├── __init__.py
│       │   ├── base.py                    # BaseFeatureComputer 抽象类
│       │   ├── trend.py                   # 趋势特征计算
│       │   ├── breadth.py                 # 市场广度特征计算
│       │   ├── volatility.py              # 波动率特征计算
│       │   ├── liquidity.py               # 流动性特征计算
│       │   ├── style.py                   # 风格特征计算
│       │   ├── industry.py                # 行业轮动特征计算
│       │   └── sentiment.py               # 资金/情绪特征计算 (Phase 2)
│       │
│       ├── classifiers/                   # 分类器
│       │   ├── __init__.py
│       │   ├── base.py                    # BaseClassifier 抽象类
│       │   ├── market_classifier.py       # 大盘 regime 分类器
│       │   ├── volatility_classifier.py   # 波动率 regime 分类器
│       │   ├── style_classifier.py        # 风格 regime 分类器
│       │   └── composite.py              # 综合 regime + 策略权重映射
│       │
│       ├── models.py                      # 数据模型 (RegimeFeatures, RegimeResult, etc.)
│       │
│       └── storage/                       # 存储
│           ├── __init__.py
│           └── regime_store.py            # Regime 结果读写 (对接 PhoenixA)
│
├── services/
│   ├── factor_service.py                  # 因子计算服务（已设计）
│   └── regime_service.py                  # Regime 计算服务（新增）
│
└── api/
    ├── factor_api.py                      # 因子 API（已设计）
    └── regime_api.py                      # Regime API（新增）
```

### 6.2 核心类设计

```python
# ─── models.py ─────────────────────────────────────────────

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

class MarketRegimeType(str, Enum):
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    SIDEWAYS = "SIDEWAYS"
    PANIC = "PANIC"

class VolatilityRegimeType(str, Enum):
    LOW_VOL = "LOW_VOL"
    NORMAL_VOL = "NORMAL_VOL"
    HIGH_VOL = "HIGH_VOL"
    VOL_SPIKE = "VOL_SPIKE"

class StyleRegimeType(str, Enum):
    GROWTH = "GROWTH"
    VALUE = "VALUE"
    SMALL_CAP = "SMALL_CAP"
    BALANCED = "BALANCED"

@dataclass
class RegimeLabel:
    name: str
    confidence: float    # 0.0 - 1.0
    sub_scores: Dict[str, float] = field(default_factory=dict)
    # sub_scores 记录每个子规则的得分，方便 debug

@dataclass
class RegimeResult:
    trade_date: str
    market_regime: RegimeLabel
    volatility_regime: RegimeLabel
    style_regime: RegimeLabel
    industry_leading: List[str]
    industry_lagging: List[str]
    industry_rotation_speed: float
    strategy_weights: Dict[str, float]
    factor_weight_adjustments: Dict[str, float]
    risk_level: float                   # 0.0 - 1.0
    position_limit: float               # 0.0 - 1.0
    suggested_holding_period: str       # "short" / "medium" / "long"
    
    def to_dict(self) -> dict:
        """序列化为 JSON 可存储的 dict"""
        return {
            "trade_date": self.trade_date,
            "market_regime": self.market_regime.name,
            "market_confidence": self.market_regime.confidence,
            "volatility_regime": self.volatility_regime.name,
            "volatility_confidence": self.volatility_regime.confidence,
            "style_regime": self.style_regime.name,
            "style_confidence": self.style_regime.confidence,
            "industry_leading": self.industry_leading,
            "industry_lagging": self.industry_lagging,
            "industry_rotation_speed": self.industry_rotation_speed,
            "strategy_weights": self.strategy_weights,
            "factor_weight_adjustments": self.factor_weight_adjustments,
            "risk_level": self.risk_level,
            "position_limit": self.position_limit,
            "suggested_holding_period": self.suggested_holding_period,
        }
```

```python
# ─── config.py ─────────────────────────────────────────────

@dataclass
class RegimeConfig:
    """
    Regime 引擎配置（所有阈值集中管理）
    
    这些阈值是 regime engine 的核心参数。
    MVP 阶段用经验值，后续可通过历史回测优化。
    """
    
    # ── 大盘 Regime 阈值 ──
    # 趋势判定
    trend_ma_short: int = 20               # 短期均线周期
    trend_ma_medium: int = 60              # 中期均线周期
    trend_ma_long: int = 120               # 长期均线周期（A 股用 120 而非 200）
    
    # PANIC 条件
    panic_return_5d_threshold: float = -0.08    # 5日跌幅超过这个触发
    panic_limit_down_threshold: int = 200       # 跌停数超过这个触发
    panic_vol_ratio_threshold: float = 1.8      # vol_20d/vol_60d 超过这个触发
    panic_min_score: float = 0.6                # PANIC 最低触发分数
    
    # BULL/BEAR 条件
    bull_breadth_ma20_threshold: float = 0.55   # 站上 MA20 占比
    bear_breadth_ma20_threshold: float = 0.40
    bull_bear_min_score: float = 0.6
    
    # ── 波动率 Regime 阈值 ──
    vol_lookback_days: int = 500            # 波动率历史分位数计算窗口
    vol_low_percentile: float = 0.25
    vol_high_percentile: float = 0.75
    vol_spike_ratio: float = 1.6            # vol_20d/vol_60d 突刺阈值
    vol_spike_daily_return: float = 0.03    # 日收益率绝对值阈值
    vol_spike_consecutive_days: int = 3     # 连续天数
    
    # ── 风格 Regime 阈值 ──
    style_lookback_days: int = 20           # 风格比较窗口
    style_growth_threshold: float = 0.03    # 创业板超额收益阈值
    style_value_threshold: float = 0.03
    style_small_cap_threshold: float = 0.05
    
    # ── 策略权重映射 ──
    # 见 5.3 节的完整映射表
    strategy_weight_map: Dict = field(default_factory=dict)
    
    # ── 因子权重调整 ──
    factor_weight_map: Dict = field(default_factory=dict)
```

```python
# ─── pipeline.py ───────────────────────────────────────────

class RegimePipeline:
    """
    Regime 计算 Pipeline 协调器
    
    职责:
      1. 从 PhoenixA 拉取数据
      2. 计算特征
      3. 分类 regime
      4. 输出策略权重
      5. 存储结果
    """
    
    def __init__(self, phoenixa_client, regime_store, config: RegimeConfig):
        self.client = phoenixa_client
        self.store = regime_store
        self.config = config
        
        # 初始化特征计算器
        self.feature_computers = [
            TrendFeatureComputer(config),
            BreadthFeatureComputer(config),
            VolatilityFeatureComputer(config),
            LiquidityFeatureComputer(config),
            StyleFeatureComputer(config),
            IndustryFeatureComputer(config),
        ]
        
        # 初始化分类器
        self.market_classifier = MarketRegimeClassifier(config)
        self.vol_classifier = VolatilityRegimeClassifier(config)
        self.style_classifier = StyleRegimeClassifier(config)
        self.composite = CompositeRegimeMapper(config)
    
    async def run(self, trade_date: str) -> RegimeResult:
        """
        单日 regime 计算
        
        调用时机: 每交易日收盘后 (16:30)，在行情数据入库完毕之后
        """
        # 1. 拉取数据
        data_bundle = await self._fetch_data(trade_date)
        
        # 2. 计算特征
        features = RegimeFeatures(trade_date=trade_date)
        for computer in self.feature_computers:
            partial = computer.compute(data_bundle)
            features.merge(partial)
        
        # 3. 分类
        market = self.market_classifier.classify(features)
        vol = self.vol_classifier.classify(features)
        style = self.style_classifier.classify(features)
        
        # 4. 映射策略权重
        result = self.composite.compose(
            trade_date=trade_date,
            market=market,
            volatility=vol,
            style=style,
            features=features,
        )
        
        # 5. 存储
        await self.store.save_regime_result(result)
        await self.store.save_regime_features(features)
        
        return result
    
    async def run_backfill(self, start_date: str, end_date: str) -> List[RegimeResult]:
        """
        历史回填（回测需要）
        
        对历史每个交易日计算 regime，存入数据库
        """
        trading_dates = await self.client.get_trading_dates(start_date, end_date)
        results = []
        for date in trading_dates:
            result = await self.run(date)
            results.append(result)
        return results
    
    async def _fetch_data(self, trade_date: str) -> DataBundle:
        """
        批量拉取 regime 计算所需的全部数据
        
        返回 DataBundle 包含:
          - index_bars: 各指数日线 (lookback 250天)
          - market_breadth: 全市场广度数据 (PhoenixA 聚合API)
          - industry_bars: 行业日线
          - turnover_stats: 成交额统计
        """
        lookback = max(self.config.trend_ma_long, self.config.vol_lookback_days)
        
        # 并行请求
        index_bars, breadth, industry_bars, turnover = await asyncio.gather(
            self.client.get_index_bars(
                symbols=["000300", "000016", "399006", "000852", "000015"],
                start_date=shift_date(trade_date, -lookback),
                end_date=trade_date,
            ),
            self.client.get_market_breadth(trade_date),  # PhoenixA 聚合 API
            self.client.get_industry_daily(
                taxonomy="swhy",
                start_date=shift_date(trade_date, -60),
                end_date=trade_date,
            ),
            self.client.get_market_turnover_stats(trade_date),
        )
        
        return DataBundle(
            index_bars=index_bars,
            market_breadth=breadth,
            industry_bars=industry_bars,
            turnover_stats=turnover,
        )
```

### 6.3 数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Regime Engine 数据流                                     │
│                                                                             │
│  ┌───────────────┐        HTTP         ┌───────────────────┐               │
│  │  PhoenixA     │◄───────────────────►│  Artemis           │               │
│  │  (数据网关)    │                     │  Regime Engine     │               │
│  └───────┬───────┘                     └─────────┬─────────┘               │
│          │                                       │                          │
│          │ SQL                                   │ Pipeline                  │
│          ▼                                       ▼                          │
│  ┌────────────────┐          ┌─────────────────────────────────┐            │
│  │  PostgreSQL    │          │  1. Fetch Data (index/breadth/  │            │
│  │                │          │     industry/turnover)           │            │
│  │  bars_index_*  │────────► │  2. Compute Features            │            │
│  │  bars_stock_*  │────────► │     - trend / breadth / vol     │            │
│  │  industry_daily│────────► │     - liquidity / style         │            │
│  │                │          │  3. Classify (3-layer)           │            │
│  │                │          │     - market / vol / style       │            │
│  │  regime_       │◄─────────│  4. Map Strategy Weights        │            │
│  │  features      │  存储    │  5. Store Results               │            │
│  │  regime_       │◄─────────│                                 │            │
│  │  result        │          └──────────────────┬──────────────┘            │
│  └────────────────┘                             │                           │
│                                                 │ 消费                      │
│                                    ┌────────────▼──────────────┐            │
│                                    │  Strategy Engine           │            │
│                                    │  - 根据 regime 选策略      │            │
│                                    │  - 根据因子权重选股         │            │
│                                    │  - 根据 position_limit 控仓 │            │
│                                    └───────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 七、存储设计

### 7.1 regime_features 表（特征快照）

```sql
-- 每日 regime 特征快照（调试 + 回溯分析用）
CREATE TABLE regime_features (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE NOT NULL,
    market          VARCHAR(16) NOT NULL DEFAULT 'zh_a',
    
    -- 趋势特征
    trend_features  JSONB NOT NULL DEFAULT '{}',
    -- {"hs300_above_ma120": true, "hs300_ma20_slope": 0.0012, ...}
    
    -- 广度特征
    breadth_features JSONB NOT NULL DEFAULT '{}',
    -- {"advance_pct": 0.62, "limit_up": 45, "above_ma20_pct": 0.58, ...}
    
    -- 波动率特征
    volatility_features JSONB NOT NULL DEFAULT '{}',
    -- {"vol_20d": 0.18, "vol_60d": 0.15, "vol_ratio": 1.2, ...}
    
    -- 流动性特征
    liquidity_features JSONB NOT NULL DEFAULT '{}',
    -- {"turnover": 12500, "turnover_ratio": 1.15, ...}
    
    -- 风格特征
    style_features  JSONB NOT NULL DEFAULT '{}',
    
    -- 行业特征
    industry_features JSONB NOT NULL DEFAULT '{}',
    
    -- 资金/情绪特征 (Phase 2)
    sentiment_features JSONB NOT NULL DEFAULT '{}',
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_regime_features UNIQUE (trade_date, market)
);

CREATE INDEX idx_rf_date ON regime_features (trade_date DESC);
```

### 7.2 regime_result 表（判定结果）

```sql
-- 每日 regime 判定结果（Strategy Engine 消费）
-- ⚠️ rev.2: 核心输出是 state_vector (JSONB), 离散标签仅为便利层
CREATE TABLE regime_result (
    id              BIGSERIAL PRIMARY KEY,
    trade_date      DATE NOT NULL,
    market          VARCHAR(16) NOT NULL DEFAULT 'zh_a',
    
    -- ── 核心: 连续状态向量 (策略引擎消费这个) ──
    state_vector    JSONB NOT NULL DEFAULT '{}',
    -- {"trend_strength": 0.72, "risk_appetite": 0.81, "volatility_stress": 0.22,
    --  "market_breadth": 0.64, "liquidity": 0.71, "sector_concentration": 0.31,
    --  "breadth_momentum": -0.12, "vol_acceleration": 0.05}
    
    -- ── 便利层: 离散标签 (仅用于日志/前端, 从 state_vector 推导) ──
    label_market    VARCHAR(32),            -- BULL_TREND / BEAR_TREND / SIDEWAYS / PANIC
    label_vol       VARCHAR(32),            -- LOW / NORMAL / HIGH / SPIKE
    label_confidence DOUBLE PRECISION,
    
    -- ── 策略分配输出 (从 state_vector 通过连续映射计算) ──
    strategy_weights JSONB NOT NULL DEFAULT '{}',
    factor_weight_adjustments JSONB NOT NULL DEFAULT '{}',
    position_limit  DOUBLE PRECISION,
    suggested_holding_period VARCHAR(16),
    
    -- ── 行业轮动 ──
    industry_leading JSONB DEFAULT '[]',
    industry_lagging JSONB DEFAULT '[]',
    industry_rotation_speed DOUBLE PRECISION,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_regime_result UNIQUE (trade_date, market)
);

CREATE INDEX idx_rr_date ON regime_result (trade_date DESC);
CREATE INDEX idx_rr_state_gin ON regime_result USING GIN (state_vector jsonb_path_ops);

-- Generated columns: 常用状态维度提取为物理列加速查询
ALTER TABLE regime_result
    ADD COLUMN trend_strength DOUBLE PRECISION
        GENERATED ALWAYS AS ((state_vector->>'trend_strength')::double precision) STORED;
ALTER TABLE regime_result
    ADD COLUMN volatility_stress DOUBLE PRECISION
        GENERATED ALWAYS AS ((state_vector->>'volatility_stress')::double precision) STORED;

CREATE INDEX idx_rr_trend ON regime_result (trade_date, trend_strength DESC NULLS LAST);
CREATE INDEX idx_rr_vol ON regime_result (trade_date, volatility_stress DESC NULLS LAST);

COMMENT ON TABLE regime_result IS '市场状态引擎每日输出 — 连续状态向量 + 策略分配，供 Strategy Engine 消费';
```

### 7.3 存储空间估算

| 表 | 每日行数 | 行大小 | 每年 | 10年 |
|---|---------|--------|------|------|
| regime_features | 1 | ~2 KB (JSONB) | ~0.5 MB | ~5 MB |
| regime_result | 1 | ~1 KB | ~0.25 MB | ~2.5 MB |
| **总计** | | | **< 1 MB/年** | **< 10 MB** |

→ 存储量极小，不影响现有容量规划。

---

## 八、计算调度

### 8.1 调度时间线

```
交易日流程（收盘后）:

15:00   A 股收盘
15:30   bars_* 行情数据入库完毕（已有调度）
16:00   Factor Engine 估值因子计算（已设计）
16:30   ▶ Regime Engine 计算
          1. 拉取指数/广度/行业数据   ~30s
          2. 计算 regime features      ~10s
          3. 分类 + 策略权重映射       ~1s
          4. 存储结果                  ~1s
          总耗时: < 1 分钟
17:00   Strategy Engine 可消费最新 regime

非交易日:
  不计算。
  
周末:
  可选：回填/校验历史 regime 数据
```

### 8.2 Cronjob 集成

```
Cronjob (Go) 新增调度任务:

任务名: regime_daily_compute
触发: cron("0 30 16 * * MON-FRI")    # 每交易日 16:30
调用: POST http://artemis:18000/api/v1/regime/compute
      body: {"market": "zh_a"}
依赖: bars_daily_sync 完成后
```

### 8.3 API 设计

```python
# ─── regime_api.py ─────────────────────────────────────────

@router.post("/regime/compute")
async def compute_regime(
    market: str = "zh_a",
    trade_date: Optional[str] = None,   # 默认今天
):
    """触发单日 regime 计算"""
    pass

@router.post("/regime/backfill")
async def backfill_regime(
    market: str = "zh_a",
    start_date: str = ...,
    end_date: str = ...,
):
    """历史回填 regime 数据（回测前需要先跑一次）"""
    pass

@router.get("/regime/current")
async def get_current_regime(
    market: str = "zh_a",
):
    """
    获取最新 regime 判定
    
    返回示例:
    {
      "trade_date": "2026-05-08",
      "market_regime": "BULL_TREND",
      "market_confidence": 0.72,
      "volatility_regime": "NORMAL_VOL",
      "volatility_confidence": 0.65,
      "style_regime": "GROWTH",
      "style_confidence": 0.58,
      "strategy_weights": {
        "momentum": 0.4,
        "mean_reversion": 0.1,
        "factor_select": 0.3,
        "event_driven": 0.2
      },
      "risk_level": 0.35,
      "position_limit": 0.85,
      "suggested_holding_period": "medium"
    }
    """
    pass

@router.get("/regime/history")
async def get_regime_history(
    market: str = "zh_a",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 60,
):
    """获取历史 regime 序列（回测/分析用）"""
    pass

@router.get("/regime/features")
async def get_regime_features(
    trade_date: str,
    market: str = "zh_a",
):
    """获取指定日期的 regime 特征向量（调试/分析用）"""
    pass

@router.get("/regime/transition")
async def get_regime_transitions(
    market: str = "zh_a",
    start_date: str = ...,
    end_date: str = ...,
):
    """
    获取 regime 转换记录
    
    例: BULL_TREND → SIDEWAYS (2026-04-15, 持续了 32 天)
         SIDEWAYS → BEAR_TREND (2026-05-01, 持续了 16 天)
    """
    pass
```

---

## 九、PhoenixA 侧变更

### 9.1 新增 Migration

```sql
-- migrations/postgresql/security/0004_regime_engine.sql

-- 特征快照表
CREATE TABLE IF NOT EXISTS regime_features (
    -- 见 7.1 节
);

-- 结果表
CREATE TABLE IF NOT EXISTS regime_result (
    -- 见 7.2 节
);
```

### 9.2 新增聚合 API（广度计算用）

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v2/market/breadth` | 全市场广度指标（当日上涨家数、涨跌停、MA上方占比） |
| GET | `/api/v2/market/turnover-stats` | 全市场成交额统计 |
| POST | `/api/v2/regime/features` | 批量写入 regime 特征 |
| POST | `/api/v2/regime/result` | 批量写入 regime 结果 |
| GET | `/api/v2/regime/result` | 查询 regime 结果 (by date range) |
| GET | `/api/v2/regime/features` | 查询 regime 特征 (by date) |

#### 广度 API 详细设计

```
GET /api/v2/market/breadth?date=2026-05-08&market=zh_a

PhoenixA 内部 SQL:
  SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE close > pre_close) as advance_count,
    COUNT(*) FILTER (WHERE (close - pre_close) / NULLIF(pre_close, 0) >= 0.098) as limit_up,
    COUNT(*) FILTER (WHERE (close - pre_close) / NULLIF(pre_close, 0) <= -0.098) as limit_down
  FROM bars_stock_zh_a_daily_nf
  WHERE trade_date = $1;

Response:
{
  "date": "2026-05-08",
  "total_stocks": 5126,
  "advance_count": 3178,
  "decline_count": 1948,
  "advance_pct": 0.620,
  "limit_up_count": 42,
  "limit_down_count": 8
}
```

> **MA 上方占比**需要结合历史数据计算，建议 PhoenixA 提供专门的聚合 SQL 查询，
> 或者在 Artemis 侧使用 indicator_engine 预计算每只股票的 MA20/MA60 并缓存。

---

## 十、与 Strategy Engine 的集成

### 10.1 Strategy Engine 消费 Regime

```python
class RegimeAwareStrategy(BaseStrategy):
    """
    Regime 感知策略 — 所有策略的基类升级
    
    核心变化:
      在 select_stocks() 之前先查询当前 regime，
      根据 regime 动态调整策略行为
    """
    
    def __init__(self):
        self.regime_store = RegimeStore(phoenixa_client)
    
    def run(self, as_of_date: str):
        # 获取当前 regime
        regime = self.regime_store.get_regime(as_of_date)
        
        if regime is None:
            # regime 数据不存在，使用默认保守配置
            regime = RegimeResult.default_conservative()
        
        # 根据 regime 过滤可用策略
        active_strategies = self._filter_strategies(regime)
        
        # 根据 regime 调整仓位
        max_position = regime.position_limit
        
        # 根据 regime 调整因子权重
        factor_weights = self._adjust_factor_weights(
            base_weights=self.base_factor_weights,
            adjustments=regime.factor_weight_adjustments,
        )
        
        # 执行选股 + 信号生成
        signals = []
        for strategy in active_strategies:
            weight = regime.strategy_weights.get(strategy.name, 0.0)
            if weight > 0:
                sub_signals = strategy.generate_signals(
                    as_of_date=as_of_date,
                    factor_weights=factor_weights,
                    position_limit=max_position * weight,
                )
                signals.extend(sub_signals)
        
        return signals
```

### 10.2 回测中使用历史 Regime

```python
class BacktestEngine:
    """回测引擎集成 regime"""
    
    def run_backtest(self, strategy, start_date, end_date):
        trading_dates = self.get_trading_dates(start_date, end_date)
        
        for date in trading_dates:
            # 获取当日 regime（历史 regime，已通过 backfill 预计算）
            regime = self.regime_store.get_regime(date)
            
            # 策略根据 regime 做决策
            signals = strategy.run(date, regime=regime)
            
            # 执行交易模拟
            self.execute_signals(signals, regime.position_limit)
```

---

## 十一、Regime 有效性验证

### 11.1 回测验证方法

Regime Engine 本身需要验证——"你的 regime 判定有没有用？"

```python
class RegimeBacktester:
    """
    验证 Regime 有效性
    
    核心方法: 对比不同 regime 下策略的表现差异
    
    如果 regime 有效:
      - BULL regime 下 momentum 策略收益显著 > 0
      - BEAR regime 下 momentum 策略收益显著 < 0
      - 说明 regime 确实区分了不同的市场环境
    
    如果 regime 无效:
      - 各 regime 下策略表现无显著差异
      - 需要调整阈值或特征
    """
    
    def evaluate(self, start_date: str, end_date: str):
        # 1. 回填历史 regime
        regimes = self.pipeline.run_backfill(start_date, end_date)
        
        # 2. 按 regime 分组计算各策略收益
        results = {}
        for regime_type in MarketRegimeType:
            regime_dates = [r.trade_date for r in regimes 
                          if r.market_regime.name == regime_type.value]
            
            for strategy_name in ["momentum", "mean_reversion", "factor_select"]:
                returns = self.compute_strategy_returns(strategy_name, regime_dates)
                results[(regime_type.value, strategy_name)] = {
                    "mean_return": returns.mean(),
                    "sharpe": returns.mean() / returns.std() * np.sqrt(250),
                    "win_rate": (returns > 0).mean(),
                    "count": len(regime_dates),
                }
        
        # 3. 输出交叉验证表
        # regime       | momentum | mean_reversion | factor_select
        # BULL_TREND   | +18% AR  | -2% AR         | +12% AR
        # BEAR_TREND   | -8% AR   | +6% AR         | +3% AR
        # SIDEWAYS     | +1% AR   | +9% AR         | +7% AR
        # PANIC        | -25% AR  | +2% AR         | -5% AR
        
        return results
```

### 11.2 Regime 持续时间分析

```python
def analyze_regime_duration(regimes: List[RegimeResult]):
    """
    分析 regime 持续时间分布
    
    目标:
      - 确认 regime 不会过于频繁切换（每天换 = 无效）
      - 确认 regime 不会过于持久不变（一年不换 = 无意义）
      - 理想: 平均持续 10-50 个交易日
    """
    transitions = []
    current = regimes[0].market_regime.name
    start = regimes[0].trade_date
    
    for r in regimes[1:]:
        if r.market_regime.name != current:
            transitions.append({
                "from": current,
                "to": r.market_regime.name,
                "start": start,
                "end": r.trade_date,
                "duration": business_days_between(start, r.trade_date),
            })
            current = r.market_regime.name
            start = r.trade_date
    
    return transitions
```

---

## 十二、边界情况处理

| 场景 | 处理方式 |
|------|---------|
| 数据缺失（某指数未上市/停牌） | 使用可用指数替代（如中证1000不可用时用中证500） |
| 开市第一天（无历史数据） | 不计算 regime，返回 DEFAULT（保守配置） |
| 长假前后（如春节/国庆） | 不特殊处理，但 lookback 窗口自动跳过非交易日 |
| 新股集中上市（影响广度） | 广度计算排除上市不满 20 日的新股 |
| ST/退市股票 | 广度计算排除 ST 和退市股票 |
| 市场熔断/临时停市 | PANIC regime 自动触发，position_limit → 0.05 |
| Regime 频繁切换（oscillation） | 加入 **regime inertia**：regime 必须连续 3 天满足条件才切换 |
| 同时满足 BULL + BEAR（极端情况） | 按 confidence score 取高者 |

### Regime Inertia（惯性）详细设计

```python
class RegimeInertia:
    """
    防止 regime 频繁切换
    
    规则: 新 regime 必须连续 N 天判定一致才正式切换
    
    例:
      Day 1: BULL (当前) → classifier 输出 SIDEWAYS → 不切换
      Day 2: BULL (当前) → classifier 输出 SIDEWAYS → 不切换
      Day 3: BULL (当前) → classifier 输出 SIDEWAYS → 切换 ✅
    
    特例: PANIC 无惯性要求，立即生效（因为是紧急风控信号）
    """
    
    def __init__(self, min_days: int = 3):
        self.min_days = min_days
        self.pending_regime: Optional[str] = None
        self.pending_count: int = 0
    
    def update(self, current: str, proposed: str) -> str:
        # PANIC 立即生效
        if proposed == "PANIC":
            self.pending_regime = None
            self.pending_count = 0
            return "PANIC"
        
        # PANIC 退出需要惯性
        if current == "PANIC" and proposed != "PANIC":
            if self.pending_regime == proposed:
                self.pending_count += 1
            else:
                self.pending_regime = proposed
                self.pending_count = 1
            
            if self.pending_count >= self.min_days:
                self.pending_regime = None
                self.pending_count = 0
                return proposed
            return "PANIC"  # 还没恢复
        
        # 正常切换
        if proposed != current:
            if self.pending_regime == proposed:
                self.pending_count += 1
            else:
                self.pending_regime = proposed
                self.pending_count = 1
            
            if self.pending_count >= self.min_days:
                self.pending_regime = None
                self.pending_count = 0
                return proposed
            return current  # 还没切换
        
        # 不变
        self.pending_regime = None
        self.pending_count = 0
        return current
```

---

## 十三、性能估算

| 指标 | 预估 |
|------|------|
| 单日 regime 计算总耗时 | < 1 分钟 |
| ├ 数据拉取（PhoenixA HTTP） | ~30 秒（广度聚合是主要耗时） |
| ├ 特征计算 | ~10 秒 |
| ├ 分类 + 映射 | < 1 秒 |
| └ 存储 | < 1 秒 |
| 历史回填 1 年（250 天） | ~4-5 小时（受 PhoenixA 请求限制） |
| 历史回填 5 年 | ~20-25 小时（可周末跑） |
| 查询最新 regime | < 10 ms |
| 查询历史 regime 序列（1 年） | < 50 ms |

> **优化方向**：广度计算可以用 PostgreSQL 物化视图预计算，将拉取时间从 30s 降到 1s。
> 但这是 Phase 3 的优化，MVP 不需要。

---

## 十四、实施路线

| 阶段 | 时间 | 内容 | 依赖 |
|------|------|------|------|
| **Phase 1** | Week 1-2 | 基础框架 + 核心特征 | — |
| | | - `models.py`: 数据模型定义 | |
| | | - `config.py`: 阈值配置 | |
| | | - `features/trend.py`: 趋势特征（最简单，先验证流程） | |
| | | - `features/volatility.py`: 波动率特征 | |
| | | - `pipeline.py`: Pipeline 骨架 | |
| | | - PhoenixA `regime_features` + `regime_result` 建表 migration | |
| | | - 新增指数下载任务（中证1000/创业板指/上证50/红利） | |
| **Phase 2** | Week 3-4 | 广度 + 分类器 | Phase 1 |
| | | - `features/breadth.py`: 广度特征 | |
| | | - PhoenixA 广度聚合 API (`/api/v2/market/breadth`) | |
| | | - `classifiers/market_classifier.py`: 大盘 regime 分类器 | |
| | | - `classifiers/volatility_classifier.py`: 波动率 regime 分类器 | |
| | | - Regime Inertia 机制 | |
| **Phase 3** | Week 5-6 | 风格 + 行业 + 策略映射 | Phase 2 |
| | | - `features/style.py`: 风格特征 | |
| | | - `features/industry.py`: 行业轮动特征 | |
| | | - `classifiers/style_classifier.py`: 风格 regime 分类器 | |
| | | - `classifiers/composite.py`: 策略权重映射 | |
| | | - `regime_api.py`: REST API | |
| | | - Cronjob 调度接入 | |
| **Phase 4** | Week 7-8 | 回测验证 + Strategy 集成 | Phase 3, Factor Engine Phase 4 |
| | | - 历史回填脚本（≥3 年） | |
| | | - Regime 有效性回测验证 | |
| | | - RegimeBacktester 工具 | |
| | | - Strategy Engine 集成 RegimeAwareStrategy | |
| | | - 阈值调优（根据回测结果） | |
| **Phase 5** | Week 9-10 | 资金流向 + 可视化 | Phase 4 |
| | | - `features/sentiment.py`: 北向资金/融资余额 | |
| | | - 新增数据源下载任务（北向/融资） | |
| | | - cthulhu 前端 regime 仪表盘（可选） | |
| | | - regime transition 时间线可视化 | |
| **Phase 6** | 后续 | ML 升级（按需） | Phase 5 |
| | | - KMeans/GMM 聚类自动发现 regime | |
| | | - HMM (Hidden Markov Model) | |
| | | - Meta Learning: 学习 regime → 因子有效性映射 | |
