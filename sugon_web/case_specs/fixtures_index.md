# Fixture 速查表

## ⚠️ 编写用例前必读：fixture强制约束

在每次编写自动化测试用例前，**必须**执行以下强制步骤，这是防止重复造轮子的关键防线。框架已提供丰富的资源创建fixture，**必须优先复用这些已有的fixture**，严禁自行封装功能重复的fixture。

### 步骤1：搜索现有fixture

**目的**：框架已提供丰富的资源创建fixture，**必须优先复用**，严禁自行封装功能重复的fixture。

**搜索命令**：

```bash
# 1. 搜索所有fixture定义，了解全局能力
grep -r "@pytest.fixture" --include="conftest.py"

# 2. 按功能关键词搜索特定fixture（以下是常用搜索示例）
grep -r "def vm(" --include="conftest.py"      # 搜索虚机相关fixture
grep -r "def vpc(" --include="conftest.py"      # 搜索VPC相关fixture
grep -r "def volume(" --include="conftest.py"   # 搜索云硬盘相关fixture
grep -r "def eip(" --include="conftest.py"      # 搜索公网IP相关fixture
grep -r "def slb(" --include="conftest.py"      # 搜索负载均衡相关fixture
```

**搜索范围**：

- `sugon_web/conftest.py` — 核心基础设施fixture
- `sugon_web/testcase/conftest.py` — 通用资源fixture（vm、volume等）
- `sugon_web/testcase/network/conftest.py` — 网络相关fixture
- `sugon_web/testcase/compute/conftest.py` — 计算相关fixture
- 其他模块conftest.py

### 步骤2：阅读匹配fixture的实现

**目的**：确认fixture支持的参数，特别是 `count` 参数是否支持批量创建。

**阅读方法**：

1. 定位到搜索结果中的文件路径和行号
2. 使用 Read 工具阅读该fixture的完整实现代码
3. 重点确认：
  - fixture是否支持 `count` 参数（用于批量创建多个资源）
  - fixture的返回值类型（单资源返回字典，多资源返回列表）
  - fixture是否依赖其他fixture（如vm依赖vpc时会自动复用网络）

---

## ⚠️ 强制复用fixture，禁止重复封装

框架已提供丰富的资源创建fixture，**必须优先复用**，严禁自行封装功能重复的fixture。

### 创建类fixture的强制要求


| 场景         | 强制要求                          | 禁止做法             |
| ---------- | ----------------------------- | ---------------- |
| 创建**单个**资源 | 调用现有fixture，默认参数              | ❌ 禁止自行封装新fixture |
| 创建**多个**资源 | **必须**调用fixture并传入 `count` 参数 | ❌ 禁止手动循环创建       |


**核心原则**：凡是需要创建多个资源（虚机、VPC、EIP等），**必须**使用现有fixture的 `count` 参数实现批量创建，**禁止**在测试代码中手动循环创建。

### 批量创建资源的正确用法

使用fixture的 `count` 参数配合 `indirect` 参数化实现批量创建：

```python
# 示例：批量创建4台虚机
@pytest.mark.parametrize("vm", [{"count": 4, "bind_mfip": True}], indirect=True)
def test_example(vm):
    requester, *backends = vm  # vm[0]作为请求者，vm[1:4]作为后端

# 示例：批量创建2个VPC
@pytest.mark.parametrize("vpc", [{"count": 2}], indirect=True)
def test_example(vpc):
    # vpc返回列表，包含2个VPC信息

# 示例：批量分配3个公网IP
@pytest.mark.parametrize("eip", [{"count": 3}], indirect=True)
def test_example(eip):
    # eip返回列表，包含3个IP地址
```

### 禁止行为

- ❌ 禁止自行封装与 `vm`、`vpc`、`volume`、`eip` 等现有fixture功能重复的新fixture
- ❌ 禁止在测试函数中手动循环创建多个资源，应使用fixture的 `count` 参数
- ❌ 禁止在 `conftest.py` 中新增与现有fixture功能相似的fixture

### 创建资源判断模板

当需要创建资源时，按顺序回答以下问题：


