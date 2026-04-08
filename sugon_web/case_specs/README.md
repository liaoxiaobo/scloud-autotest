# Case Specs

该目录用于存放可被程序读取的测试用例资产，而不是可执行测试代码。

建议分类：

- `prompts/`：AI 生成脚本或失败分析时使用的提示词
- `templates/`：可复用的 Markdown 模板
- 业务域目录：如 `compute/`、`storage/`、`network/`、`database/`、`backup/`

后续如果要实现“读取 md 用例 + 提示词自动生成 pytest 用例”，输入材料统一放在这里。
