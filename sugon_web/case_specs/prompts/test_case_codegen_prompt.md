# UI自动化测试用例开发规范

> **读者**：本文件面向 AI 编码代理，不是人类。在执行 `test-script-workflow`（阶段二）/ `test-self-heal` 期间，用于指导 AI 编写与当前项目风格完全一致的高质量 Playwright + Pytest 测试代码。
> **要解决的核心问题**：简单用例已能套模板写好；复杂用例（步骤多、交互复杂、业务逻辑深）在阶段三耗时长，根因是**编码前预研不足 + 代码归属决策混乱 + 初始代码质量低**。本规范用**强制预研流程**（§4）+ **归属决策树**（§2）+ **复杂场景分解**（§12）对症解决。
> **本文件的定位**：测试层（`test_*.py`）的编码权威。fixture / 断言 / 页面定位的**细节规范**不在此维护，由各权威文件负责（见 §1），本文件只规定测试层如何**调用与对齐**它们。
> **铁律**：先理解当前模块既有写法，再按既有风格写。**禁止自创新写法。** 不确定时以"项目真实代码"为准，不凭空构造。

---

## 0. 阅读与执行总则（最高优先级）

1. **以代码为事实依据**：所有公共方法名、fixture 名、断言方法名、页面文案、定位方式，**必须**来自项目真实代码或真实渲染态。本文件出现的任何方法名都是**示例，不是完整清单**；严禁把"本文件没列"当作"项目里没有"。
2. **复用优先于新建**：任何能力（fixture、断言、页面方法、公共操作）新建前**必须先 `Grep` 搜索确认无可复用项**。搜索过才能下结论。
3. **遵守字面即遵守精神**：违反规范字面要求就是违反其意图，不要用"我遵循的是精神"绕过条款。
4. **不确定就停下来查，不要猜**：定位、文案、参数、状态机不确定时，去读前端代码 / 跑侦察脚本 / 读同模块用例，**不发散编造**。

---

## 1. 规范地图与职责边界

编码涉及四个维度，每个维度有唯一权威文件。**本文件不复述它们的内容**，只在测试层调用时对齐。需要某维度细则时去读对应文件，不要凭记忆。

| 维度 | 权威文件（唯一来源） | 阅读时机 | 本文件只规定 |
|:---|:---|:---|:---|
| fixture 复用清单 | `fixtures_index.md` | 预研 Step 2 | 测试层如何引用、`count` 批量、清理归属 |
| fixture 新增/抽取 | `fixture_spec.md` | 需新增 fixture 时 | 何时该新增（仅当现有无法参数化满足） |
| 断言编写与分层 | `assertion_guidelines.md` | 编写断言时 | 测试层调用断言的顺序与 P0–P3 落点 |
| 页面方法与定位 | `page_func_spec.md` | 新增 Page 方法时 | 测试层只调 Page 方法、不碰底层定位 |

> **冲突裁决**：若本文件与上述某权威文件在其专属维度上描述冲突，**以该权威文件为准**，并视本文件为待修正。本文件不与它们竞争细节，只负责"把它们串起来用在测试层"。

---

## 2. 项目分层架构与代码归属决策树（复杂用例质量的根）

当前项目为 **Playwright + Pytest + POM 四层架构**。复杂用例代码质量差的首要根因是**代码放错层**：在 Test Class 写多步页面操作、在 Page 写跨服务编排、在 Fixture 写断言。**新增任何代码前，先判定它属于哪一层。**

### 2.1 各层职责与禁区

