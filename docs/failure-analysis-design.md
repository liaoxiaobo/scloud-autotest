# 测试失败结果分析与 CI/CD 集成方案设计

## 1. 文档信息

| 项 | 内容 |
|---|---|
| 目标 | 在 SugonCloud Playwright 自动化测试项目中，建立可落地的失败结果分析能力，并集成到现有 Jenkins CI/CD 流水线 |
| 适用范围 | `D:\playwright-sugon` 项目，覆盖 Web UI 自动化测试的失败根因分析、报告生成与通知 |
| 当前分支 | `feature/role-based-testing` |
| 关键文件 | `Jenkinsfile`、`sugon_web/tools/ai_report.py`、`sugon_web/tools/failure_analysis.md`、`sugon_web/tools/llm_api_demo.py`、`sugon_web/conftest.py`、`.claude/skills/test-failure-analysis/SKILL.md` |

---

## 2. 背景与现状

### 2.1 项目背景

本项目是基于 Python + Playwright + Pytest 的 SugonCloud Web UI 自动化测试框架，覆盖 ECS/EVS/VPC/NAT/SLB/数据库/中间件/备份等服务。测试通过 SSH 做后端验证，使用 Allure 生成测试报告，Jenkins + Docker 执行 CI/CD。

### 2.2 现有能力盘点

| 能力 | 现状 | 位置 |
|---|---|---|
| 失败现场捕获 | 测试失败时自动截图，并附加到 Allure；fixture 关闭前预截图；支持 Playwright tracing | `sugon_web/conftest.py::pytest_runtest_makereport` |
| 测试产物 | Allure `*-result.json`、pytest 日志（按 `run_id` 隔离）、PNG 截图 | `allure-result/{run_id}/`、`logs/{run_id}/`、`screenshots/` |
| AI 总结脚本 | 已存在 `ai_report.py`，可读取 Allure 结果并调用 DeepSeek/DashScope 生成 Markdown 总结；提示词路径指向 `sugon_web/tools/failure_analysis.md` | `sugon_web/tools/ai_report.py` |
| 提示词模板 | 已有 `failure_analysis.md`，包含角色定位、三分类、输出格式与约束 | `sugon_web/tools/` |
| LLM API 示例 | 新增 `llm_api_demo.py`，演示 DeepSeek API 调用 | `sugon_web/tools/llm_api_demo.py` |
| 失败分析 Skill | 已有 `/test-failure-analysis` Skill，提供结构化根因分析流程和案例库 | `.claude/skills/test-failure-analysis/` |
| CI/CD | Jenkins + Docker + Allure Report + 飞书基础通知 | `Jenkinsfile` |
| 历史案例库 | 已收录 4 种典型失败模式 | `.claude/skills/test-failure-analysis/references/case_library.md` |

### 2.3 当前缺口

1. `sugon_web/tools/ai_report.py` 尚未接入 Jenkins，AI 总结需要手动触发。
2. 飞书通知只有结果概览，缺少失败根因摘要。
3. 失败分析缺少**规则分类**和**相似聚合**，LLM 调用存在重复和浪费。
4. 没有失败知识库的持续沉淀机制。
5. `sugon_web/tools/failure_analysis.md` 与 `/test-failure-analysis` Skill 的能力未完全打通（尤其是证据等级、置信度规则、历史案例库）。

---

## 3. 设计目标

### 3.1 总体目标

建立“**自动化批量分析 + 人工深度分析 + 知识库沉淀**”三位一体的失败结果分析能力，并嵌入现有 CI/CD 流水线，使测试失败能够被快速、准确地归类和定位。

### 3.2 具体目标

| 目标编号 | 目标描述 | 成功标准 |
|---|---|---|
| G1 | 每次 Jenkins 构建自动产出 AI 失败分析报告 | Jenkins post 阶段自动生成 `reports/ai-test-summary.md` 并归档 |
| G2 | 飞书通知附带失败根因摘要 | 通知中包含 Top 3 失败根因分类和修复建议 |
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

推荐新增 `sugon_web/tools/failure_analysis/` 模块，**不改动现有 `sugon_web/tools/ai_report.py` 主流程**，保持向后兼容。

