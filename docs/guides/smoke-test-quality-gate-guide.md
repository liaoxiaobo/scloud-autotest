# 冒烟测试质量门禁实施指南

> 适用对象：测试架构负责人、各模块测试负责人、CI 流水线维护人
> 目标：在现有 900+ 用例基础上，构建以 `smoke` 标记为抓手的冒烟用例集，并落地为可阻断合入/发布的质量门禁。

---

## 1. 先理解三件事

### 1.1 框架能力已全部就绪

框架层的编码工作已经完成。以下 5 项能力逐个展示：

#### ① `smoke` 标记已注册（`pytest.ini`）

`smoke` 已在 `pytest.ini` 中作为静态标记声明，`--strict-markers` 下不会报未知标记错误：

```ini
# pytest.ini
markers =
    smoke: 冒烟测试
    bms_prepare: BMS环境准备/创建类测试
    bms_regression: BMS日常功能回归测试
    bms_destructive: BMS高风险/破坏性测试
    requires_admin: 需要admin权限（仅admin可执行）
```

#### ② `--smoke` CLI 选项（`sugon_web/conftest.py`）

一键启用冒烟模式：自动筛选 `smoke` 标记 + 失败立即停止 + 精简输出。支持与其他标记组合：

```bash
# 冒烟模式（等同 -m smoke -x --tb=line）
pytest sugon_web/testcase/ --smoke

# 与其他标记组合：仅 compute 模块的冒烟用例（自动 and）
pytest sugon_web/testcase/ --smoke -m "compute"

# 仅收集不执行，确认冒烟集范围
pytest sugon_web/testcase/ --smoke --collect-only
```

实现逻辑（`conftest.py`）：

```python
# pytest_addoption
parser.addoption(
    "--smoke", action="store_true", default=False,
    help="冒烟模式：等同 -m smoke，任一用例失败立即停止（-x），简化输出（--tb=line）",
)

# pytest_configure
if config.getoption("--smoke", default=False):
    config.option.maxfail = 1
    config.option.tb = "line"
    if config.option.markexpr:
        config.option.markexpr = f"({config.option.markexpr}) and smoke"
    else:
        config.option.markexpr = "smoke"
```

#### ③ 标记筛选（`pytest -m`）

pytest 原生支持，无需框架额外适配。冒烟标记与模块/服务标记正交，可自由组合：

```bash
# 全量冒烟
pytest sugon_web/testcase/ -m smoke

# 仅 storage 模块的冒烟用例
pytest sugon_web/testcase/ -m "storage and smoke"

# 排除需要 admin 权限的冒烟用例（用 dept_admin 角色跑时）
pytest sugon_web/testcase/ -m "smoke and not requires_admin"
```

模块级（`compute`、`storage`、`network` 等）和服务级（`ecs`、`evs`、`vpc` 等）标记由 `testcase/conftest.py::pytest_configure` 根据目录和文件名自动扫描注册，无需手动维护。

#### ④ Jenkins 调度（`Jenkinsfile` + `dispatch_builder.py`）

Jenkins 构建页 `MARK` 参数传入 `smoke`，流水线自动拼接 `-m smoke` 到 pytest 命令：

```groovy
// Jenkinsfile — Parse Dispatch Config stage
withEnv(["DISPATCH_MARK=${params.MARK}", ...]) {
    sh 'python3 sugon_web/tools/dispatch_builder.py ... --mark "$DISPATCH_MARK" ...'
}

// Run Tests stage — 最终 pytest 命令
pytest ... -m 'smoke' ...
```

构建时在 `MARK` 参数中填 `smoke`，即可在全量测试 Job 中仅跑冒烟集。若需独立的冒烟门禁 Job（推荐），参见 §4。


---

**现状总结：**