| 问题                 | 回答"是"      | 回答"否" |
| ------------------ | ---------- | ----- |
| 是否已有同名fixture？     | **必须复用**   | 可考虑新增 |
| 是否支持count参数？       | **必须使用**   | 可考虑新增 |
| 是否可通过参数化满足？        | **必须使用**   | 可考虑新增 |
| 是否只是需要额外处理（如角色分配）？ | **在用例中处理** | 可考虑新增 |


---

## 核心fixture快速索引

以下为高频使用fixture，支持 `count` 参数批量创建，**必须优先复用**：


| Fixture      | 文件位置                           | count参数 | 一句话说明                             |
| ------------ | ------------------------------ | ------- | --------------------------------- |
| `**vm`**     | `testcase/conftest.py`         | ✅ 支持    | 批量创建多台虚机，自动绑定MFIP；若引用vpc则自动复用网络   |
| `**vpc`**    | `testcase/network/conftest.py` | ✅ 支持    | 批量创建多个VPC，返回name、subnet_name、cidr |
| `**eip**`    | `testcase/network/conftest.py` | ✅ 支持    | 批量分配多个公网IP                        |
| `**volume**` | `testcase/conftest.py`         | ❌ 不支持   | 创建云硬盘，若local存储且引用vm则自动获取host      |
| `**port**`   | `testcase/network/conftest.py` | ✅ 支持    | 批量创建多个端口                          |
| `**slb**`    | `testcase/network/conftest.py` | ❌ 不支持   | 创建负载均衡实例                          |


---

## 完整fixture表格

以下列出框架中所有可复用的fixture：

### 一、核心基础设施（session/class级别，全局共享）


| 文件名           | Fixture名称             | 参数              | 功能说明                          |
| ------------- | --------------------- | --------------- | ----------------------------- |
| `conftest.py` | `config`              | 无               | 配置对象，返回Config实例，包含环境配置信息      |
| `conftest.py` | `browser`             | 无               | Session级浏览器实例，所有测试共享          |
| `conftest.py` | `browser_context`     | 无               | Class级浏览器上下文，保留登录态            |
| `conftest.py` | `page`                | 无               | Function级页面实例，每个用例独立页面        |
| `conftest.py` | `ssh_host`            | 无               | 直接SSH连接目标主机（不经过跳板机）           |
| `conftest.py` | `jump_host`           | 无               | 跳板机SSH连接设置                    |
| `conftest.py` | `ssh_vm`              | 无               | 通过跳板机连接虚机的SSH会话               |
| `conftest.py` | `check_compute_nodes` | 无（autouse=True） | Session级自动fixture，检查物理机节点信息   |
| `conftest.py` | `_get_patch_version`  | 无（autouse=True） | Session级自动fixture，获取补丁版本和架构信息 |


---

### 二、页面对象 Fixture（function级别，导航到对应服务）


| 文件名                               | Fixture名称         | 导航服务                    | 功能说明             |
| --------------------------------- | ----------------- | ----------------------- | ---------------- |
| `testcase/conftest.py`            | `login_page`      | 登录页                     | 登录页对象，已退出登录状态    |
| `testcase/conftest.py`            | `evs_page`        | 云硬盘                     | 云硬盘页对象           |
| `testcase/conftest.py`            | `ecs_page`        | 弹性云服务器                  | ECS页对象           |
| `testcase/conftest.py`            | `ops_page`        | 网络设施                    | 运维管理页对象          |
| `testcase/conftest.py`            | `ecs_create_page` | 弹性云服务器                  | ECS创建页对象（高级创建模式） |
| `testcase/network/conftest.py`    | `vpc_page`        | 虚拟私有云                   | VPC页对象           |
| `testcase/network/conftest.py`    | `sg_page`         | 安全组                     | 安全组页对象           |
| `testcase/network/conftest.py`    | `qos_page`        | 网络QoS                   | QoS页对象           |
| `testcase/network/conftest.py`    | `acl_page`        | 网络ACL                   | ACL页对象           |
| `testcase/network/conftest.py`    | `slb_page`        | 负载均衡                    | SLB页对象           |
| `testcase/network/conftest.py`    | `ip_group_page`   | 负载均衡                    | IP地址组页对象         |
| `testcase/database/conftest.py`   | `mysql_page`      | AnhanDB(for MySQL)      | MySQL页对象         |
| `testcase/database/conftest.py`   | `doris_page`      | 数据仓库 Doris              | Doris页对象         |
| `testcase/database/conftest.py`   | `pgsql_page`      | AnhanDB(for PostgreSQL) | PostgreSQL页对象    |
| `testcase/database/conftest.py`   | `mongodb_page`    | AnhanDB(for MongoDB)    | MongoDB页对象       |
| `testcase/middleware/conftest.py` | `redis_page`      | AnhanDB(for Redis)      | Redis页对象         |
| `testcase/middleware/conftest.py` | `kafka_page`      | 分布式消息服务 Kafka           | Kafka页对象         |
| `testcase/backup/conftest.py`     | `backup_page`     | 备份                      | 备份页对象            |
| `testcase/storage/conftest.py`    | `kms_page`        | 可信密码模块                  | 密钥管理页对象          |


