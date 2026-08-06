# LLM 任务输入模板与输出结构检查开发规则

本文档定义后端 LLM 任务输入模板、运行时渲染、输出 schema 和结构校验的开发规则。适用于 `app/prompts/templates/*/prompt.j2`、同级 `output_schema.py`、Python prompt builder、LLM client 调用链和相关测试。

## 1. 模板来源规则

- `.j2` 文件是运行时真实 prompt 来源，不只是说明文档。
- 每个 LLM 任务必须拥有独立模板目录，例如 `app/prompts/templates/business_story_decomposer/`。
- 每个模板目录至少包含：
  - `prompt.j2`
  - `output_schema.py`
- 新增模板必须登记到 `app/prompts/template_registry.py`。
- 静态文本必须放在 `prompt.j2` 内，包括角色、任务目标、输入解释、输出解释、生成规则、禁止事项和典型示例。
- Python 侧不要再维护大段静态 prompt 文本，避免 `.j2` 与 Python prompt 规则分裂。

## 2. `.j2` 固定结构规则

- 每个 `prompt.j2` 必须且只能包含一个 `===SYSTEM===` 和一个 `===USER===`。
- `===SYSTEM===` 必须出现在 `===USER===` 之前。
- `===SYSTEM===` 用于描述：
  - 模型角色
  - 任务定位
  - 全局输出纪律
  - JSON-only 约束
- `===USER===` 固定包含以下小节：
  - `Input`
  - `Input Descriptions`
  - `Output Descriptions`
  - `Example Input [n]`
  - `Example Output [n]`
- `Input` 只列出运行时传入变量，变量名应保持英文。
- `Input Descriptions` 解释每个输入变量的业务含义、来源、可空性和使用方式。
- `Output Descriptions` 解释输出字段、业务规则、格式要求和禁止事项。

## 3. Example 规则

- `Example Input [n]` 和 `Example Output [n]` 必须成对出现。
- 编号必须一致，例如 `Example Input [1]` 对应 `Example Output [1]`。
- 示例数量按任务复杂度决定：
  - 复杂分支任务可提供多组示例。
  - 普通结构生成任务至少提供一组示例。
- 示例必须是典型取值，不应只写占位 JSON。
- 示例输出必须匹配同级 `output_schema.py` 的 Pydantic 输出结构。
- 示例不得引导模型生成业务代码，除非该 LLM 任务本身明确要求生成代码。

## 4. Python Builder 规则

- Python prompt builder 只负责构造动态变量上下文。
- 动态变量包括但不限于：
  - `project_config`
  - `selected_story`
  - `change_set`
  - `current_assets`
  - `previous_version`
  - `related_assets`
  - `old_versions`
  - `new_versions`
  - `project_blueprint`
  - `target_output_schema` / `output_contract`
- 输出 schema 必须通过对应 Pydantic model 的 `model_json_schema()` 注入。
- builder 不应重复维护静态规则、示例、禁止事项或字段解释。
- 运行时应通过 `build_*_prompt()` 渲染 `.j2`，再把拆分后的 system/user 内容发送给 LLM。

## 5. Renderer 规则

- 运行时统一通过 `app/prompts/renderer.py` 渲染模板。
- Renderer 使用 Jinja2 `StrictUndefined`。
- 缺少变量必须直接失败。
- 渲染后必须校验：
  - `===SYSTEM===` 唯一存在。
  - `===USER===` 唯一存在。
  - `===SYSTEM===` 在 `===USER===` 之前。
  - system 内容非空。
  - user 内容非空。
- `tojson_pretty` 是模板中输出 JSON 上下文的标准过滤器。

## 6. LLM Client 输入规则

- LLM client 必须支持两种 user 输入：
  - dict user payload：兼容旧路径，会序列化为 pretty JSON。
  - string user prompt：新模板路径，必须原样作为 user message content。
- 新模板链路应优先使用 string user prompt。
- 不得对已渲染的 string user prompt 再做 `json.dumps()` 二次包装。
- Chat Completions message 固定包含：
  - `role=system`：渲染后的 SYSTEM 内容。
  - `role=user`：渲染后的 USER 内容。

## 7. 输出 Schema 规则

- 同级 `output_schema.py` 是 LLM 输出结构的第一真相。
- 不要再引入手写 `output_structure.json` 作为第二来源。
- `output_schema.py` 应定义该任务的 Pydantic response model。
- Python builder 注入的 schema 必须来自该 model 的 `model_json_schema()`。
- 修改输出结构时，应同时修改：
  - `output_schema.py`
  - `prompt.j2` 的 `Output Descriptions`
  - `Example Output`
  - 对应 service validator
  - 对应测试

## 8. 输出检查规则

- LLM 输出必须先解析为 JSON object。
- 非 object 顶层输出应视为格式错误。
- Markdown fenced JSON 可由 JSON parser 清洗后解析，但 prompt 仍必须要求模型只输出 JSON。
- 输出结构采用双层检查：
  - Pydantic schema 约束输出形状。
  - service validator 负责业务归一化、兜底和错误映射。
- service validator 应处理：
  - 必填字段缺失。
  - 空数组或空字符串。
  - 旧字段兼容。
  - 默认值补齐。
  - 枚举值规范化。
  - 业务错误消息。

## 9. 测试规则

- 模板契约测试必须覆盖所有注册模板。
- 测试至少验证：
  - `prompt.j2` 存在。
  - `output_schema.py` 存在。
  - `===SYSTEM===` / `===USER===` 唯一且顺序正确。
  - USER 区包含固定小节。
  - `Example Input [n]` / `Example Output [n]` 编号成对。
  - 模板可用最小变量上下文成功渲染。
  - 渲染结果 system/user 非空。
  - builder 注入 schema 与对应 Pydantic model 对齐。
  - renderer 对缺 marker、重复 marker、缺变量等错误路径会失败。
- LLM client 测试必须覆盖：
  - string user prompt 原样进入 user message。
  - dict user payload 保持兼容并 pretty JSON 序列化。
- 编排链路测试应验证渲染后的 prompt 文本包含关键动态上下文，例如当前 layer、related assets、新旧版本差异和 prompt pack 所需资产。

## 10. 新增 LLM 任务 Checklist

新增一个 LLM 任务时，按以下顺序开发：

1. 创建 `app/prompts/templates/<template_name>/prompt.j2`。
2. 创建 `app/prompts/templates/<template_name>/output_schema.py`。
3. 在 `app/prompts/template_registry.py` 注册模板、schema 和 response model。
4. 新增或更新 Python builder，只传动态变量和 `model_json_schema()`。
5. 新增 `build_*_prompt()`，通过 renderer 渲染模板。
6. 将运行时 LLM 调用切换为渲染后的 `prompt.system` 和 `prompt.user`。
7. 增加 service validator 或扩展既有 validator。
8. 更新模板契约测试和业务链路测试。
9. 运行：

```bash
uv run python -m pytest tests/test_prompt_template_contracts.py
uv run python -m ruff check app tests
```

