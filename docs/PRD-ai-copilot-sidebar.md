# PRD：AI Copilot 侧边栏

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 日期 | 2026-07-09 |
| 作者 | 产品组 |
| 状态 | 评审中 |
| 关联模块 | `frontend/`、`sql_api/`、`common/utils/openai.py`、`sql/models.py` |

---

## 1. 背景

### 1.1 现状

Archery 已具备四项独立 AI 能力：自然语言生成 SQL、SQL 智能分析、SQL 智能优化、SQL 风险审核（`common/utils/openai.py`）。但它们是**一次性函数调用**——用户在某个页面点一个按钮、拿到一段文本、结束。AI 与用户的交互是割裂的单点，无法在一轮对话里完成「理解意图 → 改写 → 预览 → 修复 → 提单」的闭环。

### 1.2 机会

将 AI 升级为**全局可呼出、感知当前页面上下文、能执行动作的多轮 Copilot**，是把平台从「DBA 工具集合」推向「数据库智能协作平台」的关键一步，也是 Vue3 SPA 重构期最适合引入的差异化能力。

### 1.3 目标

| 类型 | 目标 |
|---|---|
| 北极星 | 月活用户中 Copilot 周活跃率 ≥ 30% |
| 体验 | p95 首 token 延迟 ≤ 2s，流式中断率 ≤ 3% |
| 闭环价值 | 「AI 建议 → 一键修复采纳」率 ≥ 40%；「预览执行 → 提交工单」转化率 ≥ 25% |
| 成本 | 人均日 token 成本 ≤ 配额上限，超限降级不阻断主流程 |

### 1.4 非目标（YAGNI，本期不做）

- 不做 Copilot 自动直接执行任何**写操作**（DML/DDL），写操作一律生成工单草稿走既有审核流。
- 不做语音输入、不做跨会话的全局记忆（如「记住我偏好别名风格」）。
- 不做多模型路由/自选模型（复用现有 `default_chat_model` 单一配置）。
- 不做对话式数据可视化的完整 BI 形态（仅做 SQL 预览执行结果）。

---

## 2. 用户画像与故事

### 2.1 画像

- **研发**：会写 SQL 但不熟线上库结构，希望快速得到可用 SQL 并安全上线。
- **DBA / 审核人**：希望 AI 在提单前就把高风险问题修掉，减少来回驳回。
- **数据分析师 / PM**：不熟练 SQL，希望用自然语言查数。

### 2.2 核心用户故事

> **US-1（查询）**：作为研发，我在在线查询页写了一段 SQL，选中后对 Copilot 说"帮我加上按部门汇总"，AI 返回改写后的 SQL，我一键插入编辑器并预览执行，看到结果正确后保存到收藏。

> **US-2（上线）**：作为研发，我在 SQL 上线提交页，Copilot 指出"这条 UPDATE 缺 WHERE 会全表更新，风险高"，并给出修复版，我点「一键修复」替换，AI 风险分从 high 降到 low，我再提交工单。

> **US-3（慢查）**：作为 DBA，我在慢查页选中一条慢 SQL，对 Copilot 说"优化它"，AI 结合表结构给出索引建议 DDL，我点「生成工单草稿」直接进入提交流程。

> **US-4（全局）**：作为任意用户，我在任何页面右下角点开 Copilot，问"我现在在的这个库有哪些大表"，AI 调用 DDL 工具回答，我不必切换页面。

---

## 3. 功能需求

### 3.1 全局能力（所有页面可用）

- **悬浮入口**：右下角圆形按钮，点击展开为右侧抽屉（Drawer），宽度约 420px，可拖拽调宽、可全屏。
- **会话管理**：抽屉顶部可新建/切换/重命名/删除会话；会话按场景标签区分；历史持久化、跨设备可见。
- **流式输出**：AI 回复以打字机效果逐字呈现；支持「停止生成」。
- **上下文感知**：自动注入当前编辑器/选中的 SQL；当前库相关表的 DDL 按需抓取。
- **快捷输入**：预设快捷指令（"解释这段 SQL""优化它""加索引建议""转成只读预览"）。
- **反馈**：每条 AI 回复支持 👍/👎 与复制。

