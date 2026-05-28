# 断言层编写与存放规范

> **AI 行为准则**：本文档是断言层编写的规范。`assertions/` 下既有代码中存在历史遗留实现，新增断言方法时**必须遵循本文档**。

## 一、完整目录结构

```
sugon_web/assertions/
  __init__.py                    # 统一导出所有 AssertionMixin
  README.md                      # 本文件
  base/                          # 通用断言（不依赖具体业务）
    __init__.py
    popup.py                     # PopupAssertionMixin
    list.py                      # ListAssertionMixin
    status.py                    # StatusAssertionMixin
  network/                       # 网络业务断言
    __init__.py
    slb.py                       # SlbAssertionMixin
    monitor.py                   # MonitorAssertionMixin
    ip_group.py                  # IpGroupAssertionMixin
  compute/                       # 计算业务断言
    __init__.py
    ecs.py                       # EcsAssertionMixin
  database/                      # 数据库业务断言
    __init__.py
    doris.py                     # DorisAssertionMixin
  backup/                        # 备份服务断言
    __init__.py
    backup.py                    # BackupAssertionMixin
  helpers/                       # 纯函数断言（非 Mixin，供多模块复用）
    __init__.py
    lb_algorithm.py              # assert_lb_algorithm, assert_udp_source_ip_sticky, assert_udp_all_rejected
```

> 说明：目录按当前已有模块列出，新增业务域时按同样规则扩展。

## 二、怎么放：存放路径决策

按单一维度判定：**是否操作页面 Locator（需要 `self.page` / `self.locator`）**。

```
需要操作页面 Locator？
├─ 是 -> 通用（不依赖任何业务语义）？
│       ├─ 是 -> assertions/base/<类别>.py 中的 Mixin
│       └─ 否 -> assertions/<模块>/<服务>.py 中的 Mixin
└─ 否 -> 纯函数且跨模块复用？
        ├─ 是 -> assertions/helpers/<功能>.py 中的纯函数
        └─ 否 -> 测试文件内私有函数 def _assert_xxx 或裸写 assert
```

| 目录 | 类型 | 判定标准 | 示例 |
|:---|:---|:---|:---|
| `base/` | Mixin | 只操作页面 Locator，不依赖业务语义 | 弹窗、列表、状态 |
| `<module>/` | Mixin | 只操作页面 Locator，依赖具体业务元素结构 | SLB 监听器详情、ECS 镜像状态 |
| `helpers/` | 纯函数 | 无 `self`，包括 SSH/API/算法/场景验证 | 轮询算法验证、进程状态检查 |
| 测试文件 | 私有函数 | 仅当前用例使用，不复用 | 单用例组合断言 |

**关键约束**：Mixin 中**不调用 SSH、API、DB**。需要后端验证的场景，写成纯函数放在 `helpers/` 或测试文件中，由测试方法独立调用。

### 测试方法中的 assert 边界

上述决策树回答的是**断言方法放哪里**，这里补充**测试方法里什么时候直接裸写 `assert`**。

| 场景 | 做法 | 示例 |
|:---|:---|:---|
| 简单值比较（一行能说清） | 测试方法内直接 `assert` | `assert result["status"] == "active"` |
| 后端返回值直接校验 | 测试方法内直接 `assert` | `assert stdout.get("rc") == 0` |
| 涉及页面 Locator 操作 | 调用 Mixin 方法 | `page.assert_popup_success("创建成功")` |
| 纯函数 + 跨模块复用 | 调用 helpers/ 函数 | `assert_lb_algorithm(...)` |
| 复杂逻辑但单文件使用 | 测试文件内 `def _assert_xxx` | 多字段组合校验抽成私有函数 |

**一句话规则**：能用一行 `assert` 说清的，裸写；涉及 Locator、需要复用、或需要语义化命名的，抽成断言方法。

**失败消息格式**：裸写的 `assert` 同样必须遵循 3.4 节的统一格式（`[<分类标签>] <被测对象> | <描述> | 期望: <expected> | 实际: <actual>`）。测试方法中常见场景的推荐标签：后端验证用 `[BackendAssertion]`，算法/数值用 `[ScenarioAssertion]`，简单字段校验用 `[FieldAssertion]`。

## 三、怎么写：编码规范

### 3.1 Mixin 类规范

```python
class XxxAssertionMixin:
    """一句话说明验证什么资源/场景。
    属于 L? 层断言。
    """

    def assert_<资源>_<验证点>(self, ..., timeout=300):
        """验证 xxx。

        Args:
            xxx: 说明，类型，默认值。
            timeout: 最长等待秒数，默认 300。expect() 在此时间内自动轮询。
        """
```

| 规则项 | 要求 |
|:---|:---|
| `__init__` | **不定义**。Mixin 只提供方法，不管理状态 |
| 类命名 | `<业务>AssertionMixin`，如 `SlbAssertionMixin` |
| 方法命名 | `assert_<资源>_<验证点>`，如 `assert_listener_exists` |
| Docstring | **必填**。用途、每个参数含义、默认值 |
| timeout | 必须有默认值，**单位为秒**；调用 `expect()` 时内部转换为毫秒（`timeout * 1000`） |
| 定位范围 | 优先限定在 dialog / tab / 表格 / 行范围内，不全局搜 |
| 职责边界 | **只操作 Locator，不调用 SSH/API/DB** |

