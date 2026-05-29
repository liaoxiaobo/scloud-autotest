# 测试用例：负载均衡-对等连接-跨VPC正向基本功能验证

## 基本信息

- 用例编号：418861
- 所属产品：曙光云Stack
- 一级模块：网络
- 二级模块：负载均衡（基础版V2） / 对等连接

## 适配范围

### 存储适配

- 该用例不支持的存储：无

### 架构/节点限制

- 架构限制：无
- 节点要求：无

## 前置条件

> 以下资源全部共享同一套测试数据，所有场景执行完成后统一清理

1. 预置 2 个 VPC：`vpc1`、`vpc2`，两 VPC 的 CIDR 必须不重叠
2. 在 `vpc1` 下创建 2 台虚机：`ecs1-1`、`ecs1-2`（均绑定 MFIP，作为同 VPC 资源池后端 / 客户端使用）
3. 在 `vpc2` 下创建 2 台虚机：`ecs2-1`、`ecs2-2`（均绑定 MFIP，`ecs2-1` 用于跨 VPC 后端，`ecs2-2` 用于跨 VPC 客户端）
4. 在 `vpc1` 下预置负载均衡（基础版）V2 实例 `slbv2`
5. 监听器与资源池统一参数：
   - 监听器名称：由 `random_data()` 生成（业务含义：`tcp_8080`）
   - 描述：`1234567890edwqWDWQ中文~`
   - 协议：`TCP`
   - 协议端口：`8080`
   - 资源池名称：由 `random_data()` 生成（业务含义：`backend_1`）
   - 负载调度算法：`轮询`
   - 健康检查：`开启`，其它字段保持默认值（不开启会话保持等）
6. 后端 HTTP 服务：每台后端虚机在 `/root/test/index.html` 写入标识 `this is ecsX`，并通过 `nohup` 后台启动 `python3 -m http.server 8080`，轮询等待 60 秒确认端口处于监听状态

## 测试步骤

### 场景1：对等连接生效前后跨VPC负载均衡可达性验证（用例编号：418861）

#### 步骤1：创建TCP监听器与资源池（同VPC后端）

- 操作：在 `slbv2` 详情页 -> 监听器 tab，按前置条件5 参数创建 TCP 监听器，进入资源池详情后点击"新建"，选择 `ecs1-1`、`ecs1-2` 为资源池成员，对应端口为 `8080`
- 预期：
  - 监听器创建成功并提示"新建监听器 {lb_name} 成功"
  - 资源池成员列表中 `ecs1-1`、`ecs1-2` 显示，端口 `8080`，资源状态为运行中

#### 步骤2：尝试添加跨VPC虚机至资源池（对等连接前应不可见）

- 操作：在资源池详情页再次点击"新建"按钮，弹窗内尝试搜索/勾选 `ecs2-1` 作为 Real-Server
- 预期：
  - 资源选择列表中不出现 `ecs2-1`（不同 VPC 且未建立对等连接，跨 VPC 资源不可选）
  - 可读取的可选资源列表中不包含 `ecs2-1`

#### 步骤3：跨VPC客户端通过VIP访问负载均衡（对等连接前应失败）

- 操作：使用 `ssh_vm` 连接 `ecs2-2` 的 MFIP，向 `slbv2` 的内网 VIP 发起 HTTP 请求：
  ```bash
  curl -s --connect-timeout 10 http://<slbv2_vip>:8080/index.html
  ```
- 预期：
  - 请求超时或返回失败（rc 非 0 或 stdout 为空）
  - `ecs1-1`、`ecs1-2` 的 server 日志中观察不到来自 `ecs2-2` 的请求

#### 步骤4：创建对等连接（vpc1 ↔ vpc2）

- 操作：进入对等连接子菜单，点击新建，输入名称（`random_data()` 生成），本端 VPC 选择 `vpc1`，对端 VPC 选择 `vpc2`，描述按需填写后提交
- 预期：
  - 创建成功，列表中存在该对等连接
  - 对等连接的本端 VPC、对端 VPC 数据与输入一致

