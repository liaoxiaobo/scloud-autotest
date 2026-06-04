# UI自动化测试用例开发规范

> **读者与角色**：本文件由 AI 在执行 `test-script-workflow`（阶段二编码）与 `test-self-heal`（修复）时阅读。你是一名资深 UI 自动化测试工程师，任务是**复用项目现有能力**、按既有风格写出**一次就对、少返工**的脚本，而不是自创一套写法。
>
> **适用范围**：Playwright + Pytest + POM 架构的 SugonCloud Web UI 自动化测试。
>
> **执行指令**：本文所有"必须/禁止/铁律"均为硬性约束，不可违反；所有"参考"指向的文件需在对应时机按需阅读。
>
> **本文件的边界（单一事实来源，禁止重复定义）**：遇到下表主题，一律跳转对应权威文件，**不要在本文件凭记忆复述其内容**，避免规范冲突。
>
> | 主题 | 权威文件 | 本文件态度 |
> |---|---|---|
> | fixture 复用清单 / count 批量 | `../fixtures_index.md` | 只引用，不罗列 |
> | fixture 新增/封装/teardown 规范 | `fixture_spec.md` | 只引用，不重述 |
> | 断言分层模型(P0/P1/P2/P3)与编写规范 | `assertion_guidelines.md` | 只引用，不另立模型 |
> | 定位策略规范、BasePage 下沉标准、Page vs Helper 粒度决策 | `page_func_spec.md` | 只引用，不另立 |
> | 本文件负责 | 编码流程、四层架构、定位与组件模式、测试层模式、自检与反模式 | 权威定义 |
>
> **防幻觉总则**：凡是文件路径、import 路径、fixture 名、方法名、选择器，**必须以真实代码为准**——先 `grep`/`Read` 确认存在，再使用；**严禁凭组件名、字段名、经验"猜"一个不存在的标识或选择器**。本文示例中的具体方法名（如 `slb_lb_create`）是**结构示意**，换模块时不可照抄，须用所在模块真实存在的方法。

---

## 一、核心原则（先建立心智模型，再动手）

这五条是后续所有规则的根，每写一行代码前先自问是否违背。

1. **复用优先，禁止造轮子**：能用现有 fixture / 公共方法 / 断言 / 同模块写法解决的，绝不新写。新增前先搜索确认无可复用项（见第二章 Step 1）。
2. **先勘察、后编码，绝不臆造定位**：任何定位都必须有**事实依据**——来自前端工程 `.vue` 源码，或运行时侦察脚本的真实渲染态。臆造定位是阶段三反复返工的头号根因。
3. **分层职责，各司其职**：测试方法只组织步骤与断言；Page Object 只封装单步交互；fixture 只管资源生命周期；helper 只组装多步流程；断言只做只读校验。越界即难维护、难修复（见第三章）。
4. **条件等待，拒绝固定 sleep**：所有等待都等"某个条件成立"，不等"固定秒数"。固定等待是偶发失败（flaky）和稳定性轮次不过的主因（见 5.3）。
5. **面向"一次写对"**：复杂用例（步骤多、组件特殊、异步长）尤其要在编码前把定位、等待、断言、清理想清楚。**编码期多花十分钟确认事实，胜过执行期返工一小时。**

---

## 二、编码四步强制流程（按顺序执行，不可跳过）

**为什么不可跳过**：复杂用例（步骤 >8、动态表单、跨多子菜单、长等待、自定义组件）若不先规划就直接写，阶段三修复耗时将显著增加。

```
Step 1 需求解析   → 输出《步骤清单》+ 强制搜索
Step 2 编码计划   → 输出《编码计划》（复杂用例必须）
Step 3 编码执行   → 输出代码
Step 4 交付前自审 → 输出《自审结论》（见第八章）
```

### Step 1：需求解析（输出《步骤清单》）

把需求 MD 的"测试步骤"逐条拆解并标注属性，明确每步"测什么、属于哪类操作"：

| 属性标记 | 含义 | 示例 |
|:---|:---|:---|
| `UI` | UI 页面操作 | 创建监听器、添加资源池成员 |
| `SSH` | SSH 后台操作 | 启动 http.server、执行 curl |
| `WAIT` | 等待/轮询 | 等状态变"运行中"、等 PXE 插件安装 |
| `NAV` | 导航切换 | 进入转发规则 tab、返回列表 |
| `FORM` | 表单填写 | 填规则名称、选条件类型 |

**步骤清单输出格式**：

```
步骤清单：
1. [UI][NAV] 进入负载均衡模块
2. [UI][FORM] 创建监听器（[复杂]：动态表单）
3. [SSH] 启动后端服务
4. [WAIT] 等待服务就绪
5. [SSH] 执行 curl 验证
```