---

### 三、虚机创建 Fixture


| 文件名                            | Fixture名称               | 参数                                                                                                                       | 功能说明                                                                        |
| ------------------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| `testcase/conftest.py`         | `vm`                    | `count`: 创建数量（默认1） `root_gb`: 系统盘大小（默认25GB） `bind_mfip`: 是否绑定MFIP（默认True） `network`: 网络名称 `subnet`: 子网名称 `cluster`: 集群名称 | **核心fixture**：创建虚机并自动清理。count=1返回字典，count>1返回列表。若引用了vpc fixture则自动复用其网络和子网。 |
| `testcase/network/conftest.py` | `sg_vm_setup`           | `vm_count`: 虚机数量（默认2） `sg_count`: 安全组数量（默认2） `fip_count`: 公网IP数量（默认1） `sg_strategy`: 安全组分配策略                             | 创建虚机+安全组+公网IP的综合环境                                                          |
| `testcase/network/conftest.py` | `lb_pool_candidate_vms` | `count`: 创建数量（默认2） `cluster`: 集群名称 `name_prefix`: 虚机名称前缀                                                                 | 创建资源池候选虚机，用于SLB监听器资源池测试                                                     |
| `testcase/backup/conftest.py`  | `vm_backup`             | `count`: 创建数量（默认1）                                                                                                       | 创建虚机并预置数据盘、公网IP、MFIP，用于备份测试                                                 |


---

### 四、云硬盘 Fixture


| 文件名                            | Fixture名称     | 参数                                                                                  | 功能说明                                            |
| ------------------------------ | ------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------- |
| `testcase/conftest.py`         | `volume`      | `empty`: 是否空白云硬盘（默认True） `image_name`: 镜像名称 `size`: 云硬盘大小（默认30GB） `shared`: 是否共享云硬盘 | 创建云硬盘并自动清理。若存储类型为local且引用vm fixture，自动获取host参数。 |
| `testcase/compute/conftest.py` | `ecss`        | 无（依赖vm fixture）                                                                     | 创建ECS快照并自动清理                                    |
| `testcase/compute/conftest.py` | `ecss_policy` | 无                                                                                   | 创建快照策略并自动清理                                     |
| `testcase/storage/conftest.py` | `evss_policy` | 无                                                                                   | 创建云硬盘快照策略并自动清理                                  |
| `testcase/storage/conftest.py` | `evss`        | 无（依赖volume fixture）                                                                 | 创建云硬盘快照并自动清理                                    |


---

### 五、VPC/网络 Fixture


| 文件名                            | Fixture名称 | 参数                                                                                                             | 功能说明                                                                           |
| ------------------------------ | --------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `testcase/network/conftest.py` | `vpc`     | `count`: 创建数量（默认1） `name`: VPC名称 `subnet_name`: 子网名称 `cidr`: CIDR `network_type`: 网络类型 `enable_ipv6`: 是否启用IPv6 | **核心fixture**：创建VPC并自动清理。count=1返回字典，count>1返回列表。返回包含name、subnet_name、cidr等信息。 |
| `testcase/network/conftest.py` | `vip`     | 无（依赖vpc fixture）                                                                                               | 在vpc的子网中创建虚拟IP                                                                 |
| `testcase/network/conftest.py` | `port`    | `count`: 创建数量（默认1）                                                                                             | 在vpc的子网中创建端口，返回端口IP列表                                                          |


