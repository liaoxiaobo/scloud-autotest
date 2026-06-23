# 基于用户角色的自动化测试改造实战经验总结

> 项目：SugonCloud Web UI 自动化测试框架（Python + Playwright + Pytest）
> 改造范围：计算 / 网络 / 存储 / 备份模块
> 核心挑战：非 admin 用户无法访问 `/ops` 基础设施服务

---

## 一、背景与目标

### 1.1 现状

- 框架所有测试默认以 `admin / keystone_sugon` 执行。
- 用例、fixture、page object 全部围绕 admin 权限设计。
- `/ops` 根 URL 下的基础设施服务（平台网络、物理机设备、存储池、备份节点、交换机组）仅 admin 可访问。

### 1.2 目标

实现基于用户角色的测试执行能力：

| 角色 | 说明 | 可执行范围 |
|------|------|-----------|
| `admin` | 管理员 | 全量 |
| `dept_admin` | 部门管理员 | 大部分计算/网络/存储用例 |
| `user` | 普通用户 | 基础功能用例 |

核心诉求：**用例复用、改动成本尽量小**。

---

## 二、整体方案

采用四层改造架构：

```
┌─────────────────────────────────────────────┐
│ Layer 1: 配置层                              │
│   - Config 增加 user_role                    │
│   - CLI 增加 --user-role 参数                 │
├─────────────────────────────────────────────┤
│ Layer 2: 标记层                              │
│   - 新增 @pytest.mark.requires_admin         │
│   - pytest_collection_modifyitems 自动跳过   │
├─────────────────────────────────────────────┤
│ Layer 3: Fixture 层                          │
│   - ops_page: 非 admin 自动 skip             │
│   - vm_backup: 非 admin 提前 skip            │
├─────────────────────────────────────────────┤
│ Layer 4: 用例层                              │
│   - 直接依赖 /ops 的测试类/方法加标记        │
│   - 当前以 test_vpc_scenario.py 为示例       │
│   - 支持类级或方法级粒度                     │
└─────────────────────────────────────────────┘
```

---

## 三、关键实现细节

### 3.1 配置层：角色与凭据的固化配置

```yaml
# sugon_web/config/base.yaml
user_role: user

users:
  admin:
    username: admin
    password: keystone_sugon
  dept_admin:
    username: sugoncloud
    password: sugoncloud
  user:
    username: ""      # 后续补充普通用户账号
    password: ""      # 后续补充普通用户密码
```

```python
# sugon_web/conftest.py
def pytest_addoption(parser):
    # 只保留 --user-role，不再提供 --username/--password
    parser.addoption(
        "--user-role",
        action="store",
        default=None,
        help="指定测试用户角色 (admin/dept_admin/user)，未指定时使用 base.yaml 中的 user_role"
    )
```

```python
# sugon_web/conftest.py::config fixture
Config.load(host=host)
Config.override(browser=browser_type, headless=headless, stor=stor, user_role=user_role)

# 根据角色从 users 读取登录凭据
resolved_role = Config.get("user_role", "admin")
role_cfg = Config.get("users", {}).get(resolved_role, {})
Config.set("username", role_cfg.get("username", ""))
Config.set("password", role_cfg.get("password", ""))
```

```python
# sugon_web/config/config.py
@classmethod
def override(cls, browser=None, headless=None, stor=None, user_role=None):
    # 已移除 username/password 参数，登录凭据统一由 users 配置管理
    ...
```

**关键点**：
- `users` 结构按角色组织，新增角色只需加节点。
- `MfipHelper` 固定读取 `users.admin`，确保非 admin 测试用户执行时，MFIP 绑定仍使用 admin 上下文。

### 3.2 标记层：收集阶段自动跳过

```python
# sugon_web/conftest.py
def pytest_collection_modifyitems(config, items):
    user_role = config.getoption("--user-role")
    if user_role is None:
        # 关键：collection 阶段 Config 未加载，需手动加载 base.yaml
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

### 3.3 Fixture 层：双重保护

**ops_page fixture（运行时兜底）**：

```python
@pytest.fixture(scope="function")
def ops_page(page):
    user_role = Config.get("user_role", "admin")
    if user_role != "admin":
        pytest.skip("当前用例仅支持 admin 执行，暂未适配测试用户角色 '{user_role}'")
    return OpsPage(page)
