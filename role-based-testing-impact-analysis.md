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

实现基于用户角色的自动化测试执行能力：

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

## 二、改造方案（按当前代码已实现状态刷新）

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
│    - 核心用例（不依赖 ops）：所有角色可执行（受功能约束）     │
│    - 基础设施用例（依赖 ops）：靠 ops_page 自动切换 admin_page│
│    - admin-only 用例：需显式打 requires_admin 标记           │
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

#### A. `ops_page` fixture — 角色切换

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

#### C. `vm` fixture — MFIP 绑定

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

### 2.5 最小改动方案（MVP，当前已实现）

| 步骤 | 内容 | 状态 |
|------|------|------|
| Step 1 | 配置层增加 `user_role` + CLI 参数 | ✅ 已落地 |
| Step 2 | `vm` fixture 修改 `bind_mfip` 走 admin 上下文 | ✅ 已落地 |
| Step 3 | `pytest_collection_modifyitems` 自动跳过 `requires_admin` | ✅ 已落地 |
| Step 4 | 给 admin-only 测试文件加 `@pytest.mark.requires_admin` | ⚠️ 仅 4 处，覆盖率极低 |

### 2.6 进阶方案：公网IP fallback（未实现）

核心思路：**用公网IP替代 MFIP 做 SSH 验证**。

当前代码中未实现该 fallback。非 admin 角色下如需做 VM 的 SSH 后端验证，目前仍依赖 `vm["mfip"]` 字段；若环境 MFIP 资源不足或权限策略收紧，需后续评估是否启用公网IP方案。

---

## 三、测试用例适配清单（按当前代码现状）

分析范围：`sugon_web/testcase/` 下全部 `test_*.py` 文件
扫描维度：直接/间接依赖 ops、硬编码项目、admin-only fixture、全局运营面权限

| 问题类型 | 影响模块 | 涉及数量 |
| ------------------------------------ | ------------------------ | -------------------- |
| 直接/间接依赖 `ops_page` / `OpsPage` | compute、network | 18 个用例 |
| 硬编码 `"默认项目"` | network | 6 处 |
| 硬编码 `"公共测试"` 等其它项目名 | storage | 51 处，涉及 16 个文件 |
| admin-only fixture | compute、backup、network | 22 个用例（52 次 fixture 使用） |
| 全局运营面权限（IAM） | iam | 75 个用例 |
| **去重后总计** | **5 个模块** | **约 108**（维度间存在重叠，仅供参考） |

### 3.1 直接/间接依赖 `ops_page` / `OpsPage`

#### compute 模块（3 个用例）

| 文件 | 用例名 | 依赖方式 | 当前状态 |
| ----------------------------- | ---------------------------------- | ------------------------------------------------- | -------- |
| `test_bms_001_soft_create.py` | `test_bms_create_with_page_image` | 参数注入 `ops_page` | 已走 `ops_page` 自动切换 |
| `test_bms_011_017_cleanup.py` | `test_bms_012_register_delete` | 参数注入 `ops_page` | 已走 `ops_page` 自动切换 |
| `test_bms_011_017_cleanup.py` | `test_bms_016_switch_group_delete` | 参数注入 `ops_page` | 已走 `ops_page` 自动切换 |

> 注：`test_bms_011_instance_delete` 并不依赖 `ops_page`，仅使用 `bms_page` 和 `bms_env`，已从上表移除。

#### network 模块（15 个用例）

