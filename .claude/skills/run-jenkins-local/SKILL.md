---
name: run-jenkins-local
description: |
  在本地模拟 Jenkins 构建参数页面执行 Playwright 测试，帮助测试人员在提交代码前提前暴露 CI 环境中可能出现的问题。
  自动对齐 Jenkinsfile 中的参数默认值与 pytest 命令拼接逻辑，默认强制并行执行（-n 2），
  支持按模块/服务标签筛选（如 iam、container、compute），并自动完成环境预检、命令构建、测试执行、结果汇总。
  用户只需说"本地跑一下 iam 模块"或"/run-jenkins-local --mark=iam"，AI 即自动执行。
allowed-tools: [Read, Bash, Grep, Glob]
user-invocable: true
---

# Jenkins 本地模拟执行 Skill

## 1. 触发条件

当用户表达以下任意意图时，执行本 skill：

- "本地跑一下" / "本地执行" / "本地测试"
- "模拟 jenkins 跑" / "像 jenkins 一样本地执行" / "jenkins 本地模式"
- "跑一下 iam 模块" / "本地跑 container" / "执行 storage 用例"
- "/run-jenkins-local" 或 "/jenkins-local"

如果用户未指定 `--mark`，需要主动询问：
> "请告诉我你要执行哪个模块/服务的用例？例如：iam、container、compute、storage、network，或组合表达式如 `iam and not slow`。本 skill 禁止执行全量用例，必须指定筛选标签。"

---

## 2. 核心原则

1. **命令行为与 Jenkins 严格对齐**：参数默认值、pytest 命令拼接顺序必须和 `Jenkinsfile` 一致，杜绝"本地命令和 Jenkins 不一样"。
2. **并行是默认，串行需显式**：除非用户明确 `--serial` 或 `--parallel=1`，否则默认 `-n 2 --dist=loadscope`，强制暴露并发问题。
3. **参数校验提前报错**：在启动 pytest 之前完成 STOR/parallel/host 等参数校验，避免跑一半因参数错误失败。
4. **环境预检透明化**：执行前检查 Python 版本、git 分支状态等，仅做诊断信息展示。
5. **结果面向非技术人员**：业务测试人员看不懂 pytest 输出，需要给出"通过/失败 X 个/疑似环境问题/建议"的清晰结论。
6. **高危操作绝对禁止**：不修改任何测试代码、不自动 commit/push、不删除 allure 历史数据。

---

## 3. 参数规范与 Jenkins 映射

本 skill 支持的参数与 `Jenkinsfile` 中 `parameters` 的映射关系：

| Skill 参数 | Jenkins 参数 | 默认值 | 说明 |
|:---:|:---|:---|:---|
| `--mark` / `-m` | `MARK` | **必填，禁止为空** | pytest `-m` 标签表达式，如 `iam`、`container and smoke`、`not slow`。本 skill 强制要求指定，禁止全量执行。 |
| `--host` | `HOST` | 从配置读取，兜底 `172.22.1.190` | 被测环境管理 VIP |
| `--stor` | `STOR` | 从配置读取，兜底 `xstor` | 存储池类型 |
| `--username` | `USER` | 从配置读取，兜底 `admin` | 登录用户名 |
| `--password` | `PWD` | 从配置读取，兜底 `keystone_sugon` | 登录密码 |
| `--parallel` / `-n` | `PARALLEL_COUNT` | `2` | 并行线程数。最大不超过本地 CPU 核心数 |
| `--lf` | `RUN_LAST_FAILED` | `false` | 只运行上次失败的用例 |
| `--headless` | 隐式固定 | `true` | Jenkins 固定为 true，本地也默认 true |
| `--alluredir` | 报告目录 | `./allure-result` | Allure 结果输出目录 |
| `--serial` | — | `false` | 强制串行（覆盖 `--parallel`） |

### 3.1 默认值优先级（从高到低）

1. 用户显式传入的参数
2. `sugon_web/config/base.yaml` 中的对应配置
3. 上表中的兜底默认值（与 Jenkinsfile 一致）

---

## 4. 执行阶段

### 阶段一：意图解析与参数提取

**自动执行，不询问用户（除非缺少 `--mark`）**

1. 解析用户输入，提取所有显式参数
2. **强制校验 `--mark`：**
   - 如果未提供 `--mark`：询问用户目标模块/标签
   - 如果用户提供的 `--mark` 为空字符串或类似"全量""全部""所有"：明确拒绝，并提示必须指定模块/服务标签
   - 如果用户提供了类似"跑一下 iam 模块"的自然语言，自动推断 `--mark=iam`
3. 只有在 `--mark` 已确定为非空有效值时，才允许进入阶段二

**阶段完成标志**：`--mark` 已确定为非空有效标签

---

### 阶段二：配置读取与默认值填充

**自动执行**

使用 `Read` 读取以下配置文件填充默认值：

