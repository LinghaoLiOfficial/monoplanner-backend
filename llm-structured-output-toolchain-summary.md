# LLM 结构化输出工具链总结

当前后端的 LLM 结构化输出工具链以 `app/llm/structured_client.py` 的 Instructor typed `response_model` 为主契约、`app/llm/json_client.py` 的严格 JSON 解析与 `json-repair` 为兜底，并由各业务 service 在返回前完成最终归一化与错误映射。