**复杂步骤识别（满足任一即标 `[复杂]`）**：条件联动显隐的表单字段（选 A 后出现 B）／自定义组件（非标准 Element UI，如 `cl-button`、`SugonDeleteDialog`）／等待 >5 分钟或需轮询／跨多子菜单（>2 次切换）／操作列项默认隐藏需特殊触发／非标准表格（拖拽列、卡片布局）。

**编码前强制搜索（输出步骤清单后必做，对照真实代码，杜绝臆造）**：

```bash
# 1. 同模块已有 Page Object 方法
grep -rE "def (create|goto|add|delete|edit|config)" sugon_web/pages/{当前模块}/
# 2. 已有断言方法
grep -r "def assert_" sugon_web/assertions/
# 3. 可复用 fixture（并对照 ../fixtures_index.md 确认 count 等参数）
grep -r "@pytest.fixture" --include="conftest.py" sugon_web/testcase/
# 4. 同模块已有用例（参考风格）
grep -r "def test_" sugon_web/testcase/{当前模块}/ | head -20
```

判定：搜到同名/同功能 → **直接复用**；搜到相似 → **参考其实现**，判断是否扩展参数；完全没有 → **规划新增**，按第四章模式实现。

**需求描述 → 代码映射速查**：

| 需求里的关键词 | 代码映射 | 归属层 |
|:---|:---|:---|
| "进入 XXX 模块/页面" | `goto_service("XXX")` 或 fixture 预置 | Test |
| "点击 XXX 名称进入详情" | `goto_xxx_detail(name)` | Page Object |
| "点击 XXX tab" | `goto_xxx_tab(name)` | Page Object |
| "点击新建按钮" | 在 Page Object 方法内处理，**测试层不直接点** | Page Object |
| "创建 XXX，字段值为…" | `xxx_create(字段参数…)` | Page Object |
| "选择 XXX 作为成员" | `xxx_add_member(vm_names=[...])` | Page Object |
| "返回上一步/返回列表" | 在 Page Object 方法内处理导航 | Page Object |
| "ssh 连接 XXX 执行命令" | `ssh_vm.connect(mfip)` + `ssh_vm.run(cmd, return_rc=True)` | Test |
| "等待 X 秒" | 后台启动可短等；**状态等待必须轮询**（见 5.3） | Test |
| "验证/预期/检查" | 按 5.5 决策树选断言层级 | Test |
| "记录某值供后续使用" | Page Object 方法 `return`，测试层存变量（见 4.11） | Test |

### Step 2：编码计划（复杂用例必须输出）

- **简单用例**（步骤 ≤8 且无 `[复杂]` 步骤）→ 可跳过本步，直接 Step 3。
- **复杂用例**（步骤 >8，或含 `[复杂]` 步骤）→ **必须**先输出《编码计划》再写代码：

```
## 编码计划
### 1. Fixture 复用方案（参考 ../fixtures_index.md）
- vm: {"basic": {"count": 3}, "bind_mfip": True}
- slb: {"version": "V2", "ha_enable": True}
- 清理: clean_lb_listener（动态资源注册表）
### 2. Page Object 方法规划（区分复用/新增）
| 方法名 | 归属文件 | 签名 | 复用/新增 |
|---|---|---|---|
| goto_xxx_tab | pages/network/slb/lb_detail.py | def goto_xxx_tab(self, lb_name) | 复用 |
### 3. 断言规划（参考 assertion_guidelines.md）
| 步骤 | 层级 | 断言方法 |
|---|---|---|
| 创建监听器 | P0 | assert_popup_success() + assert_listener_exists() |
### 4. [复杂] 步骤处理方案
| 步骤 | 复杂点 | 处理方案 |
|---|---|---|
| 转发规则创建 | v-if 动态表单 | 已读 xxx.vue 确认 v-if 逻辑，用区域限定+相对定位 |
| PXE 安装 | 5 分钟异步 | 轮询刷新查状态，超时 skip |
```

**编码计划必须明确**：① 哪些资源由 fixture 预置；② 哪些资源运行时动态创建（需注册 cleanup）；③ 哪些 `[复杂]` 步骤需先读前端 `.vue` 源码——涉及动态表单、自定义组件、非标准表格的，必须写出"已读 xxx.vue，确认 DOM 结构如下…"；④ 每步断言层级。

### Step 3：编码执行

