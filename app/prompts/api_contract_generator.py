from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = (
    "你是一个资深 API 架构师和全栈后端工程师。你的任务是基于项目蓝图生成前后端可联调的 "
    "API 契约草案。API 契约必须服务于页面、用户故事和业务实体，不要生成无来源的接口。"
)


def build_api_contract_generation_payload(
    project: Any,
    blueprint_content: dict[str, Any],
) -> dict[str, Any]:
    return {
        "项目名称": project.name,
        "项目蓝图 JSON": blueprint_content,
        "目标 base_path": "/api/v1",
        "API 契约 JSON schema": {
            "base_path": "/api/v1",
            "resources": [
                {
                    "name": "tasks",
                    "description": "Manage tasks",
                    "endpoints": [
                        {
                            "method": "POST",
                            "path": "/tasks",
                            "operation_id": "create_task",
                            "purpose": "Create a task",
                            "request_body": "CreateTaskRequest",
                            "response_body": "TaskResponse",
                            "auth_required": True,
                            "errors": ["400", "401", "409", "500"],
                        }
                    ],
                }
            ],
            "schemas": [
                {
                    "name": "CreateTaskRequest",
                    "fields": [
                        {
                            "name": "title",
                            "type": "string",
                            "required": True,
                            "description": "Task title",
                        }
                    ],
                }
            ],
            "error_model": {
                "name": "ApiError",
                "fields": [
                    {"name": "code", "type": "string", "required": True},
                    {"name": "message", "type": "string", "required": True},
                    {"name": "details", "type": "object", "required": False},
                ],
            },
            "notes": ["string"],
        },
        "接口生成规则": [
            "必须返回严格 JSON",
            "不要返回 Markdown",
            "每个 endpoint 必须能追溯到页面或业务故事",
            "不要生成与业务无关的接口",
            "request_body 和 response_body 必须引用 schemas",
            "错误状态码要合理",
            "不要直接生成 OpenAPI 文档，本阶段生成可读 API 契约草案",
        ],
        "错误模型规则": [
            "缺省错误模型命名为 ApiError",
            "至少包含 code 和 message 字段",
            "可选包含 details 字段",
        ],
        "禁止事项": [
            "不要输出 JSON 之外的任何字符",
            "不要生成数据库字段",
            "不要生成 FastAPI 代码",
        ],
    }