#### 步骤5：配置vpc1到vpc2的自定义路由

- 操作：进入虚拟私有云子菜单，点击 `vpc1` 进入详情，切换至路由表 tab，点击"新建"，配置如下参数：
  - IP 版本：`IPv4`
  - 目的地址：`vpc2` 的 CIDR
  - 下一跳类型：`对等连接`
  - 下一跳：选择步骤4创建的对等连接
- 预期：
  - 路由表规则创建成功，路由表列表中可查看到该条规则

#### 步骤6：配置vpc2到vpc1的自定义路由

- 操作：返回虚拟私有云列表，点击 `vpc2` 进入详情，切换至路由表 tab，新建路由：
  - IP 版本：`IPv4`
  - 目的地址：`vpc1` 的 CIDR
  - 下一跳类型：`对等连接`
  - 下一跳：选择步骤4创建的对等连接
- 预期：
  - 路由表规则创建成功

#### 步骤7：将跨VPC虚机添加为Real-Server（对等连接后应可见）

- 操作：返回 `slbv2` 详情页 -> 监听器 tab -> 资源池详情，再次点击"新建"，将 `ecs2-1` 加入资源池，端口为 `8080`
- 预期：
  - `ecs2-1` 出现在可选资源列表中
  - 添加成功，`ecs2-1` 在资源池成员列表中显示，端口 `8080`，资源状态为运行中

#### 步骤8：跨VPC ping连通性验证

- 操作：使用 `ssh_vm` 连接 `ecs2-2` 的 MFIP，ping `ecs1-2` 的固定 IP：
  ```bash
  ping -c 4 -W 3 <ecs1-2_ip>
  ```
- 预期：
  - 对等连接生效，ping 可达，丢包率 < 100%

#### 步骤9：跨VPC客户端再次通过VIP访问负载均衡

- 操作：使用 `ssh_vm` 连接 `ecs2-2` 的 MFIP，执行多次 curl 请求：
  ```bash
  curl -s --connect-timeout 10 http://<slbv2_vip>:8080/index.html
  ```
- 预期：
  - 请求成功，返回 `this is ecsX`
  - 多次执行后整体符合轮询算法（命中 `ecs1-1`、`ecs1-2`、`ecs2-1` 中至少 2 个）

## ⚠️ 实现注意事项

### 1. SSH操作强制约束

- 若测试步骤或前置条件中需要 SSH 到服务器后台或虚拟机后台执行命令，**必须**调用 `sugon_web/common/ssh.py` 中封装好的公共方法
- 禁止在测试代码中直接使用 `paramiko`、`subprocess` 等方式建立 SSH 连接
- 推荐使用 fixture：
  - `ssh_vm` fixture（`sugon_web/conftest.py`）：通过跳板机连接虚机后台，调用 `ssh_vm.connect(vm_mfip)` 建立连接，再调用 `ssh_vm.run()` / `ssh_vm.ping()`
  - `ssh_host` fixture（`sugon_web/conftest.py`）：直接 SSH 连接测试环境物理机（本用例未使用）

### 2. Fixture强制约束

- 实现测试步骤或前置条件前，**必须**阅读 `sugon_web/case_specs/fixtures_index.md`，查阅 fixture 强制约束和速查表
- 优先复用已有 fixture，**禁止**针对已有的 fixture 进行重复封装，重复封装会增加维护成本并可能导致用法不一致
- 本用例需在 `vpc1`、`vpc2` 各自创建 2 台虚机，**严禁手动循环创建**。应使用 `vm` fixture 的 `instances` 参数或参数化两次实例化（参考 `_build_vm_instance_params`），并通过 `network.networks[0]` 显式指定每台 VM 所属的 VPC 网络/子网

### 3. 可复用Fixture参考