1. 按步骤清单编号**逐条实现**，完成一步标 `[已编码]`。
2. **优先调用已有方法**，不重复实现同功能。
3. 编码顺序：先写 Page Object 新增方法（如有）→ 再写测试类（fixture 声明、参数化、Allure 注解）→ 再按步骤清单逐块填充测试方法 → 最后补断言与清理注册。
4. 每新增一个 Page Object 方法立即补 docstring（用途、参数、可选值/默认值）；每完成一个步骤立即补对应断言。

### Step 4：交付前自审

按第八章《交付前自我审查清单》逐项核对，**任一 P0 项不通过禁止交付**。

---

## 三、四层架构红线（不可逾越）

| 层级 | 只做什么 | 绝对禁止 | 规范出处 |
|:---|:---|:---|:---|
| **Test 测试类** | 测试步骤、Allure 步骤块、断言、局部变量 | 直接调 `page.locator()`/`page.click()`；写跨用例辅助方法；`try/except` 吞异常 | 第五章 |
| **Page Object** `pages/` | 单步页面交互封装、元素定位策略、返回数据 | 组织测试场景编排；方法体内直接写 `assert`（断言走 Mixin）；调用 fixture / 含 `yield` | 第四章 |
| **Fixture** `conftest.py` | 参数解析、调用 helper 创建、`yield`、调用 helper 清理 | 直接写 `page.click()`/`page.fill()`；写断言；资源型用 `return` 代替 `yield` | `fixture_spec.md` |
| **Helper** `_*_helpers.py` | 纯函数：多步流程组装、SSH 命令组装、数据比较、轮询逻辑 | 声明 fixture 依赖；含 `yield`；操作 `page` 生命周期 | `fixture_spec.md` |

---

## 四、页面对象核心模式（复杂场景核心一）

> 本章给出**已在项目真实代码中验证过的**定位模式，遇到复杂页面优先照此处理，不要凭空构造。

### 4.0 Page Object 编码通则

- 只封装**单步**页面交互与业务动作，不组织测试步骤、不写断言、不写清理。
- 已有公共能力（见 4.10 速查）能覆盖时，**禁止**新增同义方法。
- 新增业务方法必须有 **docstring**（用途、参数含义、可选值/默认值）；需跨步骤使用的数据（VIP、IP、UUID 等）由方法 **return** 返回（见 4.11）。
- 断言能力通过多重继承注入，**页面对象方法体内禁止直接写 `assert`**（见 4.9）。

### 4.0a 方法粒度：Page vs Helper

核心原则：**Page 层封装"单页面内的交互单元"，Helper 层编排"跨页面的业务流程"。**

**决策口诀：**
> 一个页面、一个弹窗、一个表单 → Page；
> 多个页面、多个服务、状态依赖 → Helper。

**场景归属速查（方法命名示意）：**

| 场景 | 归属 | 示例 |
|:---|:---|:---|
| 单个弹窗/表单的填写与提交 | **Page** | `lb_forward_rule_create(rule_name, ...)` |
| 跨多个服务的资源创建链路 | **Helper** | `_prepare_lb_full_env(vpc, subnet, ecs)` |
| 创建 A 后需等待状态再创建 B | **Helper** | `_build_ecs_with_evm(evm_params)` |
| UI 操作后需 SSH 后端校验 | **Test Class** | 测试方法调用 Page → 断言 → SSH 校验 |

**具体判定标准：**
1. **单页面内的原子流程**（导航到子菜单、打开弹窗、填写表单、保存）→ **保留在 Page**
2. **涉及 2 个及以上不同服务页面** 的 URL 变化 → **下沉到 Helper**
3. **单资源单操作**（创建一个规则、删除一个实例）→ **保留在 Page**
4. **多资源串行且有状态依赖**（创建 VPC → 创建子网 → 创建 ECS）→ **下沉到 Helper**
5. **需要组合跨页面的多个 Page 方法并在中间插入等待/断言** → **下沉到 Helper**

> **关键区分：** Page 层允许"单页面内的多步组合"，但不允许"跨服务页面的流程编排"。

### 4.0b BasePage 通用组件下沉标准

项目中大量使用 Element UI 组件，各 Page 类**禁止重复写相同的 CSS 定位**。

**判定下沉标准：相同 CSS 模式在项目中出现超过 3 次，必须下沉到 BasePage/Mixin。**

> **CSS 使用豁免：** 定位规范禁止在 Page 子类中直接使用 CSS，但 **BasePage / Mixin 中允许使用 CSS 封装第三方组件（Element UI）的通用交互**。一旦下沉到 BasePage，具体 Page 代码只能通过语义方法调用，**禁止再次直接引用** `.el-select-dropdown`、`.el-form-item` 等底层 CSS。

**需要下沉的典型组件：**

