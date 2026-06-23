# 根据前端工程代码编写自动化测试脚本的实践指南

> **读者**：本文件面向 AI 编码代理（阶段二 `phase2-coding`，以及阶段三修复时定位/改 Page 方法），不是人类。
> **要解决的核心问题**：阶段三反复修复、耗时长的头号根因是**阶段二凭"读源码的印象"猜页面定位，且大概率猜错**。本指南教你：从前端源码里**能可靠拿什么、不能拿什么**，以及不能拿的部分该怎么办，从而在阶段二写出"一次就对"的定位，把返工挡在执行之前。
> **本指南与既有规范的分工**：定位"优先级与反模式"的**规则**在 `page_func_spec.md`；测试层编码的**总则与归属**在 `test_case_codegen_prompt.md`；前端目录的**查找策略**在 `module_index.yaml`。本指南**不复述**它们，只补它们都没讲的那一块——**怎么把"读到的前端代码"正确翻译成"稳定的运行态定位"**。
> **一句话原则**：**源码读"意图与流程"，运行态定"真实元素"，同模块抄"既有范式"；不确定就侦察，绝不凭印象猜。**
> **适用范围**：本指南是**通用指南**，适用于所有功能模块（计算/网络/存储/数据库/中间件…）。各模块页面差异很大，但底层都是同一套技术栈（Vue2 + Element UI + 自研 `cl-*` / `cloud-*` 组件库 + 前端权限指令），下面讲的"源码≠运行态"规律与组件配方对所有模块通用。
> **★ 代码归属（务必先看，否则会用错层、被 `precheck.py` 拦截、反而拖慢阶段三）**：本指南所有定位代码片段（`locator(...)`、`get_by_*`、`evaluate(...)`、CSS 等）**一律是写在页面对象层 `sugon_web/pages/` 的 Page 方法里**的；**测试层 `test_*.py` 严禁出现任何 `.locator(` / `expect(` / `evaluate` / XPath / CSS**（`precheck.py` 会机器拦截），测试层只调用 Page 的公共方法。所以本指南教的是"**在 Page 方法里怎么把定位写对**"，**不是**让你在测试用例里写定位。

---

## 一、为什么"只读源码就写 locator"必然踩坑（根因）

前端是 **Vue 单文件组件（`.vue`）**，你 `Read` 到的是**模板源码**，而 Playwright 操作的是**浏览器运行时真实渲染出来的 DOM**。二者**不是一一对应**的。下面 6 类"源码骗你"的情形在本项目高频出现，每类都给"错误猜法 → 正确做法"，**务必逐条记住**：

### 1.1 组件库把 DOM "传送"到别处（teleport / append-to-body）
Element UI 的 `el-select` 下拉面板、`el-dropdown` 菜单、日期选择器（以及开启 append-to-body 的 `el-dialog` 弹窗）等，**渲染时会脱离它在模板里所处的父容器、挂到接近 `<body>` 的高层级**——所以你**无法在"声明它的那个业务组件容器"里 scope 到它**。
- ❌ 错误猜法：看到 `<el-dialog>` 里有 `<el-select>`，就写 `dialog.get_by_text("选项A")` 想在弹窗内选下拉项 → **选不到**（选项根本不在 dialog 子树里）。
- ✅ 正确做法（本项目既有范式）：**两步**——先点触发器，再到**页面根**的下拉容器里选项：
  ```python
  # 1) 点开下拉（触发器用 placeholder 或 form-item label 定位，它在 dialog 内）
  algorithm_select = dialog.locator("div.el-form-item").filter(
      has_text=re.compile(r"负载调度算法")).get_by_placeholder("请选择")
  algorithm_select.click()
  # 2) 选项在 body 级的 .el-select-dropdown 里，用 self.locator(页面根)，不要用 dialog.
  self.locator("div.el-select-dropdown:visible li").filter(
      has_text=re.compile(rf"^{re.escape(value)}$")).click()
  ```
- 同理 `el-dialog`：用 `get_by_role("dialog", name="标题")` 或 `self.locator(".el-dialog:visible")` 定位，**不要**指望在声明它的那个组件容器里 scope 到它。

