export type FactorEngineHelpKey =
  | 'availability_guide'
  | 'expected_status'
  | 'live_status'
  | 'source_readiness'
  | 'capability_source'
  | 'selected_source'
  | 'required_sources'
  | 'missing_sources'
  | 'required_fields'
  | 'known_fields'
  | 'provenance'
  | 'higher_is_better'
  | 'market_data'
  | 'providers'
  | 'coverage'
  | 'linked_filter';

export interface FactorEngineLegendItem {
  key: string;
  label: string;
  color: string;
  description: string;
}

export const FACTOR_ENGINE_HELP_TEXTS: Record<FactorEngineHelpKey, string> = {
  availability_guide: 'Expected 看的是静态 factor catalog：按设计是否理论可算。Live 看的是运行时 PhoenixA capabilities：当前环境是否真的能证明 source / field 可用。',
  expected_status: 'Expected = 静态设计态。ready 表示理论上该因子设计上可算；conditional 表示需要额外前提；blocked 表示设计上当前不可算。',
  live_status: 'Live = 运行态。available：当前环境确认可算；partial：只满足部分 source/field；missing：当前环境确认缺 source/field；unknown：PhoenixA 不可达、capabilities 空或不可信，暂时无法可信判断。',
  source_readiness: 'Source Readiness 用来判断每类底层 source 的运行态状态：ready = 有可信供给；empty = 表结构存在但当前没有数据；missing = 已确认缺少；unknown = 当前拿不到可信 runtime capability 信息。',
  capability_source: 'capability_source 描述 Live 判断依据来自哪里：phoenixA_catalog = 来自 PhoenixA capabilities；phoenixA_catalog_empty = PhoenixA 可达但 payload 为空；unavailable = 当前连不到或无法信任 PhoenixA capabilities。',
  selected_source: 'Selected source 是当前 Factor Engine 请求实际携带的 Workbench source。切换 source 后，Availability 会自动刷新；已有 Compute / Snapshot / Ranking 结果会被清空，避免把旧环境结果误认为新环境结果。',
  required_sources: 'Required Sources 是该因子按 catalog 定义依赖的数据源类型，例如 bars / income / balance_sheet / corporate_action。',
  missing_sources: 'Missing Sources 只在当前环境已经确认 source 缺失或为空时出现；若只是 PhoenixA capabilities 不可达，则更可能表现为 unknown，而不是 missing。',
  required_fields: 'Required Fields 是该因子计算所需字段。对于 data_json.*，若 capabilities 只声明了 data_json 顶层而没有具体 key，页面会保守地标注为 field-level unverified / unknown，而不会误报 fully available。',
  known_fields: 'Known Fields 是 PhoenixA capabilities 当前能明确声明出来的字段集合，不一定等于业务全量字段。',
  provenance: 'Provenance 展示 catalog 中登记的来源字段与 PhoenixA 查询链路，用于追查因子值到底依赖了哪些 source / field / endpoint。',
  higher_is_better: 'Higher Better? 表示排序方向偏好：Yes = 因子值越高通常越优；No = 因子值越低通常越优。',
  market_data: 'Needs Mkt Data 表示该因子除了财务/公司行动数据外，还需要价格、成交量或其他 bars 市场数据。',
  providers: 'Providers 显示 PhoenixA capabilities 报告了哪些 provider/source，以及每个 provider 当前覆盖了多少 data types。',
  coverage: 'Coverage 汇总当前 source 的 runtime 证据：行数、时间范围、data types。empty 与 missing 的差别通常可在这里看出来。',
  linked_filter: 'Only related factors 会把下方 Factor Availability 表联动过滤到依赖该 source 的因子，方便从 source 反查受影响的 factors。',
};

export const FACTOR_ENGINE_COPY = {
  registryHigherIsBetterLabel: 'Higher Better?',
  registryMarketDataLabel: 'Needs Mkt Data',
  availabilityGuideLabel: 'Availability guide',
  availabilityGuideSummary: 'Expected = catalog design-time readiness; Live = current PhoenixA runtime proof.',
  runtimeScopeSummary: 'All runtime results on this page are scoped to the selected source.',
  linkedFilterIdleLabel: 'Only related factors',
  linkedFilterActiveLabel: 'Filtering',
  fieldMissingPrefix: 'Missing now',
  fieldUnknownPrefix: 'Unverified now',
  fieldMoreSuffix: 'more in details',
} as const;

export const FACTOR_ENGINE_STATUS_LEGENDS: {
  live: FactorEngineLegendItem[];
  expected: FactorEngineLegendItem[];
  sourceReadiness: FactorEngineLegendItem[];
} = {
  live: [
    { key: 'available', label: 'available', color: 'green', description: '当前环境确认可算' },
    { key: 'partial', label: 'partial', color: 'orange', description: 'source / field 只满足一部分' },
    { key: 'missing', label: 'missing', color: 'red', description: '当前环境确认缺 source / field' },
    { key: 'unknown', label: 'unknown', color: 'default', description: '当前环境下暂时无法可信判断' },
  ],
  expected: [
    { key: 'ready', label: 'ready', color: 'green', description: 'catalog 设计上可算' },
    { key: 'conditional', label: 'conditional', color: 'orange', description: '需要额外前提才可算' },
    { key: 'blocked', label: 'blocked', color: 'red', description: '设计上当前不可算' },
  ],
  sourceReadiness: [
    { key: 'ready', label: 'ready', color: 'green', description: '有可信 runtime 供给' },
    { key: 'empty', label: 'empty', color: 'orange', description: '表/类型存在，但当前没有数据' },
    { key: 'missing', label: 'missing', color: 'red', description: '当前环境确认缺少' },
    { key: 'unknown', label: 'unknown', color: 'default', description: '当前拿不到可信 capability 信息' },
  ],
};

export const FACTOR_ENGINE_CAPABILITY_SOURCE_MESSAGES: Record<string, string> = {
  phoenixA_catalog: 'Live statuses are backed by PhoenixA capabilities for the selected source.',
  phoenixA_catalog_empty: 'PhoenixA capabilities responded but returned an empty payload, so Live statuses stay conservative.',
  unavailable: 'PhoenixA capabilities are unavailable or untrusted right now, so Live statuses may be conservative / unknown.',
};

