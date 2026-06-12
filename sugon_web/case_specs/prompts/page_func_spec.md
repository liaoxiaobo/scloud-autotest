# Playwright Page 层方法封装规范

本规范基于 Playwright 官方文档（playwright.dev）的最佳实践，结合本项目 4 层架构（Page Object / Fixture / Helper / Test Class）制定，用于统一 Page Object 层的方法封装标准，减少因定位策略不一致导致的 flaky 用例和维护成本。

---

## 一、定位策略规范（核心）

### 1.1 优先级顺序

严格按以下优先级选择定位方式：

| 优先级 | 方法 | 适用场景 |
|:---|:---|:---|
| 1 | `get_by_role(role, name=...)` | **所有可交互元素的默认方式**。按钮、链接、输入框、复选框、表格行等。Playwright 会检查无障碍树，确保元素可被辅助技术识别。 |
| 2 | `get_by_label(text)` | 有 label 关联的表单输入。同时验证 label 与 input 的 accessibility 关联。 |
| 3 | `get_by_placeholder(text)` | 无可见 label、只有 placeholder 的输入框。 |
| 4 | `get_by_text(text, exact=...)` | 唯一静态文本，无交互 role。 |
| 5 | `get_by_test_id(test_id)` | **最后手段**。无语义 role、无可见文本的元素（图表、图标）。 |
| 6 | `locator("css")` / `locator("xpath")` | **避免使用**。仅无法修改的第三方组件例外。 |

> **本项目重要例外（必读）**：曙光云大量使用 `cl-button` 等**自定义组件**，它们**没有原生 `role=button`**，`get_by_role("button", name=...)` 会**定位不到而超时**。遇到 `cl-button` 一律改用 `get_by_text("按钮文案")`（详见 §1.3）。所以"`get_by_role` 是默认"这条对本项目自定义组件不成立——先判断是不是自定义组件。

### 1.2 谨慎使用的反模式

| 反模式 | 原因 | 正确做法 |
|:---|:---|:---|
| `.nth(n)` 解决歧义 | 掩盖 UI 歧义问题，DOM 顺序变化即失效 | 用 `filter(has_text=...)` 在父容器内精确定位 |
| `.first` 无条件使用 | 与 `.nth(0)` 等价，DOM 顺序变化即失效；仅在"唯一匹配但 Playwright 认为可能多匹配"时安全 | 优先用 `filter` 精确限定；仅在 scoped 容器内确保唯一匹配时使用 |
| `filter(has=.css_class)` | 依赖前端实现细节，class 名重构即失效 | `get_by_role("button", name="保存")` |
| `page.wait_for_timeout(n)` | 假等待，既不保证就绪又拖慢执行 | 依赖自动等待，必要时用 `expect` 显式等待 |
| `query_selector` / ElementHandle | 静态快照，可能指向已销毁的 DOM | 始终使用 Locator（惰性求值） |
| 超长 CSS 链 `div > section > ul > li` | DOM 结构变化即失效 | 按区域拆分，链式 scoped 定位 |

### 1.3 本项目自定义组件定位速查（高频陷阱，编码前必看）

> 以下是实测在复杂用例阶段三反复返工的项目专属陷阱。**编码时直接按此写，不要再用通用默认方式踩坑**；仍不确定时用 `recon_page.py` 侦察真实渲染态。

| 场景 | 错误（会超时/报错） | 正确做法 |
|:---|:---|:---|
| `cl-button` 自定义按钮（立即创建/下一步/确定/搜索/保存等） | `get_by_role("button", name="保存")` | `get_by_text("保存")`（不依赖 ARIA role） |
| Element UI 下拉框，页面存在多个（含隐藏） | `.el-select-dropdown__wrap`（strict 多匹配） | `.el-select-dropdown:visible` 限定可见，或经 BasePage `_select_dropdown` 语义封装 |
| 多步向导对话框（如监听器创建 = 3 步） | 当单页表单填完直接点"确定" | 按真实步数逐步：Step1 →"下一步"→ Step2 →"下一步"→ Step3 →"确定"；步数以侦察/前端为准 |
| 详情页返回按钮（动态渲染） | 直接 click `el-icon-arrow-left` 或猜 `.sugon-back-button` | click 前 `expect(btn).to_be_enabled()`；**以 URL 变化判定返回成功**；多策略兜底（图标→面包屑→`go_back()`） |
| 下拉选项文案 | 凭需求文档直译（如"云服务器实例"） | 以页面真实渲染文案为准（如"弹性云服务器 ECS"），不确定先侦察 |