```text
tools/
├── ai_report.py                           # 已有，保持兼容
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

可复用现有 `sugon_web/tools/ai_report.py` 中的 provider 配置，或迁移到 `llm_client.py`。
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
# 测试执行摘要
## 执行概览
## 失败分类统计
## Top 失败根因
## 详细分析
### 用例 1
- 根因分类：
- 置信度：
- 关键证据：
- 排除项：
- 修复建议：
```

---

## 6. CI/CD 流水线集成

### 6.1 集成位置

在 Jenkins `post('Send Report') → always` 阶段，按以下顺序执行：

```text
1. 合并各环境 allure-result
2. 写入 environment.properties
3. 生成 AI 失败分析报告          ← 新增
4. 生成 Allure 报告
5. 归档 AI 报告 artifact          ← 新增
6. 发送飞书通知（含 AI 摘要）     ← 增强
7. 清理临时文件和镜像
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
                        --output reports/ai-test-summary.md \
                        --json-output reports/failure-report.json \
                        --provider dashscope \
                        --max-failures 8
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
archiveArtifacts artifacts: 'reports/*', allowEmptyArchive: true

// 4. 发送飞书通知
script {
    if (params.FEISHU_NOTIFY) {
        sendNotification(currentBuild.currentResult)
    }
}
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

在 `sendNotification` 中读取 AI 报告摘要：

```groovy
def aiSummary = ""
if (fileExists('reports/ai-test-summary.md')) {
    aiSummary = readFile('reports/ai-test-summary.md')
        .split('## 详细分析')[0]
        .take(800)
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
                        {"tag": "text", "text": "测试结果: ${result}\\nAI 摘要:\\n${aiSummary}\\n"},
                        {"tag": "a", "text": "查看报告", "href": "${env.BUILD_URL}"}
                    ]]
                }
            }
        }
    }' https://open.feishu.cn/open-apis/bot/v2/hook/...