### 1.2 自研组件不是原生元素（role 可能不对）
项目大量使用 `cl-button`、`cloud-button-btn`、`cl-table`、`cl-input` 等**自研组件**。它们渲染出来**不一定是原生 `<button>`/`<input>`**，`get_by_role("button", name=...)` 可能**命中不到**。
- 源码里是：`<cl-button type="primary" @click="insertNewRule()">插入新规则</cl-button>`
- ❌ 错误猜法：`get_by_role("button", name="插入新规则")` —— cl-button 未必暴露 button role。
- ✅ 正确做法：优先按**可见文案**定位并精确匹配：`self.get_by_text("插入新规则").first`；表头操作按钮用项目类名范式 `.cloud-table-header .cloud-button-btn` + `filter(has_text=re.compile(r"^\s*新建\s*$"))`。**先确认 role 是否真的可用，不可用就退到文案/项目既有范式。**

### 1.3 条件渲染：源码里"有"不等于运行时"在"
模板里的元素常被 `v-if` / `v-show` / 权限指令 `v-limit` / hover 控制，**运行时可能根本不渲染、被隐藏、或要悬停才出现**。
- 真实例子：转发规则插入表单 `<div class="list-group-item-opeartion" v-if="element.is_insert">` —— **点了"插入新规则"后才渲染**；`<cl-button v-limit="'...'">` —— **当前账号无该权限时整个按钮不渲染**。
- ❌ 错误猜法：以为表单一进页面就在，直接定位 → 超时。
- ✅ 正确做法：理解触发条件（先点哪个按钮才会出现），定位前用收敛点等待其可见（`expect(form).to_be_visible(...)`）；操作项默认隐藏需 hover/点行才出现的，按同模块既有方法（如 `click_action`）走。

### 1.4 文案来自变量 / i18n，模板里看不到字面值
下拉选项、按钮、提示语的**真实文字**常来自 JS 数据或国际化，模板里只有变量名。
- 真实例子：`<el-option v-for="item in type_list" :label="item.label" :value="item.value">` —— 选项显示的是 `item.label`（在 JS 的 `type_list` 数据里），**模板里没有"域名""URL路径"这些字面文案**；按钮文案也可能是 `{{ $t('common.create') }}`。
- ❌ 错误猜法：在模板里找不到选项文字，就**凭业务理解编一个**（如编成"URL"而真实是"URL路径"），或按 i18n key 瞎填。
- ✅ 正确做法：选项/动态文案的**真实文字**以**需求 MD（CSV 转写的业务术语）+ 运行态侦察**为准；拿不准就 `recon_page.py` 枚举真实选项，**不照着变量名猜**。`placeholder="请输入规则名称"` 这类**模板里的字面量**可以直接用（见下文"能可靠拿什么"）。

> 注：少数模块文案走国际化（形如 `{{ $t('...') }}`），模板里只有 key 没有中文——这类同样以需求 MD / 运行态为准，别按 key 猜中文。

### 1.5 动态重渲染：选了 A 才出现 B（且常无可见 label）
表单字段常随选择联动出现/消失，且为省地方用 `label-width="0"`，**没有可见 label，只能靠 placeholder**。
- 真实例子：`<el-form-item prop="type" label-width="0" v-if="!form.type"><el-select placeholder="请选择条件类型">` —— 选了条件类型后该项 `v-if` 消失、右侧才渲染出"判断条件""动作类型"等新下拉。
- ✅ 正确做法：按"选择 → 等 Vue 重渲染收敛 → 再操作下一项"的顺序写；字段定位优先用 `placeholder`（因为没有可见 label），如 `left_section.locator("input[placeholder='请选择条件类型']")`；联动后出现的字段要等其可见再点。

### 1.6 运行态才知道的状态：disabled / 只读 / 选中
某字段是否 `disabled`、开关是否已开、复选框是否已勾，**取决于运行时数据**，源码（尤其有 V1/V2 差异时）给不出确定答案。
- ✅ 正确做法：操作前先读状态再决定动作，**不要假设**。本项目既有范式：
  ```python
  # 开关：先读 is-checked，再决定是否 click（避免把"已开"又点成"关"）
  is_checked = switch_ctrl.evaluate("el => el.classList.contains('is-checked')")
  if enable != is_checked: switch_ctrl.click()
  # 字段可能 disabled：先判 disabled 再 fill
  if not select.evaluate("el => el.disabled"): select.click()
  ```
> **注意 `evaluate` 的边界（别误解）**：用 `evaluate` **只读取状态**（如上面读 `is-checked` / `disabled`）是**允许**的；但**严禁用 `evaluate` / `dispatchEvent` 去"写值、合成点击、触发交互"**（见 §1.7）——**读状态可以，改状态/造事件不行**。

