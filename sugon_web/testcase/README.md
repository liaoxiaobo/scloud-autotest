# 测试用例目录放置规则

本文用于约束 `sugon_web/testcase` 目录内 Page Object、fixture、scenario helper 和测试代码的落位方式，避免后续把不同职责的代码继续堆到 `conftest.py`、页面对象或测试类中。

## 目标

- 让 `conftest.py` 只承载真正的模块公共 fixture 能力
- 让业务场景复用逻辑有明确归属，不和资源创建 fixture 混在一起
- 让测试文件保留必要的可读性，不因过度抽象而增加理解成本
- 让新增代码在目录、命名和职责上都有统一判断标准

## 四层职责

各业务模块内代码按以下四层组织：

1. `Page Object`
   - 只放页面元素和页面动作
   - 不放场景编排
   - 不放资源生命周期
   - 不放测试断言流程

2. `fixture`
   - 只放资源生命周期和可复用的 setup/teardown
   - 负责创建、绑定、清理、恢复
   - 不承载大段业务场景判断

3. `scenario helper`
   - 放业务环境组装、角色分配、拓扑整理、复用型前置动作
   - 不需要 fixture 语义时，不要硬写成 fixture
   - 不直接承担测试步骤表达

4. `test class`
   - 只保留测试步骤、断言、少量局部变量组织
   - 不写大段环境拼装
   - 不写通用资源创建

## 硬约束

后续新增代码时，默认遵守以下硬约束：

1. 不在 `Page Object` 中写场景级编排逻辑。
2. 不在 `conftest.py` 中写纯业务场景 helper。
3. 不把"只是环境组装"的逻辑写成 fixture。
4. 不把不依赖 `self` 的 helper 写成测试类方法。
5. 测试类中不新增跨用例复用的辅助逻辑。
6. 只在确实需要 `yield`、scope、自动清理时才新增 fixture。
7. 只在跨文件复用且无 fixture 语义时才新增 `_xxx_helpers.py`。

## 当前目录分层

结合当前实现，各业务模块目录应形成三类位置：

1. `conftest.py`
   - 放模块公共 fixture
   - 典型例子：`vpc`、`eip`、`sg`、`acl`、`slb`、`vm_sg_binding`（network 模块）
   - 典型例子：`ecs`、`vm`、`image`（compute 模块）

2. `_xxx_fixtures.py`
   - 放仅服务于某类业务场景、但又需要被多文件复用的 fixture 或业务辅助函数
   - 典型例子：`_acl_fixtures.py`（network 模块）
   - 典型例子：`_ecs_fixtures.py`（compute 模块）

3. `test_*.py`
   - 放测试类、测试步骤，以及只在当前文件使用的私有 helper
   - 典型例子：`test_acl_basic.py` 中的 `_build_acl_pair_env`、`test_acl_scenario.py` 中的 `_build_acl_env`

## 目录落位规范

各业务模块目录内新增逻辑时，按以下目录落位：

### 1. 页面对象层

页面对象代码放在 `sugon_web/pages/` 对应模块文件中。

适合放入页面对象的内容：

- 页面元素定位
- 表单填写
- 列表操作
- 页面导航
- 单个业务动作的页面实现

不适合放入页面对象的内容：

- "准备两台虚机并分配角色 A/B"
- "如果 ACL 关联子网后再补齐规则"
- "根据多个 fixture 返回值组装测试环境"

### 2. fixture 层

目录位置：

- `sugon_web/testcase/<module>/conftest.py`
- `sugon_web/testcase/<module>/_xxx_fixtures.py`

放置原则：

- 模块公共、跨多个业务域通用的 fixture，放 `conftest.py`
- 某个业务域专用、但跨文件复用的 fixture，放 `_xxx_fixtures.py`

具体约束：

- `conftest.py` 只放模块公共 fixture
- `_xxx_fixtures.py` 只放单一业务域的场景 fixture
- `_xxx_fixtures.py` 不做模块级 re-export
- 测试文件显式导入 `_xxx_fixtures.py`