- `sugon_web/config/base.yaml`

填充规则：
- `host` ← `host`
- `stor` ← `stor`
- `username` ← `username`
- `password` ← `password`

如果配置文件不存在或对应 key 缺失，使用兜底默认值。

**阶段完成标志**：所有参数都已具备最终值

---

### 阶段三：环境与参数预检

**自动执行**

本阶段合并原"环境预检"和"参数校验"，统一在执行 pytest 前完成所有检查。其中环境检查仅做诊断展示，参数检查为阻塞性校验。

#### 3.1 环境检查（仅诊断，不阻塞）

```bash
# 1. Python 版本
python --version

# 2. 当前 git 分支（仅用于诊断信息，不阻塞）
git branch --show-current

# 3. 检查是否有未提交修改（仅提醒，不阻塞）
git status --short

# 4. 探测 pytest 实际可执行路径（优先虚拟环境，避免系统 PATH 误判）
PYTEST_CMD=""
for venv_path in ".venv/bin/pytest" "venv/bin/pytest" "env/bin/pytest"; do
    if [ -x "$venv_path" ]; then
        PYTEST_CMD="./$venv_path"
        break
    fi
done
# 兜底：系统 PATH
if [ -z "$PYTEST_CMD" ]; then
    PYTEST_CMD=$(command -v pytest 2>/dev/null || echo "pytest")
fi
```

**汇报格式**：

```markdown
🔍 环境预检结果（仅供参考，不阻塞执行）：
- Python 版本：3.x.x
- pytest 路径：`./.venv/bin/pytest`（已识别虚拟环境）
- 当前分支：`dev-xxx`
- 未提交修改：N 个文件（仅提醒）
```

> 注：本 skill 不再检查 pytest 和 Playwright Chromium 的安装状态，由 pytest 自身在执行时报告依赖问题。若执行失败，请根据报错信息自行安装：`pip install -r requirements.txt`、`playwright install chromium`。
>
> 探测到的 `PYTEST_CMD` 会在阶段四/五中替代裸 `pytest` 命令使用。

#### 3.2 参数校验（阻塞性，失败时立即停止）

1. **STOR 白名单校验**：
   ```python
   VALID_STORS = ["xstor", "zbs", "ceph", "xbd", "ustor", "usan", "local", "nfs"]
   ```
   如果 `stor` 不在白名单，报错：
   > `--stor 必须是以下之一：xstor, zbs, ceph, xbd, ustor, usan, local, nfs`

2. **parallel 上限校验**：
   ```bash
   CPU_CORES=$(python -c "import os; print(os.cpu_count())")
   ```
   如果 `parallel > CPU_CORES`，自动下调为 `CPU_CORES` 并提醒用户。

3. **mark 非空强制校验**：
   - 如果 `--mark` 为空字符串，**立即停止执行**，报错："`--mark` 不能为空。本 skill 禁止执行全量用例，请指定模块/服务标签，如 iam、container、compute 等。"

4. **mark 语法简单校验**（仅检查明显错误）：
   - 如果包含非法字符或明显语法错误，给出警告但不阻塞（因为 pytest 自己会报错）

**阶段完成标志**：环境检查完成且所有参数校验通过

---

### 阶段四：pytest 命令构建

**自动执行，构建前向用户展示最终命令**

按照 `Jenkinsfile` 的拼接逻辑构建命令，使用阶段三探测到的 `$PYTEST_CMD` 替代裸 `pytest`：

```bash
# 基础命令（必须严格对齐 Jenkinsfile 的格式和顺序）
$PYTEST_CMD \
  --headless=true \
  --host=<HOST> \
  --stor=<STOR> \
  --username=<USER> \
  --password=<PWD> \
  -n <PARALLEL> \
  --dist=loadscope \
  sugon_web/testcase/ \
  --alluredir ./allure-result

# 追加 mark 筛选（skill 已强制 mark 非空，此处直接追加）
# 追加：-m '<MARK>'

# 追加 last-failed
# 如果 lf=true，追加：--lf
```

**展示命令给用户确认**：

```markdown
🚀 即将执行以下命令（与 Jenkins 构建逻辑对齐）：

./.venv/bin/pytest --headless=true --host=172.22.1.190 --stor=xstor --username=admin --password=keystone_sugon -n 2 --dist=loadscope sugon_web/testcase/ --alluredir ./allure-result -m 'iam and not slow'

参数来源：
- host：来自 sugon_web/config/base.yaml
- stor：用户显式传入
- parallel：默认值 2
- mark：用户显式传入
- pytest 路径：来自阶段三探测到的虚拟环境
```

**阶段完成标志**：命令构建完成并已展示

---

### 阶段五：执行测试

**自动执行**

执行阶段四构建的命令。执行过程中：
- 测试运行期间可输出简要进度提示（如"正在执行，预计耗时取决于用例数量..."）
- 捕获退出码

