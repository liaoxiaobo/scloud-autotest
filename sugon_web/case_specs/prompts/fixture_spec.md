# Fixture 新增与抽取规范

> 本文档是框架级通用规范，适用于所有业务模块。
>
> **阅读时机**：当 AI 需要新增 fixture 或将用例中的创建类操作抽取为 fixture 时，在已阅读 `fixtures_index.md`（确认现有 fixture 能力）之后，阅读本文档（获取新增/抽取规范）。
>
> **核心原则**：fixture 只负责资源生命周期管理（参数解析、调用 helper、yield、teardown），不负责组织测试步骤、不封装页面交互逻辑。创建与清理的具体操作必须委托给 `_helper` 完成。

---

## 一、核心原则

1. **fixture = 生命周期管理器**：只做参数接收、调用 helper 创建、yield 返回、调用 helper 清理。
2. **helper = 流程组装器**：封装创建/删除的完整页面操作流程，无 `yield`，无 fixture 依赖注入。
3. **Page Object = 单步交互器**：封装单个页面元素或单步业务操作。

---

## 二、编码规范

新增 fixture 前，必须先搜索现有 fixture 能力，避免重复封装：

```bash
# 搜索 conftest.py 中的 fixture
grep -r "@pytest.fixture" --include="conftest.py" sugon_web/testcase/

# 搜索 _xxx_fixtures.py 中的 fixture
grep -r "@pytest.fixture" --include="*_fixtures.py" sugon_web/testcase/

# 按资源类型关键词搜索
grep -r "def resource(" --include="conftest.py" sugon_web/testcase/
```

### 2.1 文件位置

| fixture 类型 | 放置位置 | 示例 |
|-------------|----------|------|
| 跨模块通用资源 | `sugon_web/testcase/conftest.py` | `vm`、`volume` |
| 模块内通用资源 | `sugon_web/testcase/{server_model}/conftest.py` | `slb`、`ip_group` |
| 清理专用 | 与创建 fixture 同文件，前缀 `clean_` | `clean_rules` |

**注意**：`_xxx_fixtures.py` 中的 fixture 不会被 pytest 自动发现，必须在测试文件中**显式 import**：

```python
from sugon_web.testcase.{server_model}._env_fixtures import backend_setup
```

**helper 文件位置（强制）**：

所有 helper 必须放在 `sugon_web/testcase/{server_model}/_xxx_helpers.py` 中。

| 文件 | 允许内容 | 禁止内容 |
|------|----------|----------|
| `conftest.py` | `@pytest.fixture` 定义 | 多步骤页面操作逻辑 |
| `_xxx_helpers.py` | 创建/删除/查询 helper 函数 | `yield`、fixture 依赖注入 |

### 2.2 命名规范

**核心原则：按实际功能命名，言简意赅，禁止冗余前缀。**

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 资源创建 fixture | 资源名单词（小写），**禁止加 `create_` 前缀** | `vm`、`volume` |
| 组合环境 fixture | 资源组合描述，后缀可加 `_setup` | `backend_setup`、`env_setup` |
| 清理 fixture | `clean_` + 资源/规则描述 | `clean_rules`、`clean_items` |
| class scope fixture | 同普通命名，在 docstring 中标注 `scope="class"` | — |

### 2.3 Helper 委托规范（强制）

**fixture 中禁止直接编写多步骤页面交互逻辑。** 资源的创建与清理必须委托给同模块的 `_helper` 函数完成。

| 层级 | 职责 | 禁止行为 |
|------|------|----------|
| **Fixture** | 生命周期管理（参数解析、调用 helper、yield、teardown） | 禁止直接调用 `page.click()`、`page.fill()` 等多步操作 |
| **Helper** | 组装创建/删除的完整流程，封装多步 Page Object 调用 | 禁止包含 `yield`、fixture 依赖注入 |

**helper 命名规则**：

- 创建 helper：`create_` + 资源名（如 `create_resource`、`create_env`）
- 删除 helper：`delete_` + 资源名（如 `delete_resource`）
- 内部辅助：`_` 前缀（如 `_wait_for_resource_active`）

### 2.4 参数与返回值规范

**入参类型（强制）：**

