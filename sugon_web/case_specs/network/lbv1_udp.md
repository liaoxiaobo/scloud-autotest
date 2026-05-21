# 测试用例：负载均衡V1-UDP监听器场景验证

## 基本信息

- 用例编号：4327 / 4932 / 410797 / 411010
- 所属产品：曙光云Stack
- 一级模块：网络
- 二级模块：负载均衡-基础版V1

## 适配范围

### 存储适配

- 该用例不支持的存储：无

### 架构/节点限制

- 架构限制：无
- 节点要求：无
- 说明：后端虚机执行 `/opt/network_tool/UDP_server.py`、`/opt/network_tool/UDP_client.py`，所属测试环境需预置该脚本工具集

## 前置条件

> 以下资源在多个场景中复用，共享同一套测试数据，所有场景执行完成后统一清理

1. 预置 VPC（如 `vpc1`），并在 VPC 下批量创建 4 台虚机：`ecs0`、`ecs1`、`ecs2`、`ecs3`，全部绑定 MFIP
2. 在 `vpc1` 下预置负载均衡（基础版）V1 版本实例 `slbv1`
3. UDP 监听器统一参数（按场景按需选用）：
   - 监听器名称：由 `random_data()` 生成（如 `udp_5050`）
   - 描述：`1234567890edwqWDWQ中文~`
   - 协议：`UDP`
   - 协议端口：`5050`
   - 资源池名称：由 `random_data()` 生成（如 `backend_1`）
   - 负载调度算法：`源IP`
   - 健康检查、会话保持等其它字段按场景指定
4. 测试用 UDP 工具：`/opt/network_tool/UDP_server.py`、`/opt/network_tool/UDP_client.py`（环境已预置）

## 测试步骤

### 场景1：v1-新建监听器-UDP+源IP基本功能验证（用例编号：4327）

#### 步骤1：创建UDP监听器

- 操作：在 `slbv1` 详情页 -> 监听器 tab 下，按前置条件3 参数创建 UDP 监听器（协议 `UDP`、端口 `5050`、算法 `源IP`、不开启会话保持、不开启健康检查）
- 预期：
  - 创建监听器成功并提示"新建监听器 {lb_name} 成功"
  - 左侧监听器列表存在该监听器

#### 步骤2：添加资源池成员

- 操作：进入监听器详情 -> 资源池 tab -> 资源池详情，点击"新建"按钮，选择 `ecs1`、`ecs2`、`ecs3` 作为资源池成员，对应端口为 `5050`
- 预期：
  - 提交成功
  - 资源池成员列表中 `ecs1`、`ecs2`、`ecs3` 均显示，端口 `5050`，资源状态为运行中

#### 步骤3：后端启动UDP server

- 操作：使用 `ssh_vm` fixture 分别连接 `ecs1`、`ecs2`、`ecs3` 的 MFIP，后台启动 UDP server
- 子步骤：
  1. 启动命令（使用 nohup 后台执行，避免占用 SSH 会话）：
     ```bash
     nohup python /opt/network_tool/UDP_server.py 0.0.0.0 5050 > /tmp/udp_server_5050.log 2>&1 &
     ```
  2. 轮询等待 60 秒内 5050 端口出现监听：`ss -lnup | grep ':5050 '` 或 `netstat -lnup | grep ':5050 '`
- 预期：
  - 命令执行成功
  - 60 秒内 5050 端口处于监听状态

#### 步骤4：内网VIP发送UDP消息（源IP算法）

- 操作：获取 `slbv1` 的内网 VIP，使用 `ssh_vm` 连接 `ecs0`，通过 UDP_client 向 VIP 发送多条 UDP 消息（每条带不同的内容，如 `"111"`、`"222"` 等）。命令示例：
  ```bash
  echo "111" | python /opt/network_tool/UDP_client.py $slbv1_vip 5050
  ```
- 预期：
  - 消息可正常发送
  - 通过查看 `ecs1/ecs2/ecs3` 的 server 日志，所有消息均落到同一个 Real-Server（源IP 算法效果）

#### 步骤5：绑定公网IP

