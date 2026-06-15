# 测试用例：云堡垒机高级版USM实例-热迁移（手动指定）

## 基本信息

- 用例编号：440218
- 所属产品：曙光云Stack
- 一级模块：安全合规
- 二级模块：云堡垒机高级版USM

## 适配范围

### 存储适配

- 该用例不支持的存储：无

### 架构/节点限制

- 架构限制：无
- 节点要求：至少 2 节点（热迁移需要源节点和目标节点不同）

## 前置条件

1. 已存在云堡垒机高级版USM实例，且实例状态满足热迁移条件（服务状态=运行，虚拟机状态=运行）
2. 环境至少存在 2 个可用物理机节点

## 测试步骤

### 场景1：USM实例热迁移-手动指定（用例440218）

#### 步骤1：进入USM列表页

- 操作：进入资源中心-安全-云堡垒机高级版USM页面
- 预期：进入堡垒机页面成功，列表可正常显示

#### 步骤2：记录USM实例物理机节点

- 操作：在USM列表页，获取目标实例的物理机字段值
- 预期：成功获取当前实例所在的物理机节点名称

#### 步骤3：进入实例详情页记录ID

- 操作：点击实例名称进入实例详情页，记录云堡垒机ID（serverId字段）
- 预期：详情页正常显示，成功获取云堡垒机ID

#### 步骤4：返回列表页执行热迁移

- 操作：返回列表页，选择该实例，点击"更多操作"-"热迁移"
- 子步骤：
  1. 在热迁移弹窗中，选择调度方式为"手动指定"
  2. 点击"选择物理机"，在物理机选择弹窗中选择一个非当前节点的可用物理机
  3. 迁移速率选择"全速"
  4. 点击确定
- 预期：
  - 热迁移弹窗正常打开，实例名称和原物理机置灰不可修改
  - 弹窗关闭后提示"热迁移成功"
  - 列表页该虚拟机状态显示"迁移中"，服务状态显示"不可用"

#### 步骤5：等待迁移完成并验证页面状态

- 操作：等待1-2分钟后刷新页面，查看USM实例状态
- 预期：
  - 列表页该USM实例物理机字段显示与迁移的目标物理机一致
  - 虚拟机状态显示"运行"，服务状态显示"运行"

#### 步骤6：SSH连接源物理机后台验证

- 操作：使用 `ssh_host` fixture 连接步骤2记录的源物理机后台，执行以下命令
- 子步骤：
  1. `sudo su -`
  2. `docker exec -it nova_libvirt /bin/bash`
  3. `virsh list`
  4. `virsh list | grep <虚机UUID前三段>`（虚机UUID可在列表页面名称字段查看）
- 预期：
  - 切换到root用户成功
  - 进入nova_libvirt容器成功
  - 可以查看到该节点上所有虚机的UUID
  - `virsh list | grep` 无返回匹配的UUID（说明虚拟机已不在源节点）

#### 步骤7：SSH连接目标物理机后台验证

- 操作：使用 `ssh_host` fixture 连接迁移后的目标物理机后台，执行以下命令
- 子步骤：
  1. `sudo su -`
  2. `docker exec -it nova_libvirt /bin/bash`
  3. `virsh list`
  4. `virsh list | grep <虚机UUID前三段>`
- 预期：
  - 切换到root用户成功
  - 进入nova_libvirt容器成功
  - 可以查看到该节点上所有虚机的UUID
  - `virsh list | grep` 返回匹配的UUID（说明虚拟机已在目标节点）

## ⚠️ 实现注意事项

### 1. SSH操作强制约束

- 若测试步骤或前置条件中需要SSH到服务器后台执行命令，**必须**调用 `sugon_web/common/ssh.py` 中封装好的公共方法
- 禁止在测试代码中直接使用 `paramiko`、`subprocess` 等方式建立SSH连接
- 推荐使用 `ssh_host` fixture：直接SSH连接目标主机（不经过跳板机）
- 本用例需要SSH连接源物理机和目标物理机两个节点后台执行virsh命令

### 2. Fixture强制约束

- 实现测试步骤或前置条件的自动化脚本前，**必须**阅读 `sugon_web/case_specs/fixtures_index.md`
- 查阅fixture强制约束和速查表，确认框架中是否已有可复用的fixture
- **禁止**针对已有的fixture进行重复封装

### 3. 可复用Fixture参考

根据 `fixtures_index.md`，本用例可能涉及的fixture：

- `usm_instance` fixture（session级）：创建USM实例并自动清理。通过 `usm_instance["name"]` 获取实例名，通过 `usm_instance["row_data"]` 获取行数据
- `usm_page` fixture（function级）：初始化云堡垒机高级版USM页对象，导航到USM服务
- `ssh_host` fixture（session级）：直接SSH连接测试环境物理机节点，用于执行virsh后台验证命令
- `check_compute_nodes` fixture（session级，autouse=True）：自动检查物理机节点信息，用于 `@skip_if_nodes_less_than(2)` 装饰器

### 4. 节点限制处理

- 本用例需要至少2个物理机节点，测试类或方法需添加 `@skip_if_nodes_less_than(2)` 装饰器
- 若环境节点不足，测试应自动跳过

### 5. 热迁移页面对象方法

- 需要在 `UsmPage` 页面对象中新增 `usm_hot_migration` 方法，支持手动指定目标物理机
- 参考 `ecs_hot_migration` 方法的实现逻辑
- 热迁移操作流程：点击更多操作 → 热迁移 → 选择手动指定 → 选择物理机 → 设置迁移速率 → 确认

### 6. 物理机选择弹窗处理

- 物理机选择弹窗为 `el-drawer` 组件，标题"选择物理机"
- 需要在可用物理机列表中选择一个非当前节点的物理机
- 排除disabled状态的物理机行

### 7. 迁移状态等待策略

- 热迁移命令下发后，虚拟机状态会先变为"迁移中"，服务状态变为"不可用"
- 需要轮询等待迁移完成，直至虚拟机状态和服务状态都恢复为"运行"
- 设置最长等待时长为 180 秒

### 8. 后台命令执行规范

- virsh命令在容器内执行，需要先 `sudo su -` 再 `docker exec -it nova_libvirt /bin/bash`
- 获取虚机UUID：可从列表页名称字段查看（server_id字段的前三段格式）

### 9. USM实例复用说明

- **本用例使用 `usm_instance` fixture 提供的USM实例**
- 测试脚本中通过 `usm_instance["name"]` 获取实例名称作为测试目标
- 实例的清理由 `usm_instance` fixture 的 teardown 机制自动完成

## 清理数据

- 本用例不创建新资源，USM实例由 `usm_instance` fixture 的 teardown 机制自动删除
- 热迁移操作完成后虚拟机保持在目标节点，无需手动迁移回源节点
