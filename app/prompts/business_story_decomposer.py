from app.models.project import Project
from app.models.requirement import Requirement

SYSTEM_PROMPT = (
    "你是一个资深产品经理、敏捷需求分析师和全栈架构师。你的任务是将用户输入的自然语言业务需求拆解为"
    "可独立开发、测试、验收的业务需求故事。每个故事必须是垂直切片，能够贯穿前端、后端、数据和验收标准。"
)


def build_business_story_decomposition_payload(
    project: Project, requirement: Requirement
) -> dict[str, object]:
    return {
        "project_name": project.name,
        "project_description": project.description,
        "raw_requirement": requirement.raw_text,
        "target_output_schema": {
            "stories": [
                {
                    "title": "创建任务",
                    "priority": "p1_must",
                    "user_story": "作为已登录用户，我希望创建一项任务，以便记录需要完成的事项。",
                    "business_scope": {
                        "included": ["输入标题"],
                        "excluded": ["子任务"],
                    },
                    "data_rules": [
                        {"field": "title", "rule": "必填，1～100 个字符"},
                    ],
                    "acceptance_criteria": ["已登录用户可以创建合法任务。"],
                    "vertical_slice_note": "这是任务管理 MVP 的核心闭环。",
                }
            ]
        },
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
            "业务范围必须包含 included 和 excluded",
            "数据规则必须尽量具体到字段、限制、来源和校验",
            "验收标准必须可测试",
            "P4 故事也要说明为什么本阶段不做",
        ],
        "forbidden": [
            "不要返回 Markdown",
            "不要返回解释文本",
            "不要输出 JSON 之外的任何字符",
            "不要把技术分层任务当作业务故事",
        ],
    }