`request.param` 必须是 `dict` 类型。

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `count` | int | 1 | 批量创建数量。count=1 返回 dict，count>1 返回 list[dict]。即使底层 helper 一次只能创建一个，也必须在 fixture 层保留 count 并通过循环实现批量 |
| `name` | str | None | 自定义名称，None 时使用 `random_data()`；count>1 时自动加编号避免冲突 |

**返回值规范（强制）：**

所有 fixture 统一返回 `dict`（单资源）或 `list[dict]`（多资源）。

| 场景 | 返回类型 | 字段要求 |
|------|----------|----------|
| count=1 | dict | 必须包含 `name` 字段；必须包含所有传入的业务参数；未传的参数必须使用默认值填充 |
| count>1 | list[dict] | 每个元素必须包含 `name` 字段及完整参数（传入的+默认的） |
| 组合资源 | dict | 顶层 key 为各子资源名称，如 `{"parent": {...}, "children": [...]}` |

**核心原则：返回值尽量与入参一致，未传的入参使用默认值。**

这意味着 helper 在创建资源时，对未传入的业务参数应使用默认值；返回的 dict 必须是**创建时实际使用的完整参数快照**，让调用方无需关心哪些参数是用户传入的、哪些是默认的。

**name 生成规范**：

| 场景 | 格式 | 示例 |
|------|------|------|
| 通用资源 | `f"{类型前缀}-{random_data()}"` | `"slb-a3f8b2"` |
| count>1 时 | `f"{base_name}-{index}"` | `"slb-a3f8b2-0"` |

### 2.5 Teardown 规范

**必须遵守：**

1. 使用 `yield` 分割创建和清理阶段
2. yield 前创建资源，yield 后清理资源
3. 清理失败时记录日志，**抛出异常**，确保资源泄漏被暴露
4. 清理顺序：**子资源先删，父资源后删**
5. 批量创建时，在 fixture 层循环委托 helper 逐个清理（或调用支持列表的批量删除 helper）
6. **清理操作必须委托给 helper**，禁止在 fixture 中直接写多步删除逻辑
7. **标准模式下，teardown 必须从 yield 返回值中提取资源标识**；setup 失败时（yield 未执行），允许从内部变量提取标识

**清理模式**：

| 模式 | 适用场景 | 代码特征 |
|------|----------|----------|
| **yield 模式（标准）** | fixture 预创建资源，测试用例只读 | `yield result` → teardown 使用 `result["name"]` |
| **try/finally 模式** | setup 失败需要截图保留现场 | `try: yield ... finally: cleanup` |
| **注册表模式** | 测试用例运行过程中动态创建资源 | 返回 `Registry`，用例登记，fixture 批量清理 |

### 2.6 Scope 选择规范

**默认 `function`。提升 scope 的判定标准：**

资源创建成本是否足够高，使得类内复用带来的时间收益大于维护成本。

| Scope | 判断标准 | 典型场景 |
|-------|----------|----------|
| `function`（默认） | 创建成本低，或不需要跨用例复用 | 安全组、公网 IP、端口、云硬盘 |
| `class` | 创建成本高，类内复用可显著减少总耗时 | 虚机、VPC、负载均衡实例 |

**Class scope fixture 必须自行创建页面**（禁止声明 function scope 的 `page` 参数）：

```python
@pytest.fixture(scope="class")
def vpc(browser_context, config, request):
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    try:
        # ...
        yield result
        # ...
    finally:
        page.close()
```

### 2.7 注释规范

fixture 必须编写**中文 docstring**，格式参考 Python 标准库（Google Style）。必须包含以下章节：

| 章节 | 是否必须 | 说明 |
|------|----------|------|
| 单行描述 | 必须 | 说明 fixture 的核心功能 |
| 参数 | 必须 | 说明 `request.param` 支持的字段及类型 |
| Yields / Returns | 必须 | 说明返回值结构和类型 |
| scope 标注 | class/session 时必须 | 在首行描述末尾标注 `(scope=class)` 等 |
| Examples | 可选 | 展示典型调用方式 |

### 2.8 索引登记规范（强制）