### 3.2 纯函数规范（helpers/）

```python
def assert_<场景>_<验证目标>(..., tolerance=0.15):
    """...

    Args:
        tolerance: 允许的偏差比例，默认 0.15。
            **属于需求参数，严禁修改。**

    """
```

| 规则项 | 要求 |
|:---|:---|
| `self` | **无**。纯函数，不依赖页面对象 |
| 复用标准 | 仅在 >=2 个模块可能复用时才放 helpers/ |
| 数值参数 | 必须在 docstring 中声明"属于需求参数，严禁修改" |

### 3.3 断言工具选择：expect() vs assert

| 场景 | 推荐工具 | 原因 |
|------|----------|------|
| UI 元素可见性/隐藏/属性/文本 | `expect()` | 内置自动重试（auto-retry），`timeout` 参数统一处理等待 |
| UI 文本内容（复杂多条件组合判断） | `assert`（**前置等待后**） | `expect()` matcher 表达能力有限；须先等待关键文本加载（见下方核心原则第 3 条） |
| 后端验证（SSH/API/DB） | `assert` | 无 Locator 依赖，纯函数中处理 |
| 算法/数值验证 | `assert` | 纯逻辑判断 |

**核心原则**：
- Mixin 中的 UI 断言**统一用 `expect(locator).to_xxx(timeout=...)`**（如 `to_be_visible()`、`to_contain_text()` 等），不手写 `while` + `time.sleep` 轮询。
- Playwright 的 `expect()` 内置自动重试，`timeout` 参数已覆盖"即时"和"等待"两种场景，不需要区分。
- **禁止直接对 `locator.text_content()` / `inner_text()` 的返回值裸写 `assert`**。这两个方法只查询当前 DOM 快照，不会等待或自动重试，DOM 未更新时取到的可能是空字符串或旧值，导致 flaky。须先用 `expect(locator).to_contain_text()` 等待关键文本出现，再做复杂判断。
- 后端验证不在 Mixin 中处理，用纯函数独立实现。

### 3.4 断言失败消息格式

所有 `assert` 语句的失败消息必须遵循统一格式：

```
[<分类标签>] <被测对象> | <描述> | 期望: <expected> | 实际: <actual>
```

| 字段 | 说明 | 示例 |
|------|------|------|
| `<分类标签>` | 方括号前缀，标识断言类型 | `[StatusAssertion]`、`[FieldAssertion]` |
| `<被测对象>` | 资源名称、ID 或定位描述 | `ECS 'web-01'`、`列表` |
| `<描述>` | 一句话说明校验点 | `状态未收敛`、`字段 'CPU' 不匹配` |
| `<expected>` | 期望结果 | `'运行中'`、`'4核'`、`存在` |
| `<actual>` | 实际结果 | `'创建中'`、`'2核'`、`不存在` |

**分类标签定义**：

| 标签 | 适用断言 | 示例 |
|------|----------|------|
| `[PopupAssertion]` | 弹窗/Toast/对话框 | `[PopupAssertion] 成功弹窗 | 文案不匹配 | 期望: '创建成功' | 实际: '创建失败'` |
| `[ListAssertion]` | 列表存在性、删除验证 | `[ListAssertion] ECS 'web-01' | 列表存在性校验失败 | 期望: 存在 | 实际: 不存在` |
| `[StatusAssertion]` | 资源状态收敛 | `[StatusAssertion] ECS 'web-01' | 状态未收敛 | 期望: '运行中' | 实际: '创建中'` |
| `[FieldAssertion]` | 详情页/弹窗字段值 | `[FieldAssertion] ECS 'web-01' | 字段 'CPU' 不匹配 | 期望: '4核' | 实际: '2核'` |
| `[BackendAssertion]` | SSH/API/后端验证 | `[BackendAssertion] 命令 'systemctl status fs-agent' | 返回码不匹配 | 期望: rc=0 | 实际: rc=1` |
| `[ScenarioAssertion]` | 算法/场景/端到端 | `[ScenarioAssertion] 轮询算法 | 分布偏差超标 | 期望: ≤15% | 实际: 23%` |

**规则**：
- `expect()` 抛出的异常由 Playwright 自动生成消息，无需手动格式化。
- `assert` 语句的消息必须包含分类标签，且顺序固定：`[标签] 对象 | 描述 | 期望 | 实际`。
- 若某字段无意义（如纯存在性判断），可省略 `期望/实际`，但分类标签和被测对象必须保留。

### 3.5 方法体两种分类

Playwright 的 `expect()` 内置自动重试，通过 `timeout` 参数统一处理异步加载和状态收敛等待。断言层不需要区分"即时"和"轮询"，只按职责分为两类：

**分类 1：UI 断言 Mixin**

