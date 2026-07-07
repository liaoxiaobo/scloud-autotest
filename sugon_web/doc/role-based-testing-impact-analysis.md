# 基于用户角色的自动化测试影响分析与改造方案

> 分析日期：2026-06-24
> 分析范围：计算 (compute)、网络 (network)、存储 (storage)、备份 (backup)、IAM 模块
> 核心问题：非 admin 用户（部门管理员、普通用户）无法访问根 URL 为 `/ops` 的基础设施服务
> 对齐版本：当前工作树 `feature/role-based-testing` 分支

---

## 一、背景与目标

### 1.1 现状

当前自动化测试默认使用 `admin / keystone_sugon` 登录（`sugon_web/config/base.yaml`）。所有测试用例、fixture、page object 均围绕 admin 权限设计。

### 1.2 目标

实现基于用户角色的自动化测试执行能力，提高自动化用例的覆盖率：

- **部门管理员** (dept_admin)：可执行大部分计算/网络/存储用例
- **普通用户** (user)：可执行基础功能用例
- **admin**：全量执行

核心诉求：**用例复用、改动成本尽量小**。

### 1.3 已知约束

只有 `admin` 有权访问根 URL 为 `/ops` 的**基础设施**服务，包括：

- 平台网络（MFIP 管理）
- 物理机设备 / 裸磁盘
- 存储池
- 备份节点
- 交换机组

---

## 二、框架改造方案

### 2.1 方案总览

```
┌─────────────────────────────────────────────────────────────┐
│                    用户角色化测试架构                         │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 配置层                                             │
│    - Config 增加 user_role (admin/dept_admin/user)          │
│    - CLI 增加 --user-role 参数                               │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 标记层                                             │
│    - 已注册 @pytest.mark.requires_admin                      │
│    - pytest_collection_modifyitems 自动跳过                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Fixture 层                                         │
│    - vm: bind_mfip 走 admin_browser_context + MfipHelper     │
│    - ops_page: 区分角色，admin 用 page，非 admin 用 admin_page│
│    - admin_browser_context / admin_page: session/function 级 │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: 用例层                                             │
│    - 不依赖 ops 的用例：所有角色可执行，无需改造         │
│    - 依赖 ops 的用例：通过 fixture 参数统一注入       │
│      ops_page，由 fixture 自动按角色切换 page/admin_page      │
│    - admin-only 用例：无法自动切换解决，显式打                 │
│      @pytest.mark.requires_admin，收集阶段自动跳过             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 配置层改造（已落地）

**`sugon_web/config/base.yaml`：**

```yaml
# 默认测试用户角色 (admin/dept_admin/user)
user_role: admin

# 各角色登录凭据（按角色固化配置）
users:
  admin:
    username: admin
    password: keystone_sugon
  dept_admin:
    username: sugoncloud
    password: Sugon@12345
    project: "公共测试"
  user:
    username: autotest-user
    password: Sugon@12345
    project: "公共测试"
```

**`sugon_web/conftest.py` 的 `pytest_addoption`：**

```python
def pytest_addoption(parser):
    """添加命令行参数支持"""
    parser.addoption("--user-role", action="store", default=None,
                     help="指定测试用户角色 (admin/dept_admin/user)，未指定时使用 base.yaml 中的 user_role")
```

**`sugon_web/config/config.py` 的 `Config.override`：**

```python
@classmethod
def override(cls, browser=None, headless=None, stor=None, user_role=None):
    if user_role is not None:
        valid_roles = ["admin", "dept_admin", "user"]
        if user_role not in valid_roles:
            raise ValueError(f"无效的用户角色: {user_role}。支持的选项: {valid_roles}")
        cfg["user_role"] = user_role
```

### 2.3 标记层改造（`requires_admin` 已落地）

```ini
# pytest.ini
markers =
    ...
    requires_admin: 需要admin权限（仅admin可执行）