| 层级 | 唯一职责 | 严禁 |
|:---|:---|:---|
| **Test Class**（`test_*.py`） | 组织测试步骤：准备 → 操作 → 校验。只调用 Page 方法和 fixture。 | 写底层定位、写多步页面流程、写 helper 函数、类体内定义 `_` 私有方法 |
| **Fixture**（`conftest.py`） | 资源生命周期：创建 → yield → 清理。 | 写断言、写多步页面交互（必须委托 helper） |
| **Helper**（`_xxx_helpers.py`） | 编排跨页面/有状态依赖的业务流程（纯函数）。 | 含 `yield`、声明 fixture 依赖 |
| **Page Object**（`pages/`） | 封装单页面内的交互与业务动作。 | 组织测试步骤、跨服务页面编排 |
| **Assertion Mixin**（`assertions/`） | 封装可复用断言。 | 写在 `pages/`、在 helpers 纯函数里放页面元素断言 |

### 2.2 新增代码归属决策树

```
需要新增代码？
│
├─ 资源生命周期（创建/删除/清理）？
│   ├─ 已有 fixture 可复用 → 复用（fixtures_index.md）
│   └─ 无匹配 → 新增 fixture（fixture_spec.md）：只做参数解析+yield+teardown，
│              创建/删除逻辑必须委托 helper；纯计算组装 → 写 helper（无 yield、无 fixture 依赖）
│
├─ 单页面内的交互封装？
│   ├─ 已有 BasePage/Mixin 公共方法可覆盖 → 复用（如 search、btn_create、get_row_data）
│   └─ 无匹配：
│       ├─ 单页面/单弹窗/单表单的原子操作 → 新增 Page 公共方法（命名 服务_操作，必带 docstring）
│       └─ 跨多个服务页面的流程编排 → 下沉 Helper（_xxx_helpers.py，命名 _build_xxx/_prepare_xxx）
│
├─ 断言？
│   ├─ UI 层面（弹窗/状态/列表/字段）→ 复用或新增 assertions Mixin（assertion_guidelines.md）
│   └─ SSH/后端验证 → 测试层直接写 assert（assertion_guidelines.md 7.2）
│
└─ 测试步骤本身？
    └─ 只能写在 Test Class 方法中：只调用 Page/Fixture/Helper，不写定位、不写多步操作封装
```

**归属口诀**：
> 一个页面、一个弹窗、一个表单 → **Page**；
> 多个页面、多个服务、状态依赖 → **Helper**；
> 资源的存在与销毁 → **Fixture**；
> 验证某个结果 → **Assertion**；
> 组织步骤 → **Test Class**。

---

## 3. 硬性约束（禁区，违反即返工）

**绝对约束，任何情况不得违反：**

1. **禁止修改公共框架代码**
   - 不改 `sugon_web/common/`（`base.py`、`playwright.py` 及各 Mixin）。
   - 不改 `sugon_web/assertions/` 下已封装的断言方法（被全平台继承，改一处影响全局）。
   - 需增强公共能力 → **新增**方法或**新增带默认值的可选参数**（保持原行为不变），不就地改写。
2. **禁止修改被测前端工程代码**：`sugon_web/refrence/` 下任何文件禁止改/删/增，它是定位与文案的事实来源，只读。
3. **测试层边界（`precheck.py` 会机器检测，违反必拦截）**
   - `test_*.py` **严禁**出现 `.locator(`、`expect(`、XPath、`page.` 底层调用——所有页面交互必须经 Page 方法。
   - **严禁**用 `time.sleep()` / `wait_for_timeout()` 作状态等待（轮询间隔内的短 sleep 属断言/等待方法内部，不在测试层写）。
   - 测试主流程**严禁**用 `try/except` / `try/finally` 包裹核心步骤。
   - **严禁**手动 `for` 循环创建资源（批量用 fixture 的 `count` 参数）。
   - 测试类体内**严禁**定义 `_` 前缀辅助方法（纯函数放模块级或 `_xxx_helpers.py`）。
4. **禁止改动需求与数据**：不改阶段一产出的需求 MD；不擅改 CSV/MD 已定义的测试数据（端口、协议、权重、IP、规格、数量等）。脚本执行失败不是改需求的理由。

---

## 4. 编码前强制预研流程（缩短阶段三耗时的核心）