---

### 六、弹性公网IP/NAT Fixture


| 文件名                            | Fixture名称 | 参数                                                           | 功能说明                                       |
| ------------------------------ | --------- | ------------------------------------------------------------ | ------------------------------------------ |
| `testcase/network/conftest.py` | `eip`     | `count`: 分配数量（默认1） `pool`: IP池名称 `method`: 分配方式 `ip`: 指定IP地址 | 分配弹性公网IP并自动释放。count=1返回单个IP，count>1返回IP列表。 |
| `testcase/network/conftest.py` | `nat`     | `eip`: 关联的EIP `public_ip_pool`: 公网IP池 `desc`: 描述             | 创建NAT网关并自动删除                               |


---

### 七、网络安全 Fixture


| 文件名                            | Fixture名称                | 参数                                                                      | 功能说明                   |
| ------------------------------ | ------------------------ | ----------------------------------------------------------------------- | ---------------------- |
| `testcase/network/conftest.py` | `sg`                     | 无                                                                       | 创建安全组并自动清理，返回安全组名称     |
| `testcase/network/conftest.py` | `qos`                    | 无                                                                       | 创建网络QoS并自动清理           |
| `testcase/network/conftest.py` | `acl`                    | 无                                                                       | 创建网络ACL并自动清理           |
| `testcase/network/conftest.py` | `acl_vpc_vms`            | `vpc_acl`: VPC是否关联ACL `sub2_acl`: 子网2是否关联ACL `vms_per_subnet`: 每个子网虚机数量 | 创建ACL关联的VPC+2个子网+虚机环境  |
| `testcase/network/conftest.py` | `acl_in_out_bound_rules` | 固定参数                                                                    | 专门为复杂内外网规则场景定制，Class级别 |


---

### 八、负载均衡 Fixture


| 文件名                            | Fixture名称  | 参数                                                                                       | 功能说明                  |
| ------------------------------ | ---------- | ---------------------------------------------------------------------------------------- | --------------------- |
| `testcase/network/conftest.py` | `slb`      | `version`: "V1"或"V2" `ha_enable`: 是否高可用 `ip_type`: IP分配方式 `cluster`: V2集群名称 `spec`: V2规格 | 创建负载均衡实例并自动清理，返回SLB名称 |
| `testcase/network/conftest.py` | `lb`       | `protocol`: 协议 `port`: 端口 `lb_name`: 监听器名称 `pool_name`: 资源池名称 `health_check`: 是否健康检查     | 创建监听器实例并自动清理          |
| `testcase/network/conftest.py` | `ip_group` | `name`: 名称 `ip_addresses`: IP地址列表 `enable_ipv6`: 是否启用IPv6                                | 创建IP地址组并自动清理          |


---

### 九、数据库实例 Fixture


| 文件名                             | Fixture名称 | 参数  | 功能说明                      |
| ------------------------------- | --------- | --- | ------------------------- |
| `testcase/database/conftest.py` | `mysql`   | 无   | 创建MySQL集群实例+数据库+用户，自动清理   |
| `testcase/database/conftest.py` | `doris`   | 无   | 创建Doris实例+2个数据库+2个用户，自动清理 |
| `testcase/database/conftest.py` | `pgsql`   | 无   | 创建PostgreSQL单机实例+用户，自动清理  |
| `testcase/database/conftest.py` | `mongodb` | 无   | 创建MongoDB副本集+分片集群实例，自动清理  |


---

### 十、中间件实例 Fixture


| 文件名                               | Fixture名称 | 参数  | 功能说明                  |
| --------------------------------- | --------- | --- | --------------------- |
| `testcase/middleware/conftest.py` | `redis`   | 无   | 创建Redis单机实例+集群实例，自动清理 |
| `testcase/middleware/conftest.py` | `kafka`   | 无   | 创建Kafka实例并自动清理        |