统一使用 `expect(locator).to_xxx(timeout=...)`（如 `to_be_visible()`、`to_contain_text()` 等）。

```python
def assert_<资源>_<验证点>(self, ..., timeout=300):
    """验证 xxx。

    Args:
        timeout: 最长等待秒数，默认 300。expect() 在此时间内自动轮询。
    """
    target = self.get_row_by_name(name)
    expect(target).to_contain_text(
        expected, timeout=timeout * 1000, use_inner_text=True
    )
```

原则：
- **不手写 `while` + `time.sleep` 轮询** — Playwright 的自动重试更稳定。
- **不调用 SSH、API、DB** — Mixin 只操作 Locator。
- 需要手动刷新页面的场景，刷新是**交互行为**，应封装在 Page Object 中，测试方法里组合调用（先刷新，再断言）。

**分类 2：后端/场景断言纯函数**

无 `self`，测试方法中独立调用。

```python
def assert_<场景>_<验证目标>(..., tolerance=0.15):
    """...

    Args:
        tolerance: 允许的偏差比例，默认 0.15。
            **属于需求参数，严禁修改。**
    """
    # 失败消息格式遵循 3.4 节统一规范
    assert condition, (
        f"[ScenarioAssertion] <被测对象> | <描述> | "
        f"期望: <expected> | 实际: <actual>"
    )
```

原则：
- **对于需要轮询等待的非 Locator 条件，优先使用 `expect.poll()`**，而不是裸写 `assert` 或 `while` 循环。
- 例如轮询后端状态至收敛：`expect.poll(lambda: get_backend_status(), timeout=30000).to_be("active")`

## 四、使用方式

页面对象通过**多重继承**引入 UI 断言能力：

```python
from sugon_web.assertions import (
    PopupAssertionMixin,
    ListAssertionMixin,
    SlbAssertionMixin,
)

class SlbPage(SlbAssertionMixin, PopupAssertionMixin, ListAssertionMixin, BasePage):
    """负载均衡页面对象，通过多重继承获得断言能力。"""
    pass
```

后端/场景断言以纯函数形式在测试方法中独立调用：

```python
from sugon_web.assertions.helpers import assert_lb_algorithm

def test_lb_round_robin(page, ssh_client):
    page.ecs_create("vm-01")
    page.assert_popup_success("创建成功")
    page.assert_status("vm-01", "运行中")

    responses = collect_lb_http_responses(ssh_client, "http://vip:8080", count=30)
    assert_lb_algorithm(
        policy="round_robin",
        responses=responses,
        backend_markers={"ecs1": "this is ecs1", "ecs2": "this is ecs2"},
        scene_name="SLB 轮询测试",
    )
```

## 五、新增断言流程

```
Step 1: 判定类型
  -> 操作页面 Locator？-> UI 断言 Mixin
  -> 不操作 Locator（SSH/API/算法）？-> 后端/场景纯函数

Step 2: 判定位置
  -> UI 断言 + 通用 -> base/
  -> UI 断言 + 业务 -> <module>/
  -> 纯函数 + 复用 -> helpers/
  -> 其他（纯函数单用例 / 非纯函数）-> 测试文件私有函数或裸写 assert

Step 3: 检查复用
  -> Grep 全库 def assert_ / def verify_ / def check_
  -> 确认无同义方法

Step 4: 编写方法
  -> 命名: assert_<资源>_<验证点>
  -> 参数: 必须有 docstring，timeout 有默认值
  -> 实现: 限定范围，优先复用现有 locator；UI 断言统一 expect(locator).to_xxx(timeout=...)

Step 5: 导出
  -> 在目录 __init__.py 中导出
  -> 在顶层 __init__.py 中导出
```

## 六、禁止清单

| # | 禁止项 | 正确做法 |
|:---|:---|:---|
| 1 | 在 Mixin 中定义 `__init__` | Mixin 无状态 |
| 2 | 命名模糊如 `assert_data` | 必须 `assert_<资源>_<验证点>` |
| 3 | 同义断言重复定义 | 新增前先 `Grep` 全库确认无同义方法 |
| 4 | 在 `pages/*.py` 中写场景编排断言 | 场景编排断言放 helpers/ 或测试文件 |
| 5 | 在 `helpers/` 中写页面元素断言 | helpers 只放纯函数 |
| 6 | 修改 tolerance/阈值/比例 | 需求参数，不可修改 |
| 7 | SSH 断言用 `|| true` | 必须断言 rc，需要时同时断言 stdout |
| 8 | `try/except` 吞断言异常 | 让真实异常抛出 |
| 9 | 页面对象（`pages/`）中直接引入 `locator()` / `expect()` | UI 断言集中到 `assertions/` Mixin 中，页面对象只负责业务操作 |
| 10 | Mixin 中调用 SSH/API/DB | 后端验证写成纯函数，测试方法中独立调用 |
| 11 | Mixin 中手写 `while` + `time.sleep` 轮询 | UI 断言统一用 `expect(locator).to_xxx(timeout=...)` |
