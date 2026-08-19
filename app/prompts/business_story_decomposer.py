from app.models.project import Project
from app.models.requirement import Requirement
from app.core.tech_stack import tech_stack_items_to_payload, tech_stack_items_to_text
from app.prompts.renderer import RenderedPrompt, render_prompt_template

TEMPLATE_NAME = "business_story_decomposer"
SYSTEM_PROMPT = TEMPLATE_NAME


def build_business_story_decomposition_payload(
    project: Project,
    requirement: Requirement,
    current_business_stories: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "project_name": project.name,
        "project_config": {
            "target_frontend_stack": getattr(project, "target_frontend_stack", None),
            "target_backend_stack": getattr(project, "target_backend_stack", None),
            "target_frontend_stack_items": tech_stack_items_to_payload(
                getattr(project, "target_frontend_stack_items", [])
            ),
            "target_backend_stack_items": tech_stack_items_to_payload(
                getattr(project, "target_backend_stack_items", [])
            ),
            "frontend_tech_stack": tech_stack_items_to_text(
                getattr(project, "target_frontend_stack_items", [])
            )
            or getattr(project, "target_frontend_stack", None),
            "backend_tech_stack": tech_stack_items_to_text(
                getattr(project, "target_backend_stack_items", [])
            )
            or getattr(project, "target_backend_stack", None),
            "global_constraints": getattr(project, "global_constraints", []),
            "coding_preferences": getattr(project, "coding_preferences", []),
            "prompt_preferences": getattr(project, "prompt_preferences", []),
        },
        "raw_requirement": requirement.raw_text,
        "current_business_stories": current_business_stories or [],
        "priority_definitions": {
            "p1_must": "P1 Must 必须完成：MVP 阶段没有它就无法成立",
            "p2_should": "P2 Should 应该完成：重要，但可以在 P1 之后完成",
            "p3_could": "P3 Could 可以完成：有价值，但不是近期核心",
            "p4_wont": "P4 Won't 本阶段不做：明确排除在当前阶段之外",
        },
        "decomposition_rules": [
            "每个故事必须是垂直切片，而不是技术分层任务",
            "不要输出“开发数据库”“实现接口”这类横向技术任务",
            "每个故事都必须包含用户故事、业务范围、数据规则、验收标准",
            "每个故事必须包含 implementation_scope 和 affected_layers",
            "affected_layers 只能从 ux_design、ui_design、frontend_pages、api_contract、"
            "backend_services、database_models、documentation 中选择",
            "改用户路径、交互流程、状态反馈、空状态、错误状态、权限体验时必须包含 ux_design",
            "改视觉层级、布局、颜色语义、组件样式、按钮层级、Badge、响应式规则时必须包含 ui_design",
            "改页面、组件、路由、目录、API client 落点时包含 frontend_pages",
            "改前端依赖、hooks、工具函数时归入 frontend_pages",
            "改接口时包含 api_contract；改后端 service、权限、事务、校验时包含 backend_services；"
            "改后端依赖、SDK、外部服务时归入 backend_services；"
            "改表、字段、索引、关系时包含 database_models",
            "例如“把首页标题字号调大一点”应输出 implementation_scope=frontend_only "
            "且 affected_layers 至少包含 ui_design、frontend_pages",
            "业务范围必须包含 included 和 excluded",
            "数据规则必须尽量具体到字段、限制、来源和校验",
            "验收标准必须可测试",
            "P4 故事也要说明为什么本阶段不做",
        ],
        "forbidden": [
            "不要返回 Markdown",
            "不要返回解释文本",
            "不要输出 JSON 之外的任何字符",
            "不要使用单引号、中文引号、尾随逗号或未转义换行",
            "不要把技术分层任务当作业务故事",
        ],
    }


def build_business_story_decomposition_prompt(
    project: Project,
    requirement: Requirement,
    current_business_stories: list[dict[str, object]] | None = None,
) -> RenderedPrompt:
    return render_prompt_template(
        TEMPLATE_NAME,
        build_business_story_decomposition_payload(
            project,
            requirement,
            current_business_stories,
        ),
    )