### 1.7 交互可靠性陷阱：源码看不出、运行时才暴露的三类"假成功/漂移"
下面三类是阶段三反复返工的高发坑（提炼自项目失败案例库的预防侧规律），源码里完全看不出，**必须在阶段二写代码时就按"正确做法"预防**：

- **`fill()` 静默失效（填了等于没填）**：Element UI 表单在弹窗动画未完成 / 输入框未聚焦时，`fill()` 可能**不真正写入值且不抛异常**；随后点"确定"触发前端空值校验 → 弹窗不关 → 后续"成功提示"断言超时（看起来像"提交失败"，实则没填进去）。
  - ✅ 正确做法：**`fill()` 前先 `click()` 聚焦**；关键字段 `fill()` 后用 `expect(input).to_have_value(值)` 兜底校验确实写入。
- **动态表格 `nth(i)` 行漂移（监控到错行）**：表格在等待/轮询期间会因新资源创建、状态刷新而**行序变化**，`row = ...nth(i)` 会指向另一行，导致状态断言"对着错的行空等超时"。
  - ✅ 正确做法：行定位**一律用 `filter(has_text=名称).first`**（先按文本锁定唯一目标，末尾 `.first` 只是满足 Playwright strict 模式、不是靠顺序选）；**严禁用 `nth(i)`、或不带 `has_text` 过滤的裸 `.first`/`.nth(0)` 靠 DOM 顺序选行**（§ 配方表 el-table 行已给范式）。
- **用 JS 硬改下拉/表单（越改越坏）**：当原生 `click`/`fill` 一时定位不准，**严禁**改用 `evaluate` / `dispatchEvent` / `$emit` 合成事件去"硬塞值/硬点选项"——实测这会引入新故障：在 dialog 内 JS 选 el-select 选项会**让整个 dialog 消失**、后续元素全部漂移；JS 直接赋值会**绕过 Vue 校验**导致提交被后端静默拒绝（无成功提示）。
  - ✅ 正确做法：定位不准 → 回去侦察/复用同模块语义封装（如 `_select_dropdown` 在 dialog 内 scope 选项）；走**原生输入路径**（`click`→`fill`→必要时显式触发 `blur`/`change` 让校验同步），**绝不自创 JS 绕过**。

> 以上为**预防**规则；阶段三若仍命中同类失败，另见 `.claude/skills/test-script-dev/references/failure_case_library.md` 的对应案例（含证据链与排查口诀），二者互补、不重复。

---

## 二、正确的工作流：读源码 → 判定 → 复用/侦察（三步法）

### 第 1 步：读源码，提取"源码能可靠给的东西"
按 `module_index.yaml` 的查找策略定位到被测模块前端目录后，**带着需求 MD 的目标**去读对应组件，**只从源码提取下列可靠信息**（这些是源码的强项）：

| 源码能可靠给（放心用） | 源码给不了/会骗你（必须运行态确认） |
|:---|:---|
| 业务**流程与步骤顺序**（点哪个按钮 → 弹什么 → 填什么 → 联动出什么） | 元素**渲染后真实位置**（teleport 到 body 与否） |
| 表单**字段构成、校验规则**（`formRules`、必填项、`v-if` 联动条件） | 下拉**选项的真实文案**（来自 `:label="变量"`） |
| 模板里的**字面量** placeholder（`placeholder="请输入规则名称"`） | 元素是否**真的渲染**（`v-if`/`v-show`/`v-limit` 权限） |
| 容器/区域的**结构划分**（如 `.form-left` / `.form-right` / `.btn-box`） | 元素的**真实 role**（自研 `cl-*` 组件是否暴露 button/textbox role） |
| 触发交互的**事件与条件**（`@click`、`:disabled` 的判断表达式） | 字段运行时是否 **disabled / 只读 / 已选中** |
| 是弹窗(`el-dialog`)、抽屉(`el-drawer`)还是**内联表单**（决定定位根） | 真实 **class 名**（可能有拼写差异，如 `list-group-item-opeartion`） |

> **铁律**：凡是落在右栏的，**严禁凭源码印象写死定位**；要么用运行态侦察确认，要么复用同模块已验证过的写法。