> **原则**：编码前花的时间越长，阶段三修复越短。**严禁跳过预研直接编码。**
> **触发**：Step 1–4 任何用例都必须做；Step 5–6 在"步骤数 > 8 或涉及 3 个以上服务"时必须做。

**Step 1 — 精读需求 MD**
用 `Read` 完整读阶段一产出的需求 MD（不跳读、不节选）。提取：测试步骤清单、测试数据（严格按 CSV）、边界条件、清理顺序、共享数据标识。按顺序列出所有步骤，标注哪些用已有公共能力、哪些需新增 Page 方法。

**Step 2 — 搜索现有 Fixture**（必须执行命令，不能凭记忆）
```bash
grep -r "@pytest.fixture" --include="conftest.py" sugon_web/testcase/
grep -r "def <资源关键词>(" --include="conftest.py" sugon_web/testcase/
```
`Read` 匹配 fixture 的实现，确认：是否支持 `count`、返回值结构（dict / list[dict]）、依赖关系（如 vm 依赖 vpc 自动复用网络）。决策：有同功能 → 复用；不支持 count → 看能否参数化；完全无匹配 → 按 `fixture_spec.md` 新增。

**Step 3 — 搜索现有 Page 方法与断言**
```bash
grep -r "def <服务>_" sugon_web/pages/<模块>/
grep -r "def assert_<对象>" sugon_web/assertions/
```
`Read` 匹配实现确认能否直接复用：覆盖需求 → 复用；接近但对象不同 → 参考另建；无匹配 → 按规范新增。

**Step 4 — 研读同模块现有用例**
选 1–2 个最相似用例完整 `Read`，提炼并对齐：Allure 标题风格、步骤拆分粒度、fixture 使用模式（indirect / class scope）、清理策略。**新用例风格必须与同模块一致，禁止自创。**

**Step 5 — 复杂场景结构规划（步骤 > 8 或 3+ 服务时强制）**
把步骤按页面/服务分组，每组对应一个 Page 方法或一个 `allure_step_log` 块；划清"准备→操作→校验→清理"边界；识别哪些资源 fixture 预创建、哪些用例内动态创建；末态集中规划 P0/P1/P3 断言落点。

**Step 6 — 定位策略预判（复杂表单/自定义组件时）**
能读前端代码就按 `page_func_spec.md` 优先级定位；无法仅凭前端代码唯一确定（操作项隐藏需 JS 触发、同名菜单多个、复杂表单多 input）→ 标记"需运行时侦察"，编码时用侦察脚本枚举真实渲染态再写定位，**不凭空构造 locator**。

### 4.1 预研完成自检（全部"是"方可编码）

| # | 自检问题 | 验证方式 |
|:--:|:---|:---|
| 1 | 已完整读需求 MD？ | 能按顺序复述所有步骤 |
| 2 | 已 grep 确认 fixture 复用方案？ | 能指出复用的 fixture 名及参数 |
| 3 | 已确认 Page 方法复用/新增边界？ | 能列出复用方法和需新增方法 |
| 4 | 已读同模块相似用例并提炼风格？ | 能说出标题风格、步骤粒度、fixture 模式 |
| 5 | 复杂场景已按页面分组规划？ | 能说出每个步骤块包含什么操作 |
| 6 | 断言已按 P0/P1/P2/P3 规划？ | 能指出每个断言的层级和所用方法 |

---

## 5. 用例文件结构与推荐骨架

### 5.1 结构规则

