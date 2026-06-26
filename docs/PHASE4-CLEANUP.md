# Phase 4 清理计划（延后执行）

> 状态：**延后**。前置条件未满足前不要执行删除/下线，否则会搞崩正在跑的应用。

## 背景

前端 Vue3 SPA 重构已完成（23/25 菜单页 + 全部后置功能迁入；配置项管理 / OpenAPI 保留 legacy）。
`nginx.conf` + `Dockerfile` 已改为生产服务 SPA（capstone）。本文件记录**迁移完成后可做的清理**，
但需先满足前置条件。

## 前置条件（全部满足才能开始删除）

1. **e2e 回归通过**：SPA 在生产（docker）完整跑通登录/查询/上线/导出/归档/权限/慢查/Dashboard 全流程。
   当前所有迁入页的端到端均"待用户跑"，从未验证。
2. **无外部依赖**：确认没有外部脚本/定时任务/其他系统在调用即将下线的旧 JSON 接口
   （`/group/*` `/instance/*` `/query/*` 等——这些接口 SPA 自己仍在用，是"补充"非"取代"）。
3. **数据库已备份**，可回滚。

## 为什么现在不能删

- **旧 JSON 接口仍在用**：SPA 调用约 18 个旧前缀（`/group/` `/instance/` `/query/` `/audit/`
  `/slowquery/` `/sql_analyze/` `/data_dictionary/` `/archive/` `/binlog/` `/sqlexport/`
  `/downloadfile/` `/rollback/` `/inception/` `/sqlworkflow/backup_sql/` `/sqlworkflow_list_audit/`
  `/db_diagnostic/` `/param/` `/check/`）。它们被 DRF **补充**而非**取代**，删了 SPA 就废。
- **legacy 页仍需模板**：配置项管理（`/config/`）、OpenAPI（`/api/swagger/`）、用户管理（`/admin/`）
  故意保留旧版，依赖 `sql/templates/*.html` 与 `base.html`。
- 删除是难回退的破坏性操作。

## 可清理项（满足前置条件后）

### A. 旧渲染视图 + 模板（已被 SPA 取代的页）

已被 SPA 完全取代、且无 legacy 跳转依赖的页，可删 `sql/views.py` 渲染视图 + `sql/templates/<x>.html`：

- Dashboard：`dashboard.html`（SPA 已 echarts 重写）
- SQL 上线：`sqlworkflow.html` / `detail.html`（含回滚/OSC 入口已迁）
- 在线查询：`sqlquery.html`
- 实例管理组：`instance.html` / `dbdiagnostic.html` / `database.html` / `instanceaccount.html` /
  `param.html` / `paramcompare.html`
- SQL 优化/分析：`sqlanalyze.html` / `sqladvisor.html` / `slowquery.html` / `schemasync.html`
- 数据字典：`data_dictionary.html`
- 系统审计：`audit.html` / `audit_sqlworkflow.html`（及 query 审计）
- 资源组：`group.html` / `groupmgmt.html`
- 相关文档：`dbaprinciples.html`
- 数据导出：`sqlexportworkflow.html` / `sqlexportsubmit.html`
- 权限管理：`queryapplylist.html` / `queryapplydetail.html` / `queryuserprivileges.html`
- 归档：`archive.html` / `archivedetail.html`
- My2SQL：`my2sql.html`
- 2FA：`2fa.html`（SPA 已迁 2FA 登录）
- 提交：`submitsql.html` / `submitotherinstance.html`

> **保留**：`config.html`（配置项）、`login.html`（SSO/传统登录入口）、`error.html`、`base.html`、
> 各 SSO 回调页、`workflow_display.html`（若仍被某处 include）。

### B. 可下线的旧 JSON 接口

**仅当下线**：已有 DRF 等价接口、且 SPA 不再调用的。需逐个核对 `frontend/src/api/*.ts` 不再引用。
当前绝大多数旧接口仍被 SPA 调用（见上），**不要下线**。真正可下线的候选：
- `/dashboard/api/`（pyecharts HTML，已被 `/api/v1/dashboard/charts/` 取代，SPA 不再用）
- `/slowquery/report/`（pyecharts HTML，已被 `/api/v1/slowquery/trend/` 取代）

### C. nginx / vite proxy 宽前缀收紧

`vite.config.ts` 与 `nginx.conf` 里 `/archive/` `/sqlexport/` `/binlog/` 等宽前缀会拦截
SPA 深链刷新（如刷新 `/archive/5`）。建议在 e2e 验证后改为完整路径（参考已用的
`/sqlworkflow/backup_sql/` `/rollback/` `/inception/osc_control/` 写法）。

## 验证方式

每删一组：
1. `python manage.py check` + `pytest -q sql sql_api common`
2. docker 重建镜像，e2e 跑全流程
3. 确认 SPA 各页正常、无 404/500
