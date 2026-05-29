# 测试用例：负载均衡（基础版）V1-TCP监听器+公网IP绑定功能验证

## 基本信息

- 用例编号：3514、3509
- 所属产品：曙光云Stack
- 一级模块：网络
- 二级模块：负载均衡-基础版V1

## 适配范围

### 存储适配

- 该用例不支持的存储：无

### 架构/节点限制

- 架构限制：无
- 节点要求：无

## 前置条件

1. 已预置VPC（如vpc1），并在VPC下创建四台虚机：ecs0、ecs1、ecs2、ecs3（**本资源在多个场景中复用**）
2. 在vpc1下，预置负载均衡(基础版)-v1实例slbv1（**本资源在多个场景中复用**）
3. 监听器参数配置（**本配置在多个场景中复用**）：
   - 监听器名称：tcp_8080
   - 描述：1234567890edwqWDWQ中文~
   - 协议：TCP
   - 协议端口：8080
   - 资源池名称：backend_1
   - 负载调度算法：轮询
   - 其他字段保持默认值（如不开启会话保持、不开启健康检查等）
4. 预置2个公网IP（**场景2专用，场景1不依赖**）

> **测试数据复用说明**：本MD文件包含的所有场景共享同一套测试数据，所有用例执行完成后统一清理。

## 测试步骤

### 场景1：新建监听器-TCP+轮询基本功能验证（用例3514）

#### 步骤1：进入负载均衡模块

- 操作：进入负载均衡模块，依次点击：产品与服务 -> 网络 -> 负载均衡SLB
- 预期：可以正常进入负载均衡模块，lbv1列表可以正常显示

#### 步骤2：进入监听器详情页

- 操作：在lbv1列表页，点击预置的slbv1实例名称，进入详情，选择监听器tab
- 预期：详情页可以正常显示

#### 步骤3：创建TCP监听器

- 操作：点击新建按钮，按前置条件3中的参数，创建TCP监听器
- 预期：
  - 创建监听器成功并提示信息
  - 监听器详情页显示信息与新建数据一致

#### 步骤4：添加资源池成员

- 操作：在slbv1详情页 -> 监听器tab下 -> 点击监听器名称tcp_8080 -> 选择资源池tab，进入资源池backend_1详情后，点击创建按钮，选择ecs1、ecs2、ecs3为该资源池的成员，对应端口为8080
- 预期：
  - 新建成员成功
  - 资源池列表显示信息与新建资源数据一致

#### 步骤5：后端虚机配置（ecs1、ecs2、ecs3）

- 操作：使用 `ssh_vm` fixture，通过 `ssh_vm.connect(vm_mfip)` 方式分别登录ecs1、ecs2、ecs3，执行如下操作
- 子步骤：
  1. 创建测试目录：
     ```bash
     cd /root && mkdir test
     ```
  2. 创建测试文件（以ecs1为例，其他虚机注意修改标识）：
     ```bash
     cd /root/test/ && echo "this is ecs1" >> index.html
     ```
  3. 启动web server（使用nohup后台执行，避免占用SSH会话）：
     ```bash
     cd /root/test/ && nohup python3 -m http.server 8080 > /dev/null 2>&1 &
     ```
  4. 轮询等待web服务启动成功，最长等待60秒：
     ```bash
     # 轮询检查命令
     ss -lntp | grep 8080
     ```
- 预期：
  - 目录创建成功
  - 文件创建成功
  - web服务启动成功（轮询检查8080端口监听成功）

#### 步骤6：内网VIP访问测试

- 操作：使用 `ssh_vm` fixture，通过 `ssh_vm.connect(vm_mfip)` 方式ssh连接ecs0，然后在ecs0中执行以下命令请求此slbv1实例的VIP：
  ```bash
  curl http://<slbv1_vip>:8080/index.html
  ```
- 预期：
  - 执行成功，显示"this is ecsX"
  - 多次执行后，整体符合1:1:1的轮询规律

#### 步骤7：绑定公网IP

- 操作：在负载均衡列表页，针对此slbv1实例，点击其操作栏的绑定公网ip按钮，绑定公网ip
- 预期：fip绑定成功，可以在列表显示绑定的公网ip地址

#### 步骤8：公网IP访问测试