- 操作：在负载均衡列表页，针对 `slbv1` 实例点击操作栏"绑定公网IP"，绑定一个公网 IP
- 预期：
  - 绑定成功
  - 列表显示绑定的公网 IP 地址

#### 步骤6：公网FIP发送UDP消息

- 操作：使用 `ssh_host` fixture 连接测试环境物理机后台，通过 UDP_client 向 `slbv1` 公网 IP 发送多条 UDP 消息：
  ```bash
  echo "aaa" | python /opt/network_tool/UDP_client.py $slbv1_fip 5050
  ```
- 预期：
  - 消息可正常发送
  - 同样所有消息均落到同一个 Real-Server（源IP 算法效果）

### 场景2：v1-健康检查器-UDP基本功能验证（用例编号：4932）

> 依赖：场景1 的预置资源（VPC、虚机、slbv1），需独立创建本场景的 UDP 监听器

#### 步骤1：后端启动UDP server

- 操作：使用 `ssh_vm` 分别连接 `ecs1`、`ecs2`、`ecs3`，后台启动 UDP server：
  ```bash
  nohup python /opt/network_tool/UDP_server.py 0.0.0.0 5050 > /tmp/udp_server_5050.log 2>&1 &
  ```
- 预期：60 秒内 5050 端口处于监听状态

#### 步骤2：创建UDP监听器（开启健康检查）

- 操作：在 `slbv1` 详情页创建 UDP 监听器，参数：协议 `UDP`、端口 `5050`、算法 `源IP`、健康检查开启、不开启会话保持
- 预期：创建监听器成功

#### 步骤3：添加资源池成员

- 操作：进入资源池详情，添加 `ecs1`、`ecs2`、`ecs3` 为成员，端口 `5050`
- 预期：成员添加成功，状态为运行中

#### 步骤4：停止ecs1、ecs2的UDP server

- 操作：使用 `ssh_vm` 分别连接 `ecs1`、`ecs2`，执行 `pkill -f 'UDP_server.py'` 停止 UDP server
- 预期：UDP server 进程已退出

#### 步骤5：确认健康状态变化

- 操作：进入资源池详情页，轮询确认各 Real-Server 状态（最长 120s）
- 预期：`ecs3` 状态为运行中，`ecs1`、`ecs2` 在 120 秒内变为离线

#### 步骤6：内网VIP发送UDP消息

- 操作：使用 `ssh_vm` 连接 `ecs0`，通过 UDP_client 向 VIP 发送消息：
  ```bash
  echo "111" | python /opt/network_tool/UDP_client.py $slbv1_vip 5050
  ```
- 预期：消息可正常发送，最终在 `ecs3` 的 server 日志中查看到消息内容

#### 步骤7：恢复ecs1、ecs2的UDP server

- 操作：使用 `ssh_vm` 分别连接 `ecs1`、`ecs2`，再次后台启动 UDP server
- 预期：服务启动成功，60 秒内端口被监听

#### 步骤8：确认全部恢复运行中

- 操作：进入资源池详情页，确认 Real-Server 状态
- 预期：`ecs1`、`ecs2` 在 120 秒内恢复为运行中，`ecs3` 仍为运行中

#### 步骤9：关闭健康检查

- 操作：在资源池详情页点击"健康检查 -> 配置"，关闭健康检查
- 预期：健康检查关闭成功

#### 步骤10：再次停止ecs1、ecs2的UDP server

- 操作：使用 `ssh_vm` 分别连接 `ecs1`、`ecs2`，执行 `pkill -f 'UDP_server.py'` 停止 UDP server
- 预期：UDP server 进程已退出

#### 步骤11：确认健康状态不受影响

- 操作：进入资源池详情页，确认各 Real-Server 状态、健康检查状态
- 预期：健康检查状态为关闭，各 Real-Server 资源状态均为运行中（停掉 UDP server 不影响其健康状态）

#### 步骤12：重新开启健康检查（类型UDP）

