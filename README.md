# SmartChatBot — Secure Data Gateway Chatbot

基于 **openGauss (Docker)** 的安全数据网关聊天机器人。

## 架构

```
用户 → [PII脱敏] → [openGauss加密存储] → [审计日志]
```

## 三大安全亮点

| 安全层 | 技术 |
|--------|------|
| **数据存储安全** | openGauss TDE 透明列加密 |
| **输入安全** | Presidio PII 检测 + 脱敏 |
| **审计追踪** | openGauss 审计日志 + 前端面板 |

## 快速启动

```bash
# 1. 启动 openGauss
docker compose up -d

# 2. 安装后端依赖
cd backend && pip install -r requirements.txt

# 3. 启动后端
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 4. 打开前端
open frontend/index.html
```

## 项目结构

```
smart-chatbot/
├── docker-compose.yml    # openGauss 容器配置
├── db/
│   └── init.sql          # 建表 + TDE + 审计
├── backend/
│   ├── main.py           # FastAPI 入口
│   ├── auth.py           # JWT 认证
│   ├── config.py         # 配置
│   ├── database.py       # 数据库连接池
│   ├── pii_redactor.py   # PII 检测脱敏
│   └── audit.py          # 审计日志
├── frontend/
│   └── index.html        # 聊天 UI + 审计面板
└── docs/
    └── README.md
```

## 团队分工

| 成员 | 模块 |
|------|------|
| A | openGauss Docker 部署 + 数据库设计 + TDE/审计 |
| B | FastAPI 后端 + JWT 认证 + API 开发 |
| C | 前端聊天 UI + 审计面板 |
| D | Presidio 集成 + 安全测试 + 报告 |
