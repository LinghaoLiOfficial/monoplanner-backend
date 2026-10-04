# 测试集盲审提交要求

## 目标

本轮测试已完成 48 个提示包：24 个测试需求变更分别由两种方法生成一次：

- `rule`：规则共享契约基线
- `joint`：Monoplanner 联合生成

当前已完成模型运行，但尚未完成语义盲审。因此 `C`、严格成功率、可评价率和两种方法的最终差异暂不能计算。

## 需要完成的文件

解压本目录后：

1. 阅读 `packets.json` 中的 48 个匿名提示包。
2. 以 `reviews.template.json` 为基础填写审阅结果。
3. 将填写后的文件保存为 `reviews.json`。
4. 将 `reviews.json` 发回。

不要打开、修改或提交 `blind-key.json`。该文件只用于评测器在审阅完成后恢复方法身份。

## 每个审阅项的填写要求

每个 packet 中的每个 `fact_id` 必须恰好保留一条 assessment。填写：

- `label`：只能使用 `consistent`、`contradiction`、`omission`、`uncertain` 或 `common_error`。
- `explanation`：说明为什么作出该判定，不能为空。
- `evidence`：引用提示中的原文，并填写准确的字符起止位置。

判定含义：

| 标签 | 含义 |
| --- | --- |
| `consistent` | 必要端均覆盖事实，且前后端要求可以同时成立 |
| `contradiction` | 前后端对同一操作和状态给出不能同时成立的要求 |
| `omission` | 必要端没有覆盖该事实 |
| `uncertain` | 信息不足，无法稳定判断 |
| `common_error` | 前后端彼此一致，但共同违背目标事实 |

`contradiction` 和 `common_error` 必须同时提供前端、后端两端证据。`consistent` 必须覆盖该事实的全部 `required_sides`。`omission` 和 `uncertain` 可以不提供证据，但必须在 `explanation` 中说明原因。

## 证据格式

```json
{
  "side": "frontend",
  "start": 10,
  "end": 35,
  "quote": "与提示原文完全一致的片段"
}
```

`start` 和 `end` 使用 Python 字符位置的半开区间 `[start, end)`。`quote` 必须逐字等于对应 prompt 在该位置的内容，不能改写、翻译或省略字符。

## 顶层字段

```json
{
  "schema_version": "requirement-review-v1",
  "reviewer": "审阅者姓名或稳定标识",
  "human_attestation": true,
  "reviews": []
}
```

保持 `schema_version` 不变。完成全部 48 个 packet 后，才将 `human_attestation` 设置为 `true`。不要修改任何 `blind_id` 或 `pack_sha256`。

## 返回文件

只需返回填写完成的：

```text
reviews.json
```

不需要返回 `blind-key.json`，也不需要重新运行模型。收到后将进行证据校验并生成最终指标报告。
