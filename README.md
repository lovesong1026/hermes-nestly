# HermesNestly

> 基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 构建的多租户 Web Agent 应用平台。

HermesNestly 将通用 Agent Runtime 封装为可供多用户使用的在线服务，提供流式对话、受控 Tool Calling、用户私有文件/知识库/Memory/Skill 管理及管理后台。平台通过用户级上下文隔离、工具白名单和工作区沙箱，为 Agent 在共享 Web 服务中建立安全边界。

> 本项目基于 Hermes Agent 二次开发，并持续同步上游运行时能力。Hermes 提供 Agent Loop、模型调用、通用工具和 Skill/Memory 基础设施；HermesNestly 负责 Web 服务接入、多租户隔离、平台控制面与受控工具层。

## 核心能力

- **流式 Agent 对话**：基于 Hermes AIAgent 封装 Web Agent Runner，通过 SSE 实时输出生成文本、推理状态、工具调用进度与执行结果。
- **受控 Tool Calling**：按 Web 场景装配文件操作、知识检索、记忆和 Skill 管理工具；工具通过动态 Registry 暴露 Schema，并使用白名单控制可调用能力。
- **用户私有上下文**：会话、文件工作区、知识库、Memory 和 Skill 均以用户身份为边界，避免多租户共享服务中的状态串扰。
- **知识与记忆管理**：用户上传资料后可由 Agent 按需调用知识检索工具；记忆采用“提议 → 用户审核 → 长期记忆投影”流程，避免黑盒式写入长期上下文。
- **平台控制面**：提供注册/登录、工作区、文件与知识库管理、模型偏好、用量查看、管理员用户管理与审计能力。
- **可靠性与安全边界**：用户工作区路径沙箱限制文件访问范围；运行时对单轮重复失败和无进展工具调用进行中断保护，避免 Agent 陷入工具循环。

## 架构

~~~text
                         ┌──────────────────────────┐
                         │        React Web SPA     │
                         │ Chat · Files · Memory    │
                         │ Skills · Admin           │
                         └────────────┬─────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
        /api/v1/*   ▼                       /api/chat    ▼
┌──────────────────────────┐              ┌──────────────────────────┐
│ Platform API :8700       │              │ Agent Gateway :8643      │
│ Auth · Workspace · RAG   │              │ SSE · Sessions · Runner  │
│ Memory · Skills · Admin  │              │ User Context · Toolsets  │
└────────────┬─────────────┘              └────────────┬─────────────┘
             │                                         │
             └───────────┬─────────────────────────────┘
                         ▼
              ┌───────────────────────┐
              │ Hermes Agent Runtime  │
              │ AIAgent · Tools ·     │
              │ Skills · Memory       │
              └───────────┬───────────┘
                          ▼
              OpenAI-Compatible Model Gateway
~~~

## 与上游 Hermes 的边界

| 层级 | 主要职责 |
| --- | --- |
| Hermes Agent（上游） | Agent Loop、模型 Provider、通用工具、Skill/Memory 框架、终端与消息平台能力 |
| HermesNestly | web_chat Gateway、Web Agent Runner、SSE 协议、平台 API、React SPA、多租户上下文隔离、沙箱化 Web 工具 |
| OpenAI-Compatible 网关 | 模型路由、模型 API Key 管理与用量/计费能力；可对接自建网关、new-api、LiteLLM 或其他兼容服务 |

本项目的 Web 工具集不向普通 Web 用户开放任意终端或代码执行能力；文件、知识、Memory 和 Skill 操作在用户身份与工作区边界内执行。

## 多租户与安全设计

~~~text
用户身份
  ├─ 会话与消息：查询写入均携带 user_id
  ├─ 文件与 Skill：$HERMES_HOME/web_workspaces/<user_id>/
  ├─ 知识库：按 tenant_id / workspace_id / user_id 过滤检索结果
  ├─ Memory：在用户上下文中读取、提议与投影
  └─ 上游模型 Key：加密存储，请求期间通过 ContextVar 注入
~~~

- **路径隔离**：沙箱工具拒绝访问用户工作区之外的路径。
- **工具最小权限**：Web Agent 仅装配面向 Web 场景的受控工具，不继承全部本地 Agent 工具。
- **调用保护**：对单轮工具调用中的重复失败、重复无进展等行为进行检测与中断；该机制是单轮保护，并非跨会话的全局工具健康熔断。
- **密钥处理**：平台可将上游 Key 以 Fernet 加密形式存储；生产环境必须设置独立主密钥并通过 TLS 传输。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- 一个 OpenAI-Compatible 模型服务

### 1. 安装依赖

~~~bash
git clone git@github.com:lovesong1026/hermes-nestly.git
cd hermes-nestly

python3.11 -m venv venv
source venv/bin/activate
pip install -e ".[web-chat,platform]"

cd web-chat
npm install
npm run build
cd ..
~~~

### 2. 配置模型网关与平台数据库

在 ~/.hermes/.env 中配置模型服务；以下以 OpenAI-Compatible 网关为例：

~~~bash
NEW_API_BASE_URL=https://your-openai-compatible-gateway.example.com
HERMES_WEB_KEY_VAULT_SECRET=<使用 Fernet.generate_key() 生成的主密钥>
~~~

本地开发可使用 SQLite，无须先启动 PostgreSQL：

~~~bash
export PLATFORM_DATABASE_URL="sqlite:///$HOME/.hermes/platform.db"
export UPSTREAM_PROVISIONER=manual
~~~

生产部署请使用 PostgreSQL、TLS 和独立密钥管理。完整环境变量示例见 [deploy/.env.example](deploy/.env.example)。

### 3. 启动服务

最简方式（Platform API 与 Agent Gateway）：

~~~bash
./startplatform.sh --host 127.0.0.1
~~~

也可在两个终端分别启动：

~~~bash
# 终端 1：Platform API
source venv/bin/activate
export PLATFORM_DATABASE_URL="sqlite:///$HOME/.hermes/platform.db"
hermes-platform-api

# 终端 2：Agent Gateway
source venv/bin/activate
export PLATFORM_DATABASE_URL="sqlite:///$HOME/.hermes/platform.db"
./startweb.sh --host 127.0.0.1
~~~

| 服务 | 地址 | 职责 |
| --- | --- | --- |
| Platform API | http://127.0.0.1:8700 | 认证、工作区、知识库、Memory、Skill、Admin |
| Agent Gateway | http://127.0.0.1:8643 | Web Chat、SSE、会话与 Agent 执行 |

访问 http://127.0.0.1:8643 使用生产构建页面；前端开发可运行 cd web-chat && npm run dev，默认地址为 http://127.0.0.1:5173。

### 4. 健康检查

~~~bash
curl http://127.0.0.1:8700/api/v1/healthz
curl http://127.0.0.1:8643/api/healthz
~~~

## 测试

~~~bash
# Platform API
python -m pytest tests/platform -q

# Web Gateway 与用户隔离
python -m pytest tests/gateway/test_web_*.py tests/hermes_state/test_user_id_filtering.py -q

# React SPA：类型检查、单测与生产构建
cd web-chat && npm run verify
~~~

当前版本已完成 337 项 Web/隔离测试、165 项平台测试、273 项前端测试及生产构建验证。

## 项目结构

~~~text
gateway/web/          Web Agent 适配层、Runner、SSE、沙箱工具与用户上下文
platform_api/         FastAPI 控制面：认证、工作区、文件、RAG、Memory、Skill、Admin
web-chat/             React 前端：Chat、用户工作区和管理页面
agent/                Hermes 上游 Agent Runtime
tools/                上游通用工具与 Toolset 基础设施
tests/                Web、平台、会话隔离与回归测试
deploy/               Docker Compose、Nginx、环境变量示例与压测脚本
docs/                 部署、运维、平台设计与人工验收文档
~~~

## 部署与文档

- [部署说明](deploy/README.md)
- [平台架构与测试](docs/user-guide/platform-saas.md)
- [Web Chat 运维说明](docs/user-guide/web-chat.md)
- [人工验收清单](docs/user-guide/platform-manual-testing.zh-CN.md)
- [安全检查清单](docs/user-guide/SECURITY_REVIEW.md)

## 上游同步

~~~bash
git remote add upstream https://github.com/NousResearch/hermes-agent.git
git fetch upstream
git merge upstream/main
~~~

同步前建议先运行测试；发生冲突时优先保留 gateway/web/、platform_api/、web-chat/ 及租户隔离相关改动，再按上游接口变化完成适配。

## License

本项目采用 [MIT License](LICENSE)，并遵循 Hermes Agent 上游项目的许可证要求。