- 固定三段式：**准备数据 → 执行操作 → 校验结果**。
- 步骤统一用 `with allure_step_log("步骤x: ...")` 包裹，描述含资源名。
- **一个步骤块只做一件事**：禁止在同一块内混排"操作"和"校验"。
- 步骤拆分粒度：简单用例（≤5 步）3–4 块；复杂用例（6–15 步）按页面/服务分组，每页 1–2 块；超长用例（>15 步）按"准备→操作→校验→清理"四阶段分组再细分。
- 临时创建、fixture teardown 不覆盖的资源，**必须**补"清理数据"步骤，顺序严格依据需求。
- 共享同一套数据的多个用例，置于同一测试类，用 class-scoped fixture 共享，批次结束统一清理。
- 每个测试方法 = 一个独立场景；**多个仅参数不同的场景必须 `@pytest.mark.parametrize` 参数化**，不得合并进一个方法，也不得复制多个高重复方法。测试方法数与 CSV/MD 场景数必须一致。

### 5.2 推荐骨架（务必参照此骨架编写）

```python
import allure
import pytest
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic("一级服务分类")
@allure.feature("二级模块")
@allure.story("功能点分组")
class TestXxx:
    """一句话描述本测试类的验证范围。"""

    @allure.title("资源名-功能点")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}}], indirect=True)  # 按需，复用 fixture 批量
    def test_xxx(self, ecs_page, vm):
        """一句话描述本用例的测试目的。"""
        name = vm.get("name")

        with allure_step_log("步骤1: 准备/导航"):
            ecs_page.goto_service("弹性云服务器")

        with allure_step_log("步骤2: 执行页面操作"):
            ecs_page.some_business_action(name, ...)   # 只调 Page 方法

        with allure_step_log("步骤3: 校验结果"):
            ecs_page.assert_popup_success("...成功")     # P0 操作成功
            ecs_page.assert_status(name)                 # P0 状态收敛/存在性
            # P1 末态字段回读、P2 SSH 后端验证按需补充
```

> 骨架是结构基线，不是填空模板。步骤数、fixture、断言层级依据需求与同模块既有风格调整。

### 5.3 用例独立性（解耦）铁律（适用所有模块，非某一模块专属）

> **解耦定义**：每个 `test_` 方法都是自给自足的独立场景——**可单独跑、可任意顺序跑、可重复跑，结果都一致**。用例之间不传递状态、不依赖彼此的执行顺序或残留数据。
> **为何重要**：解耦差的用例（依赖"上一个用例建好的数据"、共用未清理的残留、依赖页面停留位置）在 `-k` 单跑 / 乱序跑 / 并发跑时会随机失败，是阶段三反复返工的高发根因。本铁律适用于所有业务模块。

**逐条对照编写：**

1. **资源自给**：用例所需基础资源一律由 fixture 注入创建，**禁止**依赖"其它用例已创建好"或"环境已预置"的具名资源；需求写"已预置 X"时按阶段一转写的"自建 / 复用前序场景"方案处理（见需求 MD 与 §8），不照搬"环境已有"的假设。
2. **唯一命名**：资源名一律 `random_data()`，**禁止**硬编码固定名；衍生资源用"前缀+源名"（如 `clone_<name>`、`snapshot_<name>`），避免乱序/重复/并发跑时同名冲突。
3. **自导航**：用例开头自行 `goto_service` / `goto_submenu` 跳到目标页，**不依赖**上个用例停留的页面或回收站等残留状态。
4. **自清理 + 状态复原**：用例内临时创建、fixture teardown 不覆盖的资源（克隆盘、快照、镜像、亲和组等）必须在用例内清理并断言删除成功；对修改类操作（改名/挂载/绑定）测试后改回/卸载/解绑，使共享 fixture 资源恢复初始态、不污染后续用例（fixture 注入的资源由 fixture 清理，用例不重复删）。
5. **无顺序依赖**：禁止"用例 B 复用用例 A 未清理的残留数据"这类跨用例耦合；确需共享同一套数据的多个用例，必须同测试类 + class-scoped fixture 共享、批次末统一清理（见 §12.3），而非靠执行顺序传递。
6. **环境前提用 skip 声明**：节点数/存储类型/架构等环境前提，用 `skip_if_nodes_less_than` / `skip_stor` / `skip_arch` 等装饰器声明跳过——**这是合理的环境依赖、不是用例耦合**；禁止用"上个用例顺带把环境准备好了"来替代 skip 判断。

