# Monoplanner 数据集 v2 开发集盲审需求

## 目的

v2 数据集将事实分为两类：

- `must_be_explicit`：必须在适用的前端或后端提示中明确出现。
- `derivable`：继承的当前契约事实，可由其他明确事实推导，不因没有逐字重复而判定为漏项。

本轮只审阅 `must_be_explicit` 事实。共有 12 个匿名提示包、82 个事实判定项，来自两条开发链的 6 个步骤，比较规则基线和联合生成。

## 需要填写的内容

解压文件后：

1. 阅读 `packets.json`。
2. 使用 `reviews.template.json` 作为模板。
3. 为每个 packet 中的每个 `fact_id` 填写一次审阅结果。
4. 填写完成后将文件保存为 `reviews.json`。
5. 将 `reviews.json` 发回。

不要打开、修改或提交 `blind-key.json`。该文件包含方法身份映射，审阅完成前必须保持盲化。

## 判定标签

每个事实只能使用以下一个标签：

| 标签 | 判定标准 |
| --- | --- |
| `consistent` | 所有 `required_sides` 均明确表达事实，且前后端要求可以同时成立 |
| `contradiction` | 前端和后端对同一事实给出不能同时成立的要求 |
| `omission` | 至少一个必要端没有明确表达该事实 |
| `uncertain` | 现有提示内容不足以稳定判断 |
| `common_error` | 前后端彼此一致，但共同违背目标事实 |

`derivable` 事实无需加入 assessment，也不应因为未逐字出现而标记为 `omission`。

## 证据要求

每条 assessment 必须有非空 `explanation`。

证据格式：

```json
{
  "side": "frontend",
  "start": 10,
  "end": 35,
  "quote": "与 prompt 原文完全一致的片段"
}
```

规则：

- `consistent`：为每个必要端提供至少一条证据。
- `contradiction`：必须提供前端和后端两端证据。
- `common_error`：必须提供前端和后端两端证据。
- `omission`、`uncertain`：可以没有证据，但 explanation 必须说明原因。
- `start`、`end` 使用 Python 字符位置的半开区间 `[start, end)`。
- `quote` 必须逐字匹配对应 prompt 的指定区间。

## 顶层字段

保持以下字段格式：

```json
{
  "schema_version": "requirement-review-v1",
  "reviewer": "审阅者姓名或稳定标识",
  "human_attestation": true,
  "reviews": []
}
```

完成全部 12 个 packet 后才将 `human_attestation` 设置为 `true`。不要修改 `blind_id`、`pack_sha256` 或事实 ID。

## 返回内容

只需返回：

```text
reviews.json
```

不需要返回 `blind-key.json`，也不需要重新调用模型。收到审阅文件后将计算：

- `C_evaluable`
- `C_observed`
- 可评价率
- 严格成功率
- 漏项率、不确定率和共同错误率
- `rule` 与 `joint` 的配对差异
