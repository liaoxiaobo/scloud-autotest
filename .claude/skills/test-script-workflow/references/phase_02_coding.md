# 阶段二：脚本编写与对齐

## 第一部分：编写自动化测试脚本

> 必须根据以下要求编写自动化测试用例脚本。开始编码前必须先使用 Read 工具依次读取以下关联文件，全部读完后再继续，不可跳过。

**在开始本次任务之前，你必须先全文阅读以下关联文件**

1. 阶段一产出的需求 MD 文件
   - 作用：阶段一从 CSV 转换并校验完善的结构化需求文档，是本次编码的目标与依据。
   - 用法：从对话上下文中定位并读取该文件，先明确本次要测什么（测试步骤、测试数据、边界条件、清理顺序），再带着这个目标去读后续规范文件，编码必须按其中定义的测试需求实现。
2. `sugon_web/case_specs/prompts/test_case_codegen_prompt.md`
   - 作用：UI 自动化测试脚本的开发规范，指导你基于项目现有框架结构编写标准、统一、可复用的测试代码。
   - 用法：编码过程中必须严格遵守本文件规范，用例骨架务必参考本文件的推荐骨架章节。
3. `sugon_web/case_specs/prompts/page_func_spec.md`
   - 作用：Playwright Page 层方法封装规范，定义定位策略优先级、反模式、方法粒度决策（Page vs Helper）、BasePage 通用组件下沉标准、Scoped 链式定位、等待策略等。
   - 用法：封装 Page Object 方法时必须遵守本文件规范；定位策略优先 `get_by_role`/`get_by_text`/`get_by_placeholder`，避免 CSS 类名；BasePage 已封装通用组件交互时禁止在 Page 子类中重复写 CSS 定位。
4. `sugon_web/case_specs/fixtures_index.md`
   - 作用：fixture 强制约束和速查表，开头"编写用例前必读"章节规定了 fixture 强制要求并列出所有可复用 fixture。
   - 用法：编写用例前必须先阅读，优先复用现有 fixture，禁止对已有 fixture 重复封装。
5. `sugon_web/case_specs/prompts/fixture_spec.md`
   - 作用：fixture 封装规范，定义各类 fixture（资源创建/清理、class-scoped 共享、count 批量参数、纯计算型、clean_ 清理型等）的标准封装方法与适用场景。
   - 用法：当需要新增或封装 fixture 时必须先阅读，严格按其规范实现，确保 fixture 的创建、回写、teardown 清理逻辑与项目既有约定保持一致。
6. `sugon_web/case_specs/prompts/assertion_guidelines.md`
   - 作用：断言编写规范，第一部分定义断言四层模型（P0/P1/P2/P3）和决策树，第二部分定义断言编写、复用和新增方法的规范。
   - 用法：编写断言时按决策树判定每个步骤的断言层级；先搜索已有方法优先复用，无可复用方法时按规范自行编写。
7. `sugon_web/refrence/module_index.yaml`
   - 作用：前端工程代码的模块索引与搜索策略文档，"模块匹配策略"章节定义被测模块与前端目录的映射规则，"前端代码搜索工具约束"章节规定查阅前端代码的搜索策略与工具限制。
   - 用法：严格遵照其匹配策略和搜索约束，定位并读取匹配到的前端工程代码——
     - **若匹配成功**：基于该前端工程代码中的实际元素文案、组件结构和交互逻辑编写页面对象，严禁脱离前端代码凭空构造定位方式。
     - **若匹配失败**：立即停止任务，并在对话框中输出醒目提示：已结束本任务，因为无法找到与本任务对应的前端工程目录，请直接告知该任务对应的前端工程目录，以便继续执行本任务。

**开始编写脚本**

阅读完以上文件之后，你再严格根据这些文件中的内容，开始编写本次任务的自动化测试用例。**编写过程必须全面遵守上述所有关联文件中的规范（编码规范、fixture 约束、断言分层、需求定义、前端代码匹配等）**；其中以下两点为高频易错、需特别强调的硬约束：

- **MD 保护**：严禁修改阶段一产出的 MD 需求文档，除非确认 MD 本身存在转换错误（如未按 CSV 转换、描述错误等）；脚本执行失败不得作为修改 MD 的理由。
- **CSV 数据保护**：严禁擅自修改测试需求 CSV 中已明确定义的测试数据、测试参数（如端口、协议、权重、IP、规格、数量等），必须严格按 CSV 取值编码。

## 第二部分：测试脚本与需求对齐检查（自主循环）

> 第一部分编写完脚本后，对照阶段一产出的需求 MD、第一部分引用的编码规范（`sugon_web/case_specs/prompts/test_case_codegen_prompt.md`）**和断言规范（`sugon_web/case_specs/prompts/assertion_guidelines.md`）以及对应前端工程代码**，按以下检查项逐项检查，发现遗漏或偏差直接修改，循环直至完全对齐。

**一、需求对齐检查**

1. **步骤完整性**
   - 规则：脚本覆盖需求 MD 中的所有测试步骤，无遗漏、无多余，步骤顺序与需求一致。