> **解耦 ≠ 步骤无序**：用例内部步骤（准备→操作→校验→清理）本身有先后是正常的，不属于耦合；解耦约束的只是"用例与用例之间"的独立性。

---

## 6. 命名规范

| 对象 | 规则 | 正确示例 | 错误示例 |
|:---|:---|:---|:---|
| 测试类 | `Test` + 服务/模块 + 场景类型 | `TestECSBasic` | `Test_ecs` |
| 测试方法 | `test_<服务>_<功能>` | `test_ecs_off_start` | `test_001` |
| `@allure.title` | 沿用同模块风格，`资源名-功能点` | `弹性云服务器-关机和启动` | `test ecs off` |
| 数据驱动 title | 保留参数化占位 | `资源名-创建-{params[case_name]}` | `创建测试` |
| 资源名（数据） | 用 `random_data()`，禁止硬编码固定名 | `random_data(length=4)` | `"vm-test-1"` |
| 新增 Page 方法 | `服务_操作`（公共）/ `_动作_对象`（私有），见 `page_func_spec.md` | `acl_rule_create` / `_select_cluster` | `do_it` |

---

## 7. 框架公共能力速查（非完整清单，以代码为准）

> 编码前确认能否复用以下能力，**严禁重复造轮子**。这些方法由 `BasePage` 各 Mixin 提供；本表不维护完整签名，**参数与最新方法以 `sugon_web/common/` 代码为准**。

| 类别 | 常用能力（示例） |
|:---|:---|
| 导航 | `goto_service(服务名)`、`goto_submenu(子菜单)`、`goto_detail_page(...)` |
| 公共按钮 | `btn_create` / `btn_submit` / `btn_reset` / `btn_refresh` / `btn_batch_delete` |
| 对话框 | `dialog_confirm` / `dialog_cancel` / `dialog_close` / `close_dialog_if_exists()` |
| 行/列数据 | `get_row_data(name)`、`get_column_data(列名)`、`get_row_by_name(name)`、`select_rows_by_names(names)` |
| 交互操作 | `click_action(资源名, 操作项)`、`search(关键词)` |
| 等待 | `wait_for_page_ready()`、`wait_for_operation_complete(timeout)`、`wait_for_source_complete(name, timeout)` |
| 断言（base） | `assert_popup_success/error`、`assert_status`、`assert_list_contain/not_contain`、`assert_deleted` |

> 新增业务方法前自查：上表是否已有能覆盖大部分需求的方法？有则复用，仅补专属逻辑。找不到时先 `Grep` 确认，再在正确的层新增，不在测试层自构等价 locator 绕过。

---

## 8. 测试数据与 fixture（细则见 `fixtures_index.md` / `fixture_spec.md`）

本文件只规定测试层调用纪律，复用清单与新增规范见权威文件：

- **必须复用现有 fixture**；仅当"现有 fixture 完全无法通过参数化满足需求"时才新增。
- **批量创建必须用 `count` 参数**（`@pytest.mark.parametrize("vm", [{"basic": {"count": N}}], indirect=True)` 或 `[{"count": N}]`），**严禁手动 `for` 循环创建**。
- **清理归属于 fixture**：现有 teardown 能覆盖的不在用例里手动删；无法覆盖的按 `fixture_spec.md` 的 yield-based / 注册表模式补充。
- fixture 内**禁止写断言、禁止写多步页面交互**（委托 helper）；helper 内**禁止 `yield`、禁止 fixture 依赖注入**。

**Fixture 委托 Helper 示例**（测试层不写此代码，但需理解此分离，避免把多步操作写进 fixture）：
```python
# conftest.py — fixture 只负责生命周期
@pytest.fixture
def resource(request, page, resource_page):
    params = request.param or {}
    name = params.get("name") or f"resource-{random_data()}"
    result = create_resource(page, resource_page, name=name)  # 委托 helper
    yield result
    delete_resource(page, resource_page, result["name"])      # 委托 helper

# _resource_helpers.py — helper 负责完整流程（无 yield、无 fixture 依赖）
def create_resource(page, resource_page, name: str) -> dict:
    resource_page.create(name=name)
    return {"name": name}
```

