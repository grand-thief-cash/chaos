# phoenixA 数据中台服务设计文档

## 1. 背景与目标
- **使命**：phoenixA 作为“数据中台服务”，负责接收其他服务推送的股票/金融类数据（例如股票日线未复权 OHLC），将其落到统一的数据源（当前阶段主要是 MySQL），并以统一格式对外提供读写能力。
- **定位**：
  - 只做 **数据采集 + 存储 + 标准化格式 + 对外 CRUD 接口**。
  - **不做数据分析、回测、风控等复杂业务逻辑**，这些由其它服务负责。
- **框架对齐**：
  - 复用 `app/infra/go/application` 提供的生命周期管理、配置、组件注册、Hook 等机制，使用方式参考 `app/projects/cronjob`。
  - 通过 `cmd/main.go` 启动应用，侧重在 `internal/*` 包内完成 API、Service、DAO、Config、Registry 等的自注册与装配。

## 2. 需求梳理与范围

### 2.1 功能性需求
1. **数据写入（Ingest）**
   - 支持从其他服务接受股票/金融数据：
     - 当前重点：HTTP、gRPC 请求写入。
     - 预留：后续可扩展 Kafka 等消息通道，但本阶段只做接口预留/简单规划，不实现。
   - 写入内容示例（以股票日线未复权为例）：
     - 股票代码、交易日期、开高收低、成交量、成交额等基础字段。
   - 操作类型：
     - 插入新记录（Create）。
     - 更新已有记录（Update）。

2. **数据读取（Serve）**
   - 对其他服务提供读取接口：
     - 从 MySQL 查询数据（当前只考虑 MySQL）。
     - HTTP、gRPC 查询接口。
   - 支持典型 CRUD 中的：
     - 读取单条（按主键/业务主键）。
     - 条件查询、区间查询（如按股票代码+日期区间的日线数据）。
     - 更新 / 删除（如修订错误数据、清理测试数据等）。

3. **缓存（可选、内部细节）**
   - 设计上允许对某些读取结果做 Redis 缓存以提升读取性能。
   - **缓存不会作为单独的架构层**，而是由 Service 在读写流程中按业务策略选择是否访问 Redis：
     - 读取时：先查缓存，无则回源 MySQL 并写入缓存。
     - 写入/更新/删除时：适时失效或更新缓存。
   - 是否启用缓存、缓存粒度与策略，在后续业务设计阶段再确定；本设计只定义位置和方式，不做复杂策略。

### 2.2 非功能性需求
- **可靠性**：
  - 写入操作要求至少“最终一致”，保证关键数据（如日线数据）不会静默丢失。
- **可扩展性**：
  - 未来可以接入 Redis、S3、MongoDB、ClickHouse 等更多数据源，但当前阶段不实现统一的“存储抽象层”，使用 **Service + DAO** 直接访问 MySQL。
- **可维护性**：
  - 结构与 `cronjob` 保持类似分层和目录布局，方便团队统一维护与扩展。

### 2.3 显式不在本阶段范围内
- 不实现统一的 `StorageConnector` 等通用**存储抽象层**，只做面向场景的 Service + DAO。
- 不实现数据分析、报表、聚合统计等功能，这些由其他服务或下游分析系统完成。
- 不实现复杂的权限策略、多租户、风控等，只保留简单接口形式，后续可在网关或调用方加强控制。
- 暂不实现独立的 `internal/telemetry` 模块，先复用基础框架已有的监控/日志能力即可。

## 3. 高层架构（High-Level Architecture）

phoenixA 整体层次设计（重点对齐 `cronjob` 的实践）：

1. **入口层（Entry Point） - `cmd/main.go`**
   - 使用 `application.GetApp()` 获取应用实例并调用 `Run()`。
   - 通过匿名导入的方式初始化内部模块，例如未来的：
     - `internal/api`（注册 HTTP/gRPC 路由）。
     - `internal/config`（业务配置装载）。
     - `internal/registry_ext`（注册 service、dao 等组件）。
   - 参考 `cronjob` 中的做法，根据需要在 `hooks.BeforeStart` 中做一些服务前准备（例如读取本机 IP、打印启动信息等）。

2. **配置层（Config） - `internal/config` + `config/config.yaml`**
   - 在应用启动时，利用框架的 ConfigManager 读取 `config.yaml`。
   - 关键配置：
     - `app_info`：服务名称、环境等。
     - `logging`：日志等级、输出方式等。
     - `mysql_gorm`：MySQL 连接信息和连接池配置（目前主要数据源）。
     - `http_server` / `grpc_server`：服务端口、超时配置。
     - `biz_config`：业务相关的配置，如：
       - 哪些表/数据集启用缓存。
       - 某些数据集的默认查询限制（如最大返回行数）。

