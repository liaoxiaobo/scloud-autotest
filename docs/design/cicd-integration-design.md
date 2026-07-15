# 测试失败结果分析与 CI/CD 集成方案设计

## 1. 文档信息

| 项 | 内容 |
|---|---|
| 目标 | 在 SugonCloud Playwright 自动化测试项目中，建立可落地的失败结果分析能力，并集成到现有 Jenkins CI/CD 流水线 |
| 适用范围 | `D:\playwright-sugon` 项目，覆盖 Web UI 自动化测试的失败根因分析、报告生成与通知 |
| 当前分支 | `feature/role-based-testing` |
| 关键文件 | `Jenkinsfile`、`sugon_web/tools/failure_analysis_cli.py`、`sugon_web/tools/failure_analysis.md`、`sugon_web/tools/llm_api_demo.py`、`sugon_web/conftest.py`、`.claude/skills/test-failure-analysis/SKILL.md` |

---

## 2. 背景与现状

### 2.1 项目背景

本项目是基于 Python + Playwright + Pytest 的 SugonCloud Web UI 自动化测试框架，覆盖 ECS/EVS/VPC/NAT/SLB/数据库/中间件/备份等服务。测试通过 SSH 做后端验证，使用 Allure 生成测试报告，Jenkins + Docker 执行 CI/CD。

### 2.2 现有能力盘点

| 能力 | 现状 | 位置 |
|---|---|---|
| 失败现场捕获 | 测试失败时自动截图，并附加到 Allure；fixture 关闭前预截图；支持 Playwright tracing | `sugon_web/conftest.py::pytest_runtest_makereport` |
| 测试产物 | Allure `*-result.json`、pytest 日志（按 `run_id` 隔离）、PNG 截图 | `allure-result/{run_id}/`、`logs/{run_id}/`、`screenshots/` |
| AI 分析 CLI | `failure_analysis_cli.py` 已接入 Jenkins，可读取 Allure 结果并调用 DeepSeek/DashScope 生成结构化失败分析报告；提示词路径指向 `sugon_web/tools/failure_analysis.md` | `sugon_web/tools/failure_analysis_cli.py` |
| 提示词模板 | 已有 `failure_analysis.md`，包含角色定位、三分类、输出格式与约束 | `sugon_web/tools/` |
| LLM API 示例 | 新增 `llm_api_demo.py`，演示 DeepSeek API 调用 | `sugon_web/tools/llm_api_demo.py` |
| 失败分析 Skill | 已有 `/test-failure-analysis` Skill，提供结构化根因分析流程和案例库 | `.claude/skills/test-failure-analysis/` |
| CI/CD | Jenkins + Docker + Allure Report + 飞书基础通知 | `Jenkinsfile` |
| 历史案例库 | 已收录 4 种典型失败模式 | `.claude/skills/test-failure-analysis/references/case_library.md` |

### 2.3 当前缺口

1. 飞书通知需要增强，附带测试执行概览和 AI 报告链接。
2. 失败分析缺少**规则分类**和**相似聚合**，LLM 调用存在重复和浪费。
3. 没有失败知识库的持续沉淀机制。
4. `sugon_web/tools/failure_analysis.md` 与 `/test-failure-analysis` Skill 的能力未完全打通（尤其是证据等级、置信度规则、历史案例库）。

---

## 3. 设计目标

### 3.1 总体目标

建立“**自动化批量分析 + 人工深度分析 + 知识库沉淀**”三位一体的失败结果分析能力，并嵌入现有 CI/CD 流水线，使测试失败能够被快速、准确地归类和定位。

### 3.2 具体目标

