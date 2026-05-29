# CLAUDE.md

本项目是基于 Python + Playwright + Pytest 的 Web UI 自动化测试框架，针对 SugonCloud（涵盖 ECS/EVS/VPC/SLB/数据库/中间件/备份等），通过 SSH 做后端验证。

## 运行测试

```bash
# 默认排除 slow 测试
pytest sugon_web/testcase/

# 指定模块 / 方法
pytest -k "ecs" sugon_web/testcase/
pytest sugon_web/testcase/compute/test_ecs_basic.py::TestECSBasic::test_ecs_operations

# 并行 / 无头 / slow 测试
pytest -n 2 --dist=loadscope sugon_web/testcase/
pytest sugon_web/testcase/ --headless=true
pytest sugon_web/testcase/ -m "slow"

# CLI 覆盖配置
pytest sugon_web/testcase/ --host=172.22.1.190 --browser-type=chromium --headless=true --stor=xstor --username=admin --password=keystone_sugon
```

## 架构（严格 4 层分离）

1. **Page Object**（`pages/**/*.py`）— 封装页面元素和单步业务操作。
   - 必须继承 `BasePage`。
   - 公共方法命名：`服务_操作`（如 `ecs_create`、`evs_delete`）。
   - 私有辅助方法前缀 `_`（如 `_select_cluster`）。

2. **Fixture**（`testcase/*/conftest.py`、`_xxx_fixtures.py`）— 管理资源生命周期。
   - 使用 `yield` 做清理。
   - 领域专属 fixture 放在 `_xxx_fixtures.py`。
   - 模块公共 fixture 放在 `conftest.py`。

3. **Helper**（`_xxx_helpers.py` 或模块级私有函数）— 纯函数，无 `yield`。
   - 命名规范：`_build_xxx`、`_prepare_xxx`。

4. **Test Class**（`test_*.py`）— 只写测试步骤、断言和局部变量。
   - 禁止写跨用例辅助方法。

**新代码决策规则：** 页面交互→Page Object，资源生命周期→Fixture，环境组装→Helper，单文件用→私有函数，跨文件复用→`_xxx_helpers.py`。

## Fixture 作用域（关键）

`page` 是 `function` 级（每个测试新建标签页），但复用同一 `class` 级 `browser_context` 以保持测试类内登录态。`browser` 是 `session` 级。

- `session` → `browser`、`config`、`ssh_host`、`jump_host`
- `class` → `browser_context`、`ssh_vm`
- `function` → `page`（通过 `_create_logged_in_page` 自动登录）

## 配置系统

配置按顺序合并三层：
1. `sugon_web/config/base.yaml` — 默认值
2. `sugon_web/config/env.yaml` — 环境专属覆盖
3. CLI 参数（`--host`、`--browser-type`、`--headless`、`--stor`、`--username`、`--password`）

通过 `Config.get("key")` 或 `Config.get()` 读取。

**默认值：** host=172.22.1.190、username=admin、password=keystone_sugon、stor=xstor、browser=chromium、headless=false。

## 服务导航

页面使用 `goto_service("服务名")` 导航，通过 `SERVICE_PATH_MAP`（URL 快捷方式）或回退到 `SERVICE_MAP`（菜单导航）解析。**测试中禁止直接写 URL。**

在子菜单内操作的方法必须加 `@submenu("子菜单名")` 装饰器。

## 命名规范

### Page Object
- 公共方法：`服务_操作`（如 `ecs_create`、`evs_delete`、`vpc_edit`）。
- 私有辅助：`_` 前缀（如 `_select_cluster`、`_input_search`）。
- 公共方法必须写 docstring。

### Fixture
- 资源 fixture：`vpc`、`sg`、`ecs`、`vm`、`volume`。
- 组合 fixture：`vm_sg_binding`。
- 清理 fixture：`clean_xxx`。

### 测试
- 类名：`Test*Basic`、`Test*Create`、`Test*Scenario`。
- 方法名：`test_服务_功能描述`（如 `test_ecs_operations`）。
- Allure 类注解：`@allure.epic('服务域')` → `@allure.feature('服务名')` → `@allure.story('功能模块')`。
- Allure 方法注解：`@allure.title("服务-功能验证")`。
- 步骤块：`with allure_step_log("步骤X: 描述"):`。

### 测试数据
- 资源名称：`random_data()`。
- 参数化数据：`load_data(case_name, data_file)` 从 `testcase/test_data/*.yaml` 加载。