新增或抽取的 fixture 必须同步登记到 `fixtures_index.md`。该文档是框架所有可复用 fixture 的权威索引，若不更新，后续开发者将无法发现该 fixture，导致重复封装。

**登记步骤**：

1. 打开 `sugon_web/case_specs/fixtures_index.md`
2. 按 fixture 所属业务模块，定位到对应章节（如"三、虚机创建 Fixture"、"八、负载均衡 Fixture"）
3. 若现有章节无匹配分类，在末尾新增章节
4. 按现有表格格式追加一行，字段与同级保持一致

**登记格式示例**：

```markdown
| `testcase/network/conftest.py` | `lb_v2` | `protocol`: 协议 `port`: 端口 `pool_name`: 资源池名称 | 创建V2监听器并自动清理 |
```

**字段说明**：

| 字段 | 说明 |
|------|------|
| 文件名 | fixture 所在文件路径（相对 `sugon_web/`） |
| Fixture 名称 | `@pytest.fixture` 装饰的函数名 |
| 参数 | `request.param` 支持的关键字段及默认值 |
| 功能说明 | 一句话描述创建的资源类型及自动清理能力 |

---

## 三、标准代码模板

### 3.1 Helper 模板

```python
# _resource_helpers.py
from typing import Any

from sugon_web.utils.logger import logger


def create_resource(page, resource_page, name: str, **kwargs) -> dict[str, Any]:
    """创建资源。

    Args:
        page: Playwright 页面对象。
        resource_page: 资源页面对象。
        name: 资源名称。
        **kwargs: 业务参数。未传的参数使用默认值。

    Returns:
        dict: 包含 name 及所有实际使用参数的完整字典。
    """
    # 未传参数使用默认值，传入的参数覆盖默认值
    config = {
        "type": kwargs.get("type") or "standard",
        "size": kwargs.get("size") or 30,
        "region": kwargs.get("region") or "default",
    }

    resource_page.create(name=name, **config)

    # 返回完整参数快照：name + 实际使用的所有参数
    return {"name": name, **config}


def delete_resource(page, resource_page, name: str) -> None:
    """删除资源。

    Args:
        page: Playwright 页面对象。
        resource_page: 资源页面对象。
        name: 要删除的资源名称。
    """
    resource_page.delete(name=name)
```

### 3.2 Fixture 模板（Function Scope）

```python
# conftest.py
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data
from sugon_web.testcase.{server_model}._resource_helpers import create_resource, delete_resource


@pytest.fixture
def resource(request, page, resource_page):
    """创建资源并自动清理。

    参数:
        request.param: dict, 可选
            - count: int, 创建数量，默认 1
            - name: str, 自定义名称，默认使用 random_data()
            - type: str, 资源类型，默认 "standard"
            - size: int, 资源大小，默认 30
            - region: str, 区域，默认 "default"

    Yields:
        dict 或 list[dict]:
            count=1 返回单字典，包含 name 及所有实际使用的参数（传入的+默认的）。
            count>1 返回列表，每个元素均为完整参数字典。
            调用方可直接使用返回值的任意字段，无需关心默认值逻辑。
    """
    params = request.param or {}
    count = params.get("count", 1)
    base_name = params.get("name") or f"resource-{random_data()}"

    # 过滤 fixture 控制参数，只保留业务参数传给 helper
    create_params = {k: v for k, v in params.items() if k not in ("count", "name")}

    # --- 创建阶段：委托 helper ---
    results = []
    for i in range(count):
        name = f"{base_name}-{i}" if count > 1 else base_name
        item = create_resource(page, resource_page, name=name, **create_params)
        results.append(item)

    yield results[0] if count == 1 else results

    # --- 清理阶段：委托 helper ---
    with allure_step_log(f"清理: 删除 {len(results)} 个资源"):
        for item in results:
            delete_resource(page, resource_page, item["name"])
```

### 3.3 Fixture 模板（Class Scope）