### 3. scenario helper 层

目录位置：

- 当前文件私有：直接放对应 `test_*.py`
- 跨文件复用：新增 `_xxx_helpers.py`

放置原则：

- 文件内独占使用：放测试文件顶部，作为模块级私有函数
- 同一业务域复用：放 `_xxx_helpers.py`
- 不写成测试类方法，除非它必须依赖实例状态

### 4. test 层

目录位置：

- `test_*.py`

放置原则：

- 保留测试步骤表达
- 保留断言
- 保留少量当前用例临时变量
- 不承载通用 helper 仓库角色

## 放置规则

### 1. `conftest.py` 放什么

只放"模块范围内普遍可复用"的 pytest fixture 和其配套的通用内部函数。

允许放入 `conftest.py` 的内容：

- 页面对象 fixture，如 `vpc_page`、`sg_page`、`acl_page`、`ecs_page`
- 资源生命周期 fixture，如 `vpc`、`eip`、`sg`、`acl`、`slb`、`ecs`、`volume`
- 通用编排型 fixture，但前提是职责仍然清晰且可跨多个测试文件复用
  - 例如：`vm_sg_binding` 这类"组合已有资源并负责 teardown"的 fixture
  - 注意：跨多个业务域共用的组合 fixture，因无法归属单一 `_xxx_fixtures.py`，允许放 `conftest.py`
- 只服务于上述 fixture 的内部函数
  - 例如参数构建、批量创建、统一清理、参数引用解析

不应继续放入 `conftest.py` 的内容：

- 仅服务于某一个业务域的场景拼装逻辑
- 不带资源生命周期、只是为了让测试步骤更顺一点的业务 helper
- 某个复杂场景专用的前置/后置操作，且只会被少数场景文件使用

### 2. `_xxx_fixtures.py` 放什么

当一段逻辑具备以下特征时，放到 `_xxx_fixtures.py`，不要塞进 `conftest.py`：

- 明显带有业务场景语义，而不是通用资源创建
- 需要 `yield` 前后置处理，或者需要独立 teardown
- 会被多个测试文件复用
- 复用范围还没有大到值得进入模块级 `conftest.py`

适合放在 `_xxx_fixtures.py` 的例子：

- ACL 规则清理 fixture
- 某类场景专用的"补齐默认规则 / 恢复环境 / 构造规则基线" fixture
- 某类业务域的复用型 setup/teardown 封装

文件命名规则：

- 按业务域拆分，如 `_acl_fixtures.py`、`_sg_fixtures.py`、`_ecs_fixtures.py`、`_volume_fixtures.py`
- 一个文件只承载一个相对聚焦的业务域，避免再出现"大而全"的辅助文件

导入方式：

- 在测试文件中显式 `from ... import ...`
- 不通过 `conftest.py` 做二次转发

### 3. `_xxx_helpers.py` 或测试文件私有函数放什么

不具备 fixture 生命周期语义的逻辑，不要硬抽成 fixture。

优先放 helper 的场景：

- 只是组装测试环境描述数据
- 只是对已有 fixture 返回值做标准化、打标签、筛选、映射
- 只是把多个步骤前要重复执行的小段业务动作提炼出来
- 不需要 teardown
- 不依赖 `request`、`yield`、fixture scope

规则如下：

- 只在当前测试文件使用：直接放在该 `test_*.py` 内，使用私有函数 `_build_xxx`、`_prepare_xxx`
- 被同一业务域下多个测试文件复用：新建 `_xxx_helpers.py`

当前对应先例：

- `_build_acl_pair_env`
- `_build_acl_env`
- `ensure_sg_ingress_allow_all`

其中 `ensure_sg_ingress_allow_all` 目前放在 `_acl_fixtures.py` 中是可接受的，但从职责上看它更偏 helper；后续若 ACL/SG 相关辅助函数增多，优先把这类"纯业务动作但无 teardown"的逻辑沉到 `_acl_helpers.py`。