```

**收集阶段自动跳过：**

```python
# sugon_web/conftest.py::pytest_collection_modifyitems
def pytest_collection_modifyitems(config, items):
    # ... BMS 排序逻辑省略 ...

    user_role = config.getoption("--user-role")
    if user_role is None:
        Config.load(host=config.getoption("--host"))
        user_role = Config.get("user_role", "admin")
    if user_role != "admin":
        skip_marker = pytest.mark.skip(
            reason=f"当前用例仅支持 admin 执行，暂未适配测试用户角色 '{user_role}'"
        )
        for item in items:
            if item.get_closest_marker("requires_admin"):
                item.add_marker(skip_marker)
```

### 2.4 Fixture 层改造（已落地）

#### A. `ops_page` fixture — 实现自动角色切换

```python
# sugon_web/testcase/conftest.py:135-147
@pytest.fixture(scope="function")
def ops_page(request):
    """初始化运维管理页对象。

    admin 角色直接使用当前 page；非 admin 角色自动切换为 admin_page，
    以支持普通用户执行测试时用 admin 权限操作基础设施服务。
    """
    user_role = Config.get("user_role", "admin")
    if user_role == "admin":
        page = request.getfixturevalue("page")
    else:
        page = request.getfixturevalue("admin_page")
    return OpsPage(page)
```

#### B. `admin_browser_context` / `admin_page` fixture

```python
# sugon_web/conftest.py:396-488
@pytest.fixture(scope="session")
def admin_browser_context(browser, config):
    """Session 级 admin 浏览器上下文，用于普通用户角色执行测试时复用 admin 登录态。"""
    ...

@pytest.fixture(scope="function")
def admin_page(admin_browser_context, config):
    """Function 级 admin page，从 admin_browser_context 创建新 page。"""
    ...
```

#### C. `vm` fixture — MFIP 绑定走admin上下文

`vm` fixture 默认 `bind_mfip=True`，绑定逻辑走 `admin_browser_context`，不依赖当前测试用户角色：

```python
# sugon_web/testcase/conftest.py:308-331
if instance_config.get("bind_mfip", True):
    _bind_vm_fixture_mfips(admin_browser_context, config, current_metadata)

if bind_mfip:
    _bind_vm_fixture_mfips(admin_browser_context, config, metadata_list)
```

`_bind_vm_fixture_mfips` 调用 `sugon_web/common/mfip_helper.py` 中的 `MfipHelper`，通过 API 方式完成绑定。

#### D. `lb_peer_vms` fixture

已显式声明 `admin_browser_context` 参数用于 MFIP 绑定，VM 创建仍使用普通 `browser_context`：

```python
# sugon_web/testcase/network/_lb_peer_fixtures.py
@pytest.fixture(scope="class")
def lb_peer_vms(browser_context, admin_browser_context, config, vpc, ssh_host, request):
    ...
    _bind_vm_fixture_mfips(admin_browser_context, config, metadata_list)
```

#### E. `ops_page_class` fixture — 供 class-scoped fixture 使用

新增 class 级 `ops_page_class`，用于 `vm_backup` 等 class-scoped fixture 访问基础设施服务：

```python
# sugon_web/testcase/conftest.py
@pytest.fixture(scope="class")
def ops_page_class(browser_context, admin_browser_context, config):
    """Class 级运维管理页对象。"""
    user_role = Config.get("user_role", "admin")
    if user_role == "admin":
        page = _create_logged_in_page(browser_context, config)
    else:
        page = _create_admin_logged_in_page(admin_browser_context, config)

    try:
        yield OpsPage(page)
    finally:
        page.close()