- 操作：进入资源池详情页 -> 健康检查 -> 配置，开启健康检查，类型选 `UDP`，健康检查请求与返回结果保持为空，其它参数保持默认
- 预期：
  - 健康检查开启成功
  - `ecs3` 的资源状态为运行中
  - `ecs1`、`ecs2` 在 120 秒内变为离线

#### 步骤13：恢复ecs1、ecs2的UDP server

- 操作：再次启动 `ecs1`、`ecs2` 的 UDP server
- 预期：服务启动成功

#### 步骤14：确认全部恢复运行中

- 操作：进入资源池详情页，确认各 Real-Server 状态
- 预期：`ecs1`、`ecs2`、`ecs3` 均为运行中

#### 步骤15：再次内网VIP发送UDP消息

- 操作：使用 `ssh_vm` 连接 `ecs0`，通过 UDP_client 向 VIP 发送多条消息
- 预期：消息可正常发送，根据源 IP 算法所有消息落到同一个 Real-Server

### 场景3：v1-访问控制-黑名单场景（内网）（用例编号：410797）

> 依赖：场景1 的预置资源（VPC、虚机、slbv1），需独立创建本场景的 UDP 监听器与 IP 地址组

#### 步骤1：预置IP地址组（包含ecs0的IP）

- 操作：进入 IP 地址组子菜单，创建 IP 地址组 `ip_group1`，成员包含 `ecs0` 的固定 IP（不是 MFIP）
- 预期：IP 地址组创建成功，列表显示 `ecs0` 的 IP

#### 步骤2：后端启动UDP server

- 操作：使用 `ssh_vm` 分别连接 `ecs2`、`ecs3`，后台启动 UDP server：
  ```bash
  nohup python /opt/network_tool/UDP_server.py 0.0.0.0 5050 > /tmp/udp_server_5050.log 2>&1 &
  ```
- 预期：60 秒内 5050 端口处于监听状态

#### 步骤3：创建UDP监听器

- 操作：在 `slbv1` 详情页创建 UDP 监听器（协议 `UDP`、端口 `5050`、算法 `源IP`，不开启健康检查/会话保持），并在资源池中添加 `ecs2`、`ecs3` 为成员，端口 `5050`
- 预期：监听器创建成功，资源池成员状态为运行中

#### 步骤4：配置访问控制（黑名单）

- 操作：在监听器详情 tab，点击访问控制的编辑按钮，配置：
  - 启用访问控制
  - 访问控制：`黑名单`
  - IP 地址组：选择 `ip_group1`
- 预期：访问控制编辑成功，详情中访问控制信息显示为"黑名单"

#### 步骤5：黑名单内客户端访问（ecs0）

- 操作：使用 `ssh_vm` 连接 `ecs0`，通过 UDP_client 向 VIP 发送消息：
  ```bash
  echo "111" | python /opt/network_tool/UDP_client.py $slbv1_vip 5050
  ```
- 预期：消息无法在 `ecs2`、`ecs3` 的 UDP server 日志中观察到（请求被拒绝）

#### 步骤6：黑名单外客户端访问（ecs1）

- 操作：使用 `ssh_vm` 连接 `ecs1`，通过 UDP_client 向 VIP 发送消息：
  ```bash
  echo "111" | python /opt/network_tool/UDP_client.py $slbv1_vip 5050
  ```
- 预期：消息可正常发送，在 `ecs2`/`ecs3` 的 server 日志中能查看到

#### 步骤7：IP地址组添加ecs1的IP

- 操作：进入 IP 地址组子菜单，在 `ip_group1` 中追加 `ecs1` 的固定 IP
- 预期：添加成功，列表显示 `ecs0`、`ecs1` 的 IP

#### 步骤8：ecs1再次访问

- 操作：使用 `ssh_vm` 连接 `ecs1`，再次通过 UDP_client 向 VIP 发送消息
- 预期：消息无法被后端收到（已加入黑名单）

#### 步骤9：IP地址组移除ecs1的IP

- 操作：在 `ip_group1` 中删除 `ecs1` 的 IP
- 预期：删除成功，列表只显示 `ecs0` 的 IP

#### 步骤10：ecs1再次访问