| 目标编号 | 目标描述 | 成功标准 |
|---|---|---|
| G1 | 每次 Jenkins 构建自动产出 AI 分析报告 | Jenkins post 阶段自动生成 `reports/ai-test-summary.md` 并归档 |
| G2 | 飞书通知附带测试执行概览 | 通知中包含总用例数、通过数、失败数、跳过数，并提供 AI 报告链接 |
| G3 | 失败被自动分类 | 每个失败至少被归类为：环境 / 用例 / 产品缺陷 |
| G4 | 相似失败自动聚合 | 相同根因的失败合并为一条，减少重复分析 |
| G5 | 关键失败支持人工深度分析 | 工程师可通过 `/test-failure-analysis` 对疑难失败做深度根因定位 |
| G6 | 知识库持续沉淀 | 典型失败模式定期回写到 `case_library.md`，提升自动化分析准确率 |

---

## 4. 总体架构

### 4.1 三层架构

```text
┌─────────────────────────────────────────────────────────────┐
│                     展示层（Presentation）                    │
│   Allure 报告详情页  /  飞书通知  /  Jenkins Artifacts       │
├─────────────────────────────────────────────────────────────┤
│                     分析层（Analysis）                       │
│   规则分类器  →  相似聚合器  →  LLM 根因推断  →  建议生成    │
├─────────────────────────────────────────────────────────────┤
│                     数据层（Data）                           │
│   Allure result.json  +  日志  +  截图  +  Playwright trace  │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 数据流

```text
pytest 执行测试
    ↓
Allure result.json / 日志 / 截图 / trace
    ↓
collector.py 收集并解析
    ↓
classifier.py 规则分类
    ↓
aggregator.py 相似聚合
    ↓
llm_client.py 调用模型（DeepSeek / DashScope）
    ↓
reporter.py 生成报告（Markdown + JSON）
    ↓
Jenkins 归档 / Allure 展示 / 飞书通知
```

---

## 5. 失败分析引擎设计

### 5.1 模块划分

推荐新增 `sugon_web/tools/failure_analysis/` 模块，并通过 `failure_analysis_cli.py` 作为 Jenkins/本地统一调用入口。

```text
tools/
├── failure_analysis_cli.py                # Jenkins/本地统一调用入口
├── failure_analysis.md                    # 自动化根因分析提示词（已从 case_specs/prompts/ 迁移至此）
├── llm_api_demo.py                        # LLM API 调用示例
├── failure_analysis/                      # 新增
│   ├── __init__.py
│   ├── collector.py                       # 数据收集
│   ├── classifier.py                      # 规则分类
│   ├── aggregator.py                      # 相似聚合
│   ├── llm_client.py                      # 统一 LLM 调用
│   ├── reporter.py                        # 报告生成
│   └── knowledge_base.py                  # 知识库匹配与更新
```

### 5.2 数据收集（collector.py）

统一读取 Allure 结果、日志、截图和 trace：

```python
@dataclass
class FailureContext:
    case: TestCaseResult
    log_excerpt: str
    screenshot_path: Path | None
    trace_path: Path | None
    ssh_state: dict | None
    timestamp: datetime
