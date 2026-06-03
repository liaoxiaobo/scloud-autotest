# 测试用例：流量镜像-云内实例-镜像会话生效性验证

## 基本信息

- 用例编号：407249
- 所属产品：曙光云Stack
- 一级模块：网络
- 二级模块：流量镜像

## 适配范围

### 存储适配

- 该用例不支持的存储：无

### 架构/节点限制

- 架构限制：无
- 节点要求：无

## 前置条件

1. 已预置虚拟私有云 **tm-vpc1**（网段无要求），并在其下创建弹性云服务器 **tm-vm1**（创建时名称加前缀 `tm-`）
2. 已预置虚拟私有云 **tm-vpc2**（网段无要求），并在其下创建弹性云服务器 **tm-vm2** 和 **tm-vm3**（创建时名称加前缀 `tm-`）
3. 已预置流量镜像实例 **tm-inside-test1**，类型为**云内实例**，目的实例选择 **tm-vm1**
4. 在流量镜像实例 **tm-inside-test1** 下已预置镜像会话 **tm-session**，配置如下：
   - 状态：**开启**
   - 专有网络：**tm-vpc2** 及其子网
   - 镜像源：**tm-vm2**
   - 方向：**全部流量**

> **测试数据策略**：本场景测试数据不可复用（标记为"否"），独立创建、独立清理。

## 测试步骤

### 场景1：镜像会话生效性验证-云内实例（用例407249）

> 本场景测试数据独立创建、独立清理（测试数据不可复用）

#### 步骤1：在目的实例tm-vm1上启动抓包

- 操作：使用 `ssh_vm` fixture 连接 tm-vm1 后台，启动 tcpdump 抓包并将输出保存到文件
- 子步骤：
  1. 通过 `ssh_vm.connect(tm_vm1_mfip)` 建立 SSH 连接
  2. 执行命令启动后台抓包：
     ```bash
     nohup tcpdump -i eth1 icmp -nvv -c 10 > /tmp/tcpdump_result.txt 2>&1 &
     ```
  3. 轮询等待，验证抓包进程已启动，最长等待 10 秒
- 预期：
  - SSH 连接 tm-vm1 成功
  - tcpdump 后台进程启动成功

#### 步骤2：在tm-vm3上发起流量

- 操作：使用 `ssh_vm` fixture 连接 tm-vm3 后台，向 tm-vm2 发起 ICMP 请求
- 子步骤：
  1. 通过 `ssh_vm.connect(tm_vm3_mfip)` 建立 SSH 连接
  2. 执行命令：
     ```bash
     ping -c 10 $vm2_ip
     ```
     其中 `$vm2_ip` 为弹性云服务器 tm-vm2 的 IP 地址
  3. 将命令输出记录到日志中
- 预期：
  - SSH 连接 tm-vm3 成功
  - ping 命令执行成功，可以 ping 通 tm-vm2 的 IP 地址
  - 输出显示 10 个 ICMP 请求均有回复

#### 步骤3：在tm-vm1上验证抓包结果

- 操作：使用 `ssh_vm` fixture 连接 tm-vm1 后台，读取抓包结果文件并验证
- 子步骤：
  1. 通过 `ssh_vm.connect(tm_vm1_mfip)` 建立 SSH 连接
  2. 轮询等待 `/tmp/tcpdump_result.txt` 文件内容符合预期，最长等待 60 秒
  3. 执行命令读取文件内容：
     ```bash
     cat /tmp/tcpdump_result.txt
     ```
  4. 将命令输出记录到日志中
- 预期：
  - SSH 连接 tm-vm1 成功
  - 抓包结果文件中包含 tm-vm3 发给 tm-vm2 的 ICMP 请求包（方向：tm-vm3 -> tm-vm2）
  - 抓包结果文件中包含 tm-vm2 回复 tm-vm3 的 ICMP 响应包（方向：tm-vm2 -> tm-vm3）
  - **断言**：输出中同时包含两个方向的 ICMP 流量，证明流量镜像功能生效

## ⚠️ 实现注意事项

### 1. SSH操作强制约束

- 若测试步骤或前置条件中需要 SSH 到服务器后台或虚拟机后台执行命令，**必须**调用 `sugon_web/common/ssh.py` 中封装好的公共方法
- 禁止在测试代码中直接使用 `paramiko`、`subprocess` 等方式建立 SSH 连接
- 推荐使用 fixture：
  - `ssh_vm` fixture：通过跳板机连接虚机的 SSH 会话
  - `ssh_host` fixture：直接 SSH 连接目标主机（不经过跳板机）

### 2. Fixture强制约束

- 实现测试步骤或前置条件的自动化脚本前，**必须**阅读 `sugon_web/case_specs/fixtures_index.md`
- 查阅 fixture 强制约束和速查表，确认框架中是否已有可复用的 fixture
- **禁止**针对已有的 fixture 进行重复封装

### 3. 可复用Fixture参考

根据 `fixtures_index.md`，本用例可能涉及的 fixture：

- `vpc` fixture：创建 VPC（支持 `count` 参数批量创建）
- `vm` fixture：创建虚机（支持 `count` 参数批量创建，自动绑定 MFIP）
- `tm_page` fixture：流量镜像页对象（导航到流量镜像服务）
- `ecs_page` fixture：弹性云服务器页对象（用于清理阶段删除 ECS）

### 4. 后台命令执行规范

- 所有需要后台长期运行的命令（如 tcpdump 抓包），**必须**使用 `nohup` 命令并在末尾添加 `&` 符号，避免在自动化用例执行过程中长时间占用 SSH 会话连接
- 示例：`nohup tcpdump -i eth1 icmp -nvv -c 10 > /tmp/tcpdump_result.txt 2>&1 &`

### 5. 抓包流程时序说明

- 必须先启动 tcpdump 抓包，再发起 ping 流量，否则可能抓不到包
- tcpdump 使用 `-c 10` 参数，抓到 10 个包后自动退出，因此需要轮询等待文件生成
- ping 使用 `-c 10` 参数，发送 10 个 ICMP 包后自动停止
- 验证时需断言抓包结果中同时包含请求包（Request）和响应包（Reply）两个方向的流量

### 6. 断言策略

- 抓包结果验证：通过 `ssh_vm.run()` 执行 `cat /tmp/tcpdump_result.txt`，断言输出内容：
  - 包含 "ICMP echo request" 或 "request" 字样（表示请求方向）
  - 包含 "ICMP echo reply" 或 "reply" 字样（表示响应方向）
  - 或同时包含 tm-vm3 的 IP 和 tm-vm2 的 IP 的双向流量记录

## 清理数据

### ⚠️ 清理顺序强制要求

本用例测试数据清理流程**必须**按照如下顺序执行：

1. 在流量镜像实例 **tm-inside-test1** 的镜像会话 Tab 页，删除镜像会话 **tm-session**
2. 返回流量镜像列表页，删除流量镜像实例 **tm-inside-test1**
3. 进入弹性云服务器模块，删除前置条件中准备的虚机 tm-vm1、tm-vm2、tm-vm3（注意需要从**回收站**中彻底删除）
4. 进入虚拟私有云模块，删除前置条件中准备的虚拟私有云 tm-vpc1、tm-vpc2

### 清理注意事项

- 清理顺序不可颠倒，必须严格按照上述顺序依次执行
- 如果在清理过程中某一步骤失败，需先解决该步骤的问题后再继续后续清理
- 每个清理步骤完成后应验证清理成功，再执行下一个清理步骤
- 虚机和 VPC 的清理由 fixture 的 teardown 机制自动完成，但需确保在此之前已完成镜像会话和流量镜像实例的清理