### 3.1 测试类里不放什么

以下内容不要放到测试类内部作为方法：

- `_build_xxx_env`
- `_prepare_xxx_topology`
- `_tag_xxx_roles`
- `_normalize_xxx_data`

原因：

- 它们通常不依赖 `self`
- 它们本质上不是测试对象状态
- 写成类方法后，不利于后续平移到 `_xxx_helpers.py`
- 会让测试类从"步骤容器"变成"杂项工具类"

推荐方式：

- 当前文件使用：模块级私有函数
- 跨文件复用：`_xxx_helpers.py`

### 4. 页面对象放什么

页面对象仍然只负责页面交互和业务动作封装，不负责：

- fixture 编排
- 场景步骤组织
- 测试数据分组
- 断言结果解释

如果一段逻辑本质上是在"操作页面"，应优先补到 page object；如果本质上是在"组织测试上下文"，不要放到 page object。

### 5. 测试文件里保留什么

以下内容应当保留在测试文件中，不必强行上提：

- 只在单文件使用的环境组装函数
- 强依赖当前测试标题和步骤语义的动作
- 读取后仅服务于本文件断言的派生数据

判断原则：

- 抽出去后如果不能明显降低重复，反而让读者来回跳文件，就不要抽

## 命名规范

### 1. 文件命名

- 模块公共 fixture：`conftest.py`
- 业务域 fixture：`_acl_fixtures.py`、`_sg_fixtures.py`、`_ecs_fixtures.py`、`_volume_fixtures.py`
- 业务域 helper：`_acl_helpers.py`、`_sg_helpers.py`、`_ecs_helpers.py`、`_volume_helpers.py`
- 测试文件：`test_xxx_basic.py`、`test_xxx_scenario.py`

约束：

- `_xxx_fixtures.py` 和 `_xxx_helpers.py` 必须按业务域命名，不使用 `_common.py`、`_utils.py` 这类模糊命名
- 一个文件只承载一个聚焦业务域

### 2. fixture 命名

命名原则：

- 资源 fixture 用资源名词
- 组合 fixture 用"结果名"或"绑定结果"
- 清理 fixture 用 `clean_` 前缀
- 场景基线 fixture 用 `baseline_` 或业务名词短语

示例：

- `vpc`、`sg`、`acl`、`slb`、`ecs`、`volume`
- `vm_sg_binding`
- `clean_acl_inbound_rules`
- `acl_rule_baseline`

避免：

- `do_acl`
- `handle_sg`
- `common_fixture`

### 3. helper 命名

命名原则：

- helper 一律使用动词短语
- 文件私有 helper 使用前导下划线
- 跨文件 helper 不使用前导下划线，除非明确只供模块内部使用

示例：

- `_build_acl_env`
- `_tag_vms_by_subnet`
- `_prepare_sg_rule_inputs`
- `build_acl_env`
- `prepare_nat_topology`

避免：

- `_acl`
- `_data`
- `_helper`

### 4. 测试类命名

- 基础功能：`TestAclBasic`、`TestSGBasic`、`TestEcsBasic`
- 场景验证：`TestAclScenario`、`TestSGScenario`、`TestEcsScenario`
- 特定专题：`TestSlbLbRoundRobin`、`TestEcsAffinity`

约束：

- 类名表达"测试主题"，不表达"实现细节"
- 不把 helper 语义写进测试类名

### 5. 测试方法命名

- 保持当前仓库的 `test_xxx` 风格
- 名称表达业务场景，不表达内部编排实现

示例：

- `test_acl_associate_subnet_acl`
- `test_sg_vm_binding_connectivity`
- `test_ecs_create_with_volume`

避免：

- `test_acl_with_build_env_helper`
- `test_sg_use_private_method`

## 决策表

新增一段复用逻辑时，按以下顺序判断：