---

## 9. 页面交互与定位（细则见 `page_func_spec.md`）

- 测试层**只调用 Page 公共方法**，不出现任何底层定位（见 §3 约束 3）。
- 新增/修改 Page 方法时，定位优先级（详见权威文件）：`get_by_role` > `get_by_label` > `get_by_placeholder` > `get_by_text(exact=True)` > `get_by_test_id` > （仅第三方组件兜底）CSS。**禁止 XPath**。
- 优先在 `dialog` / 当前 `tab` / 目标表格或目标行范围内 scoped 定位；`first()` / `nth()` 仅作缩小范围后的兜底，不作首选。
- 通用组件（el-select / el-dialog / el-table）的 CSS 交互**下沉 `BasePage`/Mixin**，Page 子类只调语义方法。
- 新增 Page 公共方法**必须有 docstring**（用途、参数及可选值/默认值、返回值）。

---

## 10. 等待策略（细则见 `page_func_spec.md`）

- **禁止固定等待**（`time.sleep` / `wait_for_timeout`）作状态等待。
- 进入页面/提交表单后先 `wait_for_page_ready()`；状态收敛用 `wait_for_operation_complete()` / `wait_for_source_complete()`，或断言方法内置 `expect` 轮询。
- 需求 CSV 明确的等待时长作为收敛方法的 `timeout` 参数传入，**不得转成固定 sleep**；未明确则用框架默认值。

---

## 11. 断言（细则见 `assertion_guidelines.md`）

测试层调用断言的纪律（分层模型、决策树、新增规范见权威文件）：

| 层级 | 断言内容 | 是否显式 assert | 典型数量 |
|:---|:---|:--:|:--:|
| **P0 流程阻塞点** | 操作成功弹窗 + 资源存在性/状态收敛 | 必须 | 2–4 |
| **P1 末态字段** | 字段值与预期一致（末态一次性集中回读） | 必须 | 1–3 |
| **P2 业务逻辑** | 端到端正确性（SSH/网络/数据一致） | 建议 | 0–3 |
| **P3 隐式验证** | 导航/输入/点击等操作本身 | 不写 | 每步都有 |

- **先搜索复用**：`grep -r "def assert_<对象>" sugon_web/assertions/`，有匹配直接复用，无匹配再按规范在正确层新增。
- **顺序**：状态变更类先等待收敛 → P0 断操作成功 + 存在性/状态 → P1 集中断字段值。**P0 与 P1 不重复断同一内容**（P0 不断字段值，P1 不再断存在性）。
- **SSH**：必须断言 `rc` 与 `stdout`，禁止 `|| true` 掩盖、禁止只 `logger.info` 不断言。
- 一个用例断言总数通常 3–8 个（长流程不超过 10）。过多 → 多半把 P3 也断了；过少 → 多半漏了 P0。

**断言分布示例**（P0 与 P1 分工、不重复）：
```python
with allure_step_log("步骤2: 创建规则"):
    sg_page.rule_create(...)
    sg_page.assert_popup_success("创建成功")   # P0 操作成功
    sg_page.assert_list_contain(rule_name)      # P0 存在性

with allure_step_log("步骤3: 验证规则字段"):
    data = sg_page.get_row_data(rule_name)      # 末态一次性取行数据
    assert data["端口"] == "22"                  # P1 字段值
    assert data["协议"] == "TCP"                 # P1 字段值
```

---

## 12. 复杂场景专项指南（步骤 > 8 或涉及 3+ 服务时）

> 复杂用例除遵循以上全部规范外，额外遵守本节。这是阶段三耗时长的高发区。