| 文件 | 用例名 | 依赖方式 | 当前状态 |
| -------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------- | -------- |
| `test_er_vpc_connectivity.py` | `test_er_vpc_connectivity` | 参数注入 `ops_page`，经 `_create_vm_and_bind_mfip` 调用 | 已走 `ops_page`；仍硬编码“默认项目” |
| `test_er_vpc_connectivity_non_ha.py` | `test_er_vpc_connectivity_non_ha` | 同上 | 同上 |
| `test_er_peer_connection.py` | `test_er_peer_connection_ha2ha` | 参数注入 `ops_page` | 已走 `ops_page`；仍硬编码“默认项目” |
| `test_er_peer_connection.py` | `test_er_peer_connection_noha2noha` | 参数注入 `ops_page` | 同上 |
| `test_peer_connect_routing.py` | `test_peer_connect_vpc_routing` | 参数注入 `ops_page` | 已走 `ops_page`；project 已动态化 |
| `test_tm_inner_instance_validation.py` | `test_tm_inner_instance_validation` | 参数注入 `ops_page` | 已改为 fixture 参数注入 |
| `test_tm_session_edit_validation.py` | `test_tm_session_edit_validation` | 参数注入 `ops_page` | 已改为 fixture 参数注入 |
| `test_slb_peer_connect.py` | `TestLbPeerConnectScenario::test_lb_peer_connect_scenario` | 通过 `_lb_peer_fixtures.py::lb_peer_vms` 间接引入 | 已使用 `admin_browser_context` 绑定 MFIP |
| `test_slb_peer_connect.py` | `TestSlbV1HttpPeerForwardScenario::test_http_peer_forward` | 通过 `_lb_peer_fixtures.py::lb_peer_vms` 间接引入 | 已使用 `admin_browser_context` 绑定 MFIP |
| `test_vpn_vpn_connection_vpc_effectiveness.py` | `test_vpn_vpn_connection_vpc_effectiveness` | ~~fixture 内部 `OpsPage(admin_page)`~~ → 已改为 `ops_page` fixture 注入 | 已统一注入 |
| `test_vpn_vpn_connection_er_noha_effectiveness.py` | `test_vpn_vpn_connection_er_noha_effectiveness` | ~~fixture 内部 `OpsPage(admin_page)`~~ → 已改为 `ops_page` fixture 注入 | 已统一注入 |
| `test_vpn_vpn_connection_er_ha_effectiveness.py` | `test_vpn_vpn_connection_er_ha_effectiveness` | ~~fixture 内部 `OpsPage(admin_page)`~~ → 已改为 `ops_page` fixture 注入 | 已统一注入 |
| `test_vpc_scenario.py` | `test_vpc_cross_subnet_ping` | 参数注入 `ops_page` | 已加 `@pytest.mark.requires_admin` |
| `test_vpc_scenario.py` | `test_vlan_two_vms_ping` | 参数注入 `ops_page` | 已加 `@pytest.mark.requires_admin` |
| `test_vpc_scenario.py` | `test_vlan_two_vms_ping_centralized` | 参数注入 `ops_page` | 已加 `@pytest.mark.requires_admin` |
| `test_vpc_scenario.py` | `test_dual_stack_two_vms_ping` | 参数注入 `ops_page` | 已加 `@pytest.mark.requires_admin` |

> 注：`test_slb_peer_connect.py` 实际只有 2 个测试方法（`TestSlbV2HttpPeerForwardScenario` 未再定义新的测试方法），原文档误列为 3 个。

#### 涉及的 fixture 文件

| fixture 文件 | 创建 OpsPage 的 fixture | 影响范围 | 当前状态 |
| ---------------------- | ----------------------- | ----------------------------------- | -------- |
| `_lb_peer_fixtures.py` | `lb_peer_vms` | `test_slb_peer_connect.py` 全部用例 | 已改造 |

### 3.2 硬编码项目名

#### 3.2.1 硬编码 "默认项目"（network 模块，6 处）

| 文件 | 行号 | 硬编码位置 |
| ------------------------------------ | ----- | ------------------------------------------------ |
| `test_er_vpc_connectivity.py` | 33 | `ops_page.mfip_create("默认项目", vpc_name, vm_ip)` |
| `test_er_vpc_connectivity_non_ha.py` | 33 | 同上 |
| `test_er_peer_connection.py` | 33 | `ops_page.mfip_create("默认项目", vpc_name, vm_ip)` |
| `test_vpn_vpn_connection_er_ha_effectiveness.py` | 359 | `ops_page.mfip_create(project="默认项目", ...)` |
| `test_vpn_vpn_connection_er_noha_effectiveness.py` | 360 | 同上 |
| `test_vpn_vpn_connection_vpc_effectiveness.py` | 265 | 同上 |

> 注：`test_peer_connect_routing.py`、`test_vpc_scenario.py` 已改为从 `vm_data["project"]` 动态获取 project。

#### 3.2.2 硬编码 "公共测试"（storage 模块，51 处）

除 network 模块的 `"默认项目"` 外，storage 模块（OBS 相关测试）存在大量硬编码 `"公共测试"`，共 **51 处，涉及 16 个文件**。该问题在角色化测试场景下同样会造成项目选择错误。

涉及文件（按出现次数降序）：

