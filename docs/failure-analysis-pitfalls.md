# 测试失败 AI 分析方案落地复盘（阶段 1~2）

> 记录目的：沉淀阶段 1、阶段 2 落地过程中遇到的典型问题、设计取舍与解决方案，便于后续阶段复盘，并帮助团队工程师快速理解方案边界与注意事项。

---

## 1. 概述

本方案旨在将 AI 失败分析能力集成到 Jenkins CI/CD 流水线中，分阶段实现：

- **阶段 1**：在 Jenkins post 阶段调用 AI 分析脚本，生成报告并归档，飞书通知附带摘要。
- **阶段 2**：建立规则分类、相似聚合、LLM 根因分析和结构化报告能力，降低 LLM 调用成本。

本文为阶段 1~2 的问题复盘。

---

## 2. 典型问题与解决方案

### 2.1 Windows 上 `python3` 命令异常

**现象**

在 Git Bash 或 PyCharm 终端执行：

```bash
python3 .\sugon_web\tools\failure_analysis_cli.py --results-dir allure-result --dry-run
```

直接返回 `exit code 49`，没有任何有效输出。

**原因**

Windows 上 `python3` 被解析为 `C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python3`，这是 Microsoft Store 的 wrapper，不是真正的 Python 解释器。

**解决方案**

- 本地验证时使用完整 Python 路径：

  ```bash
  "/d/Program Files/Python312/python" .\sugon_web\tools\failure_analysis_cli.py --results-dir allure-result --dry-run
  ```

- 在 `failure_analysis_cli.py` 脚本开头增加 `sys.path` 自举，支持直接运行：

  ```python
  import sys
  from pathlib import Path

  _PROJECT_ROOT = Path(__file__).resolve().parents[2]
  if str(_PROJECT_ROOT) not in sys.path:
      sys.path.insert(0, str(_PROJECT_ROOT))
  ```

**复盘要点**

- 团队内 Windows 环境调试 CLI 工具时，应优先使用完整 Python 路径或 `python -m` 方式运行。
- 脚本自身应具备路径自举能力，避免依赖外部 `PYTHONPATH` 配置。

---

### 2.2 直接运行 CLI 报 `ModuleNotFoundError: No module named 'sugon_web'`

**现象**

直接运行子目录下的脚本时：

```bash
python3 .\sugon_web\tools\failure_analysis_cli.py ...
```

报错找不到 `sugon_web` 包。

**原因**

Python 执行脚本时，会把脚本所在目录加入 `sys.path`，但不会把项目根目录加入。因此 `sugon_web/tools/` 能被找到，但 `sugon_web` 这个包无法被识别。

**解决方案**

在 `failure_analysis_cli.py` 开头动态把项目根目录加入 `sys.path`（见 2.1）。

**复盘要点**

- 项目内所有以包形式组织的 CLI 脚本，都应考虑入口点的路径自举。
- 使用 `python -m sugon_web.tools.failure_analysis_cli` 也能避免此问题，但对用户不够直观。

---

### 2.3 Allure result.json 重复导致用例数翻倍

**现象**

Jenkins 上生成的 AI 报告显示用例数是 Allure 报告的 2 倍。

**原因**

Jenkinsfile 在 `post` 阶段合并各环境 `allure-result/env-*` 子目录到根目录：

```groovy
for d in allure-result/env-*; do
    cp -rn "$d"/* allure-result/ || true
done
```

`cp -rn` 保留了原子目录，同时把文件复制到根目录。`collector.py` 使用 `rglob("*-result.json")` 递归查找，会同时扫到根目录和子目录下的同一份 `result.json`。

**方案对比**

| 方案 | 位置 | 优点 | 缺点 |
|---|---|---|---|
| A | `collector.py` 按 `historyId` 去重 | 通用，兼容本地和 Jenkins，兼容 Allure retry | 增加 collector 职责，本地调试本来不会重复 |
| B | `Jenkinsfile` 合并后删除子目录 | 精准修复问题现场，collector 保持简单 | 本地无此问题，无需修改；Allure retry 场景仍需单独处理 |

