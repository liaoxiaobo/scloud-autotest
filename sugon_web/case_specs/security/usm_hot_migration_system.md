# 测试用例：云堡垒机高级版USM-热迁移-系统分配验证

## 基本信息

- 用例编号：440219
- 所属产品：曙光云Stack
- 一级模块：安全合规
- 二级模块：云堡垒机高级版USM

## 适配范围

### 存储适配

- 该用例不支持的存储：无

### 架构/节点限制

- 架构限制：无
- 节点要求：至少 2 节点

## 前置条件

1. 测试环境已配置可创建USM实例的集群
2. 已存在一台可用的云堡垒机USM实例（由 session 级 `usm_instance` fixture 自动创建，与同模块其他 USM 测试共享）
3. USM 实例状态：服务状态为"运行"，虚拟机状态为"运行"
4. **本资源在多个场景中复用**

## 测试步骤

### 场景1：USM热迁移-系统分配（用例440219）

> 依赖：无（使用 fixture 提供的共享 USM 实例）

#### 步骤1：进入USM列表页并记录当前物理机节点

- 操作：进入资源中心-安全-云堡垒机高级版USM页面，记录该USM实例物理机字段显示的节点
- 预期：进入堡垒机页面成功，顶部导航栏标题显示"云堡垒机高级版USM"，记录当前USM实例所在节点

#### 步骤2：进入实例详情页记录云堡垒机ID

- 操作：点击实例名称进入实例详情页，记录当前页面云堡垒机的id
- 预期：记录该云堡垒机id号（server_id）

#### 步骤3：执行热迁移（系统分配模式）

- 操作：返回列表页，选择云堡垒机实例，操作：更多-热迁移
- 子步骤：
  1. 选择"系统分配"调度方式
  2. 迁移速率选择"全速"
  3. 点击确定
- 预期：
  - 弹窗关闭，提示"热迁移成功"
  - 列表页该虚拟机状态显示"迁移中"，服务状态显示"不可用"

#### 步骤4：等待迁移完成并验证页面状态

- 操作：等待1-2分钟，刷新页面查看该USM实例状态
- 预期：
  - 列表页该USM实例物理机字段显示与迁移的目标物理机一致
  - 虚拟机状态显示"运行"
  - 服务状态显示"运行"

#### 步骤5：SSH连接源物理机后台验证虚拟机已迁出

- 操作：使用 `ssh_host` fixture 连接步骤1记录的源物理机节点后台
- 子步骤：
  1. `ssh_host.run(f"ssh -o StrictHostKeyChecking=no {source_host_short} 'docker exec -i nova_libvirt virsh list'")`
  2. `ssh_host.run(f"ssh -o StrictHostKeyChecking=no {source_host_short} 'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'")`
- 预期：
  - virsh list 可以查看该节点上所有虚机的UUID
  - virsh list | grep 无返回匹配的UUID（虚拟机已迁出）

#### 步骤6：SSH连接目标物理机后台验证虚拟机已迁入

- 操作：使用 `ssh_host` fixture 连接迁移后的目标物理机后台
- 子步骤：
  1. `ssh_host.run(f"ssh -o StrictHostKeyChecking=no {target_host_short} 'docker exec -i nova_libvirt virsh list'")`
  2. `ssh_host.run(f"ssh -o StrictHostKeyChecking=no {target_host_short} 'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'")`
- 预期：
  - virsh list 可以查看该节点上所有虚机的UUID
  - virsh list | grep 返回匹配的UUID（虚拟机已迁入）

## ⚠️ 实现注意事项

### 1. SSH操作强制约束

- 若测试步骤或前置条件中需要SSH到服务器后台或虚拟机后台执行命令，**必须**调用 `sugon_web/common/ssh.py` 中封装好的公共方法
- 禁止在测试代码中直接使用 `paramiko`、`subprocess` 等方式建立SSH连接
- 推荐使用fixture：
  - `ssh_host` fixture：直接SSH连接目标主机（不经过跳板机）

### 2. Fixture强制约束

- 实现测试步骤或前置条件的自动化脚本前，**必须**阅读 `sugon_web/case_specs/fixtures_index.md`
- 查阅fixture强制约束和速查表，确认框架中是否已有可复用的fixture
- **禁止**针对已有的fixture进行重复封装

### 3. 可复用Fixture参考

根据 `fixtures_index.md`，本用例可能涉及的fixture：

- `usm_instance` fixture：session级USM实例（自动创建和清理，与现有USM测试共享）
- `usm_page` fixture：云堡垒机高级版USM页对象
- `ssh_host` fixture：直接SSH连接目标主机，用于执行 `docker exec` 和 `virsh` 命令

### 4. 后台命令执行规范

- 所有需要后台长期运行的命令，**必须**使用 `nohup` 命令并在末尾添加 `&` 符号
- 示例：`nohup <command> > /dev/null 2>&1 &`

### 5. 系统分配与手动指定的区别

- 系统分配模式下，目标物理机由平台自动选择，测试脚本需在迁移完成后从列表页读取实际迁移的目标物理机
- 系统分配模式下，`usm_hot_migration` 方法返回 `None`（无手动选择的目标物理机）
- 与现有 `test_usm_hot_migration_manual`（手动指定）的主要区别：
  - m_type 参数：`"系统分配"` vs `"手动指定"`
  - 目标物理机未知，需要迁移完成后从页面回读
  - 不执行 `assert target_host != source_host`（系统分配可能分配到同一节点）

### 6. SSH命令执行规范

- 由于 Windows 测试机无法直接解析内网节点域名，SSH 命令必须使用 `ssh_host.run(f"ssh -o StrictHostKeyChecking=no {host_short} 'cmd'")` 方式中转执行
- 物理机节点名称从列表页"物理机"字段获取，取 `.` 前的短名称部分
- server_id 从详情页 URL 获取，取 UUID 前三段用于 virsh grep 匹配

## 清理数据

### ⚠️ 清理顺序强制要求

本用例的测试数据清理流程**必须**按照如下顺序执行：

1. 无需额外清理（USM实例由 session 级 `usm_instance` fixture teardown 自动完成）

### 清理注意事项

- USM实例的清理由 session 级 fixture 的 teardown 机制自动完成
- 本用例标记为"测试数据不可复用"，但使用 `usm_instance` fixture 共享实例，不影响清理策略