2. **边界条件覆盖**
   - 规则：脚本实现需求 MD 中定义的所有边界条件测试代码。

3. **断言完整性**
   - 规则：脚本实现需求 MD 中定义的所有断言点，P0 流程阻塞点（操作成功+存在性/状态收敛）、P1 末态字段（字段值回读）、P2 业务逻辑（SSH 后端验证）三层覆盖完整无遗漏；P3 导航/操作步骤无显式断言。

4. **测试数据对齐**
   - 规则：资源名称使用 `random_data()`；批量创建必须用 fixture 的 `count` 参数，禁止手动循环创建（如 `for i in range`）；测试数据准备与前置条件一致。
   - 示例：vm fixture 用 `{"basic": {"count": N}}` 格式，其他 fixture 用 `{"count": N}` 格式。
   - 自检：`Grep` 搜索 `@pytest.mark.parametrize("vm"`，确认未出现手动循环创建。

5. **清理策略对齐**
   - 规则：脚本实现需求 MD 中定义的所有清理步骤，覆盖所有创建的资源；**清理顺序必须严格依据测试需求 CSV 的"测试数据清理顺序"字段（经 MD 转写）执行，不得自行调整**。
   - 核心原则：清理由 fixture 负责回收，测试方法只负责测试——资源已由现有 fixture teardown 完整覆盖则直接复用，现有 teardown 无法覆盖则参照 yield-based cleanup fixture 模式补充。
   - 共享数据：MD 中标注"共享同一套测试数据"的场景，必须置于同一测试类中通过 class-scoped fixture 共享资源，待该批次所有用例执行完成后统一清理。

**二、编码规范检查**

1. **fixture 复用**
   - 规则：优先复用现有 fixture，禁止自行封装功能重复的 fixture；实现测试步骤或前置条件前已阅读 `fixtures_index.md` 确认参数支持情况。

2. **页面对象规范**
   - 规则：页面对象只封装页面交互与业务动作，不组织测试步骤；新增业务方法必须有 docstring（至少含用途、参数含义、可选值或默认值）；已有公共能力能覆盖时禁止新增同义方法；测试 class 体内禁止有 Helper 方法（纯函数放模块级或 `_xxx_helpers.py`）。
   - 自检：`Grep` 搜索 class 体内是否有 `_` 前缀的辅助函数。

3. **定位规范**
   - 规则：测试层严禁直接使用 `locator()` / `expect()` / XPath，所有页面交互必须通过 Page Object 封装方法调用；定位优先 `get_by_role()` / `get_by_text(exact=True)` / `get_by_placeholder()`，并限定在 dialog / tab / 表格 / 行范围内，`first()` / `nth()` 仅作兜底。
   - **运行时侦察(按需,无法仅凭前端代码确定唯一定位时)**：当某交互的定位**无法仅凭前端工程代码确定唯一、稳定的选择器**（典型：操作项默认隐藏需 JS 触发、同名菜单多个需 nth、复杂表单组件内部多 input、自定义组件如 cl-table/SugonDeleteDialog），**应先用运行时侦察脚本(黑盒,先 `--help`)** 从真实渲染态枚举候选元素再写定位，不要凭空构造或仅靠静态代码猜测：
     `python .claude/skills/test-script-workflow/scripts/recon_page.py --service "<服务名>" [--submenu "<子菜单>"] [--grep "<关键词>"]`
     侦察脚本**只读不改**(复用项目登录态/`goto_service`、整页截图、枚举 button/a/input/tab/列头)，只用于发现定位，定位写回 Page Object。简单用例能直接确定定位的**不必触发**，避免拖慢。
   - 自检：`Grep` 搜索 `\.locator\(` 或 `from.*playwright import expect`，确认测试层未出现底层 API 调用。

4. **等待规范**
   - 规则：禁止使用固定等待；进入页面或表单提交后先 `wait_for_page_ready()` 或 `wait_for_load_state('networkidle')`，状态收敛优先 `wait_for_operation_complete()` / `wait_for_source_complete()`。
   - 数据来源：CSV 已明确等待时长的，作为收敛等待方法（如 `wait_for_operation_complete()` / `wait_for_source_complete()` / `assert_status()`）的 `timeout` 参数传入，禁止转为固定等待；CSV 未明确的用框架方法默认值。

5. **断言分层合规**
   - 规则：断言按 P0/P1/P2/P3 分层，符合 `assertion_guidelines.md` 决策树判定；P3 导航/操作步骤无显式断言；P0 只断言操作成功+存在性，不混杂字段值；P0 与 P1 不重复断言同一内容。