```

收集来源：
- `allure-result/{run_id}/*-result.json`
- `allure-result/{run_id}/*-attachment.txt`（日志、失败信息、步骤日志）
- `allure-result/{run_id}/*-attachment.png`（截图）
- `traces/*.zip`（Playwright trace）
- `logs/{run_id}/pytest-*.log`（完整 pytest 日志）

### 5.3 规则分类（classifier.py）

采用“**规则优先，LLM 兜底**”策略，降低调用成本和延迟。

| 分类 | 判定规则示例 |
|---|---|
| 环境问题 | 响应体包含“系统升级中”、HTTP 503、SSH 连接失败、节点不可达 |
| 用例问题 | `AssertionError`、`TimeoutError`、元素定位失败、等待超时 |
| 产品缺陷 | 接口返回业务错误码、后端状态与 UI 不一致、功能未按预期执行 |
| 未知 | 规则无法覆盖，交给 LLM 推断 |

示例规则：

```python
def classify_failure(ctx: FailureContext) -> FailureCategory:
    msg = (ctx.case.status_message or "").lower()
    trace = (ctx.case.status_trace or "").lower()

    if "系统升级中" in msg or ("404" in msg and "html" in msg):
        return FailureCategory.ENV_MAINTENANCE
    if "timeout" in trace or "timeouterror" in trace:
        return FailureCategory.SCRIPT_TIMEOUT
    if "assertionerror" in trace:
        return FailureCategory.ASSERTION
    if "element not found" in trace or "could not find" in trace:
        return FailureCategory.SCRIPT_LOCATOR
    return FailureCategory.UNKNOWN
```

### 5.4 相似聚合（aggregator.py）

按以下维度分组，减少重复分析：

```python
def aggregate(failures: list[FailureContext]) -> list[FailureGroup]:
    groups = defaultdict(list)
    for f in failures:
        key = (
            f.category,
            extract_top_frame(f.case.status_trace),
            normalize_error_message(f.case.status_message),
        )
        groups[key].append(f)
    return [FailureGroup(...) for ... in groups.values()]
```

聚合收益：
- 同类失败只调用一次 LLM
- 飞书通知更简洁
- 便于识别批量环境问题（如平台升级导致大量 404）

### 5.5 LLM 调用（llm_client.py）

统一封装 DeepSeek / DashScope 调用，支持：
- 自动选择 provider 和 model
- 超时控制
- Token 用量统计
- 失败重试

统一封装 DeepSeek / DashScope 调用，provider/model 等配置由 `llm_client.py` 集中管理。
`llm_api_demo.py` 可作为接入新模型或调试时的参考示例。

### 5.6 报告生成（reporter.py）

输出多种格式：

| 格式 | 用途 | 示例路径 |
|---|---|---|
| Markdown | 人读报告 | `reports/ai-test-summary.md` |
| JSON | 下游系统消费 | `reports/failure-report.json` |
| Allure description | 在 Allure 详情页展示根因 | 追加到 `*-result.json` 的 `description` |

Markdown 报告结构：

```markdown
# AI分析报告
## 执行概览
- 总用例数：
- 通过：
- 失败：
- 跳过：
- 通过率：
## 失败分类统计
## 详细分析
### 1. 失败签名摘要
- **原始错误**：
- **分类**：
- **置信度**：
- **影响范围**：
#### 根因
#### 关键证据
- 【直接证据】...
- 【间接证据】...
- 【缺失证据】...（仅低置信度时出现）
#### 修复建议
- 短期：...
- 长期：...
```

### 5.7 自动化 Prompt 与交互式 Skill 的分工

自动化分析由 `failure_analysis_cli.py` 读取 `sugon_web/tools/failure_analysis.md` 作为 system prompt，批量生成失败概览；`/test-failure-analysis` Skill 则由工程师人工触发，对疑难失败做深度根因分析。两者不是替代关系，而是互补：

| 维度 | 自动化 Prompt | `/test-failure-analysis` Skill |
|---|---|---|
| 使用方式 | 被 `failure_analysis_cli.py` 读取为 system prompt | Claude Code 交互式 Skill |
| 运行时机 | CI/CD 自动化，批量生成 | 人工触发，单点深度分析 |
| 输入材料 | 受限于 CLI 预收集内容 | 主动读取 result.json、附件、代码、trace、案例库 |
| 分析深度 | 浅-中等 | 深，有完整 checklist |
| 可自动化 | 高 | 低 |
| 最适合场景 | 每次构建后的批量总结 | 疑难失败的根因定位 |

Prompt 优化方向：

1. **保留并强化三分类**：按 `环境问题 / 用例问题 / 产品缺陷` 分类，继续强化规则触发。
2. **补充证据等级**：明确 `trace > 截图 > 日志 > 代码 > 推断`。
3. **补充置信度规则**：高/中/低的判定条件。
4. **补充案例库上下文**：调用 LLM 前把 `case_library.md` 作为上下文输入。
5. **保留输出格式**：根因、关键证据（含缺失证据）、修复建议。

---

## 6. CI/CD 流水线集成

### 6.1 集成位置

在 Jenkins `post('Send Report') → always` 阶段，按以下顺序执行：

```text
1. 合并各环境 allure-result
2. 写入 environment.properties
3. 生成 AI 分析报告          ← 新增
4. 生成 Allure 报告
5. 归档 AI 报告 artifact     ← 新增
6. 发送飞书通知（含执行概览和 AI 报告链接）     ← 增强
7. 清理临时文件、镜像和工作区
```

> **关键注意点**：当前 `Jenkinsfile` 在 `allure()` 调用后清理了 `allure-result` 目录，AI 分析必须在清理之前执行。

### 6.2 Jenkinsfile 改造建议

在 `post('Send Report') → always` 中增加：

```groovy
// 1. 生成 AI 失败分析报告
script {
    try {
        docker.image("playwright-sugon:${env.IMAGE_TAG}").inside() {
            withCredentials([string(credentialsId: 'dashscope-api-key', variable: 'DASHSCOPE_API_KEY')]) {
                sh '''
                    python3 sugon_web/tools/failure_analysis_cli.py \
                        --results-dir allure-result \
                        --logs-dir logs \
                        --output reports/ai-test-summary.md \
                        --json-output reports/failure-report.json \
                        --provider deepseek \
                        --max-failures 100
                '''
            }
        }
    } catch (err) {
        echo "AI report generation failed: ${err}"
    }
}

// 2. 生成 Allure 报告
allure includeProperties: false, jdk: '', report: 'allure-report', results: [[path: 'allure-result']]

// 3. 归档产物
archiveArtifacts artifacts: 'reports/*.md', allowEmptyArchive: true

// 4. 发送飞书通知
script {
    if (params.FEISHU_NOTIFY) {
        sendNotification(currentBuild.currentResult)
    }
}

// 5. 清理工作区，避免历史 artifact 污染下次构建
deleteDir()
```

### 6.3 API Key 管理

使用 Jenkins Credentials 注入：

```groovy
withCredentials([
    string(credentialsId: 'dashscope-api-key', variable: 'DASHSCOPE_API_KEY'),
    string(credentialsId: 'deepseek-api-key', variable: 'DEEPSEEK_API_KEY')
]) {
    sh 'python3 sugon_web/tools/failure_analysis_cli.py ...'
}
```

### 6.4 飞书通知增强

在 `sendNotification` 中读取 AI 报告的执行概览，拼接为简洁通知内容：

```groovy
def aiSummary = ""
if (fileExists('reports/ai-test-summary.md')) {
    aiSummary = readFile('reports/ai-test-summary.md')
        .split('## 失败分类统计')[0]
        .take(400)
}

sh """
curl -X POST -H "Content-Type: application/json" \
    -d '{
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": "${env.JOB_NAME} #${env.BUILD_NUMBER}",
                    "content": [[
                        {"tag": "text", "text": "测试结果: ${result}\\n${aiSummary}\\n"},
                        {"tag": "a", "text": "查看 AI 分析报告", "href": "${env.BUILD_URL}artifact/reports/ai-test-summary.md/*view*/"},
                        {"tag": "text", "text": "\\n"},
                        {"tag": "a", "text": "查看 Allure 报告", "href": "${env.BUILD_URL}allure/"}
                    ]]
                }
            }
        }
    }' https://open.feishu.cn/open-apis/bot/v2/hook/...