| 组件类型 | 封装目标（语义接口） |
|:---|:---|
| 下拉框选择 | `_select_dropdown(label, value, *, container)` |
| 弹窗/对话框 | `_get_dialog(title)`、`_dialog_click_button(dialog, name)` |
| 表格行操作 | `_table_row_action(table, row_text, action_name)` |
| 表单字段填写 | `_fill_form_field(form, label, value)` |

**封装原则：** 语义优先（对外只收业务参数）、内部兜底（无 ARIA role 时可用 CSS）、断言内聚、限制透明（docstring 声明前提）。

### 4.1 定位器优先级（严格递减）

```
1. get_by_role("按钮类型", name="可见文本")     ← 语义化，最稳定
2. get_by_text("精确文本", exact=True)           ← 文本匹配
3. get_by_placeholder("占位符文本")              ← 表单输入框
4. locator("CSS选择器").filter(has_text=...)     ← 缩小范围后
5. 区域限定 + 子定位器                           ← dialog/tab/表格内
6. nth() / first()                               ← 兜底，必须配合范围限定且基于真实渲染态确认序号
7. XPath                                         ← ❌ 绝对禁止
```

测试层**严禁直接使用** `locator()` / `expect()`，所有页面交互必须经 Page Object 封装。

> **补充反模式（第九章未覆盖）：** `.nth(n)` 解决歧义、`filter(has=.css_class)` 依赖实现细节、`query_selector` / ElementHandle 静态快照、超长 CSS 链。正确做法参考 4.1 定位器优先级与第九章速查表。

### 4.2 区域限定（先限定范围，再查找元素）

```python
# 模式 A：对话框内操作
dialog = self.get_by_role("dialog", name="新建资源池")
expect(dialog).to_be_visible(timeout=5000)
dialog.locator("div.el-form-item").filter(
    has_text=re.compile(r"资源池名称")
).get_by_role("textbox").fill(pool_name)

# 模式 B：Vue 自定义表单分组（左条件 / 右动作）
condition_area = self.locator(".form-left").first
action_area = self.locator(".form-right").first
match_type_select = condition_area.locator(".el-select").first

# 模式 C：激活的 Tab Pane
active_pane = self.locator(".el-tab-pane:not([aria-hidden='true'])").last
```

### 4.3 下拉选择

```python
select_trigger = dialog.locator("div.el-form-item").filter(
    has_text=re.compile(r"负载调度算法")
).get_by_placeholder("请选择")
select_trigger.click()
self.locator("div.el-select-dropdown:visible li").filter(
    has_text=re.compile(rf"^{re.escape(balance_method)}$")
).click()
```

要点：`get_by_placeholder("请选择")` 触发下拉；`:visible` 过滤当前可见层；`re.escape()` + `^...$` 精确匹配，避免误选相似项。

### 4.4 按钮点击（注意 cl-button 自定义组件）

```python
# ⚠️ 项目部分按钮是 cl-button 自定义组件（类名 .cloud-button-btn），不继承 .el-button
# ❌ 错误：self.locator(".el-button", has_text="保存")    # 永远找不到
# ✅ 正确：
save_btn = self.get_by_text("保存", exact=True).first
expect(save_btn).to_be_visible(timeout=3000)
save_btn.click()

# 表格头部"新建"按钮（cl-button）
create_btn = table_container.locator(
    ".cloud-table-header .cloud-button-btn"
).filter(has_text=re.compile(r"^\s*新建\s*$")).first
```

### 4.5 表单填写

```python
# 通过标签文本定位
dialog.locator("div.el-form-item").filter(
    has_text=re.compile(r"资源池名称")
).get_by_role("textbox").fill(pool_name)

# 通过 placeholder 定位
self.get_by_placeholder("请输入规则名称").first.fill(rule_name)

# strict mode 冲突规避：一个表单项含多个 input（如"用户名"含 text+password 两框）
self.get_by_placeholder("请输入用户名").first.fill(username)   # 用 .first 明确限定
```

### 4.6 动态表单（v-if / v-show）—— 头号陷阱

`v-if` 控制的字段在条件未满足时**不存在于 DOM**，条件满足后原元素可能被销毁重建，导致旧定位器失效。

```python
# ❌ 错误：用首次定位到的句柄在 Vue 重建 DOM 后继续使用
# ✅ 正确：初始态用 placeholder 触发，后续用区域限定 + 相对定位重新获取
condition_select = self.get_by_placeholder("请选择条件类型").first
condition_select.click()
# ...选择后 DOM 已变化...
match_type_select = condition_area.locator(".el-select").first   # 重新定位
```