"""
```

---

## 7. `/test-failure-analysis` Skill 与 Prompt 的分工融合

### 7.1 两者差异

| 维度 | `sugon_web/tools/failure_analysis.md` | `/test-failure-analysis` Skill |
|---|---|---|
| 使用方式 | 被 `ai_report.py` 读取为 system prompt | Claude Code 交互式 Skill |
| 运行时机 | CI/CD 自动化，批量生成 | 人工触发，单点深度分析 |
| 输入材料 | 受限于 `ai_report.py` 预收集内容 | 主动读取 result.json、附件、代码、trace、案例库 |
| 分析深度 | 浅-中等 | 深，有完整 checklist |
| 可自动化 | 高 | 低 |
| 最适合场景 | 每次构建后的批量总结 | 疑难失败的根因定位 |

### 7.2 融合策略

两者不是替代关系，而是**互补**：

```text
自动化层：ai_report.py + 优化后的 prompt  →  批量生成失败概览
         ↓
人工层：/test-failure-analysis Skill       →  对关键失败做深度根因分析
         ↓
知识库：case_library.md                    →  沉淀结论，反哺自动化层
```

### 7.3 Prompt 优化方向

把 Skill 中的核心方法吸收进 `sugon_web/tools/failure_analysis.md`：

1. **保留并强化三分类**：`failure_analysis.md` 已要求按 `环境问题 / 用例问题 / 产品缺陷` 分类，继续强化规则触发。
2. **补充证据等级**：明确 `trace > 截图 > 日志 > 代码 > 推断`。
3. **补充置信度规则**：
   - 高：材料完整，关键证据无矛盾
   - 中：缺少 trace 但可交叉验证
   - 低：仅 result.json + 代码推断
4. **补充案例库上下文**：调用 LLM 前把 `case_library.md` 作为上下文输入。
5. **保留输出格式**：结论、关键证据、排除项、修复建议。

### 7.4 知识库闭环

```text
1. 新失败出现
2. 工程师用 /test-failure-analysis 做深度分析
3. 高置信度结论按模板追加到 case_library.md
4. ai_report.py 下次运行时读取 case_library.md 作为 prompt 上下文
5. 同类失败自动化分析准确率提升，减少 LLM 调用
```

---

## 8. 实施路线图

### 阶段 1：接入现有 AI 总结（1-2 天）

**目标**：让 Jenkins 每次构建自动产出 AI 报告。

**任务**：
- [x] 在 `Jenkinsfile` post 阶段调用 `sugon_web/tools/ai_report.py`
- [x] 将 `reports/ai-test-summary.md` 作为 Jenkins artifact 归档
- [x] 将 API Key 迁移到 Jenkins Credentials
- [x] 调整执行顺序：AI 分析在 Allure 报告生成和清理之前

**验收标准**：
- 每次构建失败时，Jenkins 页面可直接下载 `ai-test-summary.md`
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

**目标**：飞书通知附带 AI 摘要，建立知识库闭环。

**任务**：
- [ ] 增强 `sendNotification`，读取并拼接 AI 摘要
- [ ] 定义 `case_library.md` 追加模板
- [ ] 制定“高置信度结论回写知识库”的流程规范
- [ ] 可选：接入缺陷系统（Jira/Tapd/禅道）自动创建产品缺陷

**验收标准**：
- 飞书通知包含 Top 3 失败根因
- 测试团队能按规范将 Skill 分析结论沉淀到案例库

### 阶段 4：历史趋势与看板（可选，1-2 周）

**目标**：基于多次构建数据生成失败趋势。

**任务**：
- [ ] 持久化每次构建的 `failure-report.json`
- [ ] 生成失败分类趋势图、flaky 用例排行
- [ ] 可选：搭建 Web 看板或定期发送趋势邮件

---

## 9. 风险与成本控制

| 风险 | 影响 | 对策 |
|---|---|---|
| LLM 调用成本高 | 每次构建可能分析大量失败 | 规则分类优先、相似聚合、限制 `max-failures`、命中知识库不走 LLM |
| LLM 输出不稳定 | 报告质量波动 | 用 try-catch 包裹，失败不影响主流程；Prompt 强制输出格式 |
| Allure 产物被清理 | AI 分析无输入 | 调整 Jenkins 执行顺序，AI 分析在清理前执行 |
| 敏感信息泄露 | API Key 或日志泄露 | API Key 走 Jenkins Credentials；日志中脱敏处理 |
| 报告与事实不符 | 误导排障 | 要求每个结论引用证据；不确定时明确标注低置信度 |
| Skill 与自动化冲突 | 重复建设 | 明确分工：Skill 用于人工深度分析，Prompt + 脚本用于自动化 |

---

## 10. 附录

### 10.1 关键文件清单

| 文件 | 作用 |
|---|---|
| `Jenkinsfile` | CI/CD 流水线主配置 |
| `sugon_web/tools/ai_report.py` | 现有 AI 总结脚本 |
| `sugon_web/tools/failure_analysis.md` | 自动化根因分析提示词模板 |
| `sugon_web/tools/llm_api_demo.py` | LLM API 调用示例 |
| `sugon_web/tools/failure_analysis/`（新增） | 失败分析引擎 |
| `sugon_web/conftest.py` | 失败截图、Allure 配置 |
| `.claude/skills/test-failure-analysis/SKILL.md` | 交互式失败分析 Skill |
| `.claude/skills/test-failure-analysis/references/case_library.md` | 历史失败案例库 |

### 10.2 失败分类定义

| 分类 | 定义 | 示例 |
|---|---|---|
| 环境问题 | 测试环境不稳定、资源不足、服务未就绪、网络抖动、平台维护等外部因素 | “系统升级中”404、SSH 不通、节点离线 |
| 用例问题 | 断言错误、等待超时不足、依赖顺序错误、清理不彻底、数据准备缺陷、locator 失效等 | 元素找不到、断言超时、资源泄漏 |
| 产品缺陷 | 被测系统功能异常、接口返回错误、状态机不符合预期、UI 与后端不一致等 | 创建资源后状态始终为“创建中”、接口返回业务错误 |

### 10.3 置信度定义

| 置信度 | 条件 |
|---|---|
| 高 | 材料清单完整（result.json + 截图/日志 + 代码），关键证据互相印证，推断占比 ≤ 20% |
| 中 | 缺少 trace 或部分附件，但 result.json + 截图 + 代码 足够交叉验证，推断占比 ≤ 50% |
| 低 | 仅 result.json + 代码推断，缺少截图或关键日志，或推断占比 > 50% |