---

## 二、方法封装规范

### 2.1 公共方法

- **命名**：`服务_操作`（如 `lb_forward_rule_create`）
- **参数**：全部业务数据化，不硬编码任何前端值
- **返回值**：必要时返回创建的资源标识
- **内部断言**：使用 `expect` 断言关键节点可见性
- **操作日志**：方法完成后记录操作结果（资源名、状态等），便于失败排查

### 2.2 私有方法

- **命名**：`_动作_对象`（如 `_select_condition_type`）
- **职责**：封装单步页面交互，不暴露给测试层

### 2.3 示例

> 本节展示**按规范实现的最佳实践**。

```python
from sugon_web.utils.logger import logger

def lb_forward_rule_create(self, slb_name, rule_name):
    """创建 L7 转发规则。

    参数全部业务数据化，不硬编码任何前端值。
    """
    # 1. 导航到正确页面
    self.goto_slb_detail(slb_name, tab_name="监听器")

    # 2. 点击触发按钮（优先 get_by_text，不用 CSS）
    self.get_by_text("插入新规则").click()

    # 3. 等待表单出现（用 expect 断言，不用 wait_for_timeout）
    dialog = self.get_by_role("dialog", name="新建规则")
    expect(dialog).to_be_visible(timeout=5000)

    # 4. 填写表单（优先 get_by_placeholder）
    dialog.get_by_placeholder("请输入规则名称").fill(rule_name)

    # 5. 保存（优先 role）
    dialog.get_by_role("button", name="保存").click()

    # 6. 断言结果并记录日志
    self.assert_popup_success()
    logger.info(f"转发规则创建成功: {rule_name}")
```

### 2.4 方法粒度决策规则（Page vs Helper）

核心原则：**Page 层封装"单页面内的交互单元"，Helper 层编排"跨页面的业务流程"。**

| 场景 | 归属 | 示例 |
|:---|:---|:---|
| 单个弹窗/表单的填写与提交 | **Page** | `lb_forward_rule_create(rule_name, ...)` |
| 单个表格行的查找与操作 | **Page** | `click_action(vm_name, "删除")` |
| 当前页面内的标签切换+内容操作 | **Page** | `goto_slb_detail(slb_name, tab_name="监听器")` |
| 跨多个服务的资源创建链路 | **Helper** | `_prepare_lb_full_env(vpc, subnet, ecs)` |
| 创建 A 后需等待状态再创建 B | **Helper** | `_build_ecs_with_evm(evm_params)` |
| UI 操作后需 SSH 后端校验的完整流程 | **Test Class / Helper** | 测试方法调用 Page → 断言 → SSH 校验 |

**决策口诀：**
> 一个页面、一个弹窗、一个表单 → Page；
> 多个页面、多个服务、状态依赖 → Helper。

**具体判定标准：**
1. **单页面内的原子流程**（导航到子菜单、打开弹窗、填写表单、保存）→ **保留在 Page**
2. **涉及 2 个及以上不同服务页面** 的 URL 变化（如从 VPC 页面跳转到 ECS 页面）→ **下沉到 Helper**
3. **单资源单操作**（创建一个规则、删除一个实例）→ **保留在 Page**
4. **多资源串行且有状态依赖**（创建 VPC → 创建子网 → 创建 ECS）→ **下沉到 Helper**
5. **需要组合跨页面的多个 Page 方法并在中间插入等待/断言** → **下沉到 Helper**

> **关键区分：** Page 层允许"单页面内的多步组合"（如导航→打开弹窗→填表单→保存），但不允许"跨服务页面的流程编排"。前者是页面交互原子，后者是业务场景组装。

### 2.5 BasePage 通用组件封装规范

项目中大量使用 Element UI 组件（`el-select`、`el-dialog`、`el-table`、`el-form`），各 Page 类**禁止重复写相同的 CSS 定位**。以下通用操作应在 `BasePage` 或对应 `Mixin` 中统一封装，Page 子类直接调用。

**判定下沉标准：相同 CSS 模式在项目中出现超过 3 次，必须下沉到 BasePage/Mixin。**