### 12.1 分解策略

- **按服务页面分组**：同一页面的连续操作合并为一个步骤块；跨页面跳转必须拆分步骤块，并在跳转后插入状态确认（P0）。
- **按操作类型分组**：创建/修改/验证各成一组，不在一个块内混排创建和删除。
- **状态等待独立成块**：异步操作后的状态收敛单独成步骤。示例：
  ```python
  with allure_step_log("步骤X: 等待资源状态收敛到运行中"):
      vpc_page.wait_for_source_complete(name, timeout=300)
  ```
- **清理独立成块**：fixture 无法覆盖的临时资源在末尾独立清理，顺序与需求"清理顺序"严格一致。

### 12.2 长流程断言分布

| 流程位置 | 层级 | 目的 |
|:---|:--:|:---|
| 每完成一个服务的核心操作 | P0 | 确认该操作成功，后续步骤依赖此结果 |
| 跨服务数据传递后 | P0 | 确认数据已正确传到下一服务 |
| 全部操作完成后 | P1 | 集中回读所有关键字段 |
| 端到端验证点 | P2 | SSH/API 验证最终业务结果 |

### 12.3 多资源依赖

- **共享资源**（需求标注"共享同一套测试数据"）：必须同一测试类 + `scope="class"` fixture 共享，全部用例跑完统一清理；禁止跨测试方法共享 function scope fixture 创建的资源状态。
- **动态创建**：用注册表模式 `clean_items` fixture 登记并统一清理，禁止漏登记导致资源泄漏。

### 12.4 复杂场景反模式

| 反模式 | 错误表现 | 正确做法 |
|:---|:---|:---|
| 单方法过长 | 一个 `test_` 超过 80 行 | 按服务/阶段拆分，或用 Helper 封装子流程 |
| 步骤块过大 | 一个 `allure_step_log` 含 10+ 行操作 | 按页面区域拆成多个步骤块 |
| 断言集中爆发 | 所有断言堆在最后一步 | P0 分散在每个关键操作后，P1 集中末态 |
| 资源泄漏 | 动态创建未登记清理 | 注册表模式 `clean_items` fixture |
| 硬编码等待 | `time.sleep(60)` 等异步完成 | `wait_for_source_complete()` / `assert_status()` 轮询 |

---

## 13. 常见错误与反模式（编码时主动规避）

| # | 反模式 | 错误做法 | 正确做法 |
|:--:|:---|:---|:---|
| 1 | 测试层写底层定位 | `page.locator(...)` / `expect(...)` 出现在 `test_*.py` | 封装到 Page 方法，测试层只调方法 |
| 2 | 手动循环创建资源 | `for i in range(3): page.create(...)` | fixture 的 `count` 参数 |
| 3 | 重复造 fixture/断言/方法 | 不搜索就新建同义能力 | 先 `Grep`，复用现有 |
| 4 | 固定等待 | `time.sleep(60)` 后直接断言 | 收敛等待方法 + 轮询 |
| 5 | 未等待就断言 | 资源"创建中"就断"运行中" | 先 `wait_for_source_complete()` 再断言 |
| 6 | 日志代替断言 | `logger.info(f"结果:{r}")` | `assert r["rc"] == 0` |
| 7 | 主流程 try/except 兜底 | `try/finally` 包裹核心步骤 | 让失败自然抛出，框架捕获 |
| 8 | 多场景塞一个方法 | 一个 `test_` 内跑多个独立场景 | `@pytest.mark.parametrize` 拆分 |
| 9 | 把流程写进 Page | Page 方法跨服务页面编排 | 下沉到 Helper |
| 10 | 改公共/前端代码 | 改 `common/` / `assertions/` / `refrence/` | 新增方法或新增可选参数 |
| 11 | 条件过宽 | `assert "运行" in status` | `assert status == "运行中"` 精确匹配 |

---

## 14. Red Flags —— 出现即停下重做