```python
from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.{server_model} import ResourcePage
from sugon_web.testcase.{server_model}._resource_helpers import create_resource, delete_resource
from sugon_web.utils.logger import allure_step_log, logger


@pytest.fixture(scope="class")
def resource(browser_context, config, request):
    """创建资源并自动清理（scope=class）。

    参数:
        request.param: dict, 可选
            - count: int, 创建数量，默认 1
            - name: str, 自定义名称，默认使用 random_data()

    Yields:
        dict 或 list[dict]: count=1 返回单字典，count>1 返回列表。
    """
    page = _create_logged_in_page(browser_context, config)
    resource_page = ResourcePage(page)

    params = request.param or {}
    count = params.get("count", 1)
    base_name = params.get("name") or f"resource-{random_data()}"
    create_params = {k: v for k, v in params.items() if k not in ("count", "name")}

    result = None
    try:
        results = []
        for i in range(count):
            name = f"{base_name}-{i}" if count > 1 else base_name
            item = create_resource(page, resource_page, name=name, **create_params)
            results.append(item)

        result = results[0] if count == 1 else results
        yield result
    except Exception:
        # setup 失败时保留现场（可选：调用 capture_fixture_failure）
        raise
    finally:
        # --- 清理阶段 ---
        try:
            if result is not None:
                with allure_step_log(f"清理: 删除 {len(results)} 个资源"):
                    for item in results:
                        delete_resource(page, resource_page, item["name"])
        finally:
            page.close()
```

### 3.4 注册表清理模式模板

```python
@pytest.fixture
def clean_items(page, resource_page):
    """注册表模式：测试用例动态登记资源，fixture 统一清理。

    Yields:
        list: 资源名称注册表，测试用例通过 append() 登记。
    """
    registry = []
    yield registry

    with allure_step_log(f"清理: 删除 {len(registry)} 个动态资源"):
        for name in registry:
            delete_resource(page, resource_page, name)
```

---

## 四、边界情况处理

### 4.1 创建失败处理

setup 阶段创建资源失败时，**必须抛出异常**，让 pytest 标记用例为 error，同时保留失败现场：

```python
result = None
try:
    result = create_resource(page, resource_page, name=name, **create_params)
    yield result
except Exception:
    capture_fixture_failure(page, request, "setup")
    raise
finally:
    # setup 成功时（result 不为 None），执行 teardown 清理
    if result is not None:
        delete_resource(page, resource_page, result["name"])
```

### 4.2 资源依赖

**直接依赖**：在 fixture 参数列表中声明依赖 fixture。

```python
@pytest.fixture
def nat(vpc_page, vpc, request):
    vpc_name = vpc["name"]
    # ...
```

**可选依赖**：通过 `request.fixturenames` 动态检测。

```python
@pytest.fixture
def volume(evs_page, request):
    host = None
    if "vm" in request.fixturenames:
        vm = request.getfixturevalue("vm")
        host = vm.get("host")
    # ...
```

### 4.3 组合资源 Fixture（建议谨慎使用）

**一般原则**：资源之间的关联操作（绑定、配置、加入资源池）应放在**用例步骤**中完成，fixture 只负责让单个资源存在。

**例外场景**：当满足以下全部条件时，允许抽取组合 fixture：

1. **组合关系固定**：子资源间的关联方式不随用例变化
2. **高频复用**：≥3 个测试类需要完全相同的资源组合
3. **生命周期一致**：组合内所有资源同时创建、同时销毁

**返回值格式**：

```python
yield {
    "vm": vm_data,
    "sg": sg_data,
    "eip": eip_data,
}
```

**命名规范**：组合 fixture 使用 `env_setup`、`backend_setup` 等描述性名称，**禁止**用 `create_xxx_env`。

---

## 五、禁止行为清单

- 禁止在测试函数中手动 `for` 循环创建资源（必须用 fixture 的 `count` 参数）
- 禁止新增与现有 fixture 功能相似的 fixture
- 禁止在 fixture 中直接编写页面交互逻辑（如 `page.click()`、`page.fill()` 等，必须委托 helper）
- 禁止在 fixture 中写断言（断言是测试层的职责）
- 禁止在 fixture 中使用 `return` 而不做 `yield` 清理（除非是纯计算型 fixture）
- 禁止在 teardown 中静默吞掉所有异常（必须记录日志并抛出异常）
- 禁止修改 `sugon_web/common/` 下的公共模块来支持新 fixture
- 禁止 fixture 命名加 `create_` 或 `new_` 前缀（资源 fixture 直接用名词）
- 禁止 helper 中编写 `yield` 或声明 fixture 依赖
- 禁止 class scope fixture 的参数列表中声明 `page`（scope mismatch）