| 文件 | 出现次数 |
| ------------------------------------ | -------- |
| `test_obs_bucket_acl.py` | 16 |
| `test_obs_bucket_create.py` | 5 |
| `test_obs_object_acl.py` | 4 |
| `test_obs_object_acl_user_roles.py` | 3 |
| `test_obs_object_metadata_delete.py` | 3 |
| `test_obs_object_download_types.py` | 3 |
| `test_obs_credential_create.py` | 2 |
| `test_obs_bucket_quota_modify.py` | 2 |
| `test_obs_mirror_backsource.py` | 2 |
| `test_obs_object_metadata_edit.py` | 2 |
| `test_obs_object_metadata_add_existing.py` | 2 |
| `test_obs_redirect_backsource.py` | 2 |
| `test_obs_bucket_delete.py` | 2 |
| `test_obs_bucket_storage_policy.py` | 1 |
| `test_obs_proxy_add_custom_domain.py` | 1 |
| `_obs_helpers.py` | 1 |

> 注：以上统计为字符串出现次数，同一测试方法内可能出现多次；`_obs_helpers.py` 中的硬编码会影响多个用例。

### 3.3 admin-only fixture

#### pool fixture（1 个用例）

| 文件 | 用例名 | fixture | 当前状态 |
| ------------------- | -------------------------- | ------- | -------- |
| `test_ecs_basic.py` | `test_ecs_mount_bare_disk` | `pool` | 依赖 `ops_page`，间接受益于角色切换；fixture 本身无显式角色判断 |

#### bms_instance fixture（1 个用例）

| 文件 | 用例名 | fixture | 当前状态 |
| ----------------------------- | --------------------------------- | -------------- | -------- |
| `test_bms_001_soft_create.py` | `test_bms_create_with_page_image` | `bms_instance` | 依赖 `bms_page`，无角色切换逻辑 |

> 注：原文档误将 `test_bms_011_instance_delete` 列入，该方法实际仅使用 `bms_page` 和 `bms_env`，未使用 `bms_instance`。

#### vm_backup / _get_enabled_backup_nodes fixture（18 个用例）

| 文件 | 用例名 |
| ---------------------- | ------------------------------ |
| `test_back_basic.py` | `test_backup_create_scenario` |
| `test_back_basic.py` | `test_backup_once` |
| `test_back_basic.py` | `test_backup_search` |
| `test_back_basic.py` | `test_backup_task_start` |
| `test_back_basic.py` | `test_backup_edit_name` |
| `test_back_basic.py` | `test_backup_edit_vm` |
| `test_back_basic.py` | `test_backup_edit_policy` |
| `test_back_basic.py` | `test_backup_batch_operation` |
| `test_back_basic.py` | `test_backup_exec_full` |
| `test_back_basic.py` | `test_backup_reset_task` |
| `test_back_basic.py` | `test_backup_auto_migrate` |
| `test_back_basic.py` | `test_backup_manually_migrate` |
| `test_back_basic.py` | `test_resume_create_scenario` |
| `test_back_basic.py` | `test_resume_scenarios` |
| `test_back_basic.py` | `test_backup_migrate_start` |
| `test_back_recycle.py` | `test_backup_recovery` |
| `test_back_recycle.py` | `test_backup_recycle_search` |
| `test_back_recycle.py` | `test_backup_recycle_delete` |

当前状态：`vm_backup` 和 `_get_enabled_backup_nodes` 已显式判断角色并在非 admin 时 `pytest.skip()`；用例本身未打 `requires_admin`，但 fixture 层面已拦截。

#### _lb_peer_fixtures.py::lb_peer_vms fixture（2 个用例）

| 文件 | 类名 | 用例名 | 当前状态 |
| -------------------------- | ------------------------ | -------------------------- | -------- |
| `test_slb_peer_connect.py` | `TestLbPeerConnectScenario` | `test_lb_peer_connect_scenario` | 已改造为使用 `admin_browser_context` 绑定 MFIP |
| `test_slb_peer_connect.py` | `TestSlbV1HttpPeerForwardScenario` | `test_http_peer_forward` | 同上 |

> 注：`TestSlbV2HttpPeerForwardScenario` 未再定义新的测试方法，原文档误将 slb_peer 用例数计为 3。

### 3.4 全局运营面权限（IAM）

#### iam 模块（75 个用例 / 11 个文件）

涉及文件：

- `test_iam_01_org_create.py`
- `test_iam_02_org_quota.py`
- `test_iam_03_org_child.py`
- `test_iam_04_user_create.py`
- `test_iam_05_user_modify.py`
- `test_iam_06_user_admin_ops.py`
- `test_iam_07_user_access_control.py`
- `test_iam_09_org_modify.py`
- `test_iam_10_user_batch_ops.py`
- `test_iam_11_tenant_user_ops.py`
- `test_iam_12_project_management.py`