| 已就绪 | 缺失 |
|---|---|
| `pytest.ini` 已注册 `smoke` 标记 | 没有任何用例打了 `@pytest.mark.smoke`（0 条） |
| `--smoke` CLI 选项已实现（`conftest.py`） | Jenkins 没有专用冒烟门禁 Job |
| `pytest -m smoke` 可直接筛选 | 冒烟用例筛选标准未定义 |
| `Jenkinsfile` 的 `MARK` 参数已支持 `smoke` | 没有冒烟失败阻断合入的流程 |
| `dispatch_builder.py` 已支持 `--mark` | |

**本指南的剩余工作只有两件：① 选出冒烟用例并打标 → ② 新建独立的冒烟门禁 Jenkins Job 并接入合入/发布流程。**

### 1.2 冒烟集≠全量精简版，是"核心链路探活"

冒烟集的定位是**分钟级快速回答一个问题："这个版本的软件还能不能用？"**——不是"所有功能有没有 bug"。选入冒烟集的用例必须在 **10–15 分钟内**跑完（约 50–100 条），覆盖每个服务最核心的创建/删除/连通性验证。

### 1.3 冒烟标记与模块标记是正交的

一个用例可以同时带多个标记：

```python
@pytest.mark.smoke      # 属于冒烟集
# 模块级标记由 pytest_collection_modifyitems 自动添加（compute/storage/network...）
class TestEcsBasic:
    ...
```

筛选时可以组合：`-m "compute and smoke"`（仅 compute 模块的冒烟用例），或 `-m "smoke and not requires_admin"`。

---

## 2. 冒烟用例筛选决策树

对模块内每个测试方法，按以下决策树判断是否纳入冒烟集：

```
对每个 def test_ 方法：

  问题 A：这个用例验证的是"核心功能的基本可用性"吗？
  │          （创建→验证→删除 的最短闭环，不涉及边界/组合/异常/长异步）
  │
  ├─ 否 → 不纳入
  │
  └─ 是
        │
        问题 B：单次执行时间通常 ≤ 2 分钟？
        │
        ├─ 否 → 不纳入（即使功能核心，执行太慢不适合冒烟集）
        │
        └─ 是
              │
              问题 C：依赖特定物理资源（裸金属、特定节点、特定网络）？
              │
              ├─ 是 → 不纳入（冒烟集要求环境通用性高）
              │
              └─ 否 → 【纳入冒烟集】打 @pytest.mark.smoke
```

### 2.1 筛选口诀

> **"CRUD 基本操作、主链路一个来回、不带长异步、不绑死资源"**

**典型应纳入的：**

| 服务  | 冒烟用例示例            |
| --- | ----------------- |
| ECS | 创建→查看详情→删除（最简规格）  |
| EVS | 创建云硬盘→挂载→卸载→删除    |
| VPC | 创建 VPC→查看→删除      |
| SLB | 创建实例→创建监听器→删除     |
| IAM | 创建组织→查看→删除（admin） |
| 安全组 | 创建→查看规则→删除        |
| 镜像  | 查看镜像列表            |

**典型不应纳入的：**

| 排除原因 | 示例 |
|---|---|
| 长异步等待 | BMS 创建/销毁（单次 30–70 min）、快照还原 |
| 边界/组合测试 | 多网卡、亲和组、参数化覆盖 |
| 需特定物理资源 | BMS、存储池巡检 |
| 权限验证 | 多角色权限矩阵（已在冒烟集中用 admin 跑主链路即可） |
| 需 admin 且非核心 | 运维巡检、物理机管理 |

### 2.2 每个模块建议配额

按当前 900+ 用例、目标 50–100 条的规模，建议每模块：

| 模块 | 总用例（约） | 建议冒烟（条） | 理由 |
|---|---|---|---|
| compute (ECS) | ~150 | 10–15 | 核心 IaaS，多规格各一条 + 生命周期主链路 |
| storage (EVS/SFS) | ~100 | 8–12 | 创建/挂载/卸载/删除 |
| network (VPC/SLB/VPN/SG/EIP/ER) | ~200 | 15–20 | 网络是骨架，每个子服务至少 1 条 |
| iam | ~100 | 5–8 | 组织/用户基本 CRUD |
| container (CCE) | ~80 | 5–8 | 集群创建/查看/删除 |
| database | ~80 | 5–8 | 各类 DB 实例基本生命周期 |
| middleware | ~60 | 3–5 | 核心中间件基本操作 |
| backup | ~30 | 2–3 | 备份基本操作 |
| security | ~30 | 2–3 | 核心安全功能 |
| bigdata | ~30 | 2–3 | 大数据服务基本操作 |

