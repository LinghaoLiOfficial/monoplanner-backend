# 测试集盲审提交说明

## 需要填写的文件

以 `reviews.template.json` 为基础填写，完成后保存为同目录的 `reviews.json`。
本轮共有 48 个随机化提示包和 688 个事实判定项。

审阅时只使用 `packets.json` 和 `reviews.template.json`。审阅完成前不得打开
`blind-key.json`，因为其中包含规则基线和 Monoplanner 联合生成的身份映射。

## 顶层字段

```json
{
  "schema_version": "requirement-review-v1",
  "reviewer": "审阅者姓名或稳定标识",
  "human_attestation": true
}
```

`schema_version` 不修改。全部事实完成后才将 `human_attestation` 设为 `true`。

## 判定标签

每个 `fact_id` 必须恰好判定一次：

| 标签 | 判定条件 |
| --- | --- |
| `consistent` | 所有必要端均覆盖该事实，且指令可同时成立 |
| `contradiction` | 两端对同一操作和状态给出不能同时成立的事实 |
| `omission` | 一个或多个必要端没有覆盖该事实 |
| `uncertain` | 文本不足以稳定判断是否一致 |
| `common_error` | 两端彼此一致，但共同违背目标事实 |

同一事实的重复句子只计一次。`contradiction` 和 `common_error` 必须同时提供前端和
后端原文证据；没有双端证据时不得使用这两个标签。

## 证据格式

```json
{
  "side": "frontend",
  "start": 0,
  "end": 18,
  "quote": "与对应提示完全一致的片段"
}
```

字符位置使用半开区间 `[start, end)`。`quote` 必须与对应 `frontend_prompt` 或
`backend_prompt` 的该区间逐字一致。`consistent` 必须覆盖每个 `required_sides`；
`omission` 和 `uncertain` 可无引用，但 `explanation` 必须说明原因。

## 完成条件

提交前确认 48 个 packet 全部保留、`pack_sha256` 未修改、688 个 assessment 均有
非空 explanation，且所有证据位置可精确匹配。完成的 `reviews.json` 用于计算逐包
矛盾数、严格成功率、可评价率、漏项率、不确定率、共同错误率和两种方法的配对差异。