6. **断言规范**
   - 规则：状态变更类断言按 P0→P1 顺序——P0 先断言操作成功（如 `assert_popup_success()`）和资源存在性/状态收敛（如 `assert_list_contain()` / `assert_status()` / `assert_deleted()`），P1 再集中断言末态字段值（详情页/行数据回读）；状态变更必须先等待收敛（`wait_for_operation_complete()` / `wait_for_source_complete()`）再断言；SSH 命令必须断言返回值（`rc`、`stdout`），禁止用 `` `|| true` `` 掩盖错误；每步操作后必须紧跟断言，禁止仅用 `logger.info()` 记录而不断言。
   - 新增方法：先搜索 `sugon_web/assertions/` 已有方法优先复用，无可复用时按 `assert_<对象>_<行为>` 命名、参数带默认值、写完整 docstring。

7. **用例结构规范**
   - 规则：用例结构为准备数据 → 执行操作 → 校验结果，步骤用 `with allure_step_log()`；测试主流程禁止用 `try/finally` 或 `try/except` 包裹核心步骤。
   - 自检：`Grep` 搜索 `try:` + `finally:`，确认测试方法体内未出现 `try/finally`。

8. **数量对齐**
   - 规则：CSV 场景数、MD 场景数、测试脚本中 `def test_` 方法数三者必须一致；CSV 含多个仅参数不同的高度重复需求（如同类创建场景）时，必须用 `@pytest.mark.parametrize` 参数化实现，严禁把多个需求合并进同一个测试方法、也不写多个高重复率的方法。
   - 自检：`Grep` 搜索正则 `def test_\w+` 数量，确认测试方法数与 CSV 行数一致。

9. **Allure 标题规范**
   - 规则：`@allure.title` 沿用同模块现有风格命名，格式为 `资源名-功能点`；数据驱动用例保留参数化占位风格。

10. **公共操作复用**
    - 规则：优先使用 `base.py` 已封装的公共操作元素（如 `btn_create`、`search`、`click_action` 等），禁止自行构造等价 locator 重复实现。

11. **代码侵入检查**
    - 规则：脚本仅可新增/修改测试文件（`test_*.py`）和必要的页面对象文件；禁止修改 `sugon_web/common/`、`sugon_web/refrence/` 下任何文件，也禁止修改阶段一产出的 MD 需求文档。

**循环规则：** 按上述各项检查规范逐项检查 → 发现不符合 → 修改脚本 → 重新检查 → 直至全部符合。
- **遵循通用循环约定，严禁停下来询问用户**，因为循环中断会浪费已执行的进度，所有检查发现的问题自主修改
- 直至全部检查项均通过，方可进入下一阶段

**三、静态门禁闸门（对齐检查全部通过后、进入阶段三前必跑）**

> 上述对齐检查是 AI"自证式"逐项检查；为兜底"可机器判定"的机械违规（防止它们被带到阶段三长时执行才暴露），在对齐检查全部通过后，再跑一次静态门禁脚本（黑盒，先 `--help`），形成 validator→fix→repeat 反馈环：

```
python .claude/skills/test-script-workflow/scripts/precheck.py <本次测试文件或目录> --expected-tests <CSV/MD 场景数>
```

- 门禁客观检出：测试层 `.locator(`/`expect`/XPath、`wait_for_timeout`/`time.sleep` 固定等待、测试方法体 `try/except|finally` 包裹、SSH `|| true`、`def test_` 数 ≠ 场景数、未在 pytest.ini 登记的 marker、触碰禁区文件。
- **退出码非 0 → 必须先修复违规再重跑门禁，直至通过方可进入阶段三**。
- **门禁是兜底，不是替代**：断言分层是否合理、是否对齐需求语义，仍由上面"一、需求对齐检查 / 二、编码规范检查"负责；门禁通过不代表语义正确。

## 阶段二完成时立即输出（必须，不得延迟到 SKILL 总收尾）

**触发时机**：本阶段达到完成标志或被迫中断时,立即在对话框输出以下内容（不得跳过、不得合并到下一阶段）。

> **同步持久化（强制）**：以下内容在对话框输出的同时，必须**追加写入运行报告文件** `skill_runs/test-script-workflow/test-script-workflow_{任务标识}_{YYYYMMDD_HHMM}.md`（任务标识 = 本次任务的需求 MD 英文文件名去 `.md`，与阶段一一致，不得改用脚本名）。追加前先按任务标识 glob 取最新的该运行报告文件并在其末尾追加，**严禁新建第二个文件**；仅当以本阶段作为执行入口、glob 确实找不到任何文件时，才创建并写入文件头（任务标识、运行开始时间、来源信息）。追加内容最前面须记录本阶段完成时间，格式：`## 阶段二：脚本编写与对齐　完成时间：YYYY-MM-DD HH:MM:SS`。**确认本阶段完成块已写入该运行报告文件后，方可进入下一阶段。**

1. **状态标题**
   - 正常完成 → `阶段二任务已完成`
   - 被迫中断 → `阶段二任务被迫中断：{主要原因}`。如有深层根因则补充，无则省略。

2. **完成清单**

| 测试脚本路径 | 脚本名称 | 测试方法列表 | 覆盖场景数 | 对齐检查结果 |
|---|---|---|---|---|
| `sugon_web/testcase/xxx/test_xxx.py` | `test_xxx.py` | `test_xxx1`, `test_xxx2` | N | 通过/不通过 |