> **CSS 使用豁免：** 1.1 节禁止在 Page 子类中直接使用 CSS，但 **BasePage / Mixin 中允许使用 CSS 封装第三方组件（Element UI）的通用交互**。一旦下沉到 BasePage，具体 Page 代码只能通过语义方法调用，**禁止再次直接引用** `.el-select-dropdown`、`.el-form-item` 等底层 CSS。

**需要下沉到 BasePage/Mixin 的典型组件：**

| 组件类型 | 封装目标（语义接口） |
|:---|:---|
| 下拉框选择 | `_select_dropdown(label, value, *, container)` |
| 弹窗/对话框 | `_get_dialog(title)`、`_dialog_click_button(dialog, name)` |
| 表格行操作 | `_table_row_action(table, row_text, action_name)` |
| 表单字段填写 | `_fill_form_field(form, label, value)` |

**封装原则：**
1. **语义优先**：封装后的对外接口只接受业务语义参数（label 文本、按钮名称），不接受 CSS 选择器
2. **内部兜底**：Element UI 组件无标准 ARIA role 时，允许内部使用 CSS 作为 fallback
3. **断言内聚**：封装方法内部自行处理 `expect` 断言（如弹窗可见、按钮可点击），不暴露给调用方
4. **限制透明**：若封装方法有前提假设（如"页面只有一个可见下拉框"），必须在 docstring 中声明

**Page 子类调用示例：**

```python
# 正确：通过 BasePage 语义方法调用
self._select_dropdown("条件类型", condition_type, container=dialog)

# 错误：直接写 CSS
self.locator("div.el-select-dropdown:visible li").filter(...)
```

---

## 三、Scoped 链式定位规范

**核心原则：按页面区域拆分，避免超长选择器。**

```python
# 错误：脆弱的长链
dialog.locator("div.el-form-item").filter(
    has_text=re.compile(r"负载调度算法")
).get_by_placeholder("请选择").click()

# 正确：按区域 scoped 定位
# 转发规则表单分左右两栏
left_section = form_container.locator(".form-left").first
right_section = form_container.locator(".form-right").first

# 左栏选条件
left_section.get_by_role("combobox", name="条件类型").click()

# 右栏选动作
right_section.get_by_role("combobox", name="动作类型").click()
right_section.get_by_role("combobox", name="转发至").click()

# 保存按钮在底部 btn-box
form_container.locator(".btn-box").get_by_role("button", name="保存").click()
```

---

## 四、等待策略规范

| 场景 | 反模式 | 正确做法 |
|:---|:---|:---|
| 等待弹窗出现 | `page.wait_for_timeout(3000)` | `expect(dialog).to_be_visible(timeout=5000)` |
| 等待列表加载 | `time.sleep(5)` | `table_container.locator(".el-loading-mask").wait_for(state="hidden", timeout=15000)` |
| 等待元素可点击 | `page.wait_for_selector(".btn")` | `expect(btn).to_be_enabled()`，然后 `btn.click()` |
| 轮询检查状态 | `while time.time() < deadline: ... sleep(10)` | `expect.poll(lambda: get_status(), timeout=120).to_equal("运行中")` |
| Vue 渲染后操作 | `page.wait_for_timeout(1500)` | 用 `expect` 断言目标元素可见后再操作 |

---

## 五、与项目 4 层架构的结合

| 层级 | 官方规范落地 | 当前项目改进点 |
|:---|:---|:---|
| **Page Object** | 方法内部全部使用 `get_by_role` / `get_by_label` / `get_by_placeholder` 定位；用 `expect` 做可见性断言；禁止 `wait_for_timeout` | 仍大量依赖 `.el-form-item`、`.el-button` 等 CSS 类名；`wait_for_timeout` 使用普遍 |
| **Fixture** | 资源生命周期管理不变，`yield` + teardown 保持现有模式 | 符合规范，无需改动 |
| **Helper** | 纯函数，不持有 page 引用 | 符合规范，无需改动 |
| **Test Class** | 只调用 Page Object 公共方法，不写定位逻辑；用 `assert` 做业务断言（非 DOM 断言） | 部分测试中存在 DOM 定位逻辑，应下沉到 Page Object |

---

## 六、总结

**核心原则一句话：优先用语义定位（role/label/placeholder），避免用 CSS 类名；用自动等待替代固定 sleep；用 expect 断言替代原生 assert。**