```bash
# 记录执行开始时间戳（阶段六统计过滤用）
START_TS=$(python -c "import time; print(int(time.time()))")

$PYTEST_CMD <完整命令>
EXIT_CODE=$?
```

**阶段完成标志**：pytest 执行完成，退出码已捕获

---

### 阶段六：结果汇总与建议

**自动执行，必须输出清晰结论**

根据 pytest 退出码和 allure 结果进行汇总：

```bash
# 获取用例统计及失败用例标题（仅统计本轮执行生成的文件，过滤历史残留）
python -c "
import json, glob, os, sys

start_ts = int(sys.argv[1]) if len(sys.argv) > 1 else 0
counts = {'passed': 0, 'failed': 0, 'skipped': 0, 'broken': 0}
failures = []

for f in glob.glob('allure-result/*-result.json'):
    try:
        # 过滤：只统计 mtime >= START_TS 的文件
        if os.path.getmtime(f) < start_ts:
            continue
        with open(f) as fp:
            d = json.load(fp)
        s = d.get('status', 'unknown')
        name = d.get('name', 'unknown')
        if s in counts:
            counts[s] += 1
        if s in ('failed', 'broken'):
            failures.append({'name': name, 'status': s})
    except Exception:
        pass

print(json.dumps({'counts': counts, 'failures': failures}, ensure_ascii=False))
" "$START_TS"
```

**输出格式**：

```markdown
📊 本地 Jenkins 模拟执行结果：

### 执行命令
```
<阶段四构建的命令>
```

### 用例统计
| 状态 | 数量 |
|:---|---:|
| ✅ 通过 | N |
| ❌ 失败 | N |
| ⏭️ 跳过 | N |
| 💥 错误 | N |

### 失败用例详情（Allure 标题）

| 状态 | Allure 标题 |
|:---|:---|
| 💥 错误 | 云硬盘快照-数据一致性验证 |
| 💥 错误 | 快照策略-绑定和解绑云硬盘 |

### 结论
- 如果全部通过：
  > ✅ 本地执行通过。建议提交后关注 Jenkins 首次构建结果。

- 如果有失败：
  > ❌ 本地执行发现 N 个失败用例。如需根因分析，请使用 `/test-failure-analysis`。

### 报告位置
- Allure 结果：`./allure-result/`
- 如需查看 HTML 报告，可运行：`allure serve ./allure-result`
```

**阶段完成标志**：结果汇总已输出

---

## 5. 异常处理

### 5.1 pytest 执行超时

如果 pytest 命令执行时间过长（超过 Bash 工具默认超时），使用 `timeout=600000`（10分钟）或根据用户 mark 大小动态调整。

### 5.2 allure-result 目录不存在

如果执行后未生成 `allure-result/`，提示：
> "未检测到 allure-result 目录，可能 pytest 未正常启动或中途异常退出。"

### 5.3 本地环境缺失修复命令速查

环境预检不阻塞执行，若 pytest 启动失败，常见修复命令如下：

| 缺失项 | 修复命令 |
|:---|:---|
| pytest 未安装 | `pip install -r requirements.txt` |
| Playwright 浏览器未安装 | `playwright install chromium` |
| allure 命令未安装 | `brew install allure` 或参考 Allure 官方文档 |

### 5.4 `--lf` 无历史记录

如果用户启用 `--lf` 但本地没有 `.pytest_cache/v/cache/lastfailed`，提示：
> "本地没有上次失败的记录，`--lf` 将运行全部用例。"

---

## 6. 安全红线

以下操作**严禁执行**：

| # | 禁止行为 |
|:---:|:---|
| 1 | 修改任何测试代码或 Page Object |
| 2 | 自动执行 `git commit` / `git push` |
| 3 | 删除 `allure-report/history` 或其他历史数据 |
| 4 | 修改 `sugon_web/config/base.yaml` |
| 5 | 超出用户请求范围执行全量测试（如用户说跑 iam，不得跑全量） |
| 6 | 使用 `--force` 类参数 |

---

## 7. 典型使用示例

**示例 1：自然语言触发**
```
用户：本地跑一下 iam 模块
AI：正在为您模拟 Jenkins 参数执行 iam 模块测试，默认并行 2 线程...
```

**示例 2：带参数触发**
```
用户：/run-jenkins-local --mark="iam and not slow" --parallel=4 --stor=ceph
AI：已识别参数，正在按 Jenkins 构建逻辑执行...
```

**示例 3：串行验证**
```
用户：帮我串行跑一下 container 模块，排除 slow
AI：已切换到串行模式，执行命令：pytest ... -m "container and not slow" -n 1 ...
```

---

## 8. 输出约束

1. 命令展示必须完整、可复制执行
2. 结果汇报必须包含"通过数/失败数/跳过数"统计
3. 失败时提示用户可使用 `/test-failure-analysis` 进行根因分析
4. 不使用技术黑话，面向业务测试人员可理解