```

backup 模块的 `vm_backup` 已改为注入 `ops_page_class`，非 admin 角色时自动使用 admin page 访问备份节点。

#### F. 仍依赖 admin 上下文的 fixture（遗留问题）

部分 fixture 本身依赖 admin 上下文，但未显式进行角色判断或标记 `requires_admin`，在角色化测试中仍存在隐患：

| fixture | 影响用例 | 当前状态 |
| ------- | -------- | -------- |
| `pool` | `test_ecs_basic.py::test_ecs_mount_bare_disk` | 依赖 `ops_page`，间接受益于角色切换；fixture 本身无显式角色判断 |
| `bms_instance` | `test_bms_001_soft_create.py::test_bms_create_with_page_image` | 依赖 `bms_page`，无角色切换逻辑 |
| `lb_peer_vms` | `test_slb_peer_connect.py` 2 个用例 | 已改造为使用 `admin_browser_context` 绑定 MFIP，但 fixture 仍依赖 admin 能力 |

> 注：原文档误将 `test_bms_011_instance_delete` 列入 `bms_instance` 影响范围，该方法实际仅使用 `bms_page` 和 `bms_env`，未使用 `bms_instance`。

`vm_backup` / `_get_enabled_backup_nodes` 已通过 `ops_page_class` 完成改造，backup 模块 18 个用例已统计在 第三章 B 节。

## 三、用例层改造方案

用例层按对 `/ops` 基础设施服务的依赖程度，分为三类采用不同改造策略：

### A. 不依赖 ops 的用例 —— 无需改造

覆盖 compute、network、storage 等模块中不依赖平台网络 / 物理机 / 裸磁盘 / 存储池 / 备份节点 / 交换机组的用例。此类用例在 `dept_admin` / `user` 角色下可直接执行，无需改动。

> **重要说明：**「无需改造」仅表示用例代码层面不依赖 `/ops` 基础设施服务，不等同于该用例在所有角色下均可执行。具体是否支持 `dept_admin` / `user`，仍需测试人员结合业务权限判断；若业务上仅 admin 可执行，应移至 C 类并显式标记 `@pytest.mark.requires_admin`。

典型范围：

- ECS 基础生命周期（创建、启停、重启、删除）
- VPC / 子网 / 安全组 / 路由表基础 CRUD
- EVS 磁盘生命周期
- SLB 监听器与后端服务器管理

### B. 依赖 ops 的用例 —— 统一注入 `ops_page`

对依赖 `ops_page` / `OpsPage` 的用例，统一改为通过 fixture 参数注入 `ops_page`（function 级）或 `ops_page_class`（class 级）。fixture 内部按角色自动选择 page：

- `admin` 角色：使用当前测试 `page`
- 非 admin 角色：自动切换为 `admin_page`

已按此方式完成改造的用例如下：

| 模块 | 文件 | 用例名称 | 当前状态 |
| ---- | ---- | -------- | -------- |
| compute | `test_bms_001_soft_create.py` | `test_bms_create_with_page_image` | 已改造 |
| compute | `test_bms_011_017_cleanup.py` | `test_bms_012_register_delete`、`test_bms_016_switch_group_delete` | 已改造 |
| network | `test_er_vpc_connectivity.py` | `test_er_vpc_connectivity` | 已改造（仍硬编码“默认项目”） |
| network | `test_er_vpc_connectivity_non_ha.py` | `test_er_vpc_connectivity_non_ha` | 已改造（仍硬编码“默认项目”） |
| network | `test_er_peer_connection.py` | `test_er_peer_connection_ha2ha`、`test_er_peer_connection_noha2noha` | 已改造（仍硬编码“默认项目”） |
| network | `test_peer_connect_routing.py` | `test_peer_connect_vpc_routing` | 已改造 |
| network | `test_tm_inner_instance_validation.py` | `test_tm_inner_instance_validation` | 已改造 |
| network | `test_tm_session_edit_validation.py` | `test_tm_session_edit_validation` | 已改造 |
| network | `test_slb_peer_connect.py` | `test_lb_peer_connect_scenario`、`test_http_peer_forward` | 已改造 |
| network | `test_vpn_vpn_connection_vpc_effectiveness.py` | `test_vpn_vpn_connection_vpc_effectiveness` | 已改造 |
| network | `test_vpn_vpn_connection_er_noha_effectiveness.py` | `test_vpn_vpn_connection_er_noha_effectiveness` | 已改造 |
| network | `test_vpn_vpn_connection_er_ha_effectiveness.py` | `test_vpn_vpn_connection_er_ha_effectiveness` | 已改造 |
| network | `test_vpc_scenario.py` | `test_vpc_cross_subnet_ping`、`test_vlan_two_vms_ping`、`test_vlan_two_vms_ping_centralized`、`test_dual_stack_two_vms_ping` | 已改造 |
| backup | `test_back_basic.py` | 全部 15 个用例 | 已改造（通过 `ops_page_class` 自动切换） |
| backup | `test_back_recycle.py` | `test_backup_recovery`、`test_backup_recycle_search`、`test_backup_recycle_delete` | 已改造（通过 `ops_page_class` 自动切换） |

### C. admin-only 用例 —— 显式标记 `requires_admin`

对无法通过 `ops_page` 自动切换解决、或业务上仅 admin 可执行的用例，在测试类或方法上添加 `@pytest.mark.requires_admin`。非 admin 角色执行时，`pytest_collection_modifyitems` 会自动跳过。

典型场景：

- **IAM 模块**：组织 / 用户 / 项目 / 配额等全局运营面操作

当前覆盖情况：

| 模块 | 标记位置 | 覆盖用例数 | 标记原因 |
| ---- | -------- | ---------- | -------- |
| iam | 11 个文件、19 个测试类 | 75 | 组织 / 用户 / 项目 / 配额等全局运营面操作，仅 admin 可执行 |

### D. 数据适配问题 —— 硬编码项目名

除上述三类角色化改造问题外，用例层还存在因硬编码项目名导致的数据适配问题。部分 network 模块用例在调用 `ops_page.mfip_create` 时固定写入 `"默认项目"`，当测试角色所属项目非默认项目时，MFIP 绑定会失败。

当前残留位置（6 处）：

| 文件 | 行号 | 硬编码位置 |
| ---- | ---- | ---------- |
| `test_er_vpc_connectivity.py` | 33 | `ops_page.mfip_create("默认项目", vpc_name, vm_ip)` |
| `test_er_vpc_connectivity_non_ha.py` | 33 | 同上 |
| `test_er_peer_connection.py` | 33 | `ops_page.mfip_create("默认项目", vpc_name, vm_ip)` |
| `test_vpn_vpn_connection_er_ha_effectiveness.py` | 359 | `ops_page.mfip_create(project="默认项目", ...)` |
| `test_vpn_vpn_connection_er_noha_effectiveness.py` | 360 | 同上 |
| `test_vpn_vpn_connection_vpc_effectiveness.py` | 265 | 同上 |

处理建议：将 `"默认项目"` 替换为从 `vm_data["project"]` 或 ECS 行数据中动态获取的项目名称。`test_peer_connect_routing.py`、`test_vpc_scenario.py` 已按此方式完成动态化。

---

## 四、仍未完成的缺口与建议

### 4.1 标记体系覆盖率

- `requires_admin` 已覆盖 iam 模块全部 75 个用例（类级标记）。
- compute 中 `pool`、`bms_instance` 仍依赖 admin 上下文，未显式打 `requires_admin`。

### 4.2 硬编码项目名

- network 模块 `_create_vm_and_bind_mfip` 及 VPN fixture 中仍硬编码 `"默认项目"`，影响多项目/非默认项目环境。

### 4.3 建议后续行动

| 优先级 | 行动项 | 影响文件 |
|--------|--------|----------|
| P1 | 为 compute 中依赖 admin 上下文的用例补 `@pytest.mark.requires_admin` 或增加显式角色处理 | `test_bms_*.py`、`test_ecs_basic.py` 等 |
| P2 | 替换 `_create_vm_and_bind_mfip` 中 `"默认项目"` 为 `vm_data["project"]` 动态获取 | `test_er_vpc_connectivity*.py`、`test_er_peer_connection.py`、`test_vpn_*.py` |
| P4 | 评估是否为 `pool`、`bms_instance` 等 fixture 增加显式角色判断或标记 | `sugon_web/testcase/compute/conftest.py` |