**以下情况必须先读取前端 `.vue` 源码，不可跳过**：① 表单字段条件显隐（选 A 后出现 B）；② 列表是非标准表格（拖拽、卡片）；③ 按钮/组件是自定义标签；④ 保存/提交后无弹窗反馈；⑤ 页面有嵌套 Tab。
源码搜索：`find sugon_web/refrence/ -name "*.vue" | xargs grep -l "关键词"`。

**当静态 `.vue` 源码仍无法唯一确定定位时（操作项默认隐藏、同名元素多个、自定义组件内部结构复杂），先用运行时侦察脚本从真实渲染态枚举候选元素，再写定位**：

```
python .claude/skills/test-script-workflow/scripts/recon_page.py --service "<服务名>" [--submenu "<子菜单>"] [--grep "<关键词>"]
```

侦察脚本只读不改，复用项目登录态、整页截图、枚举 button/a/input/tab/列头，仅用于发现稳定定位。简单用例能直接确定定位的不必触发。

### 4.7 导航与子菜单

```python
from sugon_web.common.base import BasePage, submenu   # ✅ submenu 在 common.base，不在 utils

class XxxPage(BasePage):
    @submenu("子菜单名称")
    def goto_xxx_submenu(self):
        """导航到子菜单。"""
        self.goto_service("服务名称")
```

子菜单操作方法必须加 `@submenu("子菜单名")` 装饰器。

> ⚠️ 同名菜单消歧：当不同版本（如软装版 vs 智能网卡版）存在同名菜单/同名按钮时，需用 `.nth(i)` 选中正确项，并在导航后**校验 URL** 确认进对了页面。

### 4.8 表格与加载等待

```python
row_data = self.get_row_data(vm_name)                 # 获取行数据（字典）
self.click_action(vm_name, "删除")                    # 操作列点击（兼容平铺/下拉）
self.select_rows_by_names([vm1_name, vm2_name])       # 批量勾选
# 等待表格/对话框 loading 消失（el-loading）
table_container.locator(".el-loading-mask").wait_for(state="hidden", timeout=15000)
```

> ⚠️ `get_column_data()` 仅适用于标准表格；非标准表格（拖拽列、卡片布局）改用 `filter(has_text=...)` 在范围内定位。

### 4.9 断言 Mixin 继承

Page Object 通过多重继承引入断言能力，**页面对象方法体内禁止直接写 `assert`**：

```python
from sugon_web.assertions import PopupAssertionMixin, ListAssertionMixin
from sugon_web.common.base import BasePage   # ✅ BasePage 在 common.base，无 pages/base.py

class XxxPage(XxxAssertionMixin, PopupAssertionMixin, ListAssertionMixin, BasePage):
    pass   # 断言经继承链注入，测试层直接调用 self.assert_xxx()
```

### 4.10 `base.py` 公共交互能力速查（优先复用，禁止自造等价 locator）

> ⚠️ 本表非完整清单：**断言**见 `assertion_guidelines.md`、**fixture** 见 `../fixtures_index.md`；其余能力用 `grep` 搜索 `sugon_web/common/components/` 各组件确认，**不要凭本表猜测不存在的方法**。

| 类别 | 方法 | 用途 |
|---|---|---|
| 导航 | `goto_service(service)` / `goto_submenu(name)` | 进入服务页 / 切换子菜单 |
| 按钮 | `btn_create` / `btn_submit` / `btn_reset` / `btn_refresh` / `btn_batch_delete` | 标准操作按钮 |
| 对话框 | `dialog_confirm` / `dialog_cancel` / `dialog_close` / `close_dialog_if_exists()` | 标准对话框按钮 |
| 行操作 | `click_action(resource_name, option_text)` | 点击资源行操作项（兼容平铺/下拉） |
| 搜索 | `search(keyword)` | 复用搜索框搜索并等待结果 |
| 表格读取 | `get_row_data(name)` / `get_column_data(header)` / `get_row_by_name(name)` / `get_rows_by_text(text)` / `select_rows_by_names(names)` | 读行/列数据、定位行、批量勾选 |
| 等待 | `wait_for_page_ready()` / `wait_for_operation_complete(timeout)` / `wait_for_source_complete(name, ...)` | 页面就绪 / 操作完成 / 资源中间态收敛 |

### 4.11 跨步骤变量捕获

需求中"记录某值供后续步骤使用"（VIP、实例 IP、注册 UUID 等）时，由 Page Object 方法读取并 `return`，测试层存变量后续引用，**不要重复读页面**：

```python
lb_vip = vpc_page.get_slb_vip(slb["name"])                  # 捕获
ssh_vm.run(f"curl http://{lb_vip}:{PORT}/index.html")        # 后续复用
```

---

## 五、测试层核心模式

### 5.1 测试类骨架（推荐骨架）