---

## 六、AI 自检清单

完成 fixture 抽取后，逐项自检：

### P0（阻塞项，不通过不能交付）

- [ ] 是否已通过 `grep` 搜索确认无同名/同功能现有 fixture（含 `_xxx_fixtures.py`）
- [ ] `request.param` 是否为 `dict` 类型
- [ ] 返回值是否包含 `name` 字段及完整业务参数（传入的+默认的）
- [ ] 是否使用 `yield` 并包含 teardown 清理逻辑
- [ ] 标准模式下 teardown 是否从 yield 返回值中提取资源标识（setup 失败除外）
- [ ] teardown 是否处理了清理失败（记录日志并抛出异常）
- [ ] 创建与删除是否均委托给 helper（非 fixture 内直接写多步操作）
- [ ] helper 是否放在 `_xxx_helpers.py` 中

### P1（建议项，提升质量）

- [ ] 是否支持 `count` 参数（批量创建）
- [ ] scope 是否选择合理（默认 function，共享需求才提升为 class）
- [ ] class scope fixture 是否自行创建页面并在 finally 中关闭
- [ ] fixture 中是否无断言、无页面交互逻辑封装
- [ ] 依赖的其他 fixture 是否在参数列表中正确声明
- [ ] 是否编写了 docstring（说明用途、参数、返回值）
- [ ] 命名是否言简意赅（无 `create_` / `new_` 等冗余前缀）
- [ ] 是否已同步登记到 `fixtures_index.md` 的对应章节

---

## 七、常见错误速查表

| 错误场景 | 错误表现 | 正确做法 |
|----------|----------|----------|
| **fixture 中直接写页面操作** | fixture 内出现 `page.click()`、`page.fill()` 等多步操作 | 委托 helper 完成，fixture 只负责生命周期管理 |
| **命名冗余** | 使用 `create_xxx`、`new_xxx`、`xxx_object` 等前缀/后缀 | 直接用名词，如 `resource`、`pool` |
| **用 return 代替 yield** | `return {"name": name}`，无清理逻辑 | 使用 `yield`，在 yield 后写 teardown |
| **参数未过滤透传** | `create_resource(..., **params)` 把 `count`、`name` 传给 helper | 过滤控制参数：`create_params = {k: v for k, v in params.items() if k not in ("count", "name")}` |
| **fixture 中写断言** | `assert resource_page.is_visible()` 出现在 fixture 中 | 断言移到测试方法中 |
| **未更新索引表** | 新增 fixture 后 `fixtures_index.md` 无对应记录 | 按模块补充到对应章节的表格中 |
| **不支持 count 参数** | 批量需求时只能在用例中手动 `for` 循环创建 | fixture 支持 `count` 参数，通过 `request.param` 接收 |
| **返回值不完整** | `yield {"id": "123"}` 不含 `name`；或仅返回 `{"name": name}` 不含业务参数 | 返回完整参数快照：`{"name": name, "type": "standard", "size": 30, ...}` |
| **静默吞异常** | `except: pass`，无任何日志 | `logger.warning(f"...")` 后重新抛出异常，记录且暴露 |
| **手动循环创建** | 测试函数中 `for i in range(3): resource_page.create(...)` | 使用 fixture 的 `count` 参数：`@pytest.mark.parametrize("resource", [{"count": 3}], indirect=True)` |
| **缺少 docstring** | fixture 函数无注释 | 编写中文 docstring，含参数、Yields/Returns |
| **scope 标注遗漏** | class scope fixture 的 docstring 首行未标注 `(scope=class)` | 首行描述末尾标注 `(scope=class)`，如 `创建后端资源（scope=class）。` |
| **teardown 依赖闭包变量** | `delete_resource(page, name)` 使用内部 `name` 变量 | `delete_resource(page, item["name"])` 使用 yield 返回值 |
| **class scope 使用 page 参数** | `def resource(page, ...)` 与 `scope="class"` 冲突 | class scope fixture 自行创建页面：`page = _create_logged_in_page(browser_context, config)` |
