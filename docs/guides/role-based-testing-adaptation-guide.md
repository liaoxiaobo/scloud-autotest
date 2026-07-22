# 用例适配开发指南：支持普通用户执行

> 适用对象：各模块测试负责人
> 目标：依据本文档即可上手完成用例适配，最大化用例复用，让同一套用例既能 admin 执行、也能普通用户（user）执行。
> 配套文档：`role-based-testing-impact-analysis.md`（框架改造方案与现状分析）

---

## 0. 先理解一件事：框架已就绪，你只需要给用例"分类"

角色化能力在**框架层（配置 / 标记 / Fixture）已全部落地**，你**不需要改任何框架代码**。

- 切换执行角色：命令行加 `--user-role=user`（或 `dept_admin` / `admin`），不传则用 `base.yaml` 的默认值。
- 需要 admin 权限的基础设施操作（平台网络/MFIP、物理机、裸磁盘、存储池、备份节点、交换机组），框架已通过 `ops_page` / `ops_page_class` / `admin_browser_context` 自动切到 admin 上下文完成，**普通用户执行时这些操作会自动借用 admin 能力**。

所以你的工作只有一件：**把自己负责模块的每一个用例，对照下面的决策树归类，并做对应的最小处理。**

> ⚠️ 重要：请对模块内**每个测试类 / 测试方法**都走一遍下面的判断。

---

## 1. 决策树：每个用例只需回答两个问题

```
对每个测试类 / 测试方法：

  问题 A：这个用例的「测试点 / 功能按钮交互」普通用户能不能做？
  │
  ├─ 不能（仅 admin 有该功能/按钮/菜单）
  │     → 【情况一】直接打 @pytest.mark.requires_admin  （见 §2）
  │
  └─ 能
        │
        问题 B：普通用户登录态下的页面交互，与 admin 是否基本一致？
        │
        ├─ 基本一致（元素、流程相同）
        │     → 【情况二】无需改造，框架已支持。用 --user-role 验证一遍即可（见 §3）
        │
        └─ 差异很大（布局/入口/字段/步骤明显不同，现有用例点不动）
              → 【情况三】先打 requires_admin 占位，后续再评估改造/新建（见 §4）
```

判断口径补充：
- 「测试点支持普通用户」指的是**业务权限**上普通用户被允许做这件事，而不仅仅是代码上没调用 `/ops`。
- 一个用例代码里**用到了 `/ops` 基础设施操作 ≠ 仅 admin 可执行**。只要这些操作是通过 `ops_page` / `vm` fixture 走的，框架会自动用 admin 上下文兜底，普通用户照样能跑——这类用例属于【情况二】。

---

## 2. 情况一：用例测试点 / 按钮不支持普通用户 → 打 `requires_admin`

适用：组织/用户/项目/配额等全局运营面操作、仅 admin 可见的菜单或按钮、业务上明确只有 admin 能执行的功能。

非 admin 角色执行时，`pytest_collection_modifyitems`（`sugon_web/conftest.py`）会在收集阶段**自动跳过**这些用例，不会误报失败。

### 2.1 代码示例

**① 整个测试类都仅 admin 可执行（最常见）—— 打在类上**

标签放在 allure 装饰器**之后**、`class` 定义**之前**：

```python
import pytest
import allure


@allure.epic('身份认证IAM')
@allure.feature('组织管理-组织结构树')
@allure.story('创建组织')
@pytest.mark.requires_admin          # ← 类级标记，类内所有方法都会被非 admin 角色跳过
class TestIamOrgCreate:

    @allure.title("IAM-组织管理-创建组织并验证")
    def test_iam_create_org(self, iam_page, iam_shared_org):
        ...
```

**② 类里只有个别方法仅 admin 可执行 —— 打在方法上**

```python
class TestEcsBasic:

    @pytest.mark.requires_admin       # ← 方法级标记，只跳过这一个方法
    @allure.title("ECS-挂载裸磁盘")
    def test_ecs_mount_bare_disk(self, ecs_page, pool):
        ...

    @allure.title("ECS-基础生命周期")  # 这个方法不带标记，普通用户照常执行
    def test_ecs_operations(self, ecs_page, vm):
        ...
```

### 2.2 AI 问答示例（可直接复制给 Claude Code）

> 在仓库根目录对 Claude Code 这样提问，让它帮你判断并改：

**示例提问 A（你已确认结论，让 AI 只执行标记）：**

```
 帮我在如下的用例上加 @pytest.mark.requires_admin 标签
  1、云硬盘-转换为镜像
  2、集群详情-节点规格缩容
```

**示例提问 B（拿不准时，先让 AI 给依据再决定）：**

```
逐个列出 sugon_web/testcase/storage/ 下每个测试方法的核心测试点，
并告诉我哪些操作普通用户在产品上没有权限/没有入口，给出判断依据，
先不要改代码，等我确认后再标记 @pytest.mark.requires_admin。
```

---

## 3. 情况二：用例测试点支持普通用户 → 无需改造，只需验证

这是我们**追求的主路径**：用例代码一行都不用动，框架自动支持普通用户执行。你要做的是**用 `--user-role` 跑一遍确认它真的能过**。

