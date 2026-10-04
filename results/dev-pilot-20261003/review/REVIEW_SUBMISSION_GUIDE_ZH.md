# 开发集盲审提交说明

## 提交文件

以 `reviews.template.json` 为基础填写，保存为同目录的 `reviews.json`。

审阅时使用 `packets.json`；该文件中每个 `packet-###` 是一个随机化的提示包。
审阅完成前不得打开 `blind-key.json`，以避免方法身份影响判定。

## 顶层字段

填写以下字段：

```json
{
  "schema_version": "requirement-review-v1",
  "reviewer": "审阅者姓名或稳定标识",
  "human_attestation": true
}
```

`schema_version` 不修改。`human_attestation` 仅在全部包完成审阅后设为 `true`。

## 每个事实的判定

每个 `packet-###` 必须保留全部 `assessments` 条目；每个 `fact_id` 恰好出现一次。
`facts` 中的 `target`、`value` 和 `sources` 定义该事实的期望状态。根据同一
packet 的 `frontend_prompt` 与 `backend_prompt` 判断下列 `label` 之一：

| 标签 | 定义 | 对主指标的影响 |
| --- | --- | --- |
| `consistent` | 两端指令均与该事实相容，且没有相互排斥的实现要求 | 不增加 `C` |
| `contradiction` | 两端对同一操作和状态提出不能同时成立的要求 | 每个 `fact_id` 最多使 `C` 加一 |
| `omission` | 一个或多个必要端没有覆盖该事实，无法确认同步状态 | 该包不可有效评价 |
| `uncertain` | 表述不足以稳定判断相容性或矛盾性 | 该包不可有效评价 |
| `common_error` | 两端相互一致，但共同违背事实目标 | 不增加 `C`，但不能计为有效零矛盾包 |

不得因同一事实在文本中重复出现而重复计数。没有前端和后端原文证据时，不得填写
`contradiction` 或 `common_error`。

## 证据字段

每条 assessment 填写非空 `explanation`。`evidence` 的每一项结构如下：

```json
{
  "side": "frontend",
  "start": 0,
  "end": 18,
  "quote": "与原提示完全一致的片段"
}
```

`side` 只能是 `frontend` 或 `backend`。`start` 和 `end` 是对应提示字符串按 Python
Unicode 字符位置计算的半开区间 `[start, end)`；`quote` 必须与该区间逐字一致。

证据规则：

- `consistent`：每个 `required_sides` 均至少提供一条证据。
- `contradiction` 与 `common_error`：前端和后端各至少提供一条证据。
- `omission` 与 `uncertain`：可不提供文本证据，但 explanation 必须说明缺失或不确定的原因。

## 交付检查

提交前确认：

1. `reviews.json` 可被 JSON 解析。
2. 共 18 个 `packet-###`，且每个 packet 的 `pack_sha256` 未修改。
3. 所有事实均有一条 assessment，且没有重复 `fact_id`。
4. 每个 explanation 非空；所有 quote 与对应提示片段、位置完全一致。
5. 已完成所有包后才将 `human_attestation` 设为 `true`。

提交 `reviews.json` 后，评测器将验证哈希、证据位置和覆盖完整性，随后输出逐包 `C`、
总数、均值、全部计划单位为分母的有效零矛盾比例，以及方法和需求链汇总。
