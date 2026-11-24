# 双厂商自动切换（2026-11-24）

DeepSeek 和百炼在 .env 里各存一组，代码按顺序调用：主厂商（DeepSeek）
失败——报错、超时、欠费、被限流——自动切百炼顶上；两家都挂了才回落
本地规则（和以前一样）。回答里的 model 字段写的是实际应答的那家，
切换不会悄悄发生。这是第 2 周「多模型网关」的核心机制（故障转移），
提前在项目 0 上做出来。

## 安装（在 ~/dev/project-0 里操作）

1. 解压本包：`app/classifier_chain.py` 放进 app/，
   `tests/test_classifier_chain.py` 放进 tests/（都是新文件，不覆盖谁）
2. 按 `config_additions.txt` 给 app/config.py 加 6 行
3. 按 `main_patch.txt` 改 app/main.py 两处（加一行 import、换 classify 函数）
4. 按 `env_additions.txt` 给 .env 末尾加三行，key 填百炼按量付费那把
5. 跑测试：`python3.13 -m pytest -q`（新增 5 个切换测试，应全绿）

## 验收（两步）

1. 起服务，/docs 页测反讽句：model 显示 `deepseek-chat`（主厂商正常工作）
2. 验自动切换：把 .env 里 DeepSeek 的 key 故意改错最后一个字符，重启
   服务，再测同一句：model 变成 `qwen-plus` = 自动切换生效。验完把
   key 改回来

## 线上（可选，随后做）

Render 的 Environment 里加同样三行 PROJECT0_LLM2_*，线上也会自动切换；
不加不影响线上现有的 DeepSeek。
