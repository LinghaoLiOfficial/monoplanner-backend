# v2.1 修正后开发集盲审需求

## 任务

审阅 12 个匿名提示包中的 82 个 `must_be_explicit` 事实。使用 `packets.json` 和
`reviews.template.json`，不要查看 `blind-key.json`。

本轮与前一轮使用相同事实，但联合生成提示已经修正，必须根据本轮新文本重新审阅，
不能直接复制上一轮对联合提示的判定。

## 标签

- `consistent`：所有 `required_sides` 均明确表达事实及具体值，且要求可同时成立。
- `contradiction`：前后端对同一事实给出不能同时成立的要求。
- `omission`：至少一个必要端未明确表达事实或具体值。
- `uncertain`：文本不足以稳定判断。
- `common_error`：两端一致，但共同违背目标事实。

每项必须填写非空 `explanation`。`consistent` 需要所有必要端证据；`contradiction` 和
`common_error` 需要前后端两端证据。证据 quote 必须与 `[start, end)` 指定的 prompt
原文逐字一致。

## 返回文件

完成后将 `reviews.template.json` 保存为 `reviews.json`。设置审阅者字段，并在全部完成
后设置 `human_attestation: true`。只需返回 `reviews.json`。