- 操作：使用 `ssh_vm` 连接 `ecs1`，再次通过 UDP_client 向 VIP 发送消息
- 预期：消息可被后端 `ecs2`/`ecs3` 收到

#### 步骤11：修改为允许所有IP

- 操作：在监听器详情 tab，编辑访问控制，关闭"启用访问控制"
- 预期：修改成功，访问控制信息显示"允许所有IP访问"

#### 步骤12：所有客户端访问测试

- 操作：使用 `ssh_vm` 分别连接 `ecs0`、`ecs1`，通过 UDP_client 向 VIP 发送消息
- 预期：均可正常发送，后端能收到内容

### 场景4：v1-访问控制-黑名单场景-外网LB（用例编号：411010）

> 依赖：场景1 的预置资源（VPC、虚机、slbv1），需独立创建本场景的 UDP 监听器与 IP 地址组

#### 步骤1：预置IP地址组（包含ecs0的IP）

- 操作：创建 IP 地址组 `ip_group1`，成员为 `ecs0` 的固定 IP
- 预期：IP 地址组创建成功

#### 步骤2：后端启动UDP server

- 操作：使用 `ssh_vm` 分别连接 `ecs2`、`ecs3`，后台启动 UDP server：
  ```bash
  nohup python /opt/network_tool/UDP_server.py 0.0.0.0 5050 > /tmp/udp_server_5050.log 2>&1 &
  ```
- 预期：60 秒内端口被监听

#### 步骤3：创建UDP监听器

- 操作：创建 UDP 监听器（协议 `UDP`、端口 `5050`、算法 `源IP`），添加 `ecs2`、`ecs3` 为资源池成员
- 预期：监听器创建成功，成员状态为运行中

#### 步骤4：配置访问控制（黑名单）

- 操作：在监听器详情 tab，开启访问控制，类型 `黑名单`，IP 地址组选 `ip_group1`
- 预期：访问控制编辑成功

#### 步骤5：ecs0访问（内网黑名单内）

- 操作：使用 `ssh_vm` 连接 `ecs0`，通过 UDP_client 向 VIP 发送消息
- 预期：消息无法到达后端（被拒绝）

#### 步骤6：绑定公网IP

- 操作：在负载均衡列表页（或详情 tab 中）为 `slbv1` 绑定公网 IPv4
- 预期：绑定成功，列表显示公网 IP

#### 步骤7：外网客户端访问（黑名单外）

- 操作：使用 `ssh_host` 连接测试环境物理机，通过 UDP_client 向公网 IP 发送消息：
  ```bash
  echo "111" | python /opt/network_tool/UDP_client.py $slbv1_fip 5050
  ```
- 预期：消息可正常发送，能在后端 server 日志查看到

#### 步骤8：IP地址组添加本机IP

- 操作：进入 IP 地址组子菜单，在 `ip_group1` 中追加 `ssh_host` 实际外网请求的源 IP
- 预期：添加成功

#### 步骤9：外网客户端再次访问

- 操作：使用 `ssh_host` 再次通过 UDP_client 向公网 IP 发送消息
- 预期：请求被拒绝（已加入黑名单）

## ⚠️ 实现注意事项

### 1. SSH操作强制约束

- 若测试步骤或前置条件中需要 SSH 到服务器后台或虚拟机后台执行命令，**必须**调用 `sugon_web/common/ssh.py` 中封装好的公共方法
- 禁止在测试代码中直接使用 `paramiko`、`subprocess` 等方式建立 SSH 连接
- 推荐使用 fixture：
  - `ssh_vm` fixture（`sugon_web/conftest.py`）：通过跳板机连接虚机，调用 `ssh_vm.connect("mfip")` 建立 SSH 连接，再调用 `ssh_vm.run()` 执行命令
  - `ssh_host` fixture（`sugon_web/conftest.py`）：直接 SSH 连接目标测试环境物理机

### 2. Fixture强制约束

- 实现测试步骤或前置条件前，**必须**阅读 `sugon_web/case_specs/fixtures_index.md`，查阅 fixture 强制约束和速查表
- 优先复用已有 fixture，**禁止**针对已有的 fixture 进行重复封装，重复封装会增加维护成本并可能导致用法不一致