> ⚠️ 骨架中 `slb_lb_create` / `lb_pool_add_vm` / `get_slb_vip` / `assert_listener_exists` 等是 **SLB 模块专属方法，仅示意结构**。换模块时**严禁照抄方法名或臆造同名方法**——必须先按第二章 Step 1 读所在模块真实用例与 Page Object，使用该模块实际存在的方法。
>
> ⚠️ `vm` fixture 的参数形态为 `{"basic": {"count": N}, ...}`（这是项目真实约定，`count` 嵌在 `basic` 内），不要写成 `{"count": N}`。

```python
import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import prepare_http_backend
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data

PORT = 7070


# 批量资源用 count 参数（注意 vm 的 count 嵌在 basic 内），禁止手动循环创建
@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V2", "ha_enable": True}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("转发规则场景验证")
class TestSlbV2HttpForward:
    """负载均衡V2 HTTP监听器转发规则验证（与同模块现有用例风格保持一致）。"""

    def test_lb_v2_http_forward_url_path(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        allure.dynamic.title("v2-HTTP监听器-转发规则-URL路径条件验证")
        cleanup = clean_lb_listener            # 清理注册表，登记后由 fixture 统一回收
        requester, *backends = vm              # vm[0] 作请求者，其余作后端
        lb_name = f"lb-http-{random_data()}"   # random_data 避免数据冲突
        pool_name = f"pool-{random_data()}"

        with allure_step_log("步骤1: 创建HTTP监听器"):
            vpc_page.slb_lb_create(                       # 复用 Page Object 封装方法
                slb_name=slb["name"], lb_name=lb_name,
                protocol="HTTP", port=PORT, pool_name=pool_name,
                balance_method="加权轮询", health_check=False,
            )
            vpc_page.assert_popup_success()               # P0: 操作成功
            vpc_page.assert_listener_exists(lb_name)      # P0: 存在性
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

        with allure_step_log("步骤2: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name, pool_name=pool_name, ports=PORT,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)  # helper 组装多步流程
                cleanup.add_backend_server(backend, port=PORT)

        lb_vip = vpc_page.get_slb_vip(slb["name"])        # 跨步骤变量捕获

        with allure_step_log("步骤4: 内网VIP访问验证"):
            ssh_vm.connect(requester["mfip"])
            result = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/index.html",
                return_rc=True,
            )
            assert result["rc"] == 0, f"访问失败: {result.get('stderr', '')}"   # P2: SSH 断言 rc
            assert "this is ecs" in result["stdout"], f"实际: {result['stdout']}"  # P2: 断言输出
```

### 5.2 用例结构与命名

1. **结构**：`准备数据 → 执行操作 → 校验结果`，每步用 `with allure_step_log("步骤N: 动词+对象+(条件/方式)")` 包裹。
2. **方法组织**：一个 CSV 场景对应一个 `def test_` 方法；**多个仅参数不同的同类场景**用 `@pytest.mark.parametrize` 参数化，**禁止合并进同一方法**，也禁止写多个高重复方法。
3. **共享数据**：需求 MD 标注"共享同一套测试数据"的场景，置于**同一测试类**，通过 **class-scoped fixture** 共享资源，该批次全部用例执行完后统一清理。
4. **标题**：`@allure.title` / `allure.dynamic.title` 沿用同模块现有风格（通常 `资源名-功能点`），参数化用例保留占位风格。
5. **批量资源**：用 fixture 的 `count` 参数（注意 `vm` 为 `{"basic": {"count": N}}`），**禁止测试方法里 `for` 循环建资源**。
6. **异常控制**：测试主流程**禁止**用 `try/finally`、`try/except` 包裹核心步骤（清理交给 fixture teardown，断言失败让框架捕获）。

### 5.3 等待与稳定性（复杂场景核心二）

1. **禁止固定等待**（`time.sleep(固定值)`、`wait_for_timeout`）作为状态收敛手段。进入页面/提交表单后先 `wait_for_page_ready()`；状态收敛用 `wait_for_operation_complete()` / `wait_for_source_complete()`。
2. **timeout 来源**：CSV 明确等待时长的，作为收敛等待方法的 `timeout` 参数传入（不转固定 sleep）；CSV 未明确的用框架方法默认值。
3. **长异步任务**（如 BMS 注册 30~40 分钟、PXE 安装约 5 分钟）：用"轮询 + 总超时"，按需求规定间隔刷新检查目标状态；**超时按环境问题 `pytest.skip`，不要硬失败、更不要用 `try/except` 绕过**。
4. **轮询间隔**：循环内允许 `time.sleep(短间隔)` 作为**轮询间隔**（如每 30 秒刷新），这与"固定等待"不同，是允许的。

