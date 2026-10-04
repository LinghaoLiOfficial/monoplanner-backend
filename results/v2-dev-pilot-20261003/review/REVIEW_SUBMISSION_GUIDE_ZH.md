# v2 开发集盲审说明

本轮共有 12 个匿名提示包。使用 `packets.json` 和 `reviews.template.json` 完成审阅，
不要打开 `blind-key.json`。

每个 packet 只列出 `must_be_explicit` 事实。每个事实必须填写一次：

- `consistent`：适用端均明确表达事实，且要求可同时成立。
- `contradiction`：前后端对同一事实给出不能同时成立的要求。
- `omission`：至少一个适用端没有表达必须显式事实。
- `uncertain`：证据不足以判断。
- `common_error`：两端一致但共同偏离目标事实。

`consistent` 必须引用每个 `required_sides` 的原文；`contradiction` 和 `common_error` 必须
引用前端和后端原文。引用使用 prompt 的 Python 字符位置半开区间 `[start, end)`，`quote`
必须逐字匹配。

填写完成后，将文件保存为同目录的 `reviews.json`。顶层必须保留：

```json
{
  "schema_version": "requirement-review-v1",
  "reviewer": "审阅者姓名或稳定标识",
  "human_attestation": true
}
```
