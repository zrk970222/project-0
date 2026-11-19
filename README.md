# 项目 0 — FDE 第 1 周启动骨架

对应《FDE-8周学习计划.md》第 1 周、周一任务：FastAPI + Pydantic + 鉴权 + 结构化日志。
这是一个**可直接跑的起点**，不是做完的项目——周二加 Dockerfile + CI，周三/周四把分类换成真实厂商 API，周四加流式端点。

## 跑起来

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 改掉里面的 key 再部署
uvicorn app.main:app --reload
```

验证（已在本机跑通过，3 个测试全过）：

```bash
pytest -q
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/v1/classify \
  -H "X-API-Key: dev-only-change-me" -H "Content-Type: application/json" \
  -d '{"text": "这个产品很好，我很满意"}'
```

## 里面有什么

- `GET /health` — 公开健康检查；`POST /v1/classify` — 需 `X-API-Key` 请求头
- `app/schemas.py` — Pydantic 模型（请求校验：文本 1–5000 字；响应含 label / confidence / model）
- `app/config.py` — 配置只读环境变量（`PROJECT0_API_KEY` 等），密钥不进代码
- `app/main.py` — JSON 结构化日志（每行一个 JSON，带 method/path/status/耗时/request-id）；分类目前是本地关键词启发式（`model: local-heuristic-v0`），**接口不变**，周三/周四换厂商 API 时只改 `_heuristic_label` 背后的实现
- `tests/test_api.py` — 健康检查、鉴权 401、分类与 422 校验

## 本周接着做什么（按计划，不提前做）

- 周二：加 Dockerfile + GitHub Actions CI（测试 + lint），部署拿 URL
- 周三：第一家厂商 API 写同一个分类功能；周四：第二家 + 对比 + 流式端点（代码里留了 TODO）
- 周五：写 README（背景/架构/怎么跑/踩坑）+ 自查验收