> **补充等待场景：** `expect(dialog).to_be_visible()` 替代 `wait_for_timeout`；`locator(".el-loading-mask").wait_for(state="hidden")` 替代 `time.sleep`；`expect.poll()` 替代手动轮询。详见 5.3。

### 5.4 SSH 与后端命令

1. **必须用封装的 SSH fixture**：`ssh_vm`（经跳板机连虚机）、`ssh_host`（直连物理机）。**严禁**在测试代码里直接用 `paramiko` / `subprocess`。
2. **后台服务**用 `nohup ... > /dev/null 2>&1 &` 启动，启动后**轮询端口就绪**（如 `ss -lntp | grep 7070`），不要固定等待。
3. **命令必须断言**：断言返回码 `rc` 与 `stdout` 内容，**禁止** `|| true` 掩盖错误、**禁止**只 `logger.info` 不断言。无返回值命令（`mkdir`/`echo`/`cp`）由后续依赖步骤隐式验证。详见 `assertion_guidelines.md`。

```python
result = ssh_vm.run(f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/index.html", return_rc=True)
assert result["rc"] == 0, f"curl 失败: {result.get('stderr', '')}"
assert "this is vm1" in result["stdout"], f"期望 this is vm1, 实际: {result['stdout']}"
```

### 5.5 断言调用（详见 assertion_guidelines.md）

```
当前步骤操作完成后
├─ 纯交互/导航/输入？（P3）        → 不写 assert，Page Object 内部已 wait
├─ 失败阻塞后续或产生脏数据？（P0）→ assert_popup_success() / assert_xxx_exists() / assert_deleted()
├─ 流程末态验证字段值？（P1）      → get_row_data() 集中断言
└─ 端到端业务正确性？（P2）        → SSH 执行命令，assert rc + assert stdout
```

### 5.6 动态资源清理注册

```python
cleanup = clean_lb_listener
# ... 创建监听器/资源池/转发规则后登记，由 fixture 按序统一回收 ...
cleanup.add_listener({
    "slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name,
    "extra_pools": [backend_2_name], "forward_rules": [rule_1_name, rule_2_name],
})
```

---

## 六、测试数据与清理

1. **资源命名**用 `random_data()`，避免与历史数据冲突。
2. **批量创建**用 fixture 的 `count` 参数（见 `../fixtures_index.md`），禁止手动循环。
3. **清理顺序**：严格按需求 CSV 的"测试数据清理顺序"（经 MD 转写）执行，**子资源先删、父资源后删**，不得自行调整。
4. **清理归属**：能被现有 fixture teardown 覆盖的资源直接复用其清理；teardown 未覆盖的，参照 `fixture_spec.md` 的 yield-based / 注册表（registry）模式补充——运行时动态创建的资源用注册表 fixture 让用例 `add()` 登记、fixture 统一清理。**测试方法内不要自己写清理逻辑。**

---

## 七、限制约束（硬红线，任何情况下不可违反）

1. **禁止修改公共模块**：`sugon_web/common/base.py`、`sugon_web/common/playwright.py` 等公共代码一律不改；需增强公共能力时，在对应 Page Object 内封装，或向测试开发提需求。
2. **禁止修改断言公共方法**：`sugon_web/assertions/` 下 `base/`、`helpers/` 及各模块已封装断言不改，按 `assertion_guidelines.md` 新建方法或加默认值可选参数。
3. **禁止修改引用工程**：`sugon_web/refrence/` 目录（前端工程等）只读，不改、不删、不增。
4. **禁止篡改需求**：不改阶段一产出的 MD 需求文档（除非确认 MD 本身转换有误）；不擅改 CSV 已定义的测试数据/参数（端口、协议、权重、IP、规格、数量等），严格按 CSV 取值编码。

---

## 八、交付前自我审查清单（强制执行）

代码编写完成后、交付前逐项自检。**任一 P0 项未通过，禁止交付。**

### P0 — 阻塞项

- [ ] 复杂用例已输出《编码计划》，且覆盖所有 `[复杂]` 步骤处理方案
- [ ] 已对照 `../fixtures_index.md` 确认 fixture 复用方案，无重复封装
- [ ] 所有 import / 方法名 / fixture 名 / 选择器均经真实代码核实，无臆造
- [ ] 测试层未直接操作 `page`（无 `page.locator`/`page.click`/`expect`），无 XPath、无固定等待作状态收敛、无 broad except 吞异常
- [ ] 所有定位先限定区域再查找（dialog/tab/表格范围限定）
- [ ] 动态表单已确认 v-if/v-show 逻辑，定位策略正确；自定义组件已确认 `base.py` 是否适配，不适配的已在 PO 封装（未改 base.py）