3. **组件与注册层（Registry & Components） - `internal/registry_ext`**
   - 通过 `registry_ext` 中的 `init()` 函数调用框架的 `registry.Register` 或 `registry.RegisterAuto` 来注册：
     - Service 组件（如：日线数据服务）。
     - DAO 组件（如：日线数据 DAO）。
     - 必要的 MySQL 连接、Redis 客户端等（如果需要的话）。
   - 参考 `cronjob/internal/registry_ext/controller.go`、`dao.go` 等文件的模式：
     - 把 Controller（API 层）、Service、DAO 的依赖关系通过注册函数串起来。

4. **API 层（HTTP / gRPC） - `internal/api`**
   - HTTP：
     - 通过框架提供的 HTTP 服务器组件注册路由。
     - 路由组织方式参考 `cronjob/internal/api/router_all.go`：
       - 将业务相关路由集中注册，如 `/v1/stocks/daily` 等。
   - gRPC：
     - 定义股票/金融数据的 protobuf 接口（后续具体细化）。
     - 实现对应的 gRPC Server，并在 registry 中注册。
   - 责任边界：
     - API 层只做请求解析、参数校验（基本的）、调用 Service，并构造响应。
     - 不在 API 层写业务逻辑，也不直接访问 DAO。

5. **服务层（Service） - `internal/service`**
   - 封装业务相关流程：
     - `Create/Update/Delete` 写入流程：接收 API 传入的数据模型，做简单校验（字段必填、类型校验），然后调用 DAO 完成实际读写。
     - 读流程：根据查询条件调用 DAO，从 MySQL 中查询数据，必要时读取和写入缓存。
   - **缓存逻辑在 Service 内部完成**：
     - 读取时：先查 Redis -> 若未命中则调用 DAO 查询 MySQL -> 写回 Redis（可配置）。
     - 写入/更新/删除时：调用 DAO 后，按需删除或更新缓存。
   - 与 cronjob 的对比：
     - cronjob 中的 `internal/service/engine.go`, `run_service.go` 等体现了业务流程如何组合 DAO、模型和配置；phoenixA 可以采用类似方式组织与拆分服务逻辑，只是业务内容不同（这里仅是 CRUD）。

6. **数据访问层（DAO + Model） - `internal/dao`, `internal/model`**
   - DAO 直接基于框架提供的 `mysql_gorm` 组件，针对具体数据表实现 CRUD：
     - 例如 `DailyPriceDAO`：提供 `CreateOrUpdateDailyPrice`, `GetDailyPrice`, `ListDailyPriceBySymbolAndRange`, `DeleteDailyPrice` 等方法。
   - Model（数据结构）：
     - 使用 `internal/model` 定义与数据库表对应的结构体，例如：`DailyPriceModel`（字段包括 symbol、trade_date、open、high、low、close、volume 等）。
   - 不设计独立的“通用存储抽象层”，DAO 就是面向具体表/业务实体的访问层。

> 注意：缓存（Redis）若被引入，将作为 DAO 访问 MySQL 之前/之后的一个可选环节，但整体仍由 Service 调用协调，而不是单独拆为架构层。

## 4. 数据流（Data Flow）

### 4.1 写入数据流程（以 HTTP 为例）
1. 调用方通过 HTTP POST 请求，将一批股票日线数据提交到 phoenixA，如：`POST /v1/stocks/daily`。
2. API 层解析请求：
   - 做基础参数校验（例如必须有 symbol、trade_date、价格字段等）。
   - 将请求转换为内部使用的 DTO/Model 结构，调用对应的 Service 方法。
3. Service 层：
   - 按业务规则决定是插入还是更新（例如根据 symbol + trade_date 作为业务主键做 `upsert`）。
   - 调用 DAO 执行数据库写入。
   - 若启用了缓存策略：在写入成功后更新或失效相关缓存键。
4. DAO 层：
   - 使用 GORM（通过框架提供的 mysql_gorm 组件）执行具体 SQL 操作。
   - 返回操作结果给 Service。

### 4.2 读取数据流程（以 gRPC 为例）
1. 调用方通过 gRPC 接口请求获取某个股票在某日期区间的日线数据。
2. API 层（gRPC Server）：
   - 解析请求，获取 symbol、date range 等查询条件。
   - 调用 Service 的查询方法。
