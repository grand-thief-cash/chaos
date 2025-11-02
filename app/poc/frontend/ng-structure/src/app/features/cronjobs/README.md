# Cronjobs Feature Skeleton

当前仅建立基础目录骨架（方案 A 不含 detail 分组）：
```
features/cronjobs/
  pages/        # 放页面级组件 (列表、创建等)
  components/   # 局部复用组件 (表格、表单、状态标签等)
  state/        # 局部状态 (signals store / services)
  README.md     # 说明与约定
```

约定：
- 页面组件命名：`CronjobsListPage`, `CronjobCreatePage`。文件名：`cronjobs-list.page.ts`。
- 局部状态：`CronjobsStore` (文件 `cronjobs.store.ts`)；后续若加详情再新建 `CronjobDetailStore`。
- 不在 `components/` 放带路由的页面；只放可复用的展示或交互组件。
- 未来需要详情页及其子页面时，在 `pages/` 下新增目录：`cronjob-detail/`，不再嵌套第三层。
- 路由文件（后续）：`cronjobs.routes.ts` 放置在 `features/cronjobs` 根或 `pages/` 根下，二选一；建议根目录以便与 `README.md` 并列清晰。

后续添加文件建议顺序：
1. `cronjobs.routes.ts` - 定义基础路由。
2. `pages/cronjobs-list.page.ts` - 验证路由工作。
3. `components/cronjobs-table.component.ts` - 抽出展示层。
4. `state/cronjobs.store.ts` - 封装加载与筛选逻辑。

避免：
- 将数据访问逻辑直接写在页面组件里；放到 `data-access/` 下的对应服务。
- 提前创建未使用的深层目录。

扩展触发：
- 如果详情功能膨胀（多个日志、历史、指标视图） -> 迁移或新增独立 Feature `cronjob-detail`。

此目录当前无任何 TS/HTML/SCSS 文件，符合你的“只创建目录”要求。后续确认后再补。