- 操作：使用 `ssh_host` fixture，ssh连接测试环境物理机后台，在物理机后台通过slbv1实例的公网IP访问负载均衡，执行以下命令：
  ```bash
  curl http://<slbv1_fip>:8080/index.html
  ```
- 预期：
  - 执行成功，显示"this is ecsX"
  - 多次执行后，整体符合1:1:1的轮询规律

---

### 场景2：负载均衡-绑定解绑公网IP功能验证（用例3509）

> **依赖**：场景1（用例3514）已执行完成。场景1中已创建监听器tcp_8080、资源池backend_1及成员。

#### 步骤1：添加资源池成员

- 操作：在slbv1详情页 -> 监听器tab下 -> 点击监听器名称tcp_8080 -> 选择资源池tab，进入资源池backend_1详情后，点击创建按钮，选择ecs1、ecs2、ecs3为该资源池的成员，对应端口为8080
- 预期：
  - 新建成员成功
  - 资源池列表的实例名称、端口号、资源状态信息与新建资源数据一致，ecs1、ecs2、ecs3的资源状态为运行中

#### 步骤2：后端虚机配置（ecs1、ecs2、ecs3）

- 操作：使用 `ssh_vm` fixture，通过 `ssh_vm.connect(vm_mfip)` 方式依次登录ecs1、ecs2、ecs3，执行如下操作
- 子步骤：
  1. 创建测试目录：
     ```bash
     cd /root && mkdir test
     ```
  2. 创建测试文件（以ecs1为例，其他虚机注意修改标识）：
     ```bash
     cd /root/test/ && echo "this is ecs1" >> index.html
     ```
  3. 启动web server（使用nohup后台执行）：
     ```bash
     cd /root/test/ && nohup python3 -m http.server 8080 > /dev/null 2>&1 &
     ```
  4. 轮询等待web服务启动成功，最长等待60秒：
     ```bash
     ss -lntp | grep 8080
     ```
- 预期：
  - 目录创建成功
  - 文件创建成功
  - web服务启动成功

#### 步骤3：内网VIP访问测试

- 操作：使用 `ssh_vm` fixture，通过 `ssh_vm.connect(vm_mfip)` 方式ssh连接ecs0，在ecs0中执行以下命令请求此slbv1实例的网络IP即VIP：
  ```bash
  curl http://<slbv1_vip>:8080/index.html
  ```
- 预期：执行成功，显示"this is ecsX"

#### 步骤4：绑定公网IP

- 操作：在负载均衡列表页，针对此slbv1实例，点击其操作栏的绑定公网ip按钮，绑定公网ip
- 预期：绑定公网IP成功并提示信息，列表页显示信息与实际一致

#### 步骤5：公网IP访问测试

- 操作：使用 `ssh_host` fixture，ssh连接测试环境物理机后台，通过slbv1实例的公网IP访问负载均衡，执行以下命令：
  ```bash
  curl http://<slbv1_fip>:8080/index.html
  ```
- 预期：
  - 执行成功，显示"this is ecsX"
  - 多次执行后，整体符合1:1:1的轮询规律

#### 步骤6：解绑公网IP

- 操作：在负载均衡列表页，点击操作栏解绑公网IP按钮
- 预期：fip解绑成功

#### 步骤7：解绑后公网IP访问验证

- 操作：使用 `ssh_host` fixture，ssh连接测试环境物理机后台，通过之前绑定的fip访问负载均衡，执行以下命令：
  ```bash
  curl http://<slbv1_fip>:8080/index.html
  ```
- 预期：通过fip无法访问（请求失败或超时）

#### 步骤8：更换公网IP重新绑定

- 操作：重复执行步骤4（绑定公网IP），在选择公网IP时选择另一个fip地址（不同于步骤4选中的公网IP）；然后重复执行步骤5（公网IP访问测试），通过新fip访问负载均衡
- 预期：
  - 新fip地址绑定成功
  - 通过新fip可以正常访问此slbv1，显示"this is ecsX"，多次执行后整体符合1:1:1的轮询规律

## ⚠️ 实现注意事项

### 1. SSH操作强制约束