### 3.2 在线查询场景（`sqlquery`）

| 能力 | 说明 |
|---|---|
| `insert_sql_to_editor` | AI 生成的 SQL 一键插入当前编辑器光标处 |
| `preview_run_sql` | 对只读 SQL 直接执行预览，强制 LIMIT、复用查询权限与脱敏；结果在抽屉内展示 |
| `save_to_favorites` | 把当前 SQL 存入收藏 |
| `explain_sql` | 调既有 explain，AI 解读执行计划 |

### 3.3 SQL 上线场景（`sqlworkflow`）

| 能力 | 说明 |
|---|---|
| `replace_editor_sql` | 「一键修复」：用 AI 改写版替换编辑器全部内容 |
| `prefill_workflow` | 生成工单草稿（含 AI 风险分、回滚提示），用户确认后进入提交流程 |
| `apply_index_suggestion` | 把 AI 建议的索引 DDL 填入工单 SQL 区 |

> 安全红线：以上动作**均不直接执行**；提交仍走既有审核工作流与 goInception 检测。

### 3.4 慢查场景（`slowquery`）

| 能力 | 说明 |
|---|---|
| `optimize_current` | 结合表结构给优化建议与改写 SQL |
| `write_review_note` | 把优化结论写入慢查评审记录 |

---

## 4. 关键流程

### 4.1 多轮工具调用主流程

```
用户发送消息
   │
   ▼
前端 copilot store 组装 payload
   { messages, tools(按场景), context_snapshot }
   │
   ▼
POST /api/v1/copilot/chat/  (SSE) ──▶ 后端流式转发 OpenAI(stream=True)
   │                                          │
   │   逐 token 流式回传给前端展示 ◀───────────┤
   │                                          │
   │   若 AI 返回 tool_call ──────────────────┘
   ▼
前端执行工具(本地 insert/replace 或调既有接口 preview/ddl)
   │
   ▼
把 tool_result 作为新 message 追加 ──▶ 再次 POST /copilot/chat/ (SSE)
   │
   ▼
AI 基于工具结果继续，直到给出最终文本回复
   │
   ▼
落库 ChatMessage(user / assistant / tool) ；更新会话标题(首轮摘要)
```

### 4.2 一键修复闭环（上线场景）

```
Copilot 标记问题 ──▶ 用户点「一键修复」
        │
        ▼
 replace_editor_sql 替换编辑器 ──▶ 触发既有 SQL 检测 ──▶ AI 风险分重算
        │
        ▼
 用户确认 ──▶ prefill_workflow ──▶ 进入既有工单提交流程
```

---

## 5. 页面与交互设计

### 5.1 抽屉布局（ASCII）

```
┌──────────────────────────────────────────────┐
│ ☰ 历史会话   当前：订单库 · 查询场景      ⤢ — ✕ │
├──────────────────────────────────────────────┤
│ [快捷] 解释SQL · 优化 · 加索引 · 转只读预览      │
├──────────────────────────────────────────────┤
│  me: 选中这段帮加按部门汇总                     │  ← 上下文 chips：
│       └ 📋 已带入选中 SQL(12行)                 │     选中SQL / 订单表DDL
│  AI:  已改写，新增 GROUP BY department...       │
│       [⎘ 插入编辑器]  [▶ 预览执行]             │  ← 工具结果按钮
│  me: ▶ 预览执行                                 │
│  AI: 返回 23 行，首屏如下… (结果表)             │
├──────────────────────────────────────────────┤
│ ┌──────────────────────────────────┐ [发送]    │
│ │ 问点什么…                         │          │
│ └──────────────────────────────────┘          │
└──────────────────────────────────────────────┘
```

### 5.2 交互规则