**最终选择**

**方案 B：回退 `collector.py` 的去重逻辑，保持 Jenkinsfile 现有合并逻辑。**

原因：本地调试不会产生 `env-*` 子目录，因此去重逻辑在本地场景下非必要；Jenkins 侧的重复问题应由产生重复的 Jenkinsfile 合并逻辑负责，而不是下沉到数据收集层。保持 `collector.py` 职责单一，只做"收集"一件事。

> 注意：如果后续开启 Allure retry 或出现其他多结果文件场景，需要重新评估是否在 `collector.py` 增加去重。

**复盘要点**

- 多环境并行执行时，产物合并逻辑必须考虑去重。
- `rglob` 递归收集时要意识到可能扫到重复文件。
- 修复问题时应优先在"问题发生处"处理，避免把流程层问题下沉到数据层。

---

### 2.4 Jenkins Credentials ID 不匹配

**现象**

Jenkins 构建在 AI 分析阶段报错：

```text
CredentialNotFoundException: Could not find credentials entry with ID 'dashscope-api-key'
```

**原因**

Jenkinsfile 中同时引用了两个 Credentials：

```groovy
withCredentials([
    string(credentialsId: 'dashscope-api-key', variable: 'DASHSCOPE_API_KEY'),
    string(credentialsId: 'deepseek-api-key', variable: 'DEEPSEEK_API_KEY')
]) { ... }
```

但 Jenkins 上只配置了 `deepseek-api-key`，导致 `withCredentials` 查找失败。

**解决方案**

改为只引用实际配置的 Credentials：

```groovy
withCredentials([
    string(credentialsId: 'deepseek-api-key', variable: 'DEEPSEEK_API_KEY')
]) { ... }
```

同时 CLI 参数 `--provider deepseek`。

**复盘要点**

- `withCredentials` 中任意一个 ID 不存在都会整体失败。
- 新增 Credentials 时必须同步更新 Jenkinsfile，并确保 Jenkins 上已创建对应 ID。
- 建议统一 provider，减少 Credentials 管理复杂度。

---

### 2.5 Jenkinsfile 中 `$dir` 变量未定义

**现象**

修改后的 Jenkinsfile 使用路径：

```groovy
sh '''
    python3 $dir/sugon_web/tools/failure_analysis_cli.py ...
'''
```

但 `$dir` 未在脚本中定义，执行时会被替换为空字符串，导致命令路径错误。

**原因**

混用了 Groovy 变量和 Shell 变量。Jenkinsfile 中定义的是 `workspaceDir = "$workspace"`，而不是 `$dir`。

**解决方案**

使用相对路径：

```groovy
sh '''
    python3 sugon_web/tools/failure_analysis_cli.py ...
'''
```

因为 `docker.image().inside()` 默认把工作区挂载到容器内的相同路径，当前目录就是项目根目录。

**复盘要点**

- Jenkinsfile 中 `sh '''...'''` 使用单引号时，不会进行 Groovy 变量插值。
- 容器内执行命令时，优先使用相对路径，避免依赖未定义的变量。

---

### 2.6 LLM 输出格式不稳定

**现象**

LLM 返回的内容有时被 markdown 代码块包裹：

```text
```json
{ "root_cause": "..." }
```
```

有时又是纯文本，导致 JSON 解析失败。

**原因**

不同模型、不同提示词下，LLM 输出格式不一致。

**解决方案**

在 `analyzer.py` 中增加输出清洗和兜底解析：

```python
def _strip_markdown_code_block(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()

def parse_analysis_response(content: str) -> dict:
    content = _strip_markdown_code_block(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "root_cause": content[:300],
            "confidence": "低",
            "evidence": ["LLM 返回非 JSON，已按原文兜底解析"],
            "exclusions": [],
            "short_term_fix": "请人工复核 LLM 输出",
            "long_term_fix": "",
        }
```

**复盘要点**