| 问题 | 是 | 否 |
| --- | --- | --- |
| 是否是已有资源 fixture 的参数化能力？ | 继续复用现有 fixture | 进入下一问 |
| 是否负责资源创建/绑定/清理的完整生命周期？ | 放 `conftest.py` 或 `_xxx_fixtures.py` | 进入下一问 |
| 是否需要 `yield` 或 teardown？ | 放 `_xxx_fixtures.py` | 进入下一问 |
| 是否仅是额外业务处理/环境组装？ | 放 helper，不抽 fixture | 进入下一问 |
| 是否只在一个测试文件使用？ | 放当前 `test_*.py` 私有函数 | 放 `_xxx_helpers.py` |

## 判断流程

新增逻辑时，严格按下面流程判断落位：

1. 这段逻辑是不是页面交互本身？
   - 是：放 `Page Object`
   - 否：继续下一步

2. 这段逻辑是不是资源创建、绑定、清理、恢复？
   - 是：按 fixture 处理
   - 否：继续下一步

3. 这段逻辑是否需要 `yield`、scope、自动 teardown？
   - 是：放 fixture
   - 否：继续下一步

4. 这段逻辑是否只是环境组装、角色分配、拓扑整理、前置补齐？
   - 是：放 scenario helper
   - 否：继续下一步

5. 这段逻辑只在当前测试文件用吗？
   - 是：放当前 `test_*.py` 顶部模块级私有函数
   - 否：放 `_xxx_helpers.py`

6. 这段逻辑是否被多个业务域共用？
   - 是：优先重新审视是否应该下沉到 page object 或模块公共 fixture
   - 否：保持在业务域 helper / fixture 文件内

## 判断口径

为了避免分层失真，统一按以下口径判断：

- "创建一个资源并清理"是 fixture
- "把两个已有资源绑定起来并负责解绑"是 fixture
- "把已有资源按角色 A/B/C 重新整理成测试上下文"是 helper
- "补齐某个场景缺失的默认规则，但不负责回收"是 helper
- "点按钮、填表单、读取表格"是 Page Object
- "写步骤、写断言、表达预期"是 test class

## 各模块落地约束

后续在各业务模块目录新增代码时，遵守以下约束：

1. 不在 `conftest.py` 新增"纯业务场景 helper"。
2. 新增业务场景 fixture 时，优先新建 `_xxx_fixtures.py`，不要继续堆到 `conftest.py`。
3. 新增无 teardown 的业务复用逻辑时，优先考虑 `_xxx_helpers.py` 或测试文件私有函数。
4. 如果逻辑只被 1 个文件使用，默认留在该测试文件内，且写成模块级私有函数，不写成测试类方法。
5. 只有在"跨多个测试文件复用"且"确实需要 fixture 语义"时，才新增业务 fixture。
6. 如果只是对现有资源 fixture 的结果做角色分配、拓扑标记、字段整理，一律视为 helper，不新增 fixture。
7. 如果新增文件，优先使用 `_xxx_fixtures.py` / `_xxx_helpers.py` 的业务域命名，不新增模糊职责文件。

## 推荐命名

- 资源 fixture：`vpc`、`sg`、`acl`、`slb`、`ecs`、`volume`、`snapshot`
- 组合 fixture：`vm_sg_binding`、`acl_rule_baseline`、`ecs_volume_binding`
- 清理 fixture：`clean_acl_inbound_rules`、`clean_snapshot_chain`
- 业务 helper：`build_acl_env`、`prepare_sg_rules`、`tag_vms_by_subnet`、`build_ecs_env`

约定：

- fixture 名称使用业务名词或"动作结果"
- helper 名称使用动词短语
- 私有 helper 统一使用前导下划线

## 一句话原则

资源生命周期进 fixture，场景拼装进 helper，模块公共能力留在 `conftest.py`，业务域复用能力拆到 `_xxx_fixtures.py` / `_xxx_helpers.py`。