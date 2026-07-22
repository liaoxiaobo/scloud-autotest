# 测试失败分析案例库

按失败模式分类沉淀的典型 case，用于阶段三诊断时辅助同类问题的快速定位。

> **维护与移植约定（重要）**：
> - 本库是 test-script-dev 的**自包含资产**，阶段三（`phase3-execution`）诊断时按需 `Read` 本文件，命中已收录模式即优先套用其根因方向与修复建议，避免从零试错。
> - 初始内容同步自 `test-failure-analysis` skill 的 `references/case_library.md`。
> - **后期新增案例只需按下方统一格式（模式名 / 现象 / 根因 / 关键证据链 / 修复方向 / 排查口诀）追加到本文件**，无需改动任何 phase 文件或 SKILL.md——这是案例库做成独立文件而非内联的目的：移植成本最低、不污染 agent 正文、不拖累子智能体启动上下文。
> - 与 `test-failure-analysis` 的案例若有新增，按相同格式追加同步即可。

---

## 模式：动态表格行定位漂移（Locator 漂移）

### 案例：云硬盘-扩容 `test_volume_expand` 状态断言超时

**时间**：2026-06-03
**用例**：`test_volume_expand[params0]`（`new_size: 100`）
**根因分类**：用例问题

#### 现象

- `volume` fixture 创建云硬盘后，`assert_status(name, status="可用")` 等待 300 秒超时
- 报错显示实际状态为"正在使用"、25GiB、挂载到 `autotest-hj0pg`
- 但失败截图显示目标云硬盘 `autotest-yfbox` 状态已经是"可用"

#### 根因

`get_row_by_name` 遍历表格匹配到目标行后，返回 `target_rows.nth(i)`。在 `assert_status` 的 Playwright expect 重试期间，表格因新云硬盘创建导致行序变化，`nth(i)` 指向了另一行（状态为"正在使用"的其他云硬盘），持续空等至超时。

#### 关键证据链

1. **截图与报错状态矛盾**：截图目标行是"可用"，但报错捕获的是"正在使用"→ 监控对象错误
2. **Call log 行内容漂移**：expect 重试期间从"创建中 30GiB"变为"正在使用 25GiB"→ 目标行发生了变化
3. **同用例第二参数化通过**：`new_size: 500` 通过 → 排除环境与产品问题

#### 修复方向

- `get_row_by_name` 应返回基于文本过滤的稳定 locator（如 `tr.filter(has_text=name).first`），而非 `nth(i)`
- `assert_status` 可增加目标行名称校验，发现行漂移时提前报错而非空等超时

#### 排查口诀

> 看到"状态断言超时"，先问自己：截图里的目标资源状态真的不对吗？如果截图状态正常→ 极大概率是 **locator 漂移监控到了错误行**。

---

## 模式：Playwright fill 静默失效（表单填写未生效）

### 案例：CCE-修改时间同步服务器 `test_edit_time_sync_server` 成功消息断言超时

**时间**：2026-06-04
**用例**：`test_edit_time_sync_server`
**根因分类**：用例问题

#### 现象

- `cce_edit_time_sync` 方法执行后，`assert_popup_success("设置CCE集群时间同步器成功")` 等待 10 秒超时
- 报错显示等待 `.el-message__content` 未找到
- 失败截图显示"时间同步服务器"弹窗**仍然打开**，输入框为空（显示 placeholder），下方有红色校验错误"请输入有效的IP地址或域名"

#### 根因

Page Object 方法中先 `wait_for(state="visible")` 再 `fill()`，但 Element UI 表单组件在弹窗动画或 focus 未就绪时，`fill()` 可能未真正写入值（Playwright 不抛异常）。随后点击"确定"触发前端空值校验，弹窗未关闭，自然不会出现成功消息。

#### 关键证据链

1. **截图显示弹窗未关闭且输入框为空**：直接证明 `fill` 未生效，而非产品拒绝合法 IP
2. **步骤1 passed，步骤2 超时**：`cce_edit_time_sync` 内部无异常，但预期副作用（弹窗关闭）未发生 → 属于"静默失效"
3. **修复验证**：在 `fill()` 前增加 `click()` 确保 focus 后问题消失 → 确认根因是 focus 时机问题

#### 修复方向

