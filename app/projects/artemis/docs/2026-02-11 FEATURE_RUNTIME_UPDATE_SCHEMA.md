# Artemis Runtime Update Schema (Draft)

> 目标：支持运行期查看/更新 `task.yaml` 与 `task_units` 源码，减少发布频率。

## ✅ 本次需求拆解（整理后的清单）

### 1) `task.yaml` 运行期读写
- **读取原始内容**：提供 API 返回 `task.yaml` 原始文本内容。
- **更新并写回**：提供 API 支持更新 `task.yaml`，写回文件，同时刷新内存缓存。
- **缓存刷新**：更新后需清理/重载 `ConfigManager` 的 `_task_variants_cache`。

### 2) `task_units` 动态管理
- **目录/任务列表**：列出 `task_units/` 目录结构，识别可执行 task 文件（`.py`）。
- **读取任务源码**：返回指定 `.py` 文件内容。
- **更新任务源码**：更新并写回指定 `.py` 文件，确保后续任务运行使用新版本。
- **新建任务**：传入文件路径和源码，新建到 `task_units` 对应子目录。

---

## ✨ API 设计草案

> 所有接口建议挂载到 `http_gateway` 下，统一前缀 `/runtime`，避免与现有 `/tasks` 冲突。

### 1) Task YAML APIs

#### `GET /runtime/task-yaml`
- **作用**：返回 `task.yaml` 原始文本
- **Response**
```json
{
  "path": ".../config/task.yaml",
  "content": "raw-yaml-string"
}
```

#### `PUT /runtime/task-yaml`
- **作用**：更新 `task.yaml`
- **Request**
```json
{
  "content": "raw-yaml-string"
}
```
- **行为**
  - 校验 YAML 格式
  - 写回文件
  - 清除 `cfg_mgr._task_variants_cache`
  - 返回更新后的内容和更新时间

---

### 2) Task Units APIs

#### `GET /runtime/task-units/tree`
- **作用**：列出 `task_units/` 目录结构（树形）
- **Response**
```json
{
  "root": "artemis/task_units",
  "items": [
    {
      "name": "zh",
      "type": "dir",
      "children": [
        {"name": "stock_zh_a_list.py", "type": "file"}
      ]
    }
  ]
}
```

#### `GET /runtime/task-units/file`
- **作用**：读取指定任务源码
- **Query**
```
path=zh/stock_zh_a_list.py
```
- **Response**
```json
{
  "path": "zh/stock_zh_a_list.py",
  "content": "python-source"
}
```

#### `PUT /runtime/task-units/file`
- **作用**：更新指定任务源码
- **Request**
```json
{
  "path": "zh/stock_zh_a_list.py",
  "content": "python-source"
}
```
- **行为**
  - 校验路径必须在 `task_units/` 内（防路径穿越）
  - 写回文件
  - **触发 reload 策略**（详见下方）

#### `POST /runtime/task-units/file`
- **作用**：创建新的任务文件
- **Request**
```json
{
  "path": "zh/new_task.py",
  "content": "python-source"
}
```
- **行为**
  - 若目录不存在可选创建
  - 同样走安全路径校验

#### `POST /runtime/task-units/register`
- **作用**：动态注册任务（支持字符串 task_code）
- **Request**
```json
{
  "task_code": "stock_a_list_daily",
  "module": "artemis.task_units.zh.stock_zh_a_list",
  "class_name": "StockZHAListDailyTask"
}
```
- **Response**
```json
{
  "task_code": "stock_a_list_daily",
  "module": "artemis.task_units.zh.stock_zh_a_list",
  "class_name": "StockZHAListDailyTask"
}
```

---

## 🔁 任务热更新机制（已采用方案 A）

更新 `.py` 文件后，Python 运行时不会自动刷新已导入模块，因此采用以下策略：

- 每次执行任务时 **按路径动态 import + reload**
- `registry` 中存储的是 **TaskCode -> module path + class name**（而非 class 对象）
- `TaskEngine` 执行时从 registry 动态解析实现类

---

## ✅ 已确认的实现策略

1. 允许创建子目录（如 `zh/new_task.py`）
2. 暂不做版本备份
3. 更新 `.py` 后，下次执行即生效（通过动态 import + reload）
4. 接口默认内部访问（暂不加鉴权）

---

## 🛠 实施步骤（代码层面）

1. **新增 Pydantic 请求/响应模型**
2. **新增文件操作 service**（安全路径校验、读写、tree 构建）
3. **补充 http_gateway routes**
4. **更新 cfg_mgr：添加 task.yaml reload 方法**
5. **为 task_units hot reload 设计具体方案并落地**

---

## ✅ 交付物

- 新增 runtime update API 文档
- 新增接口 + 测试用例（建议）
- 更新 `RUNTIME_UPDATE_SCHEMA.md`