- 所有对接 LLM 的自动化工具，都必须做输出格式清洗和兜底。
- 提示词中要求"严格按 JSON 输出"不能保证 100%  compliance。
- 兜底解析要明确标注置信度为"低"，避免误导。

---

### 2.7 规则分类与 LLM 直通的边界

**现象**

阶段 2 验收标准要求"规则分类命中时不再调用 LLM"，但最初实现中 `classifier.py` 只做了分类，`analyzer.py` 仍对所有分类调用 LLM。

**原因**

分类和直通是两个独立步骤，初始实现遗漏了直通逻辑。

**解决方案**

在 `analyzer.py` 中定义规则直通集合：

```python
RULE_BASED_CATEGORIES = {FailureCategory.ENVIRONMENT}
```

`analyze_group()` 开头判断：

```python
if group.category in RULE_BASED_CATEGORIES:
    return build_rule_based_analysis(group)
# 否则调用 LLM
```

目前只有 `ENVIRONMENT` 分类直通，因为环境问题证据通常很明确（平台维护、503、SSH 不通等），LLM 分析价值低。用例问题和产品缺陷仍走 LLM。

**复盘要点**

- 规则分类的价值不仅是归类，还应体现在成本控制上。
- 不是所有分类都适合直通：环境问题适合，用例/产品问题需要更多上下文判断。
- 后续扩展直通分类时，改 `RULE_BASED_CATEGORIES` 即可。

---

## 3. 设计决策记录

### 3.1 为什么回退 `collector.py` 的去重逻辑

虽然 Jenkinsfile 合并脚本会产生重复，但最终选择回退 `collector.py` 的去重：

- 本地调试不会产生 `env-*` 子目录，去重逻辑在本地场景下无用。
- Jenkins 侧的重复问题应由产生重复的 Jenkinsfile 合并逻辑负责。
- 保持 `collector.py` 职责单一：只做数据收集，不做数据清洗。

如果后续出现 Allure retry 等真正需要数据层去重的场景，再重新评估。

### 3.2 为什么只有环境问题规则直通

- **环境问题**：关键词明确，结论稳定，LLM 重复分析成本高。
- **用例问题**：往往需要结合截图、trace、代码才能判断（如 locator 漂移、fill 静默失效）。
- **产品缺陷**：需要分析接口返回、后端状态，LLM 更有优势。

后续如果某些用例问题模式非常稳定（如已收录到 `case_library.md`），也可以加入直通集合。

---

## 4. 后续阶段注意清单

- [ ] 阶段 3 飞书通知增强时，注意 AI 摘要的 JSON 转义，避免破坏飞书消息体。
- [ ] 阶段 3 知识库闭环时，明确 `case_library.md` 的追加模板和审核流程。
- [ ] 阶段 4 历史趋势看板时，持久化 `failure-report.json`，并考虑失败分类趋势统计。
- [ ] 任何新增 Jenkins Credentials 时，同步更新 Jenkinsfile 和本文档。
- [ ] 扩展 `RULE_BASED_CATEGORIES` 时，补充相应规则和验证用例。

---

## 5. 相关文件

| 文件 | 作用 |
|---|---|
| `sugon_web/tools/failure_analysis_cli.py` | Jenkins/本地统一 AI 分析入口 |
| `sugon_web/tools/failure_analysis/collector.py` | Allure 结果、日志、截图、trace 收集 |
| `sugon_web/tools/failure_analysis/classifier.py` | 环境/用例/产品缺陷规则分类 |
| `sugon_web/tools/failure_analysis/aggregator.py` | 相似失败聚合 |
| `sugon_web/tools/failure_analysis/analyzer.py` | LLM 根因分析与规则直通 |
| `sugon_web/tools/failure_analysis/reporter.py` | Markdown/JSON 报告生成 |
| `sugon_web/tools/failure_analysis.md` | AI 分析提示词 |
| `Jenkinsfile` | CI/CD 流水线主配置 |
| `docs/failure-analysis-design.md` | 方案设计文档 |