- **上下文 chips**：每次请求顶部展示已注入的上下文（选中 SQL、相关 DDL），可一键移除。
- **工具结果卡片**：AI 的 `tool_call` 在前端渲染为可操作卡片（插入/预览/工单草稿），而非裸 JSON。
- **停止与重试**：流式中可停止；失败可重试上一次请求。
- **空状态**：首次打开展示场景化示例提问（点击即填入）。
- **权限态**：无查询权限时，`preview_run_sql` 卡片置灰并提示「无该库查询权限」；`sql.use_copilot` 关闭时整个抽屉隐藏入口。

---

## 6. 接口契约

### 6.1 流式对话（核心）

`POST /api/v1/copilot/chat/` —— `Content-Type: application/json`，响应 `text/event-stream`（SSE）。

请求体：

```jsonc
{
  "session_id": 42,
  "scene": "sqlquery",                 // sqlquery | sqlworkflow | slowquery | general
  "messages": [
    { "role": "user", "content": "选中这段加按部门汇总" }
  ],
  "tools": ["insert_sql_to_editor", "preview_run_sql", "get_table_ddl"],
  "context": {
    "instance_id": 7,
    "db_name": "orders",
    "editor_sql": "SELECT ... ",
    "selected_sql": "SELECT amount FROM orders WHERE ...",
    "selected_tables": ["orders"]
  }
}
```

SSE 事件流（每个事件 `event: <type>` + `data: <json>`）：

```
event: meta        data: {"message_id": 9001, "model": "gpt-4o-mini"}
event: delta       data: {"content": "已改写，"}      // 文本增量(可多次)
event: tool_call   data: {"id":"call_1","name":"insert_sql_to_editor","args":{"sql":"SELECT ..."}}
event: done        data: {"finish_reason":"stop","tokens":{"prompt":820,"completion":120}}
event: error       data: {"message":"上游超时","code":"upstream_timeout"}  // 异常时
```

> 工具循环在**前端**编排：收到 `tool_call` → 本地执行或调既有接口 → 把结果作为 `role:"tool"` 消息追加 → 再次发起一次 `/chat/` 请求。

### 6.2 会话与历史（REST）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/copilot/sessions/?scene=&page=` | 会话列表（当前用户） |
| POST | `/api/v1/copilot/sessions/` | 新建会话 `{scene, instance_id, db_name}` → `{id, title}` |
| GET | `/api/v1/copilot/sessions/<id>/messages/` | 该会话历史消息（分页） |
| PATCH | `/api/v1/copilot/sessions/<id>/` | 重命名 `{title}` |
| DELETE | `/api/v1/copilot/sessions/<id>/` | 删除会话 |
| POST | `/api/v1/copilot/feedback/` | 消息反馈 `{message_id, helpful: bool, reason?}` |

### 6.3 OpenAI 客户端扩展（`common/utils/openai.py`）

新增方法：

```python
def stream_chat_completion(self, messages, tools=None, tool_choice="auto"):
    """流式 chat，返回逐 chunk 生成器；透传 tool_calls 增量。"""
    stream = self.client.chat.completions.create(
        model=self.default_chat_model,
        messages=messages, tools=tools, tool_choice=tool_choice,
        stream=True,
    )
    for chunk in stream:
        yield chunk
```

后端 `chat/` 视图用 `StreamingHttpResponse(content_type="text/event-stream")` 把 chunk 转成 SSE。

---

## 7. 数据模型

新增到 `sql/models.py`（或独立 `copilot` app，建议后者以便后续解耦）：

