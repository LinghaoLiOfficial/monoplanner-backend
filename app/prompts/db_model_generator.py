from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = (
    "你是一个资深数据库架构师和 Python 后端工程师。你的任务是基于项目蓝图和 API 契约草案"
    "生成数据库模型草案。数据库模型必须能支撑业务实体、用户故事、API 请求响应和后续 "
    "SQLAlchemy / Alembic 开发。"
)


def build_db_model_generation_payload(
    project: Any,
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "项目名称": project.name,
        "项目蓝图 JSON": blueprint_content,
        "API 契约 JSON，如果存在": api_contract_content,
        "目标后端技术栈": project.target_backend_stack,
        "数据库模型 JSON schema": {
            "database": {
                "engine": "PostgreSQL",
                "orm": "SQLAlchemy 2.x",
                "migration_tool": "Alembic",
            },
            "entities": [
                {
                    "name": "Task",
                    "table_name": "tasks",
                    "description": "A task created by a user",
                    "fields": [
                        {
                            "name": "id",
                            "type": "uuid",
                            "primary_key": True,
                            "nullable": False,
                            "description": "Primary key",
                        }
                    ],
                    "relationships": [
                        {"field": "user_id", "target": "User", "type": "many_to_one"}
                    ],
                }
            ],
            "relationships": [
                {
                    "from": "Task",
                    "to": "User",
                    "type": "many_to_one",
                    "description": "A task belongs to a user.",
                }
            ],
            "indexes": [
                {
                    "table": "tasks",
                    "fields": ["user_id", "created_at"],
                    "reason": "Speed up task list query by user and creation time.",
                }
            ],
            "migration_notes": ["Use UUID primary keys."],
        },
        "字段类型规则": [
            "默认使用 uuid 主键",
            "文本短字段用 string，长文本用 text",
            "时间字段用 datetime",
            "结构化扩展字段用 json",
        ],
        "关系建模规则": [
            "关系必须服务于业务实体或 API 契约",
            "外键字段使用 snake_case_id",
            "多对多关系需要说明中间表建议",
        ],
        "禁止事项": [
            "必须返回严格 JSON",
            "不要返回 Markdown",
            "不要生成 SQL",
            "不要生成 SQLAlchemy 代码",
            "只生成数据库模型草案 JSON",
            "字段必须服务于业务需求或 API 契约",
            "关系必须清晰",
            "索引必须有 reason",
            "默认使用 PostgreSQL + SQLAlchemy 2.x + Alembic",
        ],
    }
