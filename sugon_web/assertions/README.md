# 断言层编写与存放规范

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
    vpc.py                       # VpcAssertionMixin
    sg.py                        # SgAssertionMixin
    eip.py                       # EipAssertionMixin
    nat.py                       # NatAssertionMixin
    acl.py                       # AclAssertionMixin
    peer_connect.py              # PeerConnectAssertionMixin
    qos.py                       # QosAssertionMixin
    internal_dns.py              # InternalDnsAssertionMixin
    ip_group.py                  # IpGroupAssertionMixin
    monitor.py                   # MonitorAssertionMixin
  compute/                       # 计算业务断言
    __init__.py
    ecs.py                       # 纯函数: assert_ecs_details_info, assert_ecs_info, ...
    image.py                     # ImageAssertionMixin
    snapshot.py                  # SnapshotAssertionMixin
    affinity.py                  # AffinityAssertionMixin
    label.py                     # LabelAssertionMixin
    recycle.py                   # ComputeRecycleAssertionMixin
  storage/                       # 存储业务断言
    __init__.py
    backup.py                    # BackupAssertionMixin
    evs.py                       # EvsAssertionMixin
    evss.py                      # EvssAssertionMixin
    recycle.py                   # StorageRecycleAssertionMixin
  database/                      # 数据库业务断言
    __init__.py
    doris.py                     # DorisAssertionMixin
    mongodb.py                   # MongodbAssertionMixin
    mysql.py                     # MysqlAssertionMixin
    pgsql.py                     # PgsqlAssertionMixin
    xscale.py                    # XscaleAssertionMixin
  middleware/                    # 中间件断言
    __init__.py
    kafka.py                     # KafkaAssertionMixin
    redis.py                     # RedisAssertionMixin
  ssh/                           # SSH 后端断言
    __init__.py
    guest.py                     # GuestAssertionMixin
  helpers/                       # 纯函数断言（非 Mixin，供多模块复用）
    __init__.py
    lb_algorithm.py              # assert_lb_algorithm, collect_lb_http_responses
  cms/                           # 占位（当前暂无专属断言）
    __init__.py
```

## 二、怎么放：存放路径决策

按两个维度判定：**是否需要 `self`（页面对象状态）** x **是否跨模块通用**。

```
需要 self（页面元素定位 / 页面对象方法调用）？
├─ 是 -> 通用（不依赖任何业务语义）？
│       ├─ 是 -> assertions/base/<类别>.py 中的 Mixin
│       └─ 否 -> assertions/<模块>/<服务>.py 中的 Mixin
└─ 否 -> 纯函数，供多模块复用？
        ├─ 是 -> assertions/helpers/<功能>.py 中的纯函数
        └─ 否 -> 测试文件内私有函数 def _assert_xxx
```

| 目录 | 类型 | 判定标准 | 示例 |
|:---|:---|:---|:---|
| `base/` | Mixin | 任何模块都能用，不依赖业务语义 | 弹窗、列表、状态 |
| `<module>/` | Mixin | 依赖具体业务页面的元素结构 | SLB 监听器详情、ECS 镜像状态 |
| `ssh/` | Mixin | 通过 SSH 验证后端，接收 `ssh_vm` 参数 | 进程运行、文件存在 |
| `helpers/` | 纯函数 | 无 `self`，供多模块复用的场景级验证 | 轮询算法验证 |
| 测试文件 | 私有函数 | 仅当前用例使用，不复用 | 单用例组合断言 |

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
            timeout: 最长等待秒数，默认 300。
        """
```

| 规则项 | 要求 |
|:---|:---|
| `__init__` | **不定义**。Mixin 只提供方法，不管理状态 |
| 类命名 | `<业务>AssertionMixin`，如 `SlbAssertionMixin` |
| 方法命名 | `assert_<资源>_<验证点>`，如 `assert_listener_exists` |
| Docstring | **必填**。用途、每个参数含义、默认值 |
| timeout | 必须有默认值，允许调用方覆盖 |
| 定位范围 | 优先限定在 dialog / tab / 表格 / 行范围内，不全局搜 |

### 3.2 纯函数规范（helpers/）

```python
def assert_<场景>_<验证目标>(..., tolerance=0.15):
    """...

    Args:
        tolerance: 允许的偏差比例，默认 0.15。

    """
```

| 规则项 | 要求 |
|:---|:---|
| `self` | **无**。纯函数，不依赖页面对象 |
| 复用标准 | 仅在 >=2 个模块可能复用时才放 helpers/ |
| 数值参数 | 必须在 docstring 中声明"属于需求参数，严禁修改" |

### 3.3 断言工具选择：expect() vs assert

Mixin 中的断言方法应根据断言目标选择工具，而非统一用一种。

| 场景 | 推荐工具 | 原因 |
|------|----------|------|
| UI 元素可见性/隐藏/属性/数量 | `expect()` | 内置自动重试（auto-retry），消除 race condition |
| UI 文本内容（需轮询等待） | `expect()` | `to_contain_text` / `to_have_text` 自带超时轮询，比手写 while 更稳定 |
| UI 文本内容（复杂多条件组合判断） | `assert` | `expect()` matcher 表达能力有限，如 `assert "A" in text or "B" in text` |
| 后端验证（SSH/API/DB） | `assert` | 无 Locator 依赖 |
| 算法/数值验证 | `assert` | 纯逻辑判断 |

