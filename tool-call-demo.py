"""第 2 周 Day 1：工具调用 + 结构化输出，最小可跑示例。

用法（在 Mac 上）：
    1. 把这个文件拷进项目 0：
       cp tool-call-demo.py ~/dev/project-0/
    2. 在项目 0 的 venv 里装 openai SDK（只装一次）：
       cd ~/dev/project-0 && .venv/bin/pip install openai
    3. 跑（key/地址/模型直接读项目 0 的 .env，不用再填）：
       .venv/bin/python tool-call-demo.py
       加 --vendor2 改走百炼：.venv/bin/python tool-call-demo.py --vendor2
"""

import argparse
import json
import os
import sys

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError


def load_settings(vendor2: bool):
    """优先读项目 0 的 app/config.py；不在项目 0 里时读环境变量。"""
    try:
        from app.config import settings

        if vendor2:
            return settings.llm2_api_key, settings.llm2_base_url, settings.llm2_model
        return settings.llm_api_key, settings.llm_base_url, settings.llm_model
    except Exception:
        prefix = "PROJECT0_LLM2" if vendor2 else "PROJECT0_LLM"
        return (
            os.environ.get(f"{prefix}_API_KEY", ""),
            os.environ.get(f"{prefix}_BASE_URL", ""),
            os.environ.get(f"{prefix}_MODEL", ""),
        )


# ---------- 工具：一个假的查天气函数（真项目里换成调 API / 查库） ----------
def get_weather(city: str) -> dict:
    fake = {
        "上海": {"weather": "多云", "temp_c": 18},
        "北京": {"weather": "晴", "temp_c": 8},
    }
    return fake.get(city, {"weather": "未知", "temp_c": None})


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 上海"},
                },
                "required": ["city"],
            },
        },
    }
]
AVAILABLE = {"get_weather": get_weather}


def run_tool_loop(client, model):
    messages = [
        {
            "role": "system",
            "content": "你是一个助手，回答问题时如果需要查天气就调用 get_weather 工具。",
        },
        {"role": "user", "content": "上海今天天气怎么样，适合出门吗？"},
    ]
    resp = client.chat.completions.create(
        model=model, messages=messages, tools=TOOLS, tool_choice="auto", temperature=0
    )
    msg = resp.choices[0].message
    print("模型第一轮返回：", "tool_calls" if msg.tool_calls else "直接回答")
    if not msg.tool_calls:
        print(msg.content)
        return
    messages.append(msg)
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        result = AVAILABLE[tc.function.name](**args)
        print(f"执行工具 {tc.function.name}({args}) -> {result}")
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )
    resp2 = client.chat.completions.create(model=model, messages=messages, temperature=0)
    print("最终回答：", resp2.choices[0].message.content)


class ClassifyResult(BaseModel):
    label: str = Field(pattern="^(positive|negative|neutral)$")
    confidence: float = Field(ge=0, le=1)
    reason: str


def classify_structured(client, model, text: str):
    system = (
        "你是情感分类器。请以 JSON 格式返回："
        '{"label": "positive|negative|neutral", "confidence": 0到1的数字, '
        '"reason": "一句话理由"}。只返回 JSON，不要解释。'
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": text}]
    for attempt in (1, 2):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = resp.choices[0].message.content
        try:
            out = ClassifyResult.model_validate_json(raw)
            print(f"第 {attempt} 次成功：", out.model_dump())
            return out
        except ValidationError as e:
            print(f"第 {attempt} 次校验失败：{e.errors()[0]['msg']}，把报错喂回去重试")
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": f"上面那段 JSON 没通过校验：{e}。请只返回修正后的 JSON。",
                }
            )
    print("两次都失败，放弃，走本地规则兜底")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor2", action="store_true", help="改走第二家厂商（百炼）")
    args = ap.parse_args()
    api_key, base_url, model = load_settings(args.vendor2)
    if not api_key or not base_url or not model:
        print("没读到厂商配置：请在 ~/dev/project-0 里跑，或先配好 .env")
        sys.exit(1)
    client = OpenAI(api_key=api_key, base_url=base_url)
    print(f"厂商：{model}（{base_url}）")
    print("== 工具调用 ==")
    run_tool_loop(client, model)
    print("== 结构化输出 ==")
    classify_structured(client, model, "这家餐厅真是太好了，等位三小时，菜还是凉的")


if __name__ == "__main__":
    main()