### 3.1 本地验证（推荐先本地跑）

```bash
# 用普通用户角色执行你的模块（举例：存储模块）
pytest sugon_web/testcase/storage/ --user-role=user

# 用部门管理员角色执行单个文件
pytest sugon_web/testcase/network/test_vpc_basic.py --user-role=dept_admin

# 指定到单个用例，便于快速定位
pytest sugon_web/testcase/compute/test_ecs_basic.py::TestECSBasic::test_ecs_operations --user-role=user

# 有头模式观察普通用户实际页面（排查交互差异时很有用）
pytest sugon_web/testcase/storage/test_evs_basic.py --user-role=user --headless=false
```

> 角色对应的账号/密码/项目在 `sugon_web/config/base.yaml` 的 `users` 段配置（admin / dept_admin / user）。如需对接你环境里的真实账号，改这里即可。

### 3.2 验证通过的判定

- 用例在 `--user-role=user`（及 `dept_admin`）下结果与 `--user-role=admin` 一致（同为 pass）。
- 若某用例仅在普通用户下失败：先判断是**情况一漏标**（其实不支持）还是**情况三页面差异**，分别按 §2 / §4 处理。

---

## 4. 情况三：支持普通用户但页面交互差异大 → 先占位，后评估

适用：业务上普通用户**应当**能做，但其登录态页面的**布局/入口/字段/步骤**与 admin 差异明显，导致现有用例（按 admin 页面写的元素/流程）在普通用户下点不动。

这类属于**极少数个例**，不要强行改造，建议按以下两步走：

**第一步：先打 `requires_admin` 占位**（写法同 §2）

并在标记处用注释留痕，方便后续认领：

```python
# TODO(role): 普通用户页面交互与 admin 差异大（XXX 入口/字段不同），
#             待评估改造现有用例或单独开发普通用户用例。
@pytest.mark.requires_admin
class TestXxx:
    ...
```

**第二步：后续专项评估**，二选一：

- **改造现有用例**：用 `Config.get("user_role")` 在用例/Page 内做差异化分支（仅当差异小、可收敛时）；
- **单独开发新用例**：为普通用户视角新建用例（差异大、强行复用反而更脆时优先选这个）。

> 推广阶段：先把情况三都用 requires_admin 兜住，把情况二的"零改造可复用"用例最大化跑通，是性价比最高的路径。

---

## 5. 验收标准（必须满足）

> **一句话：在 Jenkins 上，分别用 admin 和普通用户（user / dept_admin）执行，得到的测试结果完全一致。**

### 5.1 Jenkins 执行方式

构建页选择 **`USER_ROLE`**（`admin` / `dept_admin` / `user`），流水线会自动拼接 `--user-role=${USER_ROLE}` 执行。

验收操作：
1. 用 `USER_ROLE=admin` 触发一次构建，记录结果（通过/跳过清单）。
2. 用 `USER_ROLE=user`（及按需 `dept_admin`）再触发构建。
3. 对比两次 Allure 报告：
   - 普通用户的"跳过"应**恰好等于**你打了 `requires_admin` 的集合；
   - 其余应执行的用例结果与 admin 完全一致。

### 5.2 自查清单（提交前过一遍）

- [ ] 模块内**每个**测试类/方法都已对照决策树归类，没有遗漏。
- [ ] 情况一/三：已加 `@pytest.mark.requires_admin`（类级或方法级），位置正确（allure 之后、class/def 之前）。
- [ ] 情况二：本地 `--user-role=user` 跑通，结果与 admin 一致。
- [ ] 没有改动任何框架文件（`sugon_web/conftest.py`、`sugon_web/testcase/conftest.py`、Fixture/Page 公共能力）。
- [ ] Jenkins 上 admin 与普通用户两次构建结果一致，差异仅来自 `requires_admin` 跳过。



---

## 6. 常见疑问（FAQ）

**Q1：我的用例里用到了 MFIP 绑定 / 存储池 / 备份节点这些 `/ops` 操作，是不是必须打 requires_admin？**
不一定。只要这些操作是通过 `ops_page`、`ops_page_class` 或 `vm` fixture 走的，框架会自动用 admin 上下文兜底，普通用户能正常跑——属于【情况二】。只有当**测试点本身**（你要断言/验证的功能）仅 admin 可见时，才打 `requires_admin`。

**Q2：`requires_admin` 打在类上还是方法上？**
整类都仅 admin → 打类上；只有个别方法 → 打方法上。优先精确到最小范围，让能复用的用例尽量复用。

**Q3：普通用户跑出来某个用例失败，但我觉得它应该支持，怎么办？**
先有头模式 `--user-role=user --headless=false` 观察普通用户实际页面：若功能根本没入口 → 情况一（漏标）；若有入口但元素/流程不同 → 情况三（先占位再评估）。

**Q4：会不会需要我改 conftest 或 Page Object？**
**不会**。情况二零改造、情况一/三只加标签。若你发现必须改框架能力才能复用，说明是情况三里需要专项评估的个例，先占位、单独提出来讨论，不要直接改公共能力。