### 第 2 步：判定每个定位是"可静态确定"还是"须运行态确认"
对每个要交互的元素，问自己一句：**"它的定位只看这段源码就能 100% 确定唯一且稳定吗？"**
- **能**（如模板里写死的 `placeholder`、唯一可见文案按钮）→ 直接按 `page_func_spec.md` 优先级写。
- **不能**（命中右栏任一项：teleport、变量文案、条件渲染、自研组件 role、disabled、可疑 class）→ **标记为"须运行态确认"**，进入第 3 步。

### 第 3 步：先复用同模块范式，仍不确定才侦察
顺序固定，**不要跳过直接猜**：
1. **先读同模块既有 Page Object**：`Grep`/`Read` `sugon_web/pages/<模块>/` 下相近功能的方法，**直接复用它已验证的定位写法/BasePage 语义方法**（如 `_select_dropdown`、`click_action`、`search`、`get_row_data`）。同模块"别人已经趟过的坑"是最高性价比的事实来源——**抄已通过的范式，不自创**。
2. **仍无现成范式 → 跑 `recon_page.py` 侦察真实渲染态**（黑盒，先 `--help`），从真实 DOM 枚举候选元素/选项/容器类名再写定位。点击/导航类用 `--probe-click` 秒级验证原生点击是否生效（详见 `phase2-coding.md` / `phase3-execution.md` 的侦察约束，本指南不重复）。
3. **把侦察结论回填「页面侦察结论卡」**（阶段二完成时产出，见 `phase2-coding.md`），让阶段三直接复用、不必重新侦察。
4. **怀疑是框架配置/映射本身有问题**（如导航方法到不了目标页）→ 按规范走正确入口或标记"遗留问题/需人工补充"，**严禁在测试代码里自创绕路**（手拼 URL、`evaluate` 合成事件等）。

---

## 三、本项目组件定位"配方表"（可直接抄的 known-good 范式）

> 下列是从项目**真实 Page Object** 提炼的、已在本项目验证可用的定位范式，覆盖最常见的 Element UI / 自研组件。**新写定位前先查本表与同模块既有方法；若 BasePage/Mixin 已有语义封装（如 `_select_dropdown`），优先调用语义方法而非自己拼 CSS。** 本表是"怎么定位"的事实补充，与 `page_func_spec.md` 的"优先语义、CSS 下沉"原则一致（组件库 CSS 属其允许的兜底）。

| 组件/场景 | 关键规律 | 既有范式（照抄，按实际 label/文案替换） |
|:---|:---|:---|
| **el-select 下拉选择** | 选项在 body 级 `.el-select-dropdown:visible`，**不在 dialog/form 内**；弹窗内优先用语义封装防"选完 dialog 消失" | 触发器：`容器.locator("div.el-form-item").filter(has_text=re.compile("字段名")).get_by_placeholder("请选择")` → `.click()`；选项：`self.locator("div.el-select-dropdown:visible li").filter(has_text=re.compile(rf"^{re.escape(值)}$")).click()`。**弹窗内下拉优先调 BasePage 语义封装 `_select_dropdown`（在 dialog 内 scope 选项，避免原生 click 冒泡关闭 dialog）；严禁用 JS `evaluate` 合成事件选项（见 §1.7）** |
| **el-form-item 按 label 取字段** | 用字段中文 label 圈定表单项，再取其中的输入控件；**`fill` 前先 `click` 聚焦、填后校验值**防静默失效 | `field = dialog.locator("div.el-form-item").filter(has_text=re.compile("资源池名称")).get_by_role("textbox")`；`field.click(); field.fill(值)`；关键字段加 `expect(field).to_have_value(值)`（数字输入用 `get_by_role("spinbutton")`） |
| **el-dialog 弹窗** | 渲染在高层级、不在声明它的业务组件容器内，按标题从页面根定位 | `dialog = self.get_by_role("dialog", name="新建资源池")`，再 `expect(dialog).to_be_visible(timeout=5000)` |
| **确定/取消等弹窗按钮** | 文案精确匹配；优先复用 `dialog_confirm`/`dialog_cancel` | `dialog.get_by_text("确定", exact=True).click()` 或复用 `self.dialog_confirm.click()` |
| **自研按钮（cl-button / cloud-button-btn）** | 未必有 button role，按文案/项目类名 | `self.get_by_text("插入新规则").first`；表头新建：`容器.locator(".cloud-table-header .cloud-button-btn").filter(has_text=re.compile(r"^\s*新建\s*$")).first` |
| **el-table 行 + 行内操作** | 行用 has_text 圈定，**严禁 `nth(i)` 选行**（等待期间行序会漂移、监控到错行） | 行：`容器.locator(".el-table__body-wrapper tr").filter(has_text=re.compile(rf"\b{re.escape(名称)}\b")).first`；勾选：`row.locator("td").first.locator(".el-checkbox")`（看 `is-checked` class 判断已选）；行操作优先复用 `click_action(名称, "删除")` |
| **el-switch 开关** | 读状态再决定点不点，别盲点 | `checked = ctrl.evaluate("el => el.classList.contains('is-checked')")`（或 `get_attribute("aria-checked")=="true"`）；`if want != checked: ctrl.click()` |
| **可能 disabled 的字段** | 运行态才知道，先判再操作 | `if not el.evaluate("el => el.disabled"): el.click()` |
| **内联表单 vs 弹窗** | **必须先分清**：定位根完全不同 | 弹窗→`get_by_role("dialog")`；内联→其真实容器类（如 `.list-group-item-opeartion`、`.form-left`/`.form-right`/`.btn-box`）。**分不清就 recon，别默认是弹窗**（lbv2 教训：把内联表单当弹窗，耗尽阶段三额度） |
| **加载遮罩 el-loading-mask** | 异步加载时存在，须等其消失再操作 | `容器.locator(".el-loading-mask").wait_for(state="hidden", timeout=15000)` |
| **Vue 联动重渲染** | 选 A 后 B 才出现，需等收敛 | 选择后用收敛点等待目标可见再操作；**禁固定 sleep 作状态等待**（见 `page_func_spec.md` 等待规范） |

> **类名使用纪律**：上表用到的 `.el-*` / `.cloud-*` / `.list-group-*` 等类名，**必须是你从源码或运行态侦察"确认存在"的真实类名**，不能凭记忆拼（注意真实工程里存在 `list-group-item-opeartion` 这种拼写）；能用语义定位（role/label/placeholder/text）的优先语义，CSS 仅用于组件库/自研组件兜底。

---

## 四、交付前自检（本指南专属，补充于 codegen §15 之外）

进入阶段三前，对每个**非平凡定位**逐条确认；任一为"否"即返工：

- [ ] 每个下拉选项的定位都放在 **body 级 `.el-select-dropdown:visible`**，没有错误地 scope 在 dialog/form 内？
- [ ] 每个弹窗都按 **dialog role/标题** 定位，没有在声明它的组件容器里 scope？
- [ ] 自研组件（cl-/cloud-）按钮**没有想当然用 `get_by_role("button")`**，已确认 role 可用或改用文案/项目范式？
- [ ] 所有下拉**选项文案、动态文案**来自需求 MD 或运行态侦察，**没有照着 `:label="变量"`/i18n key 猜**？
- [ ] 联动出现的字段、`v-limit` 权限相关元素，都已理解触发/渲染条件并以可见性等待，**没有假设"一定在"**？
- [ ] 用到的每个 CSS 类名都是**确认存在的真实类名**（源码/侦察核对过），不是凭记忆拼写？
- [ ] 命中"须运行态确认"的元素，都已**复用同模块既有范式**或**经 `recon_page.py` 侦察**，并把结论写入「页面侦察结论卡」？
- [ ] 是否分清了**弹窗 vs 内联表单**，定位根选对了？
- [ ] 关键字段 `fill` 前已 `click` 聚焦、填后校验值（防静默失效）？表格行用 `filter(has_text).first`、**没有用 `nth(i)` 选行**？
- [ ] 全程**没有用 JS `evaluate`/`dispatchEvent`/`$emit` 硬改下拉、表单或合成点击**（定位不准就侦察/复用范式，不绕路）？

> **记住**：本指南的全部目的，是让你在阶段二把"会被运行时打脸"的猜测**提前消灭**。多花几分钟读源码+侦察+抄同模块范式，省下的是阶段三成倍的修复轮次。


---

## 七、复杂校验表单（多必填 + 异步加载 + 下拉/单选/规格表）填写配方（通用·2026-06-21 新增）