---

### 十一、备份 Fixture


| 文件名                           | Fixture名称                 | 参数                                | 功能说明               |
| ----------------------------- | ------------------------- | --------------------------------- | ------------------ |
| `testcase/backup/conftest.py` | `backup_task`             | `task_count`: 任务数量 `policy`: 备份策略 | 创建备份任务并自动清理        |
| `testcase/backup/conftest.py` | `backup_with_full_backup` | 无（依赖backup_task）                  | 执行全量备份，返回备份数据      |
| `testcase/backup/conftest.py` | `cleanup_backup_task`     | 无                                 | 自动清理备份任务的辅助fixture |
| `testcase/backup/conftest.py` | `cleanup_resume_data`     | 无                                 | 自动清理恢复任务和恢复产生的新虚机  |


---

### 十二、存储/密钥 Fixture


| 文件名                            | Fixture名称  | 参数                                          | 功能说明           |
| ------------------------------ | ---------- | ------------------------------------------- | -------------- |
| `testcase/compute/conftest.py` | `image`    | `name`: 镜像名称 `backend`: 存储后端 `image`: 镜像文件名 | 通过SSH创建镜像并自动删除 |
| `testcase/compute/conftest.py` | `pool`     | `node`: 物理机节点 `storage_type`: 存储类型          | 创建存储池并自动清理     |
| `testcase/compute/conftest.py` | `labels`   | `count`: 创建数量 `prefix`: 名称前缀                | 创建标签并自动清理      |
| `testcase/compute/conftest.py` | `affinity` | `count`: 创建数量 `prefix`: 名称前缀                | 创建亲和组标签        |
| `testcase/storage/conftest.py` | `bucket`   | `count`: 创建数量 `name`: 自定义名称 `capacity`: 桶容量 | 创建对象存储桶并自动清理，优先复用 autotest-* 空桶 |
| `testcase/storage/conftest.py` | `oss_bucket` | `count`: 创建数量 `name`: 自定义名称 `region`: 区域 `az_strategy`: 数据冗余存储策略 `storage_class`: 默认存储类别 `bucket_strategy`: 桶策略 `is_encryption`: 是否开启默认加密 `data_read`: 归档数据直读 `tags`: 标签列表 | 创建OSS对象存储桶并自动清理，支持多AZ/私有/加密/标签等完整参数 |
| `testcase/storage/conftest.py` | `kms_key`  | 可通过indirect传入engine参数                       | 创建密钥并自动清理      |
| `testcase/storage/conftest.py` | `sfs_instance` | `count`: 创建数量 `name`: 名称前缀 `protocol`: 文件协议（str 或 list） `cluster`: 集群 `network`: 专有网络 `subnet`: 子网 `volume_type`: 云硬盘类型 `volume_size`: 云硬盘大小 `cpu_cores`: CPU 核数 `ram_gb`: 内存 GiB | 创建文件存储 SFS 实例并自动清理；count=1 返回字典，count>1 返回列表，支持为每个实例指定不同协议 |
| `testcase/storage/conftest.py` | `clean_sfs_instances` | 无（注册表模式） | SFS 实例注册表，测试用例动态登记实例名，fixture yield 后统一清理 |


---

### 十三、辅助 Fixture


| 文件名                            | Fixture名称                      | 参数  | 功能说明                   |
| ------------------------------ | ------------------------------ | --- | ---------------------- |
| `testcase/conftest.py`         | `test_context`                 | 无   | 用于在测试用例各步骤间传递数据的上下文字典  |
| `testcase/network/conftest.py` | `clean_acl_inbound_rules`      | 无   | 清理ACL入方向规则（function级别） |
| `testcase/network/conftest.py` | `clean_acl_inbound_rules_4vms` | 无   | 清理ACL入方向规则（class级别）    |
| `testcase/network/conftest.py` | `clean_acl_outbound_rules`     | 无   | 清理ACL出方向规则（class级别）    |