```

**vm_backup fixture（提前跳过）**：

```python
@pytest.fixture(scope="class")
def vm_backup(..., config, ...):
    user_role = config.get("user_role", "admin")
    if user_role != "admin":
        pytest.skip("当前用例仅支持 admin 执行，暂未适配测试用户角色 '{user_role}'")
    # 后续 VM 创建逻辑不会执行
```

### 3.4 用例层：以 `test_vpc_scenario.py` 为示例

当前只在 `test_vpc_scenario.py` 中保留 `requires_admin` 标记作为示例，其余直接依赖 `/ops` 的用例暂未批量标记，后续可根据需要逐步补充。

**类级标记示例**（整类都依赖 ops）：

```python
@pytest.mark.requires_admin
@allure.epic("计算")
class TestBmsSoftCreate:
    ...
```

**方法级标记示例**（`test_vpc_scenario.py` 实际采用的粒度）：

```python
class TestVPCNetwork:
    @pytest.mark.requires_admin
    def test_vpc_cross_subnet_ping(self, vm, ecs_page, ops_page, ssh_vm):
        ...

    def test_vpc_two_vms_ping(self, vm, ssh_vm):
        # 非 admin 也可执行
        ...
```

**说明**：未标记但直接依赖 `ops_page` 的用例，仍会通过 `ops_page` fixture 的运行时保护自动跳过；只是跳过时机比 collection 阶段稍晚。

---

## 四、踩坑实录

### 坑 1：CLI 默认值覆盖 base.yaml

**现象**：把 `base.yaml` 的 `user_role` 改成 `user` 后，测试还是按 admin 执行。

**根因**：`parser.addoption("--user-role", default="admin")` 导致即使不传参，pytest 也返回 `"admin"`，进而通过 `Config.override()` 覆盖 base.yaml。

**修复**：把 `--user-role` 的 CLI 默认值改为 `None`，并在 `pytest_collection_modifyitems` 中手动加载 base.yaml 读取默认角色。

### 坑 1.5：登录凭据与 admin 凭据混淆

**现象**：`dept_admin` 角色下运行依赖 MFIP 的用例时，MFIP 绑定失败（admin 登录失败）。

**根因**：旧实现把 `config.get("password")` 同时当作测试用户密码和 admin 密码。当 `user_role=dept_admin` 时，`password` 是 `sugoncloud`，而 MFIP 绑定需要 admin 密码 `keystone_sugon`。

**修复**：引入 `users` 结构化配置，测试登录读取 `users.<role>`，MFIP 绑定固定读取 `users.admin`，彻底分离两种凭据。

### 坑 2：pytest_collection_modifyitems 阶段 Config 未加载

**现象**：去掉 `--user-role` 后，`requires_admin` 用例仍然不跳过。

**根因**：`pytest_collection_modifyitems` 在 `config` fixture 之前运行，此时 `Config.load()` 还没执行，`Config.get("user_role", "admin")` 只能返回默认值 `"admin"`。

**修复**：在 `pytest_collection_modifyitems` 中手动调用 `Config.load(host)` 读取 base.yaml。

### 坑 3：类级标记误伤非 admin 用例

**现象**：`TestVPCNetwork` 类加 `@pytest.mark.requires_admin` 后，类内所有方法都被跳过。

**根因**：pytest 类级 marker 会传播给所有方法。

**修复**：对该类改为方法级标记，只给真正使用 `ops_page` 的 4 个方法加标记。

### 坑 4：backup fixture 先创建 VM 再跳过

**现象**：非 admin 下 backup 用例虽然最终 skip，但已经创建了 VM。

**根因**：`vm_backup` fixture 先创建 VM，后调用 `_get_enabled_backup_nodes()` 才触发 skip。

**修复**：在 `vm_backup` fixture 开头就加角色检查，避免资源浪费。

### 坑 5：控制台中文乱码

**现象**：skip 原因在控制台显示为乱码。

**结论**：本地终端编码问题，不影响实际 skip 行为和 Allure 报告中的中文显示。

---

## 五、应用到的知识点

### 5.1 pytest hook 机制

- `pytest_addoption`：注册 CLI 参数。
- `pytest_collection_modifyitems`：在测试收集完成后、执行前修改测试项（如添加 skip marker）。
- 执行顺序：`pytest_addoption` → `pytest_collection_modifyitems` → fixture setup → test call。

### 5.2 pytest marker 传播

- 类级 `@pytest.mark.xxx` 会自动传播给类下所有方法。
- 方法级 marker 只影响单个方法。
- `item.get_closest_marker("xxx")` 可以获取最近一层（方法 > 类 > 模块）的 marker。

### 5.3 fixture 执行顺序与 skip 时机

- `pytest.skip()` 在 fixture setup 中调用时，会跳过整个测试，但已经执行过的前置 fixture 不会回滚。
- 提前 skip（collection 阶段）可以避免执行任何 fixture。
- fixture 间执行顺序由依赖关系决定，而非函数签名顺序。

### 5.4 配置系统的三层合并

- `base.yaml` → `env.yaml` → CLI 参数。
- `Config.override()` 用于 CLI 注入。
- 注意 CLI 默认值会覆盖配置文件，敏感配置项应谨慎设置 default。

### 5.5 Playwright admin context 隔离

- `vm` fixture 的 MFIP 绑定通过 `MfipHelper._create_admin_page()` 在独立 admin browser context 完成。
- 这样非 admin 测试用户页面不需要访问 `/ops`，也能获得 MFIP 用于 SSH 验证。
- 这是最大化用例复用的关键。

### 5.6 git 工作流

- 基于 `develop` 创建 `feature/role-based-testing` 分支。
- 使用 `git commit --amend` 持续整合小修复，保持提交历史清晰。
- 注意区分哪些 untracked 文件不应进入提交。

---

## 六、验证方法

### 6.1 检查 marker 注册

```powershell
pytest --markers | grep requires_admin
```

### 6.2 默认 user 角色下跳过 admin 用例（以示例文件验证）

```powershell
pytest sugon_web/testcase/network/test_vpc_scenario.py -v -k "test_vpc_cross_subnet_ping"
```

### 6.3 显式指定 admin 执行

```powershell
pytest sugon_web/testcase/network/test_vpc_scenario.py --user-role=admin -v
```

### 6.4 非 ops 用例不被误跳过

```powershell
pytest sugon_web/testcase/compute/test_ecs_basic.py --collect-only -q --no-header
```

### 6.5 检查配置生效

观察日志中 `测试配置加载完成: {..., 'user_role': 'user', ...}`。

---

## 七、后续优化方向

1. **公网 IP fallback 替代 MFIP**
   - 非 admin 场景下，若环境有公网 IP 池，可通过 `ecs_bind_pub_ip` 获取可 SSH IP，恢复后端验证覆盖率。

2. **project 参数化**
   - 当前大量硬编码 `"默认项目"`，不同角色可见项目不同，需参数化 project。

3. **更细粒度的角色权限**
   - 区分 `dept_admin` 和 `user` 的跳过范围，当前统一按 admin 阈值处理。

4. **admin-context ops_page fixture**
   - 若某些测试需要非 admin 用户身份但又要操作基础设施，可提供独立的 admin-context `ops_page`。

5. **按角色生成测试报告**
   - Allure 报告中自动标注当前执行角色，便于区分不同角色的覆盖情况。

---

## 八、核心结论

1. **最小改动 MVP 可行**：通过配置 + 标记 + fixture 保护三层机制，用较小成本实现了角色化测试。
2. **提前跳过是关键**：仅靠 fixture 保护会浪费资源，collection 阶段 marker 跳过能避免前置 fixture 执行。
3. **CLI 默认值要谨慎**：带默认值的 CLI 参数会覆盖配置文件，需要根据场景选择 default。
4. **Config 加载时机要关注**：pytest hook 和 fixture 执行顺序不同，跨阶段读取配置需确认 Config 已加载。
5. **MFIP admin context 是杠杆点**：让大量非 admin 用例无需改造即可继续运行，是本次改造最重要的发现。