---

## 3. 用例标记实施

### 3.1 标记位置

与 `requires_admin` 的标记规范一致，打在 allure 装饰器之后、class/def 之前：

**打在类上（整类都是冒烟用例）：**

```python
import pytest
import allure


@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
@allure.story('ECS基础生命周期')
@pytest.mark.smoke                   # ← 类级，类内所有方法都会进入冒烟集
class TestECSBasic:

    @allure.title("ECS-基础生命周期验证")
    def test_ecs_operations(self, ecs_page, vm):
        ...

    @allure.title("ECS-创建后详情验证")
    def test_ecs_detail(self, ecs_page, vm):
        ...
```

**打在方法上（类里只有部分方法是冒烟用例）：**

```python
class TestEVSBasic:

    @pytest.mark.smoke               # ← 方法级
    @allure.title("EVS-云硬盘创建删除验证")
    def test_evs_create_delete(self, evs_page):
        ...

    @allure.title("EVS-云硬盘扩容验证")  # 不带 smoke，不纳入
    def test_evs_extend(self, evs_page):
        ...
```

### 3.2 批量标记：让 AI 按决策树判断

> 在仓库根目录对 Claude Code 这样提问，让它帮你判断并打标：

**示例提问 A（先让 AI 分析，不直接改）：**

```
逐个列出 sugon_web/testcase/storage/ 下每个测试方法的核心测试点和预估执行时间，
判断哪些应纳入冒烟集（决策树标准：核心功能基本可用性、≤2分钟、不依赖特定物理资源），
给出判断依据，先不要改代码，等我确认后再打 @pytest.mark.smoke。
```

**示例提问 B（确认后批量执行）：**

```
对 storage 模块确认纳入冒烟集的用例，加上 @pytest.mark.smoke：
  1. test_evs_create_delete — 打在类上
  2. test_sfs_basic.py::TestSFSBasic::test_sfs_create_delete — 打在方法上
  ...
严格按本指南的标记位置规范（allure 之后、class/def 之前）。
```

### 3.3 验证标记正确性

打标后本地验证：

```bash
# 确认冒烟集能正确收集
pytest sugon_web/testcase/ --smoke --collect-only

# 完整跑一遍冒烟集，确认全部通过
pytest sugon_web/testcase/ --smoke --headless=true

# 确认冒烟集数量在预期范围内
pytest sugon_web/testcase/ --smoke --collect-only | grep "selected"  # 应在 50~100
```

---

## 4. CI 质量门禁配置

### 4.1 新建独立冒烟门禁 Jenkins Job

> 目标：一个与现有全量测试 Job 独立的、轻量的冒烟专用流水线，**在每次 MR / 合入前自动触发**，10–15 分钟内完成。

新建 Jenkins Pipeline Job，命名为 `playwright-sugon-smoke-gate`，Pipeline 脚本如下：