> **要解决的一类问题**：很多模块的"创建"页/弹窗是带 `:rules` 校验的 `el-form`，有多个**必填项**、且选项是**异步加载**的（`v-loading`）、字段之间还**有依赖**（选了 A 才解锁 B）。这类表单只要有一个必填项没真正赋值，提交按钮（"立即创建/确定/创建/提交"）就一直 `disabled`、点了没反应、资源建不出来。实测教训：某次 SLB 创建用 `page.evaluate` 合成事件 JS 盲填，漏填了必填的"集群"、"子网"又用 `setTimeout` 异步盲选没真正选上 → 校验永远不过 → 在第一步卡死、烧光全部修复额度。**这类表单是阶段三高发死穴，务必按下方配方写。**

**铁律 0：禁止用 `page.evaluate` 合成事件填表。** 严禁 `el.value = x` + `dispatchEvent(new Event('input'/'change'))`、严禁 JS 点 `.el-select-dropdown__item`、严禁在 evaluate 里 `setTimeout` 盲选——合成事件骗不过 Element UI 的响应式校验（v-model 不更新→必填被判空→按钮 disabled），`setTimeout` 在 `page.evaluate` 返回后根本没人等（竞态）。`precheck.py` 会机器拦截这些写法。**一律用 Playwright 原生交互触发真实事件链。**

**配方（按顺序，每个 Page 创建方法都照此写）**：

1. **进表单先等异步加载收敛**：表单/选项常带 `v-loading`（如 `flavorLoading`/`subnetLoading`）。先 `page.wait_for_selector(".el-loading-mask", state="hidden")`（或等目标 `el-select` 点开后选项出现），再操作；**没等加载就点 = 选项为空/点空**。
2. **文本框**：`box.click(); box.fill(value)`；必要时 `box.press("Tab")` 触发 `blur` 校验。
3. **`el-select` 下拉（含 filterable、选项 teleport 到 body）**：`select.click()` 打开 → 等 `.el-select-dropdown:visible .el-select-dropdown__item` 出现 → 在**页面根**（不是表单容器，选项在 body 级，见 §1.1）按真实文案点选项：`self.locator(".el-select-dropdown:visible li").filter(has_text=re.compile(rf"^{re.escape(value)}$")).click()`。**必须点选项触发 `@change`，v-model 才会写值**；只设输入框文字不算选中。
4. **`el-table` 行内 `el-radio` 选规格/类型**：定位目标行（按规格名文案）→ 点该行的 `el-radio`（`row.locator(".el-radio").click()`），不要 JS 设 `checked`。
5. **字段有依赖顺序**：按"前置项 → 联动出现/解锁的后置项"的顺序填（如本项目 SLB 创建：选**子网**后 IPv4 分配方式才从 disabled 解锁）；填完一项等其联动重渲染收敛再填下一项（见 §1.5）。
6. **★ 提交前自检按钮可点（1~2 次定位根因，取代 30 次盲改）**：填完所有必填项后，断言提交按钮已可点：`expect(submit_btn).to_be_enabled()`。**若仍 disabled**，说明还有必填项没满足——立刻读出是哪一项校验没过，而不是反复改 selector：
   ```python
   errors = self.page.evaluate("""() => Array.from(document.querySelectorAll('.el-form-item.is-error')).map(e => ({
       label: (e.querySelector('.el-form-item__label')||{}).innerText,
       msg:   (e.querySelector('.el-form-item__error')||{}).innerText }))""")
   logger.error(f"表单未通过校验的必填项: {errors}")
   ```
   （注：此处 evaluate **只读取** `.is-error` 用于诊断，不是用它填表，不违反铁律 0。）按 `errors` 里报红的 label 去补填那一项。
7. **提交按钮文案以真实渲染为准**：是"立即创建"还是"确定/创建/提交"，从失败现场 `*_domsnap.md` 或 `recon_page.py` 取真实文案，别凭印象写死。
8. **提交后判成功以真实反馈为准**：可能是跳列表页、可能是关弹窗 + 成功 toast、可能是列表出现新行——按真实行为等（`expect`/收敛点），不要假设一定 `wait_for_url`。

**写这类创建方法前，阶段二必须先 `recon_page.py` 侦察该创建页/弹窗**，把上面每个必填项（含异步必填项如"集群/子网/规格"）的真实定位、是否必填、选项渲染层级、提交按钮真实文案写进「页面侦察结论卡」——**严禁只 recon 下游次要表单、却对第一个创建表单凭源码猜**（那是"第一步就卡死"的根因）。