**原则**：`expect()` 与 `assert` 不是互斥关系，而是工具箱中的不同工具。UI 状态断言优先 `expect()`，业务逻辑与后端断言用 `assert`。

### 3.4 断言失败消息格式

所有 `assert` 方法的失败消息必须遵循统一格式，方便 Allure 报告和 AI 分析工具按分类标签自动归类。

**格式模板**：

```
[<分类标签>] <被测对象> | <描述> | 期望: <expected> | 实际: <actual>
```

| 字段 | 说明 | 示例 |
|------|------|------|
| `<分类标签>` | 方括号前缀，标识断言类型 | `[StatusAssertion]`、`[FieldAssertion]` |
| `<被测对象>` | 资源名称、ID 或定位描述 | `ECS 'web-01'`、`列表`、`<被测对象>` |
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

### 3.5 方法体四种模式

**模式 A：即时 UI 断言（L1/L2）**

```python
def assert_popup_success(self, text=None, timeout=10):
    popup = self.page.locator(".el-message--success")
    popup.wait_for(state="visible", timeout=timeout * 1000)
    if text:
        expect(popup).to_contain_text(text, timeout=timeout * 1000)
```

**模式 B：轮询等待断言（L3）**

优先使用 `expect()` 的自动重试机制；仅在需要**手动刷新页面**的场景保留手写轮询。

```python
def assert_status(self, names, status="运行", timeout=300, refresh=False):
    if isinstance(names, str):
        names = [names]
    for name in names:
        self.search(name)
        row = self.get_row_by_name(name)
        if not refresh:
            # 不刷新：利用 expect 自动轮询，最稳定
            expect(row).to_contain_text(status, timeout=timeout * 1000, use_inner_text=True)
        else:
            # 需手动刷新：保留手写轮询
            import time
            deadline = time.time() + timeout
            while time.time() < deadline:
                self.btn_refresh.click()
                self.wait_for_page_ready()
                row = self.get_row_by_name(name)
                if status in row.inner_text():
                    break
                time.sleep(5)
            else:
                assert False, f"状态未在 {timeout}s 内变为 '{status}'"
```

**模式 C：SSH 后端断言（L4）**

```python
def assert_command_output_contains(self, ssh_vm, command, expected):
    result = ssh_vm.run(command)
    assert result.rc == 0, f"命令失败: {result.stderr}"
    assert expected in result.stdout, f"输出未包含 '{expected}'"
```

**模式 D：算法/场景断言（L5）**

```python
def assert_lb_algorithm(algorithm, responses, backend_markers, tolerance=0.15):
    counts = Counter()
    # ... 统计逻辑 ...
    for name in backend_markers:
        deviation = abs(actual - expected) / expected
        assert deviation <= tolerance, f"偏差 {deviation:.2%} > {tolerance}"
```

## 四、使用方式

页面对象通过**多重继承**引入断言能力：

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

纯函数直接从 helpers 引入：

```python
from sugon_web.assertions.helpers import assert_lb_algorithm, collect_lb_http_responses
```

## 五、新增断言流程

```
Step 1: 判定层级
  -> 用决策树确定 L1~L5

Step 2: 判定位置
  -> 需要 self + 通用 -> base/
  -> 需要 self + 业务 -> <module>/
  -> 无 self + 复用 -> helpers/
  -> 无 self + 单用例 -> 测试文件私有函数

Step 3: 检查复用
  -> Grep 全库 def assert_ / def verify_ / def check_
  -> 确认无同义方法

Step 4: 编写方法
  -> 命名: assert_<资源>_<验证点>
  -> 参数: 必须有 docstring，timeout 有默认值
  -> 实现: 限定范围，优先复用现有 locator

Step 5: 导出
  -> 在目录 __init__.py 中导出
  -> 在顶层 __init__.py 中导出
```

## 六、禁止清单

| # | 禁止项 | 正确做法 |
|:---|:---|:---|
| 1 | 在 Mixin 中定义 `__init__` | Mixin 无状态 |
| 2 | 命名模糊如 `assert_data` | 必须 `assert_<资源>_<验证点>` |
| 3 | 同模块重复定义 | 新增前先 `Grep` 确认无同义方法 |
| 4 | 在 `pages/*.py` 中写场景编排断言 | L5 场景放 helpers/ 或测试文件 |
| 5 | 在 `helpers/` 中写页面元素断言 | helpers 只放纯函数 |
| 6 | 修改 tolerance/阈值/比例 | 需求参数，不可修改 |
| 7 | SSH 断言用 `|| true` | 必须断言 rc 和 stdout |
| 8 | `try/except` 吞断言异常 | 让真实异常抛出 |
| 9 | 页面对象（`pages/`）中直接引入 `locator()` / `expect()` | UI 断言集中到 `assertions/` Mixin 中，页面对象只负责业务操作 |
