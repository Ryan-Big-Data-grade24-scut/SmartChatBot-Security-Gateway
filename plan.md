# AI Security Assistant (AISA) — 项目修改计划

> 基于设计报告，将现有 SmartChatBot 改造为 AI 安全助手
> 日期：2026-06-16

---

## 一、当前状态 vs 目标状态

| 维度 | 当前（SmartChatBot） | 目标（AISA） |
|------|---------------------|-------------|
| 定位 | 安全数据网关聊天机器人 | AI 安全助手面板 |
| 前端 | 聊天 UI | 安全助手面板（输入区+检测结果+安全记录） |
| PII 检测 | 基础正则（邮箱/电话/信用卡/IP/URL/SSN） | 扩展正则 + 本地 NER（覆盖中国 PII） |
| 风险分级 | 无 | 三级干预（一级直接发/二级脱敏发/三级拦截提示） |
| 注入检测 | 无 | 提示注入检测 |
| 速率限制 | 无 | 基于用户/IP 的速率限制 |
| 审计日志 | 基础操作记录 | 全链路操作记录（含风险级别、处理策略） |

---

## 二、修改任务清单

### Phase 1: 后端核心改造（优先级 P0）

#### 1.1 PII 检测引擎扩展 (`backend/pii_redactor.py`)
- **新增中国 PII 正则**：身份证号、手机号、银行卡号、护照号、军官证号
- **集成本地 NER**：使用 `spaCy` + `zh_core_web_sm` 或 `pkuseg` 进行中文实体识别
- **风险定级函数**：根据检测到的 PII 类型返回风险级别（一级/二级/三级）
- **输出格式**：`(sanitized_content, pii_types, risk_level)`

#### 1.2 提示注入检测 (`backend/injection_detector.py` 新建)
- **检测规则**：
  - 关键词匹配（"ignore previous instructions", "system prompt", "DAN", "jailbreak" 等）
  - 角色扮演请求检测
  - 指令覆盖模式检测
- **输出**：`(is_injection, injection_type, confidence)`

#### 1.3 三级干预流水线 (`backend/main.py` 改造)
- **请求处理流程**：
  ```
  用户输入
    → [速率限制] 检查
    → [注入检测] 检查
    → [PII 检测] 识别 + 风险定级
    → [策略执行]
        一级（无风险）→ 直接发送
        二级（有 PII 但可控）→ 自动脱敏 → 发送 → 状态栏提示
        三级（高危）→ 拦截 → 返回提示用户决策
    → [审计日志] 记录
    → 发送给 AI / 返回用户
  ```
- **新增 API 路由**：
  - `POST /api/security-check` — 预检接口（前端先调用，获取风险级别和处理建议）
  - `POST /api/chat` — 改造为支持三级干预
  - `GET /api/security-logs` — 安全记录查询

#### 1.4 速率限制 (`backend/rate_limiter.py` 新建)
- **基于内存字典**（简单实现，适合课程项目）
- **限制策略**：
  - 每用户：60 请求/分钟
  - 每 IP：100 请求/分钟
- **集成到 main.py**：在请求入口检查

#### 1.5 审计日志增强 (`backend/audit.py` 扩展)
- **新增字段**：`risk_level`, `processing_strategy`, `pii_types_detected`
- **安全记录查询**：支持按风险级别、时间范围筛选

#### 1.6 配置更新 (`backend/config.py`)
- **新增配置项**：
  - `RATE_LIMIT_PER_USER`
  - `RATE_LIMIT_PER_IP`
  - `INJECTION_DETECTION_ENABLED`
  - `RISK_LEVEL_THRESHOLDS`

---

### Phase 2: 前端重构（优先级 P0）

#### 2.1 安全助手面板 (`frontend/index.html` 重构)
- **三栏布局**：
  - **左栏**：安全记录（历史脱敏/拦截记录）
  - **中栏**：输入区 + 检测结果展示
  - **右栏**：AI 回复区
- **输入区**：
  - 文本输入框
  - 文件上传（支持 Excel/CSV）
  - "发送" 按钮
- **检测结果区**（动态显示）：
  - 风险级别标识（绿/黄/红）
  - 检测到的 PII 类型列表
  - 处理策略说明
  - 三级拦截时的用户决策按钮（发送脱敏版/取消）
- **安全记录区**：
  - 时间线形式展示历史操作
  - 显示每次操作的风险级别、处理结果

#### 2.2 前端交互流程
```
用户粘贴内容
  → 前端调用 /api/security-check（预检）
  → 显示检测结果
    一级：绿色标识，直接发送
    二级：黄色标识，显示脱敏预览，用户确认后发送
    三级：红色标识，显示拦截原因，用户选择操作
  → 发送后显示 AI 回复
```

---

### Phase 3: 数据库更新（优先级 P0）

#### 3.1 `db/init.sql` 扩展
- **messages 表**：新增 `risk_level`, `processing_strategy` 字段
- **audit_log 表**：新增 `risk_level`, `pii_types_detected`, `processing_strategy` 字段
- **新增 security_logs 表**：专门记录安全事件

---

### Phase 4: 依赖与部署（优先级 P1）

#### 4.1 `backend/requirements.txt`
- 新增：`zh-core-web-sm`（spaCy 中文模型）、`pkuseg`（可选）

#### 4.2 `docker-compose.yml`
- 确保 PostgreSQL 配置兼容

#### 4.3 `start.sh`
- 更新启动逻辑（如有需要）

---

## 三、文件修改矩阵

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/pii_redactor.py` | 扩展 | 新增中国 PII、风险定级 |
| `backend/injection_detector.py` | 新建 | 提示注入检测 |
| `backend/rate_limiter.py` | 新建 | 速率限制 |
| `backend/main.py` | 改造 | 三级干预流水线、新路由 |
| `backend/audit.py` | 扩展 | 新增安全字段 |
| `backend/config.py` | 扩展 | 新增配置项 |
| `frontend/index.html` | 重构 | 安全助手面板 |
| `db/init.sql` | 扩展 | 新增字段和表 |
| `backend/requirements.txt` | 扩展 | 新增依赖 |
| `README.md` | 更新 | 项目说明 |

---

## 四、演示场景验证清单

| 场景 | 预期行为 | 验证方式 |
|------|---------|---------|
| 正常文本 | 一级，直接发送，绿色标识 | 粘贴普通文本 |
| 含手机号 | 二级，自动脱敏，黄色标识 | 粘贴 "我的电话是13800138000" |
| 含身份证+银行卡 | 三级，拦截，红色标识 | 粘贴身份证号+银行卡号 |
| 注入攻击 | 拦截，提示恶意输入 | 粘贴 "ignore previous instructions" |
| 安全记录 | 历史操作正确显示 | 查看左栏安全记录 |

---

## 五、时间估算

| 阶段 | 任务 | 预估时间 |
|------|------|---------|
| Phase 1 | PII 扩展 + 注入检测 + 速率限制 | 4-5h |
| Phase 1 | 三级干预流水线 + 审计增强 | 3-4h |
| Phase 2 | 前端重构 | 4-5h |
| Phase 3 | 数据库更新 | 0.5h |
| Phase 4 | 依赖更新 + 测试调试 | 2-3h |
| **总计** | | **14-18h** |

---

## 六、风险与应对

| 风险 | 应对 |
|------|------|
| spaCy 中文模型下载慢/失败 | 使用轻量级正则方案兜底 |
| 前端重构工作量大 | 先实现核心功能，UI 简化 |
| 三级干预逻辑复杂 | 先实现二级，再扩展三级 |

---

*计划制定完成，等待确认后开始执行。*