- 对 Element UI 等组件化表单，**`fill()` 前显式 `click()` 确保 focus**，或在 `fill()` 后增加 `expect(input).to_have_value(value)` 断言兜底
- 审查同类封装方法，统一添加"填值后校验"，避免静默失效导致后续断言超时

#### 排查口诀

> 看到"弹窗/表单操作后断言超时"，先问自己：截图里弹窗真的关了吗？如果弹窗还开着且字段为空→ 极大概率是 **fill 未真正写入值**，而不是提交后端失败。

---

## 模式：曙光云项目高频定位陷阱（速查·源自 lbv2 转发规则 11h 运行复盘）

> 以下陷阱在复杂用例阶段三被反复重复发现（cl-button 一次运行内重复 6 次）。诊断命中任一现象，直接按"正确做法"修复，不要再逐个试错。预防侧规则见 `page_func_spec.md` §1.3。

| 现象（报错/超时） | 根因 | 正确做法（修复方向） |
|---|---|---|
| `get_by_role("button", name=...)` timeout（立即创建/下一步/确定/搜索/保存等按钮） | 按钮是 `cl-button` 自定义组件，无原生 `role=button` | 改 `get_by_text("按钮文案")` |
| `.el-select-dropdown__wrap` strict mode violation / 匹配多个 | 页面同时存在多个（含隐藏）下拉框 | 改 `.el-select-dropdown:visible` 限定可见 |
| 向导对话框 Step2 字段 not found（如"资源池名称"） | 误把多步向导当单页表单，只填 Step1 就点确定 | 按真实步数逐步：Step1→"下一步"→Step2→"下一步"→Step3→"确定"，步数先侦察 |
| 返回按钮点击后页面未跳转 / `el-icon-arrow-left` resolved 但 click 超时(not enabled) / `.sugon-back-button` 不存在 | 动态渲染返回按钮，点击未验 enabled、未以 URL 判定成功 | click 前 `expect(btn).to_be_enabled()`；**以 URL 变化判定返回成功**；多策略兜底（图标→面包屑→`go_back()`） |
| 下拉选项找不到（如"云服务器实例"） | 凭需求文档直译文案，与页面实际渲染不符 | 用真实渲染文案（如"弹性云服务器 ECS"），不确定先 `recon_page.py` 侦察 |

### 排查口诀

> 复杂新页面阶段三反复"定位超时"，先自问：**这些选择器/流程是侦察来的还是猜的？** 若是猜的 → 立即跑 `recon_page.py` 拿真实渲染态，一次性对齐 cl-button 文案、向导步数、可见 dropdown，避免逐个试错耗尽轮次。

## 模式：SLB/Vue 表单类高频陷阱（速查·源自 lbv2 转发规则 2334 运行复盘）

> 这批坑在"复杂 Vue 表单/dialog"用例反复出现，且实测 AI 用 JS 硬改反而引入新故障。命中即按"正确做法"修，**严禁自创 JS 操作**。

| 现象（报错/超时） | 根因 | 正确做法（修复方向） |
|---|---|---|
| dialog 内选完下拉后 **dialog 消失**、后续元素定位漂移 | 在 dialog 内用 Playwright 原生 `click()` 选 el-select 选项会事件冒泡关 dialog；**而用 JS 点也会引入 dialog 消失**（实测 AI 自创 JS 改法的新故障） | 用 BasePage 语义封装 `_select_dropdown`，在 **dialog 容器内 scope 定位** `.el-select-dropdown:visible` 的选项；**不要自创 JS `evaluate`/`dispatchEvent`** |
| 监听器/表单提交后**成功 popup 不出现**（10s/30s 超时） | 用 JS/`$emit` 直接给 Vue 表单字段赋值后，**前端校验状态未同步** → 点提交被后端静默拒绝，自然无成功 popup。加大 popup 超时是治标 | 赋值后**显式触发 `blur`/`change`** 使校验同步；或改用 `fill()`+键盘输入走正常输入路径；多步向导**每步提交前断言表单校验通过**，再点下一步/确定 |
| teardown 报 `'CustomLocator' object is not callable`、资源未清理 | 把 `search(name)` 的返回值（**定位器对象**，非行数据）当可调用/数据做链式调用 | 删除直接用 `click_action(name, "删除")` 流程；`search()`/`get_row_by_name()` 返回的是定位器，**不可当数据或函数链式调用** |