当前状态：**已在全部 19 个测试类上添加 `@pytest.mark.requires_admin` 类级标记**（覆盖 75 个用例）。非 admin 角色执行时，`pytest_collection_modifyitems` 会自动跳过整个 iam 模块。

---

## 四、用例改造进度统计（按当前代码）

### 4.1 已通过 `ops_page` fixture 改造解决

核心基础设施已完成：`ops_page` 在 `sugon_web/testcase/conftest.py:135-147` 中已实现角色切换，admin 用普通 `page`，非 admin 用 `admin_page`。

| 模块 | 已改造用例数 | 说明 |
| -------- | ------------ | ---------------------------------- |
| compute | 3 | BMS 用例通过参数注入 `ops_page` |
| network | 13 | ER/peer/tm/slb/vpc_scenario 已注入或依赖 `lb_peer_vms` |
| network | 3 | VPN 3 个用例已改为 `ops_page` fixture 注入 |

### 4.2 已添加 `@pytest.mark.requires_admin` 标记

当前全仓库共有 **23 处类/方法级标记**，覆盖 **79 个用例**：

| 文件 | 标记位置 | 覆盖用例数 |
| ----------------------------- | ---------------------- | ---------- |
| `test_vpc_scenario.py` | 4 个测试方法 | 4 |
| `test_iam_*.py`（11 个文件，19 个类） | 19 个测试类 | 75 |

`test_vpc_scenario.py` 详细标记：

| 用例名 | 行号 |
| ---------------------------------- | ----- |
| `test_vpc_cross_subnet_ping` | 52 |
| `test_vlan_two_vms_ping` | 136 |
| `test_vlan_two_vms_ping_centralized` | 285 |
| `test_dual_stack_two_vms_ping` | 386 |

### 4.3 合计状态

| 原阻塞点 | 当前状态 |
| ------------------------------------------ | ------------ |
| 阻塞点一：ops_page 依赖 / 内部创建 OpsPage | 全部 18 个用例已统一使用 `ops_page` fixture（admin 用 `page`，非 admin 用 `admin_page`） |
| 阻塞点二：硬编码项目名 | network 6 处 `"默认项目"` 残留；storage 模块 51 处 `"公共测试"` 硬编码 |
| 阻塞点三：admin-only fixture | backup fixtures 已显式 skip；pool 1 个、bms_instance 1 个、lb_peer_vms 2 个未显式处理角色 |
| 阻塞点四：iam 全局运营面权限 | 75 个用例已通过类级 `@pytest.mark.requires_admin` 标记覆盖 |

---

## 五、仍未完成的缺口与建议

### 5.1 标记体系覆盖率

- `requires_admin` 已覆盖 iam 模块全部 75 个用例（类级标记）和 network 4 个用例。
- backup / compute 中仍有 admin-only 用例未显式打 `requires_admin`，靠 fixture 内部 `pytest.skip()` 拦截。

### 5.2 硬编码项目名

- network 模块 `_create_vm_and_bind_mfip` 及 VPN fixture 中仍硬编码 `"默认项目"`，影响多项目/非默认项目环境。
- storage 模块（OBS）大量硬编码 `"公共测试"`（51 处，16 个文件），角色化或非默认项目环境下会直接选错项目。

### 5.3 VPN 用例统一注入 `ops_page`

3 个 VPN 用例已由 class-scoped fixture 内部 `OpsPage(admin_page)` 改为 function-scoped fixture 注入 `ops_page`。每个测试类仍只有一个测试方法，资源生命周期未发生实质变化。

### 5.4 建议后续行动

| 优先级 | 行动项 | 影响文件 |
|--------|--------|----------|
| P1 | 为 backup / compute 中 admin-only 用例补 `@pytest.mark.requires_admin` | `test_back_*.py`、`test_bms_*.py` 等 |
| P2 | 替换 `_create_vm_and_bind_mfip` 中 `"默认项目"` 为 `vm_data["project"]` 动态获取 | `test_er_vpc_connectivity*.py`、`test_er_peer_connection.py`、`test_vpn_*.py` |
| P3 | 治理 storage 模块硬编码 `"公共测试"`，改为从配置或当前项目动态获取 | `sugon_web/testcase/storage/test_obs_*.py`、`_obs_helpers.py` |
| P4 | 评估是否为 `pool`、`bms_instance` 等 fixture 增加显式角色判断或标记 | `sugon_web/testcase/compute/conftest.py` |