3. Service 层：
   - 若对应数据集启用了缓存：
     - 构造缓存 key（例如 `daily_price:{symbol}:{start_date}:{end_date}`）。
     - 查询 Redis：命中则直接返回结果；未命中则调用 DAO 查询 MySQL，并将结果写回 Redis（可选 TTL）。
   - 若未启用缓存：
     - 直接调用 DAO 查询 MySQL。
4. DAO 层：
   - 根据输入条件构造 GORM 查询，执行 SQL。
   - 返回结果给 Service，由 Service 返回给 API，最终响应调用方。


## 5. 与 cronjob 的框架使用方式对齐

phoenixA 将按照与 cronjob 相同或相似的框架使用模式组织代码：

1. **启动入口**
   - `cmd/main.go` 中：
     - 调用 `application.GetApp()` 获取 App。
     - 视需要通过 `hooks.RegisterHook` 注册启动前/后逻辑（例如设置本机 IP 等）。
     - 调用 `app.Run()`，交给框架处理生命周期（包括组件注册、启动、优雅关闭）。

2. **配置加载**
   - 参考 `cronjob/internal/config/config.go`，在 phoenixA 中实现 `internal/config`：
     - 通过 `application.App.SetBizConfig` 或框架提供的方法，将业务配置结构体与 `config.yaml` 中的 `biz_config` 对应起来。
     - 在 `init()` 中完成配置模块的注册。

3. **组件注册（Registry 扩展）**
   - 参考 `cronjob/internal/registry_ext/controller.go`, `dao.go`：
     - 为 phoenixA 的 Controller（API）、Service、DAO、MySQL/Redis 等组件创建对应的注册函数，在 `init()` 中注册到框架的 registry。
     - 保持“按功能/领域拆分 registry 扩展”的结构，便于后续扩展多个数据域（不只是股票日线）。

4. **API 组织方式**
   - 参考 `cronjob/internal/api/router_all.go` 与各个 `*_controller.go`：
     - 为 phoenixA 设计类似的路由注册方式，将不同数据域（如日线、分钟线、其他金融产品）按模块组织路由与 Controller。

5. **Service + DAO 模式**
   - 参考 `cronjob/internal/service/*` 与 `internal/dao/*`：
     - Service 层：封装业务流程，但在 phoenixA 中保持简单 CRUD，不引入复杂调度逻辑。
     - DAO 层：面向具体表的读写操作，不抽象为通用存储接口。


## 6. 实施阶段规划（Roadmap）

### Phase 0：框架对齐 & 项目骨架
- 在 phoenixA 中补齐 `internal/config`, `internal/registry_ext`, `internal/api`, `internal/service`, `internal/dao`, `internal/model` 等目录及基本结构（只定义骨架和接口，不实现具体业务）。
- `cmd/main.go` 与 cronjob 保持一致的启动方式，确认服务可以启动并加载配置。

### Phase 1：股票日线数据 MySQL CRUD 能力
- 设计并创建（或对接现有）日线数据表结构。
- 实现对应的 Model 与 DAO，支持基本 CRUD 接口。
- 实现 HTTP & gRPC API：
  - 写入：批量/单条日线数据写入。
  - 读取：按 symbol + 日期 / 日期区间查询。
- Service 内初步集成可选 Redis 缓存（若本阶段就需要缓存，可实现简单 key 规则和 TTL）。

### Phase 2：扩展更多数据集 & 简单缓存策略
- 为更多金融数据类型（分钟线、衍生品、指数等）提供类似 CRUD 能力。
- 整理缓存策略与配置（按数据集开启/关闭缓存）。
- 完善 API 文档与错误码规范。

### Phase 3：接入更多写入通道（可选）
- 视需求实现 Kafka 等消息通道的消费者，接入统一 Service 流程。
- 按实际业务需要考虑与下游分析服务之间的数据同步方式（但仍不在 phoenixA 内做分析逻辑）。


## 7. 校验点（Validation Checklist）

- [ ] HTTP & gRPC 接口均能完成基本 CRUD（以日线数据为首个场景）。
- [ ] Service + DAO 模式清晰：API 不直接访问数据库，DAO 不包含业务逻辑。
- [ ] 可选 Redis 缓存逻辑仅存在于 Service 内，未引入独立的缓存架构层。
- [ ] 配置通过 `config.yaml` 与 `internal/config` 正确加载，MySQL 连接与 HTTP Server 正常启动。
- [ ] phoenixA 的目录结构与框架使用方式，与 cronjob 保持足够相似，便于团队迁移经验。
- [ ] 未引入统一存储抽象层、数据分析、telemetry 等超出当前需求范围的复杂设计。