- `vpc` fixture（`testcase/network/conftest.py`）：使用 `count=2` 批量创建 vpc1、vpc2（CIDR 自动随机，确保不冲突）
- `vm` fixture（`testcase/conftest.py`）：通过 `instances` 参数为每个 VPC 各创建 2 台虚机，并通过 `network.networks=[{"network": vpc[i].name, "subnet": vpc[i].subnet_name}]` 显式绑定到对应 VPC
- `slb` fixture（`testcase/network/conftest.py`）：使用 `version="V2"` 在 `vpc[0]` 下创建 slbv2 实例
- `vpc_page` fixture：负载均衡、对等连接、路由表、IP 地址组等网络服务公共页面对象
- `ssh_vm` fixture：连接虚机后台
- `clean_lb_listener` fixture（`testcase/network/_lb_fixtures.py`）：注册监听器、资源池成员、后端 HTTP server 的统一清理
- 对等连接清理在用例本身中执行（不引入新 fixture）
- VPC 路由规则清理由 VPC 删除自动级联（VPC 删除前需先删除路由表规则）

### 4. 后台命令执行规范

- 后端 HTTP server 启动必须使用 `nohup` 后台执行：
  - 示例：`cd /root/test/ && nohup python3 -m http.server 8080 > /dev/null 2>&1 &`
- HTTP server 启动后必须轮询等待 60 秒，确认 8080 端口处于监听状态后再进行连通性验证：
  - 检测命令：`ss -lntp | grep ':8080 '`
- 复合操作使用 `&&` 合并为同一行：`cd /root && mkdir -p test && cd test && echo "this is ecsX" > index.html`

### 5. 跨VPC资源选择校验

- 步骤2需校验"对等连接前 ecs2-1 不可选"。建议通过读取资源选择弹窗的可选资源名称列表进行断言，而不是通过捕获"添加失败"提示
- 校验完毕后必须关闭新建资源弹窗，避免影响后续步骤

### 6. 对等连接生效等待

- 创建对等连接 + 双向路由规则后，建议先 `sleep` 5～10 秒等待路由下发；通过 `ssh_vm.run("ping ...")` 验证连通性后再开始 HTTP 请求验证
- 步骤7添加 `ecs2-1` 为 Real-Server 后，资源状态变为"运行中"需要时间，使用 `wait_lb_pool_member_status` 或 `assert_lb_pool_member_info` 轮询

## 清理数据

测试完成后需要清理的资源。

### ⚠️ 清理顺序强制要求

**严格按以下顺序清理，顺序颠倒会导致资源删除失败**：

1. 从监听器资源池中移除全部成员（`ecs1-1`、`ecs1-2`、`ecs2-1`）— 由 `clean_lb_listener` 注册器统一回收
2. 删除监听器（业务名 `tcp_8080`）— 由 `clean_lb_listener` 注册器统一回收
3. 删除 `slbv2` 负载均衡实例 — 由 `slb` fixture teardown 自动回收
4. 删除对等连接 — 在用例本身或 finally 块中执行
5. 删除 `vpc1`、`vpc2` 路由表中的自定义路由规则 — 在用例本身或 finally 块中执行（VPC 删除前必须先删除）
6. 删除虚机 `ecs1-1`、`ecs1-2`、`ecs2-1`、`ecs2-2` — 由 `vm` fixture teardown 自动回收
7. 删除 `vpc1`、`vpc2` — 由 `vpc` fixture teardown 自动回收

### 清理注意事项

- 清理顺序不可颠倒
- 后端启动的 HTTP server 进程通过 `clean_lb_listener.add_backend_server()` 注册统一清理（`stop_http_backend`）
- 对等连接与自定义路由规则没有专门的 fixture，需在用例中通过 try/finally 或自定义 fixture 主动清理；若清理失败，会导致 VPC 删除失败连锁
- VPC、虚机、SLB、监听器的清理均由对应 fixture 的 teardown 机制自动完成