### 3. 可复用Fixture参考

- `vpc` fixture（`testcase/network/conftest.py`）：创建 VPC，所有场景共用一个 VPC
- `vm` fixture（`testcase/conftest.py`）：批量创建虚机，使用 `count=4` 一次性创建 4 台 ECS 并自动绑定 MFIP
- `slb` fixture（`testcase/network/conftest.py`）：创建负载均衡实例，使用 `version="V1"` 创建 V1 实例
- `ssh_vm` fixture：SSH 连接虚机
- `ssh_host` fixture：SSH 连接测试环境物理机
- `clean_lb_listener` fixture（`testcase/network/_lb_fixtures.py`）：监听器、资源池、公网 IP、后端 server 的统一清理注册器
- `clean_ip_group` fixture（`testcase/network/_lb_fixtures.py`）：IP 地址组的清理注册器
- `vpc_page` fixture：VPC/SLB 等网络服务的页面对象

### 4. 后台命令执行规范

- 所有需要后台长期运行的命令（如 `UDP_server.py`），**必须**使用 `nohup` 命令并在末尾添加 `&` 符号，避免在自动化用例执行过程中长时间占用 SSH 会话连接
  - 示例：`nohup python /opt/network_tool/UDP_server.py 0.0.0.0 5050 > /tmp/udp_server_5050.log 2>&1 &`
- UDP server 启动后需轮询等待最长 60 秒，确认 5050 端口处于监听状态后再执行后续步骤
  - 检测命令：`ss -lnup | grep ':5050 '`

### 5. UDP消息发送规范

- UDP client 命令推荐通过管道发送消息内容，避免在自动化中陷入交互输入：
  - 示例：`echo "111" | python /opt/network_tool/UDP_client.py $vip 5050`
- 发送消息后需要查看 `ecs1/ecs2/ecs3` 上 UDP server 的日志（如 `/tmp/udp_server_5050.log` 或 stdout），统计各后端的接收命中分布
- 源 IP 算法判定：相同 `ssh_vm` 客户端发送的消息全部命中同一台 Real-Server（不需要严格判断哪一台，只要全部命中同一台即可）

### 6. 健康检查状态同步

- 健康检查开关切换后，Real-Server 状态变更需要时间（最长约 120 秒），通过 `wait_lb_pool_member_status` 轮询确认
- UDP 健康检查请求/返回结果保持为空时，仅校验端口可达

### 7. 外网客户端源IP识别

- 外网黑名单场景中，需识别 `ssh_host` 访问公网 IP 时的实际源 IP（路由出口 IP）
- 推荐使用 `ip route get <eip>` 推导源 IP，再回退到 `hostname -I` / `ip -4 addr show scope global` 枚举候选 IP

## 清理数据

### ⚠️ 清理顺序强制要求

按以下顺序清理（必须严格遵守，否则会删除失败）：

1. 从监听器资源池中将虚机成员（`ecs1/ecs2/ecs3`）移除
2. 删除监听器（`udp_5050`）
3. 解绑负载均衡 `slbv1` 的公网 IP（如有绑定）
4. 删除负载均衡 `slbv1`（由 `slb` fixture teardown 自动回收）
5. 删除 IP 地址组 `ip_group1`（仅场景3、4，由 `clean_ip_group` 自动回收）
6. 删除虚机 `ecs0`~`ecs3`（由 `vm` fixture teardown 自动回收）
7. 删除 VPC `vpc1`（由 `vpc` fixture teardown 自动回收）

### 清理注意事项

- 清理顺序不可颠倒
- 后端启动的 UDP server 进程需通过 `pkill -f 'UDP_server.py'` 或 `clean_lb_listener` 的 backend_server 注册机制统一清理
- 监听器与公网 IP 的清理通过 `clean_lb_listener` 注册器实现；IP 地址组通过 `clean_ip_group` 注册器实现
- VPC、虚机、SLB 实例的清理由对应 fixture 的 teardown 机制自动完成
