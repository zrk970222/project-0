# 项目 0 — 情感分类 API

FDE 第 1 周项目：一个能直接跑的 FastAPI 情感分类服务。真实厂商做分类，双厂商故障自动切换，流式输出已接通并通过真厂商验证。

- 线上地址：https://project-0-x3xr.onrender.com（Render 免费档，冷启动 30–50 秒）
- 仓库：https://github.com/zrk970222/project-0

## 现在能做什么

- `GET /health` — 公开健康检查，返回 `{"status": "ok"}`
- `POST /v1/classify` — 情感分类，需 `X-API-Key` 请求头。返回 `label`（positive / negative / neutral）、`confidence`、`model`（实际应答的模型）
- `GET /v1/stream` — SSE 流式端点，已通过真厂商验证（2026-11-25 本地 curl 实测：delta 逐行流出，末行 `done: true, model: deepseek-chat`）

**双厂商故障自动切换（2026-11-24 真机验证过）：**调用顺序是 DeepSeek（deepseek-chat）→ 百炼（qwen-plus）→ 本地规则。主厂商报错、超时、欠费或被限流时自动切下一家，两家都挂才回落本地规则；回答里的 `model` 字段写实际应答的那家，切换不会悄悄发生。

验收探针句：「这家餐厅真是太好了，等位三小时，菜还是凉的」——本地规则会误判 positive，真模型应判 negative。实测：DeepSeek 判 negative 0.98，百炼判 negative 0.95；把 DeepSeek 地址改坏模拟宕机后，同一句由 qwen-plus 应答，negative 0.95。

**厂商差异实测（同一提示词）：**置信度标定不同（0.98 vs 0.95），回答风格也不同——百炼版明显更话痨，会自己加建议、反问和 emoji，DeepSeek 版克制得多。这就是为什么要做多模型网关 + 评测集，而不是凭感觉选厂商。

## 架构

五角色分工：**门卫**（API Key 鉴权）→ **前台**（FastAPI 端点）→ **大脑**（厂商调用链）→ **账本**（结构化 JSON 日志）→ **配置**（.env）。

- `app/main.py` — 端点与鉴权
- `app/schemas.py` — Pydantic 模型（请求文本 1–5000 字；响应含 label / confidence / model）
- `app/config.py` — 配置只读环境变量，密钥不进代码
- `app/classifier_llm.py` — OpenAI 兼容的厂商客户端（temperature=0，只回 JSON）
- `app/classifier_chain.py` — 按配置顺序试厂商，失败自动切下一家，空 key 跳过，全失败抛错由 main 回落本地
- `app/streaming.py` — 流式输出（SSE），已验证

## 跑起来

Mac 上用官方 Python 3.13（系统自带的 python3 是 3.7.8，装不了新版 fastapi）：

```
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # 按下面填好 key 再跑
.venv/bin/uvicorn app.main:app --port 8000
```

验证：

```
.venv/bin/python -m pytest -q          # 17 个测试全绿
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/v1/classify \
  -H "X-API-Key: dev-only-change-me" -H "Content-Type: application/json" \
  -d '{"text": "这个产品很好，我很满意"}'
```

## 环境变量（只列名字，不含值）

| 变量 | 说明 |
| --- | --- |
| `PROJECT0_API_KEY` | 自家接口的门禁 key（本地默认值 `dev-only-change-me`，线上是另一把） |
| `PROJECT0_LLM_API_KEY` / `PROJECT0_LLM_BASE_URL` / `PROJECT0_LLM_MODEL` | 主厂商：DeepSeek，`deepseek-chat`，`https://api.deepseek.com/v1` |
| `PROJECT0_LLM2_API_KEY` / `PROJECT0_LLM2_BASE_URL` / `PROJECT0_LLM2_MODEL` | 第二家：百炼按量付费，`qwen-plus`，工作空间专属 base URL |

## 测试

`pytest -q`，17 个全绿：`tests/test_api.py`（健康检查、鉴权 401、分类与 422 校验）、`tests/test_classifier_llm.py`、`tests/test_classifier_chain.py`（5 个切换测试）、`tests/test_streaming.py`（流式分片、厂商报错兜底、SSE 格式）。

## Docker 与 CI

- `Dockerfile`：基础镜像经 DaoCloud 镜像拉取——Docker Hub 经住宅代理出口会在 TLS 握手被掐；启动端口读 `${PORT:-8000}`
- GitHub Actions：测试 + lint 双绿（根目录空 `conftest.py` 是为了解决 CI 里 `No module named 'app'`）
- Render 免费档已上线；线上 LLM2 三项环境变量未配（可选，不影响现有 DeepSeek）

## 踩坑

- **两把 key 别混**：`PROJECT0_API_KEY` 是自家接口的门禁，`PROJECT0_LLM_API_KEY` 是厂商的钥匙、只存服务端，绝不出现在 curl 里。
- **百炼两把 key 别混**：套餐 key（`sk-sp-` 开头）配 token-plan 地址，留给 Qwen Code / Orca；项目 0 用按量付费 key。混用会报 401。
- **建按量付费 key 不用先充值**：控制台提示"余额不足"是免费额度用完后才停服，测试量在免费额度内。
- **curl 粘贴前切英文输入法**：中文输入法的弯引号会把命令打坏（卡 `quote>` 续行、请求体丢失）；占位符要整段替换，不要留中文字。
- **换厂商只改 .env 三行**：客户端是 OpenAI 兼容的，地址、key、模型名三行一换就行，接口和代码都不动。

## 正在做

- `/v1/stream` 流式端点真厂商验证（2026-11-25 已通过，model=deepseek-chat）
- 第 2 周主项目：项目 1 多模型网关（把项目 0 里这套双厂商切换做成独立服务）