### P1 — 质量项

- [ ] 新增方法有 docstring（用途、参数、可选值/默认值）
- [ ] SSH 命令断言了 `rc` 与 `stdout`；后台服务 `nohup &` + 端口轮询；长异步超时按环境问题 `skip`
- [ ] 断言按 P0/P1/P2/P3 分层（详见 `assertion_guidelines.md`），未用 `logger.info` 代替断言、未用 `|| true` 掩盖错误
- [ ] `def test_` 方法数 = CSV 场景数；高重复同类场景已参数化；共享数据用同类 + class-scoped fixture
- [ ] 资源用 `random_data()`；批量用 `count`（vm 为 `{"basic":{"count":N}}`）；动态资源已注册 cleanup；清理顺序按 CSV（子先父后）
- [ ] 代码通过 `pytest --collect-only` 语法检查

---

## 九、零容忍反模式速查表（编码时主动规避）

| # | 反模式（❌） | 正确做法（✅） |
|:--:|:---|:---|
| 1 | 凭组件名/经验猜一个选择器或方法名/import | 先 `grep`/`Read` 核实真实代码，再使用（防幻觉总则） |
| 2 | 测试层直接操作 `page`（`page.locator`/`page.click`） | 调用 `vpc_page.foo()` 经 Page Object 封装 |
| 3 | 使用 XPath | `get_by_role()` / `get_by_text(exact=True)` |
| 4 | `.el-button` 定位 `cl-button` 组件 | `get_by_text("保存", exact=True)` / `.cloud-button-btn`（§4.4） |
| 5 | `v-if` 销毁的元素上继续用旧定位器 | 区域限定 + `.el-select` 相对定位重新获取（§4.6） |
| 6 | `get_column_data()` 用于非标准表格 | `filter(has_text=...)` 范围内定位（§4.8） |
| 7 | `first()`/`nth()` 未限定范围或未确认序号 | `dialog.locator(".el-select").first`（§4.1） |
| 8 | 资源"创建中"就断言"运行中" | 先 `wait_for_source_complete()` 收敛再断言（§5.3） |
| 9 | `time.sleep(60)` 后直接断言 | 条件轮询 + 超时（§5.3） |
| 10 | 测试方法里 `for i in range(n)` 建资源 | fixture `count` 参数（vm 为 `{"basic":{"count":N}}`） |
| 11 | 测试方法里写 `try/finally` 清理 | 交给 fixture teardown / 注册表模式（§六） |
| 12 | SSH `cmd \|\| true` / 只 `logger.info` | 断言 `rc==0` 且 `stdout` 含预期（§5.4） |
| 13 | `except Exception: pass` 吞异常 | `logger.warning()` 后 `raise` |
| 14 | 改 `base.py` 以支持新页面 | 在该模块 Page Object 内封装（§七） |
| 15 | 多个场景合并进一个 `test_` 方法 | 一场景一方法或参数化（§5.2） |
| 16 | 跨步骤的值靠重复读页面 | 一次 `return` 捕获到变量后续复用（§4.11） |
| 17 | 长异步任务超时直接 FAIL | 超时按环境问题 `pytest.skip`（§5.3） |

---

## 十、外部参考索引（编码前按需阅读，本文件不重复其内容）

| 文件 | 阅读时机 | 核心内容 |
|:---|:---|:---|
| `../fixtures_index.md` | Step 1 必做 | fixture 强制约束、count 批量创建、fixture 速查表 |
| `assertion_guidelines.md` | Step 2 断言规划时 | P0/P1/P2/P3 分层模型、断言决策树、SSH 验证规范 |
| `page_func_spec.md` | Step 2 规划 Page Object 方法时 | 定位策略优先级、反模式、Page vs Helper 粒度、BasePage 下沉标准 |
| `fixture_spec.md` | 需新增/抽取 fixture 时 | fixture 编码规范、helper 委托、teardown 规范 |
| `sugon_web/assertions/` | Step 1 搜索已有断言时 | 已有断言 Mixin / helper，禁止重复造轮子 |
| `sugon_web/refrence/**/*.vue` | Step 2 复杂步骤读源码时 | 前端 DOM 结构、v-if 逻辑、自定义组件识别 |
| `sugon_web/refrence/module_index.yaml` | Step 1 匹配前端模块时 | 被测模块 ↔ 前端目录映射、搜索策略约束 |
| `scripts/recon_page.py`（运行时侦察） | 定位无法仅凭静态代码确定时 | 复用登录态枚举真实渲染态，发现稳定定位 |
