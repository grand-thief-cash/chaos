```markdown

├── core/ # 核心功能：容器、生命周期、组件协议
│ ├── container.py # 全局组件注册与解析容器
│ ├── component.py # 所有组件应遵循的统一接口
│ ├── lifecycle.py # 生命周期管理器（监听信号，注册回调）
│ └── context.py # 上下文管理（启动/关闭环境隔离）
│
├── components/ # 各种内置组件：可选加载
│ ├── logging/ # 日志初始化与组件实现
│ ├── mysql/ # MySQL 连接池组件
│ ├── redis/ # Redis 客户端封装
│ ├── httpserver/ # Flask/FastAPI Server 注册
│ ├── grpcserver/ # gRPC 服务器实现封装
│ ├── mq/ # 消息队列（Kafka/NATS）
│ ├── discovery/ # 服务注册发现（Consul/Nacos）
│ └── configcenter/ # 配置中心（支持动态热加载）
│
├── hooks/ # 生命周期钩子机制（按阶段加载组件）
│ ├── before_start.py
│ ├── after_start.py
│ ├── before_shutdown.py
│ └── after_shutdown.py
│
├── config/ # 配置加载与管理
│ ├── loader.py # 支持 yaml/json/env 等配置读取
│ ├── schema.py # pydantic 数据模型验证
│ └── merger.py # 支持多来源合并与优先级覆盖
│
├── utils/ # 工具库
│ ├── signal_handler.py # 信号处理（封装）
│ └── tracer.py # 分布式追踪初始化（如OpenTelemetry）
│
├── init.py # 业务项目使用的统一初始化入口
└── init.py


```

# 开发模式安装（推荐开发时使用）
cd app/infra/pyinfra
pip install -e .

# 或者直接安装
pip install app/infra/

# 如果发布到 PyPI
pip install pyinfra