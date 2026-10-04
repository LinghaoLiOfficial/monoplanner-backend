# Monoplanner 同步一致性评测数据规范

规范标识：`monoplanner-sync-data`  
文档版本：`2.0.0`（交换格式版本为 `2.0.0`）  
语言：中文  
状态：交换格式定义与实施编制稿（非已冻结数据包）  
适用范围：需求演进数据、提示包生成输入、独立测试真值标签及数据冻结记录。

## 1. 规范范围

本规范定义需求变更与前后端提示包同步一致性评测所需的数据结构。基本评测单位为一个需求变更对应的一份版本化提示包。数据应足以确定变更前状态、变更后状态、持续有效的约束、前后端职责及可评价的原子契约事实。

本规范不将代码质量、构建成功率或开发效率定义为结果指标。源码来源仅用于建立初始事实；后续设计的需求变更不得标记为未经证实的仓库历史事件。

“必须”表示强制约束；“应”表示推荐约束；“可”表示可选能力。表格中未标注可选的字段均必须存在。对象不得包含未定义字段；明确声明为开放对象的字段除外。

本文件定义面向外部系统的中性交换格式，不声明当前评测 CLI 已原生支持全部字段。接入现有实现需经过适配与校验；本文件不变更运行器、数据库或现有数据文件。

## 2. 文件组织与访问边界

```text
data/
  inputs/benchmark.json
  answers/benchmark.json
  sources/manifest.json
  sources/<repository-relative-path>
  sources/LICENSE
  locks/<dataset-version>.json
```

| 文件 | 用途 | 生成阶段可访问 |
| --- | --- | --- |
| `inputs/benchmark.json` | 需求链、项目配置、资产状态与变更集 | 是 |
| `answers/benchmark.json` | 各步骤的必要端及原子契约测试真值标签（Ground Truth） | 否 |
| `sources/manifest.json` | 固定源码及离线副本索引 | 是 |
| `sources/` 下源码与许可证 | 事实溯源和离线回放 | 是 |
| `locks/<dataset-version>.json` | 输入、答案、源码及评测配置摘要 | 仅摘要；不得通过该记录读取答案 |

测试真值标签必须独立存储在 `answers/benchmark.json`，供测试评价器读取和判分；它们不是仅供阅读的参考说明。生成阶段不得把真值标签、判分解释或答案文件拼接到模型消息、共享契约、规则基线输入或生成缓存。该禁止仅针对被测生成过程，不禁止测试评价器访问真值。输入中符合正常需求表达的契约规则不是答案泄漏。

## 3. 基础类型

| 类型 | 定义 |
| --- | --- |
| `Identifier` | 非空字符串，匹配 `^[a-z0-9_-]+$` |
| `Text` | 非空且非纯空白的 Unicode 字符串 |
| `Side` | `frontend` 或 `backend` |
| `Sides` | 非空、无重复的 `Side` 数组，最多两个元素 |
| `Sha256` | 64 位小写十六进制字符串 |
| `Timestamp` | RFC 3339 时间，必须包含时区 |
| `JsonObject` | 开放 JSON 对象；允许嵌套，但不得包含非 JSON 值 |
| `SourceRef` | 第 9 节定义的来源引用 |
| `AssetMap` | 第 6 节定义的资产映射 |

编码必须为 UTF-8。不得使用注释、尾逗号、重复对象键、`NaN` 或 `Infinity`。缺省、`null`、空字符串和空数组不得互相替代。允许空值的字段必须在类型中明确声明。数组顺序默认具有意义；显式定义为集合的数组例外。

## 4. 输入数据集

### 4.1 根对象 `Dataset`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | 字符串 | 固定为 `2.0.0` |
| `dataset_id` | `Identifier` | 数据集稳定标识，不含来源方式推断 |
| `dataset_version` | 字符串 | 数据内容版本，采用语义版本格式 |
| `status` | 枚举 | `draft`、`ready`、`frozen` |
| `source_repository` | `Text` | 仓库 HTTPS URL |
| `source_commit` | 字符串 | 固定的完整 40 位 Git 提交 SHA |
| `chains` | `Chain[]` | 有序需求链列表 |

`draft` 仅用于编制过程，不得用于正式生成。`ready` 表示所有必填字段与交叉约束已通过校验。`frozen` 表示数据与冻结记录一致，且不再原地修改。

### 4.2 需求链 `Chain`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `chain_id` | `Identifier` | 数据集内唯一链标识 |
| `topic` | 枚举 | 第 10 节指定的主题 |
| `split` | 枚举 | `dev` 或 `test` |
| `provenance` | `Provenance` | 来源和创建过程元数据 |
| `initial_assets` | `AssetMap` | 该链独立的初始资产状态 |
| `steps` | `Step[]` | 按执行顺序排列的三个连续变更 |

`Provenance` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `creator_id` | `Text` | 创建主体标识 |
| `created_at` | `Timestamp` | 创建时间 |
| `creation_method` | `Text` | 实际创建方式，不得使用未核实声明 |
| `tools_used` | `Text[]` | 实际使用工具；无工具时为空数组 |
| `requirement_origin` | 枚举 | `designed_scenario` 或 `repository_history` |
| `origin_evidence` | `Text[]` | 历史事件证据 URL；设计情景可为空 |

`repository_history` 必须提供可核验的 issue、PR 或提交证据。`designed_scenario` 表示基于仓库事实建立的假设性变更，不表示该事件实际发生。

### 4.3 需求变更 `Step`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `step_id` | `Identifier` | 数据集范围内唯一；推荐 `c01-s1` |
| `raw_requirement` | `Text` | 完整需求原文，明确行为与边界 |
| `preserved_constraints` | `Text[]` | 本步仍有效的约束；无保留约束时为空数组 |
| `sources` | `SourceRef[]` | 至少一条来源，覆盖本步需求及所依赖的已有事实 |
| `pack_input` | `PackInput` | 提示包层实验使用的显式输入 |

需求必须明确新增、修改、撤销或回退行为。字段应保留精确名称、路径、方法、类型、状态码及适用条件；不得仅使用“优化”“保持一致”等无法确定目标状态的描述。

## 5. 提示包生成输入 `PackInput`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `project_config` | `ProjectConfig` | 同一步各方法共享的项目配置 |
| `selected_story` | `Story` 或 `null` | 已确定的需求故事；未提供时为 `null` |
| `change_sets` | `ChangeSet[]` | 非空、有序的层级变更集 |
| `old_versions` | `AssetMap` | 本步变更前完整状态 |
| `new_versions` | `AssetMap` | 本步变更后完整目标状态 |

### 5.1 项目配置 `ProjectConfig`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `Text` | 项目名称 |
| `target_frontend_stack` | `Text` | 前端技术栈 |
| `target_backend_stack` | `Text` | 后端技术栈 |
| `llm_prompt_language` | 枚举 | `en` 或 `zh` |
| `global_constraints` | `Text[]` | 跨层约束 |
| `coding_preferences` | `Text[]` | 实施偏好 |
| `prompt_preferences` | `Text[]` | 提示表达偏好 |

### 5.2 需求故事 `Story`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | `Text` | 需求摘要 |
| `implementation_scope` | 枚举 | `frontend`、`backend`、`fullstack` |
| `affected_layers` | 层名数组 | 非空且无重复，取值见第 6 节 |
| `user_story` | `Text` | 角色、目标和业务目的 |
| `acceptance_criteria` | `Text[]` | 非空、可判定的验收条件 |

### 5.3 变更集 `ChangeSet`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `layer` | 层名 | 被变更资产层 |
| `added` | `ChangeItem[]` | 新增项；无新增时为空数组 |
| `modified` | `ChangeItem[]` | 修改项；无修改时为空数组 |
| `removed` | `ChangeItem[]` | 移除项；无移除时为空数组 |

每个 `ChangeItem` 必须包含 `target`（`Text`）、`before`（任意 JSON 值）、`after`（任意 JSON 值）、`reason`（`Text`）。`target` 必须使用 RFC 6901 JSON Pointer，定位至该层资产的 `content` 内部。

新增项的 `before` 为 `null`，目标路径在旧状态中必须不存在；移除项的 `after` 为 `null`，目标路径在新状态中必须不存在。修改项要求两侧路径均存在且值不同；路径值本身可为 `null`。同一目标不得在同一步不同类别中重复出现。每个变更集至少包含一项实际变更。

## 6. 资产结构与状态连续性

`AssetMap` 是非空对象，键仅允许：

```text
ux_design
ui_design
frontend_pages
frontend_tools
api_contract
backend_services
backend_tools
database_models
```

每个值必须为 `AssetSnapshot`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `version` | 正整数 | 同层资产版本 |
| `title` | `Text` | 资产标题 |
| `summary` | 字符串 | 内容摘要，可为空字符串 |
| `content` | `JsonObject` | 非空资产内容，按层业务定义组织 |

资产快照必须表达实际设计状态，不得用参考事实 ID 或评价标签代替设计内容。`content` 属于开放对象，各系统应在自己的层级模式中校验其内部结构；通过本规范结构检查不代表通过应用层资产校验。

状态连续性必须满足：

```text
steps[0].pack_input.old_versions == initial_assets
steps[i].pack_input.old_versions == steps[i-1].pack_input.new_versions  (i > 0)
```

等价判定使用 JSON 结构和值比较，忽略对象键顺序，但不忽略数组顺序。未变更资产必须完整保留且版本不变；修改资产版本必须递增。内容回退仍为新版本，不得降低版本号。新增层从版本 `1` 开始。映射表示完整状态，而非仅列出本步差异。

不同需求链不得继承其他链的状态。链内目标状态必须继承上一步保留规则，并明确替换已失效规则。

## 7. 独立测试真值标签（Ground Truth）

### 7.1 根对象 `Answers`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | 字符串 | 固定为 `2.0.0` |
| `dataset_id` | `Identifier` | 必须与输入数据集相同 |
| `dataset_version` | 字符串 | 必须与输入数据集相同 |
| `created_at` | `Timestamp` | 答案创建时间 |
| `steps` | 对象 | 键为 `step_id`，值为 `Answer` |

`steps` 的键集合必须与输入全部步骤的 ID 集合完全一致，不得缺失或增加。标签必须在相关实验输出产生前完成标注、复核并冻结。测试评价以冻结标签为唯一预期值来源，不得根据被测输出反向修改标签。

### 7.2 步骤真值 `Answer`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `required_sides` | `Sides` | 本步必须包含指令的一端或两端 |
| `facts` | `Fact[]` | 非空的原子契约事实及测试真值标签集合 |

单端变更仅将必要端列入 `required_sides`。是否需要另一端，必须依据需求影响范围确定，不得以生成结果反推。

### 7.3 原子事实 `Fact`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `fact_id` | `Identifier` | 步骤内唯一语义标识 |
| `category` | 枚举 | 取值见下表 |
| `operation` | `Text` | 操作定位，例如 `POST /api/v1/records/` |
| `state` | `Text` | 事实成立的条件，例如已认证用户、创建请求 |
| `statement` | `Text` | 一个可独立判定的契约命题，必须与 gold_label 等价 |
| `gold_label` | `GoldLabel` | 必填的结构化测试真值，第 7.4 节定义 |
| `required_sides` | `Sides` | 必须体现该事实的端；为步骤必要端集合的子集 |
| `sources` | `SourceRef[]` | 非空，支持事实的溯源 |

| `category` | 含义 |
| --- | --- |
| `path_method` | API 路径与 HTTP 方法 |
| `field_type` | 请求或响应字段名称与类型 |
| `required_nullable` | 必填性、可空性、缺省与清空语义 |
| `enum` | 枚举取值及含义 |
| `permission` | 角色、所有权与访问控制 |
| `pagination` | 参数、默认值、边界和返回结构 |
| `error` | 错误状态码、响应结构及处理行为 |
| `history` | 历史规则替换、撤销或回退 |
| `scope` | 单端职责及跨端边界 |

一条事实不得合并多个可分别判定的规则。例如“字段必须为整数且必填”必须拆分为类型事实和必填事实。同一命题的重复表达不得使用多个 ID 增加计数。跨步骤未改变的命题应保持稳定语义标识；规则改变时必须以 `state` 和 `statement` 明确当前有效含义。

### 7.4 标签的测试真值地位与结构

`Answer.required_sides` 是步骤职责真值，`Fact.required_sides` 是该事实的必要端真值，`Fact.gold_label` 是该事实的契约值真值。三者共同构成测试判分依据，必须随独立答案交付。`category` 只是事实类别，`topic` 与 `split` 只是主题和数据划分标签，不能代替契约真值。

`GoldLabel` 为封闭对象，必须且只能包含以下字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `target` | `Text` | 当前 operation/state 下的单一契约属性标识，如 `request.title.max_length`；不是快照 JSON Pointer |
| `value` | 任意 JSON 值 | 该属性唯一的预期值；可为字符串、数字、布尔值、null、数组或对象，不得为待定占位符 |

一条 gold_label 只表示一个原子命题。范围上下限拆成两条；字段是否必填、是否可空分别用布尔标签；默认值用独立属性表达；废弃规则用如 `request.title.accepted=false` 表达。枚举允许值可以是单个集合命题，以排序、去重后的数组表示；如果还需逐项解释含义，应另建原子事实。对象值仅可用于本身不可拆分的原子契约，不得把多条规则装入对象逃避原子化。

标签必须连同 `dataset_id`、`dataset_version`、`step_id`、`fact_id` 定位。`operation` 与 `state` 限定适用条件；不同角色、端点、步骤的同名字段不得混判。相同属性在不同步骤允许有不同真值，回退后使用当前步骤冻结值。

真值 value 表示被测提示应表达的契约属性，不是用来直接比较业务请求的具体值。例如 max_length 的真值 80，表示提示必须表达“上限为 80”，不是要求每个标题恰好有 80 个字符。自然语言语义抽取须引用原文证据，归一化后进行 JSON 类型与值比较，禁止把字符串 `"80"`、数字 `80`、布尔 `true` 混为一类。等价表述可以匹配；不能确定时为 uncertain，不允许猜成通过。

`statement`、gold_label、来源需求和目标快照有冲突时，必须在运行前报错并修订版本，不能静默任选一方。标签未填、来源不支持、人工复核未完成或存在冲突时，数据不得进入 ready/frozen。真值一经冻结即是本版本的测试标准；模型输出和评价器推测均无权覆盖它。

### 7.5 真值与实测标签的区分

| 对象 | 是否为运行前测试真值 | 用途 |
| --- | --- | --- |
| Answer.required_sides、Fact.required_sides、Fact.gold_label | 是 | 判定必要端、必要事实及契约正确性 |
| Fact.statement、operation、state、sources | 真值的语义解释与证据 | 确定适用范围并复核标注 |
| FactEvaluation.observed_labels | 否 | 从被测输出抽取的实际契约值 |
| FactEvaluation.status | 否 | 实际值对照真值并结合双端一致性得出的结果 |

`consistent`、`contradiction`、`omission`、`uncertain`、`common_error` 是实测结果标签，不能在未知输出时一律预填为 consistent。如果实验对象是“评价器的分类准确率”，应另建含固定提示包样本及人工裁定 status 的标注测试集；该集的人工 status 才是分类真值，不得用评价器自己的预测充当真值。本规范的主实验仍是提示包契约一致性测试。

## 8. 结构示例

下例仅展示单步骤的输入片段与答案片段，不构成满足十条链规模要求的数据集。示例资源 `records` 不表示固定仓库中的实际接口。

输入片段：

```json
{
  "step_id": "c01-s1",
  "raw_requirement": "创建记录时，title 必须为非空字符串；前端提交该字段，后端校验该字段。其他创建规则保持不变。",
  "preserved_constraints": ["创建接口继续使用 POST /api/v1/records/"],
  "sources": ["requirement:c01-s1"],
  "pack_input": {
    "project_config": {
      "name": "Example Project",
      "target_frontend_stack": "React, TypeScript",
      "target_backend_stack": "FastAPI, PostgreSQL",
      "llm_prompt_language": "en",
      "global_constraints": [],
      "coding_preferences": [],
      "prompt_preferences": []
    },
    "selected_story": null,
    "change_sets": [{
      "layer": "api_contract",
      "added": [],
      "modified": [{
        "target": "/create/request/title/min_length",
        "before": 0,
        "after": 1,
        "reason": "禁止空字符串"
      }],
      "removed": []
    }],
    "old_versions": {
      "api_contract": {
        "version": 1,
        "title": "Records API",
        "summary": "创建记录",
        "content": {"create": {"method": "POST", "path": "/api/v1/records/", "request": {"title": {"type": "string", "required": true, "min_length": 0}}}}
      }
    },
    "new_versions": {
      "api_contract": {
        "version": 2,
        "title": "Records API",
        "summary": "创建记录",
        "content": {"create": {"method": "POST", "path": "/api/v1/records/", "request": {"title": {"type": "string", "required": true, "min_length": 1}}}}
      }
    }
  }
}
```

答案片段：

```json
{
  "required_sides": [
    "frontend",
    "backend"
  ],
  "facts": [
    {
      "fact_id": "create-title-type",
      "category": "field_type",
      "operation": "POST /api/v1/records/",
      "state": "创建请求",
      "statement": "请求字段 title 的类型为 string。",
      "required_sides": [
        "frontend",
        "backend"
      ],
      "sources": [
        "requirement:c01-s1"
      ],
      "gold_label": {
        "target": "request.title.type",
        "value": "string"
      }
    },
    {
      "fact_id": "create-title-required",
      "category": "required_nullable",
      "operation": "POST /api/v1/records/",
      "state": "创建请求",
      "statement": "请求必须包含 title 字段。",
      "required_sides": [
        "frontend",
        "backend"
      ],
      "sources": [
        "requirement:c01-s1"
      ],
      "gold_label": {
        "target": "request.title.required",
        "value": true
      }
    },
    {
      "fact_id": "create-title-nonempty",
      "category": "field_type",
      "operation": "POST /api/v1/records/",
      "state": "创建请求",
      "statement": "title 不得为空字符串。",
      "required_sides": [
        "frontend",
        "backend"
      ],
      "sources": [
        "requirement:c01-s1"
      ],
      "gold_label": {
        "target": "request.title.min_length",
        "value": 1
      }
    }
  ]
}
```

示例答案不穷尽接口保留事实。正式答案必须补齐路径、方法及其余必要事实，不得仅列本次新增规则。

## 9. 来源引用与离线证据

`SourceRef` 允许以下形式：

```text
https://github.com/fastapi/full-stack-fastapi-template/blob/<source_commit>/<path>#L<start>-L<end>
requirement:<step_id>
```

源码引用必须使用固定提交，禁止使用 `main`、`master` 或其他浮动引用。行号范围必须有效，并指向支持命题的代码。需求引用可指向当前或同链之前的步骤，不得指向未来步骤或其他链。当前运行器对需求引用仅接受当前步骤；继承引用需适配后才能接入，禁止静默替换来源。

`sources/manifest.json` 根对象包含 `schema_version`、`repository_url`、`commit`、`license` 和 `files`。`files` 为非空数组，每项包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `path` | `Text` | 仓库相对路径 |
| `local_path` | `Text` | 数据根目录相对路径 |
| `url` | `Text` | 固定提交文件 URL |
| `sha256` | `Sha256` | 离线文件原始字节摘要 |

`license` 包含 `spdx_id`（例如 `MIT`）及 `local_path`。路径必须为安全相对路径，不得包含 `..`、绝对路径或越界符号链接。离线副本必须与引用提交一致。不得收录凭据、真实用户数据或与事实定位无关的仓库内容。

## 10. 本基准数据集配置

源仓库：`https://github.com/fastapi/full-stack-fastapi-template`  
固定提交：`1762adac607a1b29cfc4da129557780beea71616`  
规模：10 条链，每条 3 个步骤，共 30 个步骤。

| 链标识 | `topic` | `split` |
| --- | --- | --- |
| `chain-01` | `item_validation` | `dev` |
| `chain-02` | `pagination` | `dev` |
| `chain-03` | `permissions` | `test` |
| `chain-04` | `field_rename` | `test` |
| `chain-05` | `null_and_clear` | `test` |
| `chain-06` | `error_contract` | `test` |
| `chain-07` | `filter_sort` | `test` |
| `chain-08` | `delete_restore` | `test` |
| `chain-09` | `user_profile` | `test` |
| `chain-10` | `scope_clarification` | `test` |

步骤标识按链编号与顺序命名，例如 `c01-s1`、`c01-s2`、`c01-s3`。划分必须以完整链为单位，同链步骤不得跨集合。测试链共 24 个步骤；数据规模不等于重复运行次数，也不构成统计独立性声明。

## 11. 冻结记录与版本规则

冻结记录必须包含以下字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | 字符串 | `2.0.0` |
| `dataset_id`、`dataset_version` | 字符串 | 与输入及答案一致 |
| `stage` | 枚举 | `pilot` 或 `formal` |
| `created_at` | `Timestamp` | 冻结时间 |
| `input_sha256`、`answer_sha256` | `Sha256` | 规范化 JSON 摘要 |
| `source_hashes` | 对象 | 路径至原始字节 SHA-256 的映射 |
| `code_hashes` | 对象 | 评测代码、模板、规则及依赖配置摘要 |
| `model_configs` | `JsonObject` | 有效模型、温度、重试与其他实际参数；不得包含凭据 |
| `protocol` | `JsonObject` | 方法、重复次数、计划单位数与预登记目标 |
| `pilot_report_sha256` | `Sha256` 或 `null` | 正式冻结必须关联开发试验报告 |

规范化 JSON 使用 Python `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` 的 UTF-8 字节，之后计算 SHA-256。其他语言实现必须与该序列化结果一致；不得直接以缩进文件字节替代输入或答案摘要。源码及代码摘要使用文件原始字节。

正式生成开始前必须核验冻结摘要；发现变化必须拒绝运行。冻结后任何需求、答案、来源或模板修订必须生成新版本并保留旧文件、旧冻结记录及旧结果，不得回写历史成绩。冻结后输入状态为 `frozen`，摘要必须基于该最终状态计算。

## 12. 校验规则

| 规则编号 | 必须满足的条件 |
| --- | --- |
| `D001` | JSON 编码、基础类型、枚举、必填字段及未知字段检查通过 |
| `D002` | 数据集包含十条链、每链三个步骤，标识均唯一 |
| `D003` | 主题及开发／测试划分与第 10 节一致 |
| `D004` | 输入与答案的版本、数据集 ID、步骤集合完全一致 |
| `D005` | 链内状态连续，链间状态独立 |
| `D006` | 变更集准确对应快照差异，未变更资产未丢失 |
| `D007` | 版本递增符合第 6 节，包括内容回退情形 |
| `D008` | 来源固定、可解析、存在离线副本且摘要一致 |
| `D009` | 每个事实只有一个命题，事实 ID 及必要端无重复 |
| `D010` | 事实必要端为步骤必要端的子集 |
| `D011` | 真值标签覆盖当前变更、保留约束及被替换的历史规则；与 statement、需求及快照一致 |
| `D012` | 生成阶段不能读取答案或评价标签 |
| `D013` | 正式运行前冻结记录与实际文件、配置一致 |
| `D014` | 历史事件来源声明具备证据，创建元数据反映实际过程 |
| `D015` | 每条事实含合法且经复核的 gold_label；标签适用条件清晰，无同条件冲突，结果绑定冻结真值摘要 |

结构校验与语义校验必须区分。字符串非空、来源存在或模型解析成功，不构成事实正确、覆盖完整或同步一致的充分证据。未解决的语义歧义必须阻止正式冻结。

校验结果应包含 `rule_id`、`severity`、`json_pointer` 和 `message`。`severity` 取 `error` 或 `warning`；任何 `error` 均阻止进入 `ready` 或 `frozen` 状态。

## 13. 评价数据接口

冻结的答案标签作为测试真值，评价器必须逐事实读取并与被测输出对照；不得仅检查两端彼此一致。真值允许且必须预先标注，模型实际成绩仍须在运行后计算。实际评价必须关联 `dataset_id`、`dataset_version`、`chain_id`、`step_id`、方法标识、重复编号、提示包摘要和运行 ID。

事实评价状态必须区分：`consistent`（符合要求且同步）、`contradiction`（双端事实不能同时成立）、`omission`（必要事实缺失）、`uncertain`（证据不足或含义不明确）、`common_error`（双端一致但共同违背需求）。

矛盾证据必须包含事实 ID、两端原文、两端定位及冲突解释。原文定位采用解码后字符串的 Unicode 码点偏移，区间为 `[start, end)`；证据原文必须与定位片段完全一致。定位还必须注明对应提示字段或文件。仅有单端证据不得判为双端矛盾。

主指标 `C` 为每包经确认的不同原子矛盾数，同一命题的重复句子只计一次。`common_error` 不计入 `C`，但不满足成功条件。缺失必要端、生成失败或必要事实覆盖不完整的包不得作为有效零矛盾包。

成功包必须同时满足：生成成功、必要端存在、必要事实覆盖完整、无歧义、无共同错误且 `C = 0`。成功比例的分母必须为全部计划实验单位，失败不得被删除。结果文件不得写入或替换本规范定义的输入及答案文件。

## 14. 系统接入约束

外部系统可将本规范用作交换协议，通过模式校验、交叉引用校验和资产层语义校验接入。适配器必须记录交换格式版本、目标运行器版本、字段映射及适配后数据摘要。

本规范中的 `Story`、`ChangeSet` 与资产内容需映射至目标系统实际输出模式；不得仅因它们是 JSON 对象而直接认定为目标服务合法输入。中性来源元数据也不得自动转换为未经证实的过程声明。

提示包层实验使用冻结的 `pack_input`；完整编排层实验仅以初始资产、项目配置和逐步需求启动，再继承该次运行的真实生成状态。完整编排层不得以参考答案或预定目标快照纠正上游结果。

合格交付必须包含可校验的输入数据、独立答案、固定来源及许可证、冻结记录，以及各文件用途和访问边界说明。该条件只定义数据可用性与可复现性，不预设系统效果。

## 15. 编制说明与本次填写边界

本次修订日期：2026-10-03。文档及交换格式修订号为 `2.0.0`。本次将结构化标签明确规定为测试真值，新增必填 gold_label、observed_labels 与结果 answer_sha256，因此属于不向后兼容的模式升级；不宣称现有运行器已支持这些字段。

第 16 节为指定提交的静态源码核验结果；第 17 节为据此编制的 10 条设计情景链，均使用 `requirement_origin=designed_scenario`、`origin_evidence=[]`，不得改标为仓库真实历史。第 18—22 节补全数据落地、评价与验收要求。

本文是填写完成的规范文档，包含需求编制稿；它本身不是已经通过 D001—D015 的 JSON 数据发行包。本文没有执行模型生成、开发试验或正式评测，因此不提供虚构成绩、模型实参、评测代码摘要或正式冻结记录。数据实例在完成独立答案、离线来源、适配器与语义复核以前保持 `draft`。源码阅读只能证明静态定义，不能替代运行时集成测试。

## 16. 固定源码基线

### 16.1 核验方式

从第 10 节固定提交读取路由、模型、项目依赖、API 挂载配置与许可证原始文件，并按文件行号核对。以下证据短名只用于本文阅读；写入 `SourceRef` 时必须展开成完整固定提交 URL，不得将短名写入数据。

| 短名 | 固定提交证据 | 支持的基线事实 |
| --- | --- | --- |
| S01 | [条目路由](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/app/api/routes/items.py#L13-L45) | 列表 `GET /items/`；默认 `skip=0`、`limit=100`；普通用户仅看本人数据，超级用户看全部；按 `created_at` 降序；返回 `data`、`count` |
| S02 | [条目读写](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/app/api/routes/items.py#L48-L96) | 详情 GET、创建 POST、更新 PUT；非所有者且非超级用户访问已有条目时返回 403；不存在时返回 404；更新使用 `exclude_unset=True` |
| S03 | [条目删除](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/app/api/routes/items.py#L99-L113) | DELETE 为物理删除；成功消息为 `Item deleted successfully` |
| S04 | [条目模型](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/app/models.py#L73-L112) | 创建 `title` 必填、长度 1—255；`description` 可空、缺省 null、最长 255；更新字段均可省略；公开模型含 UUID `id`、`owner_id` 及可空 `created_at` |
| S05 | [个人资料模型](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/app/models.py#L13-L43) | `full_name` 可空且最长 255；`UserUpdateMe` 包含 `full_name`、`email` |
| S06 | [个人资料接口](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/app/api/routes/users.py#L81-L129) | `PATCH /users/me` 更新本人资料；邮箱被其他用户占用时返回 409；`GET /users/me` 返回本人资料 |
| S07 | [API 挂载](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/app/main.py#L35-L35)、[前缀](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/app/core/config.py#L22-L22)、[路由注册](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/app/api/main.py#L7-L10) | 本基准使用默认完整前缀 `/api/v1` |
| S08 | [前端依赖](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/frontend/package.json#L1-L65)、[后端依赖](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/backend/pyproject.toml#L1-L24) | React、TypeScript、Vite；FastAPI、SQLModel、PostgreSQL 驱动 |
| S09 | [许可证](https://github.com/fastapi/full-stack-fastapi-template/blob/1762adac607a1b29cfc4da129557780beea71616/LICENSE#L1-L21) | MIT；离线分发保留完整版权和许可文字 |

`ItemUpdate.title` 的输入模型允许 null，而持久化模型的 `title` 为字符串；不能仅据输入类型推断提交 null 后一定成功。涉及该边界的设计情景必须明确目标行为。路由未声明额外分页边界，不应将设计中的上限误写成仓库已存在的规则。

### 16.2 统一项目配置

本基准的设计输入采用以下配置，具体版本以固定提交的依赖和锁文件为准，不写为浮动“最新版”。

```json
{
  "name": "Monoplanner Sync Benchmark",
  "target_frontend_stack": "React, TypeScript, Vite, TanStack Query",
  "target_backend_stack": "FastAPI, SQLModel, PostgreSQL",
  "llm_prompt_language": "zh",
  "global_constraints": [
    "使用默认 API 前缀 /api/v1；路径尾斜杠按契约保留",
    "权限校验在后端执行，前端可见性控制不能替代服务端鉴权",
    "未明确替换的接口和字段契约继续有效",
    "每条需求链独立从固定源码基线开始"
  ],
  "coding_preferences": [
    "前端使用 TypeScript 类型表达请求和响应",
    "后端区分输入模型、公开响应模型与持久化模型"
  ],
  "prompt_preferences": [
    "分别给出前端和后端职责，单端变更只要求必要端",
    "明确当前有效规则及被撤销规则",
    "保留方法、路径、字段、类型、错误码与边界条件原文"
  ]
}
```

以上为编制选择，不代表已使用某个 LLM 模型。`creator_id` 可记为 `codex-document-author`，`creation_method` 应记为“AI 辅助编制；人工复核尚未完成”，`tools_used` 如实记录源码下载、文本检查及文件编辑工具。`created_at` 使用实际生成对应数据对象的带时区时间，不伪造人工签核。

## 17. 十条需求链的填写内容

### 17.1 共同解释规则

以下每个编号对应一个 `Step`。本节中的“前后端”映射为 `["frontend","backend"]`，“仅前端”或“仅后端”映射为相应单元素数组。链内每步继承前一步全部有效规则，只有明确替换或撤销的部分失效；不同链之间不继承任何设计变更。

正式写入 `raw_requirement` 时，应展开该步涉及的共用规则及保留规则，不得只填“同上”。`preserved_constraints` 需逐条列出本步生成所需的保留契约。涉及条目 API 的来源同时包含 S07；新增目标行为引用当前 `requirement:<step_id>`，既有行为引用支持它的源码或同链此前需求。

本节对新增校验失败统一要求 HTTP 422，并沿用当前链已有的校验错误结构，除非该步明确替换。所有成功响应都须保持对应端点原有公开字段，除非该步明确增删字段。前端需提交当前参数、解析当前响应并处理本步明确规定的错误；后端需校验、授权并返回同一契约。

### 17.2 chain-01：item_validation（dev）

起点：S02、S04。影响层：`api_contract`、`frontend_pages`、`backend_services`。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c01-s1` | 前后端：创建及更新的 `title` 在提交或校验前剥除首尾 U+0020 空格，再按 Unicode 码点计长，允许 3—80；创建必须提供，更新可省略，显式 null 一律 422。后端存储并返回处理后的值。 | POST `/api/v1/items/`、PUT `/api/v1/items/{id}`、权限与 description 规则不变。长度 2/81 失败，3/80 成功；全空格失败；更新缺省不改变原值。 |
| `c01-s2` | 前后端：将 title 上限由 80 调整为 120，下限仍为 3；description 的非空值上限由 255 调整为 500，不修剪 description。 | title 的修剪、必填与 null 规则不变；description 缺省和 null 语义不变。title 长度 120 成功、121 失败；description 长度 500 成功、501 失败。 |
| `c01-s3` | 前后端：仅将 title 上限从 120 回退到 80；description 上限仍为 500。已有超 80 的 title 可读取；更新省略 title 时不重校验原值，显式提交超限 title 返回 422。 | 不得撤销下限 3 或修剪规则。回退后的资产版本继续递增；用“已有 100 字 title，更新 description”检验局部更新语义。 |

### 17.3 chain-02：pagination（dev）

起点：S01。影响层：`api_contract`、`frontend_pages`、`backend_services`。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c02-s1` | 前后端：GET `/api/v1/items/` 的 skip 为整数且 ≥0，缺省 0；limit 为整数且 1—50，缺省 20；非法值 422。前端翻页按 skip/limit 发送。 | `data` 为当前页，`count` 为权限范围内全部匹配条目数，不随当前页条数改变。空页返回 `data=[]`。 |
| `c02-s2` | 前后端：替换为 page/page_size，均为整数；page ≥1，缺省 1；page_size 为 1—50，缺省 20；内部偏移为 `(page-1)*page_size`。请求只要包含 skip 或 limit 即返回 422，不接受双协议。 | 响应仍为 data/count；权限与排序不变。page 超出末页得到空 data 和真实 count；前端页码从 1 开始。 |
| `c02-s3` | 前后端：page_size 默认值由 20 改为 25，上限由 50 改为 100。响应新增整数 page、page_size，回显实际生效值。 | page 缺省 1，旧 skip/limit 仍禁止；page_size=100 成功、101 失败。前端以回显值同步控件。 |

### 17.4 chain-03：permissions（test）

起点：S01—S03。影响层：`api_contract`、`frontend_pages`、`backend_services`。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c03-s1` | 前后端：普通用户对他人已存在条目执行 GET、PUT、DELETE 时统一返回 404，`detail="Item not found"`；不存在也返回相同响应。 | 所有者和超级用户原权限不变；列表仍只包含当前用户可见数据。前端按 404 处理，不显示他人资源信息。 |
| `c03-s2` | 前后端：超级用户仍可读取他人条目，但 PUT、DELETE 他人条目返回 403，`detail="Read-only access"`；前端他人条目只读。 | 超级用户对本人条目可写；普通用户他人资源 404；不存在资源仍 404；创建 owner_id 仍为当前用户。 |
| `c03-s3` | 前后端：仅恢复超级用户修改、删除他人条目的权限；移除针对该角色的只读错误与界面限制。 | 普通用户他人资源仍 404，不得回退为源码中的 403；超级用户读全量不变。 |

### 17.5 chain-04：field_rename（test）

起点：S02、S04。影响层：`api_contract`、`frontend_pages`、`backend_services`；持久化字段保持 title。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c04-s1` | 前后端：创建/更新请求新增 name 作为 title 的别名。单独提供任一个时按原 title 约束校验；两者同时出现返回 422。创建至少提供一个，更新可都省略；显式 null 返回 422。响应同时返回 title 与 name，值完全相同。前端迁移为提交和显示 name。 | 非空字符串 1—255，不新增修剪；数据库仍存 title；列表、详情、创建和更新响应均应用别名规则。 |
| `c04-s2` | 前后端：停止接受请求 title，出现该键即 422，即使与 name 同时出现。创建 name 必填、更新可省略；响应继续同时提供 title/name。 | name 的类型、长度及 null 限制不变；禁止静默忽略旧键。 |
| `c04-s3` | 前后端：从所有条目公开响应中移除 title，只输出 name；前端移除读取 title 的回退逻辑。 | 请求 title 仍 422；数据库字段不改名；description/id/owner_id/created_at 不变。 |

### 17.6 chain-05：null_and_clear（test）

起点：S02、S04。影响层：`api_contract`、`frontend_pages`、`backend_services`。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c05-s1` | 前后端：PUT 条目时 description 缺省表示不修改，null 表示清空为数据库 NULL，空字符串表示保存空字符串；前端“清空”操作必须提交 null。 | description 字符串上限 255；不得把缺省自动转成 null，也不得把空字符串折叠为 null；创建规则不变。 |
| `c05-s2` | 前后端：仅更新请求中，description 空字符串改为与 null 一样清空为 NULL；响应为 null。空格字符串保持原样。 | 缺省仍不修改；创建时空字符串仍为空字符串；前端必须区分创建与编辑的归一化。 |
| `c05-s3` | 前后端：更新新增可省略布尔 clear_description，缺省 false。true 且 description 缺省时清空；true 与任何 description 值同时出现均 422。description=null 改为 422；空字符串恢复为保存空字符串。 | false 或缺省且 description 缺省时不修改；仅更新请求接受此控制字段，响应不回传；前端清空改为提交 `{"clear_description":true}`。 |

### 17.7 chain-06：error_contract（test）

起点：S02、S03。影响层：`api_contract`、`frontend_tools`、`backend_services`。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c06-s1` | 前后端：仅条目 GET/PUT/DELETE 的资源不存在和权限不足错误改为 `{"error":{"code":"ITEM_NOT_FOUND","message":"Item not found"}}` 与 `{"error":{"code":"ITEM_FORBIDDEN","message":"Not enough permissions"}}`，分别为 404、403；不再含顶层 detail。 | 认证错误和 422 校验错误保持原有结构；前端按状态码与 error.code 分支，不能把所有错误都强制按新结构解析。 |
| `c06-s2` | 前后端：上述两种错误的 error 内新增必填非空字符串 request_id，由后端生成并关联服务端日志，前端可展示用于反馈。 | code、message、状态码不变；成功响应及其他错误不新增该字段；request_id 不包含凭据或用户输入内容。 |
| `c06-s3` | 前后端：仅将上述两种 error.message 字段改名为 error.detail，删除旧 message；request_id 保留。 | 错误仍在 error 对象内，不能误写为顶层 detail；前端仍以 code 判断，不匹配自然语言内容。 |

### 17.8 chain-07：filter_sort（test）

起点：S01、S04。影响层：`api_contract`、`frontend_pages`、`backend_services`。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c07-s1` | 前后端：条目列表新增可选字符串 q，剥除首尾 U+0020 后最长 100 码点；空值或缺省不筛选；否则对 title 执行区分大小写的字面子串匹配，`%`、`_` 不作通配符。 | 先权限约束、再筛选、再分页；count 是筛选后分页前总数；skip/limit 沿用基线。改变 q 后前端重置 skip=0。 |
| `c07-s2` | 前后端：新增 sort 枚举 `created_at_desc`、`title_asc`，缺省前者，其他值 422。时间降序空值最后，title 按 Unicode 码点升序；主排序相同时按 UUID 标准小写字符串升序。 | 筛选规则不变；后端排序后分页；前端不得只对当前页自行重排。 |
| `c07-s3` | 前后端：sort 新增 `title_desc`，title 主键降序、UUID 次键仍升序；默认排序改为 title_asc。 | created_at_desc 仍受支持，不能作为废弃值拒绝；q、count 和分页语义保持。 |

### 17.9 chain-08：delete_restore（test）

起点：S01—S04。影响层：`api_contract`、`frontend_pages`、`backend_services`、`database_models`。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c08-s1` | 前后端：DELETE 改为软删除，设置 deleted_at 为 UTC RFC 3339 时间；新建及迁移既有条目的 deleted_at 为 null。列表排除已删除条目且 count 同步排除；GET/PUT 已删除条目返回 404。公开条目响应增加可空 deleted_at。 | 原删除权限保留；无权限操作已有资源仍 403；已授权重复删除已删除条目返回 404。首次删除保持原成功消息。 |
| `c08-s2` | 前后端：新增 POST `/api/v1/items/{id}/restore`，无请求体；所有者或超级用户可恢复，成功 200 返回 ItemPublic 且 deleted_at=null；未删除时 409 `detail="Item is not deleted"`，不存在 404，他人资源无权 403。前端记录本会话成功删除的 id 并提供撤销。 | 恢复后的条目重新参与列表和 count；不新增回收站列表接口；页面刷新后不要求保留撤销入口。 |
| `c08-s3` | 前后端：恢复增加严格 7×24 小时窗口，由服务器 UTC 时间判定；`now-deleted_at < 604800秒` 可恢复，等于或大于边界时 410 `detail="Restore window expired"`。 | 不自动物理清理；未删除 409、不存在 404、无权 403 保留。先存在性和授权，后状态及时间检查；前端以服务端判定为准。 |

### 17.10 chain-09：user_profile（test）

起点：S05、S06。影响层：`api_contract`、`frontend_pages`、`backend_services`、`database_models`。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c09-s1` | 前后端：PATCH `/api/v1/users/me` 的 full_name 非 null 时剥除首尾 U+0020，处理后长度必须为 1—80；缺省不修改，null 清空。显式提交不合规值 422。 | email 更新、占用冲突 409 不变；其他用户管理端点不调整写入规则。已有长姓名可读取，更新省略 full_name 不重校验旧值。 |
| `c09-s2` | 前后端：用户持久化与 UserPublic 新增 timezone 枚举 `UTC`、`Asia/Shanghai`、`Asia/Singapore`；既有用户回填 UTC，新用户默认 UTC。本人 PATCH 可修改，缺省不修改，null 或非枚举值 422。前端设置页提供三种选项。 | full_name 第一步规则保留；所有输出 UserPublic 的接口返回 timezone；除本人 PATCH 外，其余写接口不开放 timezone 自定义写入。 |
| `c09-s3` | 前后端：本人 PATCH 禁止出现 email 键，出现即 422（包括 null 或与原值相同）；前端本人资料页邮箱改为只读。 | 返回资料仍含 email，管理员更新邮箱接口不变；本人更新姓名和时区规则保留。删除本人 PATCH 的“邮箱重复 409”有效分支，不能误删管理员端点的 409。 |

### 17.11 chain-10：scope_clarification（test）

起点：S01—S04。影响层随步骤区分。

| 步骤 | 填写的需求及目标状态 | 保留与验收边界 |
| --- | --- | --- |
| `c10-s1` | 仅前端：新增条目标题展示规范，列表视觉展示超过 30 个 Unicode 码点时显示前 30 个加 `…`；完整标题可通过可访问名称或展开控件读取，编辑框始终使用完整值。受影响层为 frontend_pages、ui_design。 | 这不是输入长度限制；请求、响应、存储、校验和后端不变。30 码点不截断，31 码点截断；不能把省略号提交到 API。 |
| `c10-s2` | 仅后端：条目创建、更新、删除成功提交后，新增结构化服务端日志事件，字段限定为 action（create/update/delete）、actor_id、item_id、occurred_at；三个 ID/时间相关值均用字符串，时间为 UTC RFC 3339。日志不得包含 title、description 或令牌。受影响层为 backend_services、backend_tools。 | 日志不是 API 响应；失败请求不记录成功事件，不要求新增审计查询接口。第一步前端展示规范继续有效，但本步无前端实施任务。 |
| `c10-s3` | 前后端：条目创建与更新响应新增 display_title，按第一步规则计算（完整标题≤30码点原样返回，否则前30加省略号）；前端创建/更新后立即反馈使用该字段，title 继续保存完整值。受影响层为 api_contract、frontend_pages、backend_services。 | 列表与详情响应不新增字段，仍按第一步在前端展示；请求禁止包含 display_title，出现即 422；第二步服务端日志保留。 |

### 17.12 覆盖检查

每条链独立具备“初始状态→变更一→变更二→变更三”。本编制稿覆盖限制扩展与回退、分页协议替换、角色权限调整、字段迁移、null/缺省/清空、错误结构迁移、筛选排序、删除恢复、个人资料及单端边界。30 步中 28 步要求前后端，`c10-s1` 仅前端，`c10-s2` 仅后端。

这些覆盖说明不替代逐事实答案。尤其不得将一张表中的整行直接视为一个原子事实；长度下限、上限、默认值、可空性、错误状态码、响应字段位置均须分别建事实。

## 18. 数据落地与变更求值细则

### 18.1 资产最小内容

本基准采用以下层内组织约定。它们是 `content` 开放对象的一种应用层模式，适配器须单独验证，不增加交换对象顶层字段。

| 层 | 最小内容 | 典型定位 |
| --- | --- | --- |
| api_contract | 端点方法、完整路径、请求参数、响应、权限、错误与条件 | `/operations/create_item/request/title/max_length` |
| frontend_pages | 页面动作、字段显示/提交、校验、加载和错误处理 | `/pages/items/form/title/validation` |
| frontend_tools | API 客户端与错误解析映射 | `/error_handlers/items/not_found` |
| backend_services | 业务校验、授权、状态迁移、序列化 | `/services/items/update/description_policy` |
| backend_tools | 日志等内部工具的输入输出和失败边界 | `/logging/item_mutations` |
| database_models | 字段类型、可空性、默认值、索引及迁移说明 | `/models/item/fields/deleted_at` |
| ux_design | 用户操作路径与反馈状态 | `/flows/item_restore` |
| ui_design | 展示规则、控件状态与可访问性约束 | `/components/item_title` |

每链可以只包含必要层，但一旦某层进入链状态，后续快照必须完整保留，除非明确删除整层。初始资产只描述已核验事实；如新增设计需要的初始界面事实未读取源码，应补充对应来源，不能推断仓库已实现该交互。

### 18.2 确定性变更语义

1. 同一步每层最多一个 `ChangeSet`，按层名排序输出。每类 ChangeItem 按 target 的 Unicode 码点顺序排列，以得到稳定文件。
2. 同一步禁止相同路径重复，禁止任何目标为另一目标的祖先路径，避免父子覆盖。数组作为整体修改，禁止在一个变更集中使用易受索引移动影响的多个数组增删操作。
3. RFC 6901 的 `~0` 表示 `~`，`~1` 表示 `/`；拒绝其他 `~` 转义。根指针使用空字符串。由于原 ChangeItem.target 定义为非空 Text，涉及整层新增或移除时，本基准不使用根指针，而分别记录 content 的顶层成员增删；层是否存在由 old/new 映射确定。
4. 读取路径时使用独立的“不存在”标记，不得用 null 代替。`added.before=null` 只是新增占位；新增值本身可以为 null。removed 同理。
5. before 必须等于旧状态对应值，after 必须等于新状态对应值。将所有互不重叠的内容操作应用到旧 content 后，结果必须等于新 content；不允许未记录的内容差异。
6. 新增层使用空对象作为变更计算起点，目标快照 version=1。删除层要求全部原 content 顶层成员被移除，新映射无该层；最终 AssetMap 仍须非空。
7. 本基准规定变更层 version 恰加 1，未变更层整个快照不变；回退内容同样加 1。允许更宽松递增的外部实现仍可满足第 6 节，但本基准落地采用这一确定性约定。
8. title/summary 仅允许随同实际内容变更更新，且需与内容相符；纯元数据修订应作为数据编制版本修订，不构造成需求步骤。ChangeSet 不追踪快照 version/title/summary。

### 18.3 JSON 与摘要可移植性

结构比较必须区分布尔值与数值，不得直接使用会把 `true` 与 `1` 视为相等的语言默认比较。本基准的版本、长度、分页与计数均使用整数，禁止 1.0 形式的整数字段。除业务明确需要外，不在开放对象中引入浮点数；跨语言浮点规范化尚未验证时必须阻止冻结。

读入 JSON 时需检测重复键后再构建对象；文件 UTF-8 不带 BOM。保留字符串原始 Unicode 序列，不进行隐式 NFC/NFD 转换。字符串长度与证据定位都使用 Unicode 码点；UTF-16 实现不得直接以代码单元偏移代替。

## 19. 测试真值标注与评价接口补全

### 19.1 答案编制程序

先根据每步当前状态提取命题，再逐条填写 gold_label、条件和必要端，最后交叉审阅需求、快照、文字命题与结构化标签的一致性。所有正式事实必须有可判分的 gold_label；只有自然语言说明的旧版答案不构成完整测试真值。答案须涵盖受影响操作的当前变更、仍有效且完成任务所必需的约束、以及旧规则的撤销；不要求抄录与本步无关的整个应用契约。

`required_sides` 表示本步必须交付指令的端，不等于“系统里存在该端”。例如 c10-s2 的前端展示规则仍保留在快照里，但本步不需要新增前端指令，不能因此把 frontend 加入答案必要端。

事实 ID 在同链相同语义位置保持稳定；例如 `item-title-max-length` 可以在不同步骤分别表达 80、120、80。跨链无需因为相同字段名强行共享事实 ID。规则被撤销时增加或更新 `history` 命题，写清旧规则已不适用，不能同时把新旧规则判为应满足。

以下是编制拆分示例，属于评审说明，不能作为完整 answers 文件或拼入生成输入：

| 事实 ID | 条件 | 单一命题 | 类别 |
| --- | --- | --- | --- |
| item-title-max-length | c01-s2，title 完成指定修剪后 | title 最多 120 个 Unicode 码点 | field_type |
| item-title-update-omission | c01-s2，更新请求未含 title | 不修改已有 title | required_nullable |
| item-description-max-length | c01-s2，description 为字符串 | description 最多 500 个 Unicode 码点 | field_type |
| item-title-old-limit-retired | c01-s2，新提交 title | 不再以 80 作为长度上限 | history |

四条事实均以 frontend/backend 为必要端；最后一条用于追踪历史替换，若评价时与第一条产生同一实际矛盾，应按语义命题去重，不重复增加 C。

### 19.2 结果文件对象

结果另存为 `results/<run_id>/evaluations.jsonl`，每行一个实验单位。该路径不属于生成输入目录。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| schema_version | 字符串 | 本结果接口为 `2.0.0` |
| run_id、dataset_id、chain_id、step_id、method_id | Identifier | 标识完整实验单位 |
| dataset_version | 字符串 | 数据内容版本 |
| repeat_index | 正整数 | 从 1 开始 |
| answer_sha256 | Sha256 | 本次实际加载的冻结测试真值摘要，必须等于 lock.answer_sha256 |
| pack_sha256 | Sha256 或 null | 实际输出提示包规范化摘要；无可解析提示包时 null |
| generation_status | 枚举 | success、failed、timeout、invalid_output |
| present_sides | Side 数组 | 实际存在且非空的端，可为空数组 |
| facts | FactEvaluation 数组 | 成功生成时覆盖参考事实全集，失败时允许空数组 |
| contradiction_count | 非负整数或 null | C；失败、缺必要端或仍有 uncertain 时为 null |
| success | 布尔 | 按第 13 节联合条件计算 |
| failure_reason | Text 或 null | 失败原因；成功时 null |

`FactEvaluation` 必须含 `fact_id`、`observed_labels`、`status`、`evidence`、`explanation`。observed_labels 为封闭对象，键恰为该事实 required_sides 的全部端。每端值为 `{ "extraction_status": "present", "value": <JSON值> }`，或 `{ "extraction_status": "missing" }`，或 `{ "extraction_status": "uncertain" }`；后两种禁止携带 value，避免把“未抽到”与“抽到显式 null”混淆。present.value 表达与 gold_label.target 相同的契约属性，必须有对应端原文证据。status 取第 13 节五种状态；explanation 为非空 Text；evidence 为 Evidence 数组。Evidence 必须含 side、field、start、end、quote：field 为提示包内字符串字段的 RFC 6901 路径，start/end 为非负整数，quote 为非空原文。文件型提示先在适配器中转换为稳定字段，并记录文件到字段的映射。

omission 允许无原文证据，但 explanation 必须说明检查了哪些必要字段；contradiction 至少包含各一条 frontend/backend 证据。同端前后矛盾不能误标为双端 contradiction：需在 explanation 说明，无法确认有效含义则 uncertain。事实仅要求一端时，明确违反参考契约记为 common_error，统计说明注明“必要端错误”；该名称在单端任务下不表示实际存在两个端。

### 19.3 判定顺序与聚合

评价开始前先核验 answer_sha256，按事实关联冻结 gold_label，不允许用生成结果建立新真值。每个事实先检查必要端证据是否缺失；缺失判 omission。证据存在但不能确定意思时判 uncertain。可解释证据中，若两端对同一条件给出不能同时成立的规则，判 contradiction；若两端彼此一致但不匹配 gold_label，判 common_error；全部必要端的实际标签均匹配 gold_label 才判 consistent。一端正确、一端明确错误且双方冲突时属于 contradiction，不能用 common_error 掩盖。

同一事实同时涉及缺失与错误时，主状态按上述顺序确定，其他问题写入 explanation。状态枚举不承担所有诊断细节；不能通过挑选标签使错误消失。

令计划单位数为 N，成功指示量为 sᵢ，则成功率为 `sum(sᵢ)/N`。令可确定 C 的单位集合为 V，则报告 `mean_C=sum(Cᵢ)/|V|`，同时报告 `|V|/N`、各失败类型数量、omission/uncertain/common_error 数量；V 为空时 mean_C=null，禁止记为 0。有 omission 而 C=0 的包仍不成功。

单端任务的双端矛盾 C 在生成成功且必要端存在时结构上为 0，因此必须同时报告“全部任务成功率”与“仅双端任务的矛盾统计”，不得用单端任务稀释双端矛盾率。若要比较方法，应使用相同链、步骤与重复编号配对；不能把同链三个连续步骤或同一任务多次生成视为独立样本。区间估计和显著性方法应预登记，并以链为聚类单位；测试只有 8 条链，应如实报告有限样本限制。

### 19.4 实际测试对照示例

对 `c01-s2` 的 `item-title-max-length`，冻结真值为：

```json
{
  "target": "request.title.max_length",
  "value": 120
}
```

该事实须分别限定创建或更新操作；若分别建事实，使用不同 fact_id。以下仅展示其中一个操作的判定，其他条件和必要事实另行检查。

| 前端抽取值 | 后端抽取值 | 实测 status | 原因 |
| --- | --- | --- | --- |
| 120 | 120 | consistent | 均匹配测试真值 |
| 80 | 120 | contradiction | 对同一条件给出冲突上限 |
| 80 | 80 | common_error | 双端相同，但都违背真值 120 |
| missing | 120 | omission | 前端缺少必要事实 |
| uncertain | 120 | uncertain | 无法确定前端的有效契约 |

表中的 missing/uncertain 是抽取状态，不是 JSON value 的字符串取值。评价器不能把所有“双端相等”判为成功，也不能把未抽取到的标签补成真值。单条事实 consistent 不等于整包成功；整包仍按第 13 节全部条件判定。

### 19.5 旧版迁移要求

从原 1.x 规范迁移时，为每个旧 Fact 从已确认的 statement/state/需求中逐条标注 gold_label；禁止按模型输出补标签。同步更新所有交换文件 schema_version 为 2.0.0、创建新的 dataset_version、更新适配器与校验器，并重新生成输入/答案摘要及冻结记录。旧文件与旧结果保留，不能仅改 schema_version 让缺字段数据通过。

本次修改只更新 Markdown 规范及其中的标签示例，不声称已经为完整 30 步发行包生成并复核全部原子标签。后续制作数据时，完整标签是必需交付物，未齐全不得开始正式实验。

## 20. 冻结流程与实验配置

### 20.1 阶段与访问控制

| 阶段 | 输入状态 | 必要动作 | 可使用的需求链 |
| --- | --- | --- | --- |
| 编制 | draft | 填写完整输入、答案、来源，执行模式/差异/来源/语义检查 | 全部；不得据测试输出调参 |
| 开发试验 | frozen，pilot 记录 | 固定输入与答案；确定生成参数和评价流程，保存报告 | dev 两链，共 6 步 |
| 正式准备 | 新版 ready，随后 frozen | 固定最终方法、代码、模型参数；核验报告；计算最终摘要 | 预登记 test 八链，共 24 步 |
| 正式评测 | frozen，formal 记录 | 隔离答案后生成；生成结束后交由独立评价进程读取答案 | test |

同一版本从 ready 转为 frozen 时，先写最终输入状态，再计算摘要，最后原子写入 lock。试验后若内容或方法模板改变，建立新版本，不能覆盖 pilot 冻结记录。没有开发试验报告时只能保留编制材料或 pilot 计划，不能伪造 formal 的 `pilot_report_sha256`。

冻结器与评价器可读 answers；生成进程仅挂载 inputs、所需 sources 和经过筛选的公开配置。只在提示词中告知“不要读答案”不满足 D012。生成日志、缓存键值、检索索引和共享目录同样受边界约束。完整编排模式必须另建输入投影，剔除预定 new_versions 和参考事实，不能直接把整个 benchmark.json 交给模型。

### 20.2 protocol 与 model_configs 的填写规则

以下是开放对象内部的约定字段，不代表已运行配置。

| 对象字段 | 必须填写的实际内容 |
| --- | --- |
| protocol.experiment_level | `pack` 或 `orchestration`；不得混合为同一方法结果 |
| protocol.methods | 实际方法 ID 及其输入范围、模板定位、生成和后处理说明 |
| protocol.repeats | 正整数；必须在查看 test 结果前确定 |
| protocol.planned_units | pack 模式 formal 为 `24 × 方法数 × repeats`；pilot 为 `6 × 方法数 × repeats` |
| protocol.primary_endpoint | 主指标 C 的聚合方式，以及成功率、失败率的联合报告规则 |
| protocol.exclusions | 只可登记技术上无法执行的明确情形；失败不从成功率分母移除 |
| protocol.adjudication | 自动评价和人工复核流程、分歧解决方式、是否盲化方法标签 |
| model_configs.<method_id> | provider、model、temperature、top_p、输出长度限制、timeout、retry_limit、seed 是否支持及实际值 |

模型不支持的参数以明确 null 加说明表示，不宣称已经生效；严禁把待定模型名或零哈希当作正式配置。每个计划单位只计一次，技术重试记录在该单位下，不作为新成功样本；采用哪个尝试的结果必须在运行前固定，不能选最高分结果。

### 20.3 哈希与离线来源

`source_hashes` 必须覆盖 sources/manifest.json、被引用源文件、许可证以及复现所需的额外来源。manifest 内每个文件摘要按原始字节计算，路径使用 `/` 分隔。`code_hashes` 覆盖生成器、适配器、提示模板、规则基线、评价代码与实际依赖锁文件。答案来源文件若另存于专属目录，同样进入相应冻结覆盖范围但不可向生成阶段暴露。

源码 HTTPS 获取失败时不应改用浮动分支补位。应修复获取或保留阻断状态，并记录缺失项。冻结摘要用于验证完整性，不证明语义正确；仍需独立的事实审阅。

## 21. 校验实施与验收用例

校验按“解析→结构→引用→状态差异→来源→语义→访问隔离→冻结”顺序运行。前置失败可以阻止后续检查，但报告需区分失败与未执行，不得将未执行写为通过。D009、D011 和 D014 的语义部分需要人工或经过复核的评价，不可仅凭程序无异常即宣布完成。

| 用例 | 预期结果 | 关联规则 |
| --- | --- | --- |
| gold_label 缺失，或 max_length 真值与 statement 不一致 | error；阻止实验 | D011、D015 |
| 评价器加载的 answer_sha256 与冻结记录不一致 | error；拒绝判分 | D013、D015 |
| JSON 同一对象出现两次 title 键 | 解析失败，不能以最后一个值覆盖通过 | D001 |
| 任一链 2 步或 4 步，或 step_id 重复 | error | D002 |
| chain-03 被标为 dev | error | D003 |
| 答案遗漏 c10-s2 | error | D004 |
| 第二步 old_versions 与第一步 new_versions 不同 | error | D005 |
| 变更集漏记 description 的上限变化 | error | D006 |
| 回退时资产 version 从 3 降为 2 | error | D007 |
| SourceRef 使用 main，或离线字节摘要不符 | error | D008 |
| 一条事实同时声明“整数、必填、1—100” | 语义拆分后才能通过 | D009 |
| c10-s2 的事实 required_sides 含 frontend | error | D010 |
| c03-s3 答案误恢复普通用户 403 | error | D011 |
| 生成工作目录能打开 answers 或评价缓存 | error，即使消息未直接拼入答案 | D012 |
| 输入状态从 ready 改 frozen 后未重算摘要 | error | D013 |
| 设计情景被标为 repository_history 且无证据 | error | D014 |
| title/description 中包含 emoji，证据偏移按 UTF-16 计算 | 定位核验失败 | D001、评价接口 |
| 缺后端提示但 C 被记作有效零矛盾成功 | 评价结果无效 | 第 13、19 节 |

单条校验报告示例：

```json
{
  "rule_id": "D006",
  "severity": "error",
  "json_pointer": "/chains/0/steps/1/pack_input/change_sets",
  "message": "api_contract 的 description.max_length 从 255 变为 500，但 change_sets 未包含对应修改。"
}
```

结构检查全部通过后方可进行语义签核；所有 error 清零且人工复核完成才能置 ready。冻结前另执行隔离与摘要检查。校验报告必须记录校验器版本和执行时间，并作为发行说明的伴随产物保存，不能把报告内容塞进封闭的 Dataset 根对象。

## 22. 交付清单与当前完成情况

### 22.1 数据发行包的必需材料

| 材料 | 合格要求 |
| --- | --- |
| inputs/benchmark.json | 10 链、30 步、完整连续快照与准确变更集，无评价标签 |
| answers/benchmark.json | 30 步完整测试真值：逐事实 gold_label、原子命题、必要端及来源；经复核冻结，评价器可读、生成阶段隔离 |
| sources/manifest.json 与离线源码 | 固定提交、有效行号、完整摘要、安全路径 |
| sources/LICENSE | 原始 MIT 许可证和版权文字 |
| locks/<dataset-version>.json | 实际配置、代码摘要、输入与答案摘要；formal 关联真实 pilot 报告 |
| README 或发行说明 | 目录用途、版本、准备/验证/运行步骤与访问边界 |
| 校验与复核记录 | D001—D015 状态、阻断项、语义复核者及签核时间 |
| 适配记录 | 目标运行器版本、映射、无法支持的字段及适配后摘要 |

### 22.2 本文交付状态

本次已将标签明确作为测试真值，补全标签结构、真值与实测值的对照规则及版本迁移要求；并已完成规范内容补充、指定提交的核心源码静态核验、30 步需求设计、状态差异语义、评价结果字段、单端判定、统计口径、冻结程序及验收规则的填写。

本次未生成完整 JSON 数据发行包，未实施目标运行器适配，未完成独立人工答案复核，未运行 pilot/formal 实验。上述工作属于规范落地与实验执行，不是可以凭文档编写替代的事实。投入正式评测前必须按 22.1 的清单制作并验收；不得将“文档填写完成”等同于“数据已冻结可运行”。