"""
```

> 通知内容仅展示执行概览（总用例数 / 通过 / 失败 / 跳过 / 通过率），详细的根因分析和修复建议通过链接跳转到 AI 报告。

---

## 7. 实施路线图

### 阶段 1：接入现有 AI 总结（1-2 天）

**目标**：让 Jenkins 每次构建自动产出 AI 报告。

**任务**：
- [x] 在 `Jenkinsfile` post 阶段调用 `sugon_web/tools/failure_analysis_cli.py`
- [x] 将 `reports/ai-test-summary.md` 作为 Jenkins artifact 归档
- [x] 将 API Key 迁移到 Jenkins Credentials
- [x] 调整执行顺序：AI 分析在 Allure 报告生成和清理之前

**验收标准**：
- 每次构建产出 `ai-test-summary.md`，Jenkins 页面可通过 artifact 链接查看或下载
- AI 分析失败不影响 Allure 报告生成

### 阶段 2：增强分析引擎（3-5 天）

**目标**：建立规则分类、相似聚合和结构化报告。

**任务**：
- [x] 新建 `sugon_web/tools/failure_analysis/` 模块
- [x] 实现 `collector.py`、`classifier.py`、`aggregator.py`、`llm_client.py`、`reporter.py`
- [x] 新增 `failure_analysis_cli.py` 作为 Jenkins 调用入口
- [x] 优化 `sugon_web/tools/failure_analysis.md`，吸收 Skill 的证据等级、置信度规则和案例库上下文
- [x] 将 `case_library.md` 作为 prompt 上下文输入

**验收标准**：
- 自动报告包含失败分类、置信度、关键证据、修复建议
- 相似失败被聚合为一条
- 规则分类命中时不再调用 LLM

### 阶段 3：通知与闭环（2-3 天）

**目标**：飞书通知附带测试执行概览，建立知识库闭环。

**任务**：
- [ ] 增强 `sendNotification`，附带 AI 报告执行概览和报告链接
- [ ] 定义 `case_library.md` 追加模板
- [ ] 制定“高置信度结论回写知识库”的流程规范
- [ ] 可选：接入缺陷系统（Jira/Tapd/禅道）自动创建产品缺陷

**验收标准**：
- 飞书通知包含执行概览（总用例数 / 通过数 / 失败数 / 跳过数）和 AI 报告链接
- 测试团队能按规范将 Skill 分析结论沉淀到案例库

### 阶段 4：历史趋势与看板（可选，1-2 周）

**目标**：基于多次构建数据生成失败趋势。

**任务**：
- [ ] 持久化每次构建的 `failure-report.json`
- [ ] 生成失败分类趋势图、flaky 用例排行
- [ ] 可选：搭建 Web 看板或定期发送趋势邮件

---

## 8. 风险与成本控制

| 风险 | 影响 | 对策 |
|---|---|---|
| LLM 调用成本高 | 每次构建可能分析大量失败 | 规则分类优先、相似聚合、限制 `max-failures`、命中知识库不走 LLM |
| LLM 输出不稳定 | 报告质量波动 | 用 try-catch 包裹，失败不影响主流程；Prompt 强制输出格式 |
| Allure 产物被清理 | AI 分析无输入 | 调整 Jenkins 执行顺序，AI 分析在清理前执行 |
| 敏感信息泄露 | API Key 或日志泄露 | API Key 走 Jenkins Credentials；日志中脱敏处理 |
| 报告与事实不符 | 误导排障 | 要求每个结论引用证据；不确定时明确标注低置信度 |
| Skill 与自动化冲突 | 重复建设 | 明确分工：Skill 用于人工深度分析，Prompt + 脚本用于自动化 |

---

## 9. 落地实践与踩坑记录（动态更新）

本节记录在方案落地过程中遇到的实际问题、设计取舍与解决方案。随着阶段推进持续更新，既是团队经验沉淀，也可作为 AI 分析时的补充上下文。

### 9.1 Allure result.json 重复导致用例数翻倍

**现象**：Jenkins 上生成的 AI 报告显示用例数是 Allure 报告的 2 倍。

**原因**：Jenkinsfile 在 `post` 阶段合并各环境 `allure-result/env-*` 子目录到根目录时，使用 `cp -rn` 保留原子目录的同时把文件复制到根目录。`collector.py` 使用 `rglob("*-result.json")` 递归查找，同时扫到根目录和子目录下的同一份 `result.json`。

**解决方案**：在 Jenkinsfile 合并逻辑后删除 `env-*` 子目录，让根目录只保留一份结果；保持 `collector.py` 职责单一，只做收集不做去重。

**复盘要点**：
- 多环境并行执行时，产物合并逻辑必须考虑去重。
- `rglob` 递归收集时要意识到可能扫到重复文件。
- 修复问题时应优先在"问题发生处"处理，避免把流程层问题下沉到数据层。

### 9.2 LLM 输出格式不稳定

**现象**：LLM 返回的内容有时被 markdown 代码块包裹，有时又是纯文本，导致 `json.loads` 失败。

**原因**：不同模型、不同提示词下，LLM 输出格式不一致，即使 prompt 要求"严格按 JSON 输出"也无法 100% 保证。

**解决方案**：在 `analyzer.py` 中增加输出清洗和兜底解析：

- 先去除外层 markdown 代码块
- 再尝试 `json.loads`
- 失败时取前 300 字符作为根因，置信度强制标为"低"

**复盘要点**：
- 所有对接 LLM 的自动化工具，都必须做输出格式清洗和兜底。
- 兜底解析要明确标注低置信度，避免误导。

### 9.3 规则分类与 LLM 直通的边界

**现象**：阶段 2 验收标准要求"规则分类命中时不再调用 LLM"，但最初实现中 `analyzer.py` 仍对所有分类调用 LLM。

**原因**：分类和直通是两个独立步骤，初始实现遗漏了直通逻辑。

**解决方案**：在 `analyzer.py` 中定义规则直通集合：

```python
RULE_BASED_CATEGORIES = {FailureCategory.ENVIRONMENT}
```

环境类问题（平台维护、503、SSH 不通等）证据明确，直接生成分析结果；用例问题和产品缺陷仍走 LLM 深度分析。

**复盘要点**：
- 规则分类的价值不仅是归类，还应体现在成本控制上。
- 不是所有分类都适合直通：环境问题适合，用例/产品问题需要更多上下文判断。
- 后续扩展直通分类时，改 `RULE_BASED_CATEGORIES` 即可。

### 9.4 工作区清理与飞书通知顺序

**现象**：飞书通知显示"未生成 AI 摘要"，但 Jenkins artifact 页面能看到 `ai-test-summary.md`。

**原因**：`deleteDir()` 在 `sendNotification` 之前执行，工作区已被清空，`fileExists('reports/ai-test-summary.md')` 返回 false。

**解决方案**：调整 Jenkinsfile 执行顺序，先发送飞书通知，再清理工作区。

```text
生成 AI 报告 → 归档 artifact → 发送飞书通知 → deleteDir() → 清理镜像
```

**复盘要点**：
- `deleteDir()` 清理的是当前工作区，artifact 归档后文件仍存在于 Jenkins 插件存储中，但 `readFile` 读的是工作区路径。
- 任何需要读取工作区文件的后处理步骤，都必须在 `deleteDir()` 之前执行。

### 9.5 AI 报告链接的预览方式

**现象**：直接链接到 `.md` artifact 可能触发下载，体验不佳。

**决策**：使用 Jenkins 的 `/*view*/` 后缀链接，优先在浏览器中预览：

```text
${BUILD_URL}artifact/reports/ai-test-summary.md/*view*/
```

### 9.6 LLM 返回空内容导致根因缺失

**现象**：sugoncloud（Claude 兼容接口）返回的响应中 `content` 为空字符串，导致 `analyzer.py` 兜底解析后 `root_cause` 为空。AI 报告中对应失败组呈现如下残缺状态：

```markdown
### 2. AssertionError: 未找到名称为 '<IP>' 的数据行
- **原始错误**: AssertionError: 未找到名称为 '<IP>' 的数据行
- **分类**: 用例问题
- **置信度**: 低
- **影响范围**: 3 个用例（端口-创建和删除（手动分配-手动输入）, 端口-修改IP和MAC, 端口-批量删除）

#### 根因


#### 关键证据
- 【直接证据】LLM 返回非 JSON，已按原文兜底解析

#### 修复建议
- 短期：请人工复核 LLM 输出
```

可以看到"根因"字段完全为空，工程师无法从报告中获得任何有效分析结论。

**与 9.2 的区别**：9.2 是模型返回了非 JSON 文本（如 markdown 包裹、说明性文字），本次是模型**未返回任何有效内容**，属于更极端的输出失败。

**原因排查**：
- API 网关或代理层异常时可能返回空 body
- 模型对超长 prompt 或特殊输入未生成有效回复
- 当前 `_call_anthropic` 遍历 content blocks 取第一个 `text` 属性，若 blocks 为空或全部为非 text 类型，则返回空字符串

**解决方案**：
1. **Prompt 层**：在 `failure_analysis.md` 中增加 few-shot 输出示例，通过正向示例强化"只输出 JSON、不得为空"的约束。
2. **代码层兜底**：在 `analyzer.py` 中，当 `content.strip()` 为空时，将 `root_cause` 设置为更明确的文案（如"LLM 返回为空，需人工复核原始报错"），并保留原始错误信息作为证据。

**方案评估**：
- few-shot 示例对 Claude 模型有效性较高，能显著降低非 JSON 输出的概率
- 但无法完全解决 API 层或网关导致的空返回，因此代码层兜底必不可少
- 示例长度需控制，避免显著增加单次调用 token 成本

**复盘要点**：
- 任何 LLM 兜底逻辑都必须考虑"返回为空"的边界情况，而不仅是"返回非 JSON"
- 更换模型提供商后，需重新验证输出格式稳定性，不同模型的指令遵循能力存在差异

---

## 10. 附录

### 10.1 关键文件清单

| 文件 | 作用 |
|---|---|
| `Jenkinsfile` | CI/CD 流水线主配置 |
| `sugon_web/tools/failure_analysis_cli.py` | Jenkins/本地统一 AI 分析入口 |
| `sugon_web/tools/failure_analysis.md` | 自动化根因分析提示词模板 |
| `sugon_web/tools/llm_api_demo.py` | LLM API 调用示例 |
| `sugon_web/tools/failure_analysis/`（新增） | 失败分析引擎 |
| `sugon_web/conftest.py` | 失败截图、Allure 配置 |
| `.claude/skills/test-failure-analysis/SKILL.md` | 交互式失败分析 Skill |
| `.claude/skills/test-failure-analysis/references/case_library.md` | 历史失败案例库 |

### 10.2 置信度定义

| 置信度 | 条件 |
|---|---|
| 高 | 材料清单完整（result.json + 截图/日志 + 代码），关键证据互相印证，推断占比 ≤ 20% |
| 中 | 缺少 trace 或部分附件，但 result.json + 截图 + 代码 足够交叉验证，推断占比 ≤ 50% |
| 低 | 仅 result.json + 代码推断，缺少截图或关键日志，或推断占比 > 50% |

### 10.3 方案变更记录

记录方案设计层面的关键决策与变化，便于追溯设计演进过程。

| 日期 | 版本 | 变更内容 | 变更原因 |
|---|---|---|---|
| 2026-07-08 | v0.1 | 初始方案 | - |
| 2026-07-09 | v0.2 | 阶段 3 目标调整：飞书通知从"附带 Top 3 失败根因摘要"改为"附带执行概览和 AI 报告链接" | 当前能力已足够，避免通知过长 |
| 2026-07-09 | v0.3 | AI 分析报告标题改为"AI分析报告"；执行概览增加通过率（skipped 不计入分母） | 全部通过时标题更合理；明确通过率口径 |
| 2026-07-09 | v0.4 | Jenkinsfile 调整执行顺序：`sendNotification` 必须在 `deleteDir()` 之前 | 否则飞书通知会显示"未生成 AI 摘要" |
| 2026-07-09 | v0.5 | AI 报告链接使用 `/*view*/` 后缀；增加 Allure 报告链接；两个链接分行展示 | 提升通知中链接的可用性 |
| 2026-07-10 | v0.6 | 落地踩坑记录从独立文件收敛到设计文档第 9 章 | 统一经验沉淀入口，便于 AI 上下文消费 |