## pytest.ini 约束

- `testpaths = sugon_web/testcase` — 测试必须放在该路径下。
- 默认 `-m 'not slow'` — **slow 测试被排除，除非显式加 `-m "slow"`**。
- `--clean-alluredir` — 每轮运行清空 `allure-result/`。
- 标记：`smoke`、`regression`、`slow`、`login`、`evs`、`ecs`。新增标记必须同步更新此列表。

## SSH 后端验证

测试通过 SSH 验证 UI 操作的实际后端状态：
- `ssh_host` — 直连测试环境。
- `ssh_vm` — 通过跳板机连虚拟机。
- `ssh_host.run("scli ...")` — OpenStack 风格 CLI 命令。

## 代码规则

- 禁止在 Page Object 中写场景编排逻辑。
- 禁止修改 `sugon_web/config/pkey_scloudadmin`（SSH 私钥）。
- 禁止新增 pytest 标记而不更新 `pytest.ini`。
- 禁止删除测试文件或 fixture 文件，即使看起来未被使用。

## 重要行为

- `sugon_web/testcase/conftest.py` 中的 `vm` fixture 高度参数化，通过 `@pytest.mark.parametrize(..., indirect=True)` 接收 `VmFixtureParams` 字典，基于 `inject_dependencies` 自动注入依赖（SG、标签、亲和组）。
- 测试失败时自动截图，通过 `pytest_runtest_makereport` 捕获并附加到 Allure。
- `page` fixture 登录后自动执行 `close_dialog_if_exists()` 关闭弹窗。
- 会话启动时自动通过 SSH 获取节点数和补丁版本，写入 Config 供 skip 装饰器使用。

## 目录说明

- `requirements_csv/` — 原始测试需求 CSV 文件。**不是测试代码。**
- `case_specs/` — Markdown 用例规格和提示词模板。**不是测试代码。**
- `tools/ai_report.py` — 测试后 AI 总结生成。需要环境变量 `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`。

# CLAUDE.md

减少 LLM 编码常见错误的行为准则。根据需要与项目特定指令合并使用。

**权衡：** 这些指南倾向于谨慎而非速度。对于琐碎的任务，请自行判断。

## 1. 编码前思考

**不要假设。不要隐藏困惑。呈现权衡。**

开始实现前：
- 明确说明假设。如果不确定，询问而不是猜测。
- 如果存在多种解释，呈现出来 —— 不要默默选择。
- 如果存在更简单的方法，说出来。适时提出异议。
- 如果有不清楚的地方，停下来。指出困惑之处。询问。

## 2. 简洁优先

**用最少的代码解决问题。不要过度推测。**

- 不要添加要求之外的功能。
- 不要为一次性代码创建抽象。
- 不要添加未要求的"灵活性"或"可配置性"。
- 不要为不可能发生的场景做错误处理。
- 如果 200 行代码可以写成 50 行，重写它。

问自己："资深工程师会觉得这过于复杂吗？"如果是，简化。

## 3. 精准修改

**只碰必须碰的。只清理自己造成的混乱。**

编辑现有代码时：
- 不要"改进"相邻的代码、注释或格式。
- 不要重构没坏的东西。
- 匹配现有风格，即使你更倾向于不同的写法。
- 如果注意到无关的死代码，提一下 —— 不要删除它。

当你的改动产生孤儿代码时：
- 删除因你的改动而变得无用的导入/变量/函数。
- 不要删除预先存在的死代码，除非被要求。

检验标准：每一行修改都应该能直接追溯到用户的请求。

## 4. 目标驱动执行

**定义成功标准。循环验证直到达成。**

将任务转化为可验证的目标：

| 不要这样做... | 转化为... |
|--------------|-----------------|
| "添加验证" | "为无效输入编写测试，然后让它们通过" |
| "修复 bug" | "编写重现 bug 的测试，然后让它通过" |
| "重构 X" | "确保重构前后测试都能通过" |

对于多步骤任务，说明一个简短的计划：

```
1. [步骤] → 验证: [检查]
2. [步骤] → 验证: [检查]
3. [步骤] → 验证: [检查]
```

强有力的成功标准让 LLM 能够独立循环执行。弱标准（"让它工作"）需要不断澄清。

---

**这些指南正在发挥作用的标志：** diff 中不必要的改动更少、因过度复杂而导致的重写更少、澄清问题在实现之前提出而不是在犯错之后。