```groovy
pipeline {
    agent any
    parameters {
        string(name: 'TARGET_HOST', defaultValue: '172.22.3.140', description: '目标测试环境')
        string(name: 'TARGET_STOR', defaultValue: 'xstor', description: '存储池类型')
        string(name: 'USER_ROLE', defaultValue: 'admin', description: '测试角色（冒烟默认 admin）')
    }
    environment {
        START_TIME = new Date().format("yyyy.MM.dd HH:mm:ss")
    }
    stages {
        stage('Build Image') {
            steps {
                script {
                    TIMESTAMP = sh(script: "date +%Y%m%d_%H%M", returnStdout: true).trim()
                    COMMIT_ID = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
                    IMAGE_TAG = "${TIMESTAMP}_${COMMIT_ID}_smoke_${env.BUILD_ID}"
                    env.IMAGE_TAG = IMAGE_TAG
                    sh "docker build -t playwright-sugon:${IMAGE_TAG} ."
                }
            }
        }
        stage('Smoke Test') {
            steps {
                script {
                    docker.image("playwright-sugon:${IMAGE_TAG}").inside() {
                        // --smoke 自动启用 -m smoke + fail-fast + 精简输出
                        def cmd = """
                            pytest sugon_web/testcase/ \
                                --smoke \
                                --headless=true \
                                --host=${params.TARGET_HOST} \
                                --stor=${params.TARGET_STOR} \
                                --user-role=${params.USER_ROLE} \
                                --alluredir=allure-result
                        """.strip()

                        def exitCode = sh(script: cmd, returnStatus: true)

                        if (exitCode != 0) {
                            currentBuild.result = 'FAILURE'
                            error "冒烟测试未通过！退出码 ${exitCode}，阻止合入/发布。"
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            script {
                docker.image("playwright-sugon:${env.IMAGE_TAG}").inside() {
                    sh "cp -r allure-report/history allure-result/ || true"
                    script {
                        if (currentBuild.result == 'FAILURE') {
                            try {
                                withCredentials([
                                    string(credentialsId: 'sugoncloud-api-key', variable: 'SUGON_API_KEY')
                                ]) {
                                    sh '''
                                        python3 sugon_web/tools/failure_analysis_cli.py \
                                            --results-dir allure-result \
                                            --logs-dir logs \
                                            --output reports/smoke-ai-summary.md \
                                            --max-failures 50
                                    '''
                                }
                            } catch (err) {
                                echo "AI analysis failed: ${err}"
                            }
                        }
                    }
                }
            }

            allure includeProperties: false, jdk: '', report: 'allure-report', results: [[path: 'allure-result']]

            script {
                if (currentBuild.result == 'FAILURE') {
                    def msg = "冒烟测试失败! 环境: ${params.TARGET_HOST}, 版本: ${env.IMAGE_TAG}, 报告: ${env.BUILD_URL}allure/"
                    sh """
                        curl -X POST -H "Content-Type: application/json" \
                            -d '{"msg_type":"text","content":{"text":"${msg}"}}' \
                            https://open.feishu.cn/open-apis/bot/v2/hook/6a07f306-b045-4748-bead-13ce14d9beda
                    """
                }
            }

            sh "rm -rf allure-result/* || true"
            deleteDir()
            script {
                if (env.IMAGE_TAG) {
                    sh "docker image rm playwright-sugon:${env.IMAGE_TAG} || true"
                }
            }
        }
    }
}
```

关键设计决策：

- `--smoke`：自动 `-m smoke -x --tb=line`，一条命令搞定
- 单进程（无 `-n`）：冒烟集本身很小，串行避免 fixture 竞争
- **失败即阻断**：`exitCode != 0` → 直接 `error()` 标记构建失败

### 4.2 接入合入流程

| 触发时机 | 方式 | 阻断行为 |
|---|---|---|
| MR 创建/更新 | GitLab Webhook → Jenkins `playwright-sugon-smoke-gate` | 冒烟失败 → MR 显示 ❌，阻止合入 |
| 版本发布前 | 手动触发，`TARGET_HOST` 指向发布目标环境 | 冒烟失败 → 终止发布流程 |
| 每日凌晨 | Cron 定时触发，指向稳定基线环境 | 失败仅告警，不阻断 |

**GitLab MR 联动配置（GitLab 侧）：**

1. 在 GitLab 项目 Settings → Webhooks 中，添加 Jenkins 冒烟 Job 的触发 URL
2. Trigger: `Merge Request events`
3. Jenkins 侧安装 GitLab Plugin，配置 MR 状态回写
4. 冒烟 Job 的构建结果自动回写到 MR 的 Pipeline 状态

> 详细 CI 集成配置见各平台（GitLab CI / Jenkins）的 Webhook 文档，本文档不展开。

---

## 5. 分阶段推广计划

```
阶段一（第 1–2 周）：核心模块试点
├─ compute (ECS) 选出 10–15 条 → 打标 → 本地验证通过
├─ storage (EVS) 选出 8–12 条 → 打标 → 本地验证通过
├─ 冒烟门禁 Jenkins Job 搭建并跑通
└─ 验收：compute+storage 冒烟集 ≤ 8 分钟，全部 PASSED

阶段二（第 3–4 周）：全模块覆盖
├─ network / iam / container / database / middleware 各选出配额
├─ 分批打标，每批打标后立即本地验证
├─ 基线：全量冒烟集 ≤ 15 分钟
└─ 验收：全部模块冒烟集在 Jenkins 上 100% PASSED

阶段三（第 5–6 周）：接入门禁
├─ GitLab MR Webhook 接入
├─ 冒烟失败 → MR 自动阻断
├─ 飞书群失败通知
└─ 验收：提一个"故意失败"的 MR，确认被冒烟门禁拦截

阶段四（持续）：维护与演进
├─ 每迭代 review 冒烟集构成：新增核心功能的冒烟用例
├─ 每季度 review 冒烟集时效：去除非核心、过慢的用例
├─ 冒烟集超过 15 min → 必须裁剪
└─ 条件成熟后评估是否引入冒烟专用超时覆盖
```

---

## 6. 验收标准

### 6.1 冒烟集质量

- [ ] 全量冒烟用例 50–100 条，15 分钟内跑完
- [ ] 每个核心服务至少 1 条冒烟用例
- [ ] 冒烟集 100% 通过（在基线环境上连续 5 次执行无失败）
- [ ] 无依赖特定物理资源的冒烟用例
- [ ] 无单次超过 2 分钟的冒烟用例

### 6.2 门禁效果

- [ ] Jenkins `playwright-sugon-smoke-gate` Job 可独立执行
- [ ] MR 触发冒烟门禁自动运行，结果回写到 MR
- [ ] 冒烟失败 → MR 无法合入
- [ ] 冒烟失败 → 飞书群收到通知（含失败用例列表和 Allure 报告链接）

### 6.3 开发者体验

- [ ] 本地可用 `pytest --smoke` 跑冒烟自检
- [ ] 冒烟用例筛选标准文档化（即本文档 §2）

---

## 7. 常见疑问（FAQ）

**Q1：为什么不用 `--lf`（只跑上次失败）代替冒烟集？**
`--lf` 只能验证"上次失败的那些用例修没修"，不能回答"这个版本还能不能用"。冒烟集覆盖的是固定核心链路，不依赖历史失败记录。

**Q2：冒烟用例某天开始频繁失败怎么办？**
先判断根因：环境问题→修环境并告警；产品缺陷→提缺陷、该用例暂时从冒烟集移除（去掉 `@pytest.mark.smoke`），等缺陷修复后再加回；用例本身过时→更新用例或重新评估。

**Q3：冒烟集会不会随着业务增长膨胀？**
会。必须设硬上限：**15 分钟或 100 条，先到为准**。每次新增冒烟用例时，问自己"是否比现有某条更重要"，是则替换而非累加。

**Q4：`smoke` 和 `requires_admin` 能同时打吗？**
能，但需要想清楚。如果你的冒烟集默认用 admin 角色跑（推荐），就不需要排除 `requires_admin`。如果以后想让普通用户也能跑冒烟，则用 `-m "smoke and not requires_admin"` 筛选。

**Q5：现有的全量 Jenkins Job 要改吗？**
**不改。** 冒烟门禁是**新 Job**——与现有全量测试 Job 完全独立、互不影响。全量测试继续按现有节奏运行（每日/按需），冒烟门禁高频触发（每次 MR）。