写代码时若发现自己正在做下列任一件事，**立即停止并改正**，不要找理由继续：

- "先在测试里直接 `.locator` 拿一下，省得封装方法" → **停。** 封装到 Page。
- "这个 fixture 好像没有，我直接 `for` 循环建几个" → **停。** 先 `Grep`，用 `count`。
- "状态可能没那么快，`sleep` 几秒再断言保险" → **停。** 用收敛等待。
- "这步可能偶发报错，包个 `try/except` 兜底" → **停。** 主流程不兜底。
- "这几个场景差不多，合一个方法里跑完" → **停。** 参数化拆分。
- "前端代码没找到，先按经验编个定位" → **停。** 匹配前端 / 跑侦察脚本。
- "用例太长先全写完再说" → **停。** 先按 §12 做分解规划再写。

| 借口 | 事实 |
|:---|:---|
| "本文件没列这个方法，应该是没有" | 本文件只是示例。以代码为准，先 `Grep`。 |
| "封装太麻烦，测试层直接定位更快" | `precheck.py` 会拦截，阶段三必返工，更慢。 |
| "差不多对齐就行" | 字面不对齐就是不对齐，长流程用例的偏差会被放大到阶段三。 |
| "预研太花时间，先写起来" | 预研省下的是阶段三成倍的修复时间。 |

---

## 15. 编码自检清单

编码完成、进入执行前逐项自检；任一项为"否"，先改代码再继续。

**P0 阻塞项（不通过不能交付）**
- [ ] 已读 `fixtures_index.md` 并 `Grep`，确认 fixture（及 `count`）优先复用而非新建。
- [ ] 已 `Grep` 确认断言/页面方法/公共能力无可复用项后才新增。
- [ ] 每段代码都在正确的层（测试/Page/Helper/Fixture/Assertion），无错层。
- [ ] `test_*.py` 内无 `.locator(` / `expect(` / XPath / `page.` 底层调用。
- [ ] 无 `time.sleep` / `wait_for_timeout` 作状态等待。
- [ ] 主流程无 `try/except` / `try/finally`；测试类体内无 `_` 前缀辅助方法。
- [ ] 无手动 `for` 循环创建资源（批量用 `count`）。
- [ ] P0（操作成功 + 存在性/状态收敛）无遗漏，状态变更先等待收敛；P0/P1 不重复断言。
- [ ] 测试方法数 = CSV/MD 场景数；多场景已参数化。
- [ ] 资源名用 `random_data()`；测试数据严格对齐需求。
- [ ] 未改 `common/` / `assertions/` / `refrence/` / 阶段一 MD。

**P1 建议项（提升质量）**
- [ ] 已读同模块既有用例，命名与步骤风格与其一致。
- [ ] 每个 `allure_step_log` 块只含同类操作（操作/校验不混排）。
- [ ] 需求所有步骤、边界条件均覆盖，无遗漏无多余。
- [ ] 所有创建的资源都有清理路径（fixture teardown 或用例内清理）。
- [ ] P1 末态字段集中回读；SSH 断言了 `rc` 和 `stdout`；断言总数约 3–8。
- [ ] 定位优先 scoped 在 dialog/tab/表格内，基于前端代码而非凭空构造。
- [ ] 新增 Page 方法/fixture/断言均有完整中文 docstring；新增 fixture 遵循 `fixture_spec.md`、新增断言遵循 `assertion_guidelines.md` 并已登记/归位。

**复杂场景（步骤 > 8 或 3+ 服务时适用）**
- [ ] 已按页面/服务分组拆分步骤块，跨页面跳转后有状态确认。
- [ ] 异步等待已独立成步骤块，未用固定 sleep。
- [ ] 共享资源用 class-scoped fixture，独立资源用 function scope。
- [ ] 动态创建的资源已用注册表模式登记清理，无资源泄漏。

**最后**
- [ ] 已做语法检查与最小范围 pytest 收集/执行验证。