```python
class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    scene = models.CharField(max_length=32)        # sqlquery/sqlworkflow/slowquery/general
    instance = models.ForeignKey(Instance, null=True, on_delete=models.SET_NULL)
    db_name = models.CharField(max_length=128, blank=True, default="")
    title = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        index_together = [("user", "updated_at")]


class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=16)         # user/assistant/tool
    content = models.TextField(blank=True, default="")
    tool_calls = models.JSONField(default=list, blank=True)   # assistant 发起的工具调用
    tool_name = models.CharField(max_length=64, blank=True, default="")
    tool_result = models.JSONField(default=dict, blank=True)  # 工具执行结果摘要
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class CopilotUsage(models.Model):  # 配额与成本统计
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    day = models.DateField()
    prompt_tokens = models.BigIntegerField(default=0)
    completion_tokens = models.BigIntegerField(default=0)
    request_count = models.IntegerField(default=0)
    class Meta:
        unique_together = [("user", "day")]
```

> DDL 全文不入库；`tool_result` 仅存摘要（行数、是否成功、错误码），避免库表膨胀。

---

## 8. 技术方案

### 8.1 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│ Vue3 SPA  (BasicLayout.vue 全局挂载 <CopilotDrawer/>)        │
│   ├ stores/copilot.ts   会话/上下文/工具编排                   │
│   ├ composables/useCopilotContext.ts  场景上下文采集          │
│   └ composables/useSSEStream.ts  fetch+ReadableStream 解析   │
└───────────────────────────────┬─────────────────────────────┘
                          SSE / REST
┌───────────────────────────────▼─────────────────────────────┐
│ sql_api/api_copilot.py                                       │
│   chat/ (StreamingHttpResponse+SSE)  sessions/ messages/     │
└───────────────────┬───────────────────────┬─────────────────┘
                    │                       │
        ┌───────────▼────────┐    ┌─────────▼──────────┐
        │ common/utils/      │    │ sql/ 既有能力       │
        │ openai.py(stream)  │    │ query/engines/ddl   │
        └────────────────────┘    └────────────────────┘