- 若测试步骤或前置条件中需要SSH到服务器后台或虚拟机后台执行命令，**必须**调用 `sugon_web/common/ssh.py` 中封装好的公共方法
- 禁止在测试代码中直接使用 `paramiko`、`subprocess` 等方式建立SSH连接
- 推荐使用fixture：
  - `ssh_vm` fixture：通过跳板机连接虚机的SSH会话，提供 `connect(vm_mfip)`、`run(cmd)`、`ping()` 等方法
  - `ssh_host` fixture：直接SSH连接目标主机（不经过跳板机），提供 `run(cmd)` 等方法

### 2. Fixture强制约束

- 实现测试步骤或前置条件的自动化脚本前，**必须**阅读 `sugon_web/case_specs/fixtures_index.md`
- 查阅fixture强制约束和速查表，确认框架中是否已有可复用的fixture
- **禁止**针对已有的fixture进行重复封装

### 3. 可复用Fixture参考

根据 `fixtures_index.md`，本用例可能涉及的fixture：

- `vpc` fixture：创建VPC（支持count参数批量创建），返回包含name、subnet_name、cidr等信息的字典
- `vm` fixture：创建虚机（支持count=4参数批量创建4台虚机，自动绑定MFIP），返回字典或列表
- `slb` fixture：创建负载均衡实例（支持version="V1"参数），返回SLB名称
- `eip` fixture：分配公网IP（支持count=2参数批量创建），返回IP或IP列表
- `lb` fixture：创建监听器实例（支持protocol、port、lb_name、pool_name等参数），自动清理
- `slb_page` fixture：负载均衡页对象（导航到负载均衡服务）
- `ecs_page` fixture：弹性云服务器页对象
- `ssh_vm` fixture：通过跳板机连接虚机的SSH会话
- `ssh_host` fixture：直接SSH连接测试环境物理机后台

### 4. 后台命令执行规范

- 所有需要后台长期运行的命令（如启动web server），**必须**使用 `nohup` 命令并在末尾添加 `&` 符号，避免在自动化用例执行过程中长时间占用SSH会话连接
- 示例：`cd /root/test/ && nohup python3 -m http.server 8080 > /dev/null 2>&1 &`
- 同一组操作若需多个命令完成，使用 `&&` 合并为单行命令

### 5. 轮询等待规范

- 执行后不会立刻返回结果的命令（如启动web server后验证端口监听），必须增加轮询等待，直至命令输出符合预期的正确结果
- 设置最长等待时长为60秒，使用循环+sleep方式实现
- 检查命令示例：`ss -lntp | grep 8080`

### 6. 轮询算法验证

- 验证轮询算法时，建议至少执行6次curl请求，统计各后端虚机响应次数
- 验证比例应接近1:1:1（允许轻微偏差，如5:6:7均可接受）

### 7. 断言策略

- 页面操作步骤：使用页面元素断言（检查成功提示、列表字段值、状态等）
- SSH命令执行步骤：使用命令输出断言（检查curl返回内容、grep匹配结果等）
- 关键步骤建议页面断言+SSH验证两者结合

### 8. 测试数据策略

- 资源名称使用 `random_data()` 生成，避免资源名称冲突
- 批量创建资源（如4台虚机、2个公网IP）使用fixture的 `count` 参数
- 测试数据复用场景：本用例所有场景共享同一套测试数据，由class级别fixture统一创建，所有用例执行完成后统一清理

## 清理数据

### ⚠️ 清理顺序强制要求

本用例的测试数据清理流程**必须**按照如下顺序执行：

1. 将ecs1/ecs2/ecs3从LB资源池中移除
2. 删除监听器tcp_8080
3. 删除负载均衡实例slbv1
4. 删除预置的公网IP（场景2涉及）
5. 删除虚机ecs0~ecs3（由vm fixture teardown自动回收）
6. 删除VPC vpc1（由vpc fixture teardown自动回收）

### 清理注意事项

- 清理顺序不可颠倒，必须严格按照上述顺序依次执行
- 如果在清理过程中某一步骤失败，需先解决该步骤的问题后再继续后续清理
- 每个清理步骤完成后应验证清理成功，再执行下一个清理步骤
- 虚机和VPC的清理由fixture的teardown机制自动完成，但需确保在此之前已完成lb、slb相关资源的清理
- 场景2的公网IP清理应在slbv1实例删除之后、虚机清理之前执行