### 排查口诀

> 看到"dialog 莫名消失""提交后无成功提示""teardown CustomLocator not callable"——先问：**是不是用 JS 硬改了下拉/表单？** 是 → 撤掉 JS，改用语义封装 + 原生输入 + 触发 change；popup 不出现优先怀疑"表单校验没过被静默拒绝"，而非"超时不够"。

## 模式：通用高频陷阱速查（多次运行复盘汇总·2026-06-25）

> 下列陷阱在多次运行 skills 和 agent、多个模块的阶段三被反复发现。**「出现频率」列基于对 43 份历史运行报告（已剔除 1 份字节级重复副本）《第二部分：修复经验沉淀总结》的系统统计**（★越多＝越多份报告独立命中、复发概率越高），表格已**按出现频率从高到低排序**——越靠前越应优先排查。命中现象直接按"正确做法"一次改对，不要逐个试错、不要在同一处反复改。
>
> **出现频率图例**（按独立命中报告份数）：★★★★★ ≥6 份·极高频｜★★★★☆ 4~5 份·高频｜★★★☆☆ 3 份·中频｜★★☆☆☆ 2 份·偶发｜★☆☆☆☆ ≤1 份·个例（LB 类源自专项报告，本复盘语料未命中）。

| 出现频率 | 现象（报错/超时） | 根因 | 正确做法（修复方向） |
|:---:|---|---|---|
| ★★★★★ | 列表页搜索框/表格行/行内按钮 `locator resolved to 0 elements`，而 domsnap/截图显示当前 URL 是概览页等**非目标列表页**（如 `#/vpc-overview` 而非 `#/transfer-strategy`） | 导航只到了服务概览页、没真正切到目标列表页；`goto_submenu`/导航**可能误报"成功导航"**，或测试直接调组件层 `search()` 绕过了 `_ensure_list_page` 兜底 | **先核对 domsnap 真实 URL 是不是目标列表页——不是就先修导航（强制走 `_ensure_list_page` 类兜底确认到位），绝不在元素定位上反复改**；**domsnap 真实 URL 优先于"导航成功"日志（日志会误报）** |
| ★★★★★ | 列表/表格数据返回空 `[]`、`get_column_data` 取不到 | Vue 列表/表头数据**后端异步填充**，初始为空；通用页面就绪等待不覆盖数据加载 | 用专门轮询等数据/表头出现（足够的重试次数与间隔），不能只靠 `wait_for_page_ready`；**禁用 `time.sleep` 硬等** |
| ★★★★☆ | 清理/teardown/二次导航时点击被遮挡、定位失败、导航超时 | 上一步操作后页面**残留 dialog/确认弹窗未关闭**，遮挡后续操作 | 任何清理/导航操作前先 `close_dialog_if_exists()` 关残留弹窗 |
| ★★★★☆ | 弹窗输入框 `.el-input.nth(n)`/`get_by_role("textbox")` 定位失败或 strict；修改类填值后残留旧值 | nth 随渲染漂移、多文本节点致 strict、textarea 非 textbox role、`fill()` 不清空 | **label 驱动定位**（`.el-form-item__label` 文案 → 该 form-item 内输入框）；textarea 用 `get_by_placeholder`；多命中加 `filter(has_text)`+`.first`；**修改类 `fill()` 前先 `clear()`** |
| ★★★★☆ | SSH 后端验证失败：资源标识取错 / 命令不存在（`gova` not found、`admin-openrc.sh` No such file、`--all` unknown flag） | 验证用的 ID 直接取自 URL 参数（≠真实 UUID）、命令名/路径/参数凭字面 | SSH 验证的资源标识**从详情页正文取**（非 URL 参数）；命令用绝对路径、**复用同模块已验证过的命令**、先确认参数兼容；**微型系统（cirros 等）避免 `sudo`/需 root 的命令（无权限），改用 `/proc`、`lsblk`、普通用户可执行命令** |
| ★★★★☆ | `get_by_text("新建"/"同步配置"…)` strict mode violation（resolved to 2+ elements） | 页面同时存在同名按钮与 dialog 标题、或多个同名按钮 | 用 `exact=True` 精确匹配按钮文案 **且**在可见区域容器内限定 scope（如 `.cloud-main-content` 或所在 tab/dialog 容器），避免命中标题/隐藏覆盖层 |
| ★★★★☆ | 环境无资源时整批用例 AssertionError 硬失败（巡检/环境检查类） | 脚本直接断言 `total>0` 等，未先判环境是否具备前置条件 | 环境检查类用例在业务断言前先做**前置预检**：不满足时 `pytest.skip("环境未对接…")` 标环境问题、**不要硬失败**（skip 消息含环境标识与原因） |
| ★★★★☆ | 依赖资源刚建好就建子资源偶发失败（如网关创建后立即建通道） | 父资源后端异步未就绪就建子资源；或 fixture 用固定名在残留环境冲突 | 子资源创建**加重试**（失败等待后重试若干次）；资源名一律 `random_data()` 不写死，避免"已存在"冲突 |
| ★★★☆☆ | 操作/接口提示"成功"但业务实际没生效（永久删除后对象仍在、权限保存不持久、规格升级实际失败等）（高价值） | 产品后端/前端缺陷：API 200 / UI 成功提示 ≠ 后端真生效 | 关键结果必须**二次查询或后端 `scli` 取证**确认真生效；同一处连续 2 轮无进展即做后端取证，确认产品缺陷就判定并标记，**禁止靠弱化/条件跳过 P0 断言"求过"、也别在同一处继续盲改** |
| ★★★☆☆ | 删规则/解绑/禁用后"反向预期"不成立（典型：删 ICMP 规则后仍 ping 通），且反复回退多轮（高价值） | ① 新建的安全组根本没绑到 VM；② 绑定后平台**自动重新加回 `default` 安全组**放行全部流量 | 生效验证必须把目标 sg 真正绑到 VM 并排除 default（解绑 default，或 `scli port set <port_id> --security-group <sg_id>` 让端口只受目标 sg 控制）；这类核心断言**禁用条件跳过/提前 return 绕过** |
| ★★★☆☆ | 把失败笼统归为"环境问题"就跳过，实际是用例侧问题（权限/文案/时序/定位）→ 漏修、且白耗回退额度 | 凭"看起来像环境问题"就归类、未取证；或反向把环境/产品问题误判成用例问题反复改 | 判"环境问题"前必须在**原始日志 grep 确定性证据**（错误码如 `-12400078`、`ERR_CONNECTION_CLOSED`、`aria-disabled` 等）；无确定证据不归环境；判定环境/产品后**不再对该用例追加修复额度** |
| ★★★☆☆ | 状态翻转后连通性/状态不恢复（路由删或证书禁用再启用后 ping 仍不通；长流程状态长期"未知"）（连接/隧道类） | 客户端隧道（openvpn 等）变更后不会自动重连；"未知/queued"被误当失败终态 | 变更后**主动重启客户端/服务重建连接**再验连通；连通性以后端"在线"真实指标判定（非 UI 配置态）；长流程轮询把"未知"等**中间态加白名单**、区分中间态 vs 失败终态 |
| ★★★☆☆ | 成功 Toast/弹窗文案断言超时、文案不匹配 | 产品实际文案与需求描述不一致——成功 Toast 常带完整服务名前缀（需求"修改权限组成功"→实际"修改文件存储权限组成功"，或统一为"执行成功"） | 断言文案**一律以前端实际渲染为准**，阶段三首次执行时按真实弹窗校准；禁凭需求/记忆直写文案 |
| ★★☆☆☆ | 详情页字段回读为 `None`/错位/把 label 串进取值 | 详情是自研组件 `cl-item-col`/`cloud-item-col`（label 与 content 同块），且不同环境类名不同（`cl-` vs `cloud-`） | 先确认真实组件类名，按 **label 文案定位到对应 content 子元素**单独取值（别整块 `inner_text` 直接切）；优先用业务自研类名（`cloud-*`）而非通用 Element 类名 |
| ★★☆☆☆ | el-select 选完一个下拉后遮挡/选不中下一个下拉，或选项文案匹配不到 | el-select 选完不自动收起、下拉面板遮住后续元素；下拉显示的是 label 文案、非 value | 选完**主动收起下拉**（点 trigger/空白处或用封装的收起方法）再操作下一个；按真实 label 文案匹配选项；**禁自创 JS 操作 Vue 实例选项**（JS 硬改会引入 dialog 消失等新故障，见上表） |
| ★★☆☆☆ | 删除资源报"仍被引用"/删除失败 | 资源仍被关联（安全组仍绑在 ECS、LB 仍含监听器） | 删除前先解绑/删子资源：安全组先解绑 ECS 再删；含监听器的 LB 先删监听器再删 LB；清理顺序严格 |
| ★★☆☆☆ | `ScopeMismatch: fixture page of scope function cannot be used in scope class` | class-scoped fixture **直接依赖了 function-scoped fixture（如 page）** | class 级 fixture 不得依赖 function 级；需共享页面时自建 class 级页面 fixture，或对资源 fixture 取消自动注入、测试层手动管理生命周期 |
| ★★☆☆☆ | 自研组件 disabled 断言 `is_disabled()`/`to_be_disabled()` 恒为 False | `cl-*`/`cloud-*` 用 `xxx-disabled` class 或 `cursor:not-allowed` 标记禁用，无原生 disabled 属性 | disabled 改为检查该 **class 或 cursor 样式**，不能只用 `is_disabled()` |
| ★★☆☆☆ | 下载文件 `page.on("download")` 捕获不到、下载断言失败（下载类） | 前端用 blob URL + JS 造 `<a download>` 触发，非标准 HTTP 下载响应头 | 在 Page/helper 层用 `page.evaluate` **读取/校验 blob**（这是"读取内容"，与被禁的"合成 input/click 事件"不同），或 download 事件 + fetch blob 双策略，不只靠 `page.on("download")` |
| ★★☆☆☆ | 行操作（编辑/删除等）点击后 30s 超时、元素被弹窗遮挡 | 测试层又调了一次底层点击（如 `click_action(name,"编辑")`），而 Page Object 高层方法**内部已含该点击**，二次点击被已弹出的弹窗遮挡 | 调 Page Object 高层方法前先看其内部是否已封装该点击；**已封装完整操作链就别在测试层重复调底层操作** |
| ★☆☆☆☆ | 文本/下拉选项正则匹配 0 elements、`包含(区分大小写)` 失败 | 中文界面用**全角括号（）**、全角空格，或 el-tag 渲染成 `0 B`（带空格）而脚本写 `0B` | 文案逐字以渲染为准（优先 recon 截图确认），或同时兼容全/半角、有/无空格两种写法 |
| ★☆☆☆☆ | 成功操作被误判为"失败/错误"（断言报"创建失败，错误消息包含'设置…成功'"）（OSS 等） | 用泛选择器 `.el-message` / `.el-message__content` 检测成败，同时命中成功和错误 Toast、未区分类型 | 检测错误**只匹配 `.el-message--error`**、检测成功用 `.el-message--success` 或精确文案；**禁用不区分类型的 `.el-message` 判定成败** |
| ★☆☆☆☆ | 开关/按钮 `click()` 一直等到 30s 超时（元素找得到却点不动），反复改定位无效（机密互联等受控开关） | 元素处于 **disabled** 态（`aria-disabled="true"` / `el-switch is-disabled` / `cursor:not-allowed`），不是定位错 | click 前先判 disabled 状态；**确属业务/环境禁用（如 DPDK 与机密互联互斥）→ 判环境/产品并 `skip`，不要在定位上死磕**（与上文"自研组件 disabled 断言恒 False"同源） |
| ★☆☆☆☆ | LB 后端 curl 返回 502 / 加权轮询比例验证失败（LB 模块） | 成员启用健康检查后需异步收敛；SLB V2 配置变更需传播时间，脚本未等就 curl | 启用健康检查的成员加入后等其状态"运行中"再 curl；SLB V2 变更后等数秒、首次 curl 用 `check_rc=False` 容忍初期 502 |

### 排查口诀

> 命中上述任一现象，先核对"是不是同名 strict / 文案没对齐渲染 / 数据没等异步 / 弹窗没关 / scope 用错 / 环境不具备前置 / 成功提示≠业务真生效（产品缺陷）/ 自研组件(详情取值·disabled·下拉)在凭印象盲改"——这些都是**改对一次就过、盲改 N 次都白费**的确定性问题，务必按"正确做法"一次改对，不要在同一处反复试。