```

### 8.2 为什么工具循环放前端

- `insert_sql_to_editor` / `replace_editor_sql` 是纯前端 DOM/编辑器动作，后端无法代劳。
- `preview_run_sql` / `get_table_ddl` 前端调既有接口即可，结果由前端回填。
- 后端 `chat/` 保持**无状态流式转发**，便于水平扩展与限流；写操作永不在此路径执行。

### 8.3 流式实现要点

- **后端**：`StreamingHttpResponse`，`X-Accel-Buffering: no`，每条 SSE 事件即时 flush。
- **前端**：`fetch(POST)` + `response.body.getReader()` 逐块解析 `event:/data:`；不用 `EventSource`（其仅支持 GET，无法带请求体与会话 cookie body）。
- **停止生成**：前端 `AbortController`；后端检测 client 断开即停止从 OpenAI 拉取。
- **`tool_calls` 增量拼接**：OpenAI stream 的 `delta.tool_calls` 需按 `index` 累积拼接 args 字符串后再 JSON.parse。

### 8.4 上下文与 token 治理

- 系统提示按 `scene` 切换，控制基础 token。
- 上下文默认只带「选中 SQL + 表名清单」；DDL **按需**由 AI 调用 `get_table_ddl` 抓取，而非每轮全量灌入。
- 历史消息超过阈值时做**滑动窗口**裁剪（保留首轮 + 最近 N 轮 + 当前上下文摘要）。
- 单请求 token 上限可配置，超限前端提示「上下文过长，建议新建会话」。

---

## 9. 权限与安全

| 维度 | 策略 |
|---|---|
| 功能开关 | 新增配置 `enable_copilot`（默认开）；关闭则隐藏入口 |
| 使用权限 | 新增 Django permission `sql.use_copilot`；管理员可回收 |
| 查询权限 | `preview_run_sql` 复用既有 `query_priv`，无权限则工具不可用；结果走既有脱敏 |
| 写操作红线 | 任何 DML/DDL 均不直接执行，只生成工单草稿，提交走既有审核流 + goInception |
| 成本闸门 | 每用户/每日 token 配额（`CopilotUsage` 统计），超限降级为提示而非报错 |
| 审计 | 所有 `tool_call`（含 SQL 文本）写入既有审计日志 |
| 数据安全 | AI 请求体不得携带脱敏前的敏感字段；DDL 可传（结构非数据） |

---

## 10. 埋点指标

| 事件名 | 触发时机 | 关键属性 |
|---|---|---|
| `copilot.drawer_open` | 打开抽屉 | scene、has_context |
| `copilot.message_send` | 发送一条消息 | scene、session_id、msg_len、has_selected_sql |
| `copilot.tool_call` | 执行一个工具 | tool_name、success、latency_ms |
| `copilot.message_done` | AI 回复完成 | tokens、first_token_ms、finish_reason |
| `copilot.feedback` | 👍/👎 | message_id、helpful |
| `copilot.action_adopt` | 用户采纳动作 | tool_name（如 replace_editor_sql） |
| `copilot.workflow_submit_after_copilot` | Copilot 后提交工单 | risk_level、scene |
| `copilot.quota_limited` | 触达配额 | user_id、day |

**核心看板**：Copilot DAU/周活跃率、三场景占比、工具调用 Top 与成功率、一键修复采纳率、预览→提单转化率、人均 token 成本、p95 首 token 延迟、流式中断率、AI 报错率。

---

## 11. 分期计划

| 阶段 | 范围 | 验收要点 |
|---|---|---|
| **P1 MVP** | 全局抽屉 + 流式通用对话 + 会话持久化 + 查询场景（insert/preview/explain/favorites） | 可多轮对话；选中 SQL 可改写插入并预览；刷新后历史可见 |
| **P2** | 上线场景（一键修复 + 工单草稿 + 索引建议填入）+ 慢查场景 | 一键修复后风险分重算；工单草稿可进入既有提交流程 |
| **P3** | 反馈看板、配额治理 UI、更多工具、上下文裁剪优化 | 看板可见核心指标；超限降级生效 |

---

## 12. 风险与对策

| 风险 | 对策 |
|---|---|
| AI 输出不稳定的 SQL 被误用 | 写操作不直接执行；只读预览强制 LIMIT + 权限/脱敏；卡片明确「需人工确认」 |
| token 成本失控 | 按需取 DDL、历史滑动窗口、每日配额、可全局关闭 |
| 流式在 nginx/代理被缓冲 | `X-Accel-Buffering: no` + 校验网关配置 |
| 上游 OpenAI 超时/抖动 | 超时降级返回 `error` 事件 + 重试；不阻塞主流程 |
| function calling 增量拼接易错 | 封装统一的 `tool_calls` 累积器并加单测 |
| 安全：敏感数据外泄 | 禁止把查询结果/脱敏前数据进 prompt；仅传结构与 SQL 文本 |

---

## 13. 验收标准

- [ ] 任意页面可呼出 Copilot 抽屉；无 `sql.use_copilot` 权限者看不到入口。
- [ ] 多轮流式对话正常；首 token p95 ≤ 2s；支持停止/重试。
- [ ] 查询场景：选中 SQL 可由 AI 改写 → 一键插入 → 预览执行（受权限/脱敏约束）。
- [ ] 上线场景：一键修复替换编辑器并触发风险分重算；工单草稿可进入既有提交流程，且**不绕过** goInception 检测。
- [ ] 慢查场景：选中慢 SQL 可生成优化建议与工单草稿。
- [ ] 会话历史落库，跨设备可见，可删除/重命名。
- [ ] 触达每日 token 配额时降级提示而非崩溃。
- [ ] 所有 `tool_call` 入审计日志；写操作零次直接执行。

---

## 14. 附录：场景系统提示（示例）

```
[sqlworkflow 场景]
你是 Archery 的 SQL 上线助手。当前用户正在 SQL 上线提交页。
上下文：库={db_name}，选中 SQL 如下。
你可通过工具：replace_editor_sql(一键修复)、prefill_workflow(工单草稿)、
apply_index_suggestion(索引 DDL 填入)、get_table_ddl、explain_sql。
规则：任何写操作都不得直接执行，只能生成工单草稿；优先指出高风险项并给出可采纳的修复版。
```
