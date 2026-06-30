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


| 文件名                               | Fixture名称        | 导航服务                    | 功能说明                     |
| --------------------------------- | ---------------- | ----------------------- | ------------------------ |
| `testcase/conftest.py`            | `login_page`     | 登录页                     | 登录页对象，已退出登录状态            |
| `testcase/conftest.py`            | `evs_page`       | 云硬盘                     | 云硬盘页对象                   |
| `testcase/conftest.py`            | `ecs_page`       | 弹性云服务器                  | ECS页对象                   |
| `testcase/conftest.py`            | `obs_page`       | 对象存储专业版                 | 对象存储专业版(OBS)页对象          |
| `testcase/conftest.py`            | `ops_page`       | 运维管理/基础设施               | 运维管理页对象                  |
| `testcase/conftest.py`            | `bms_page`       | 裸金属服务器                  | 裸金属BMS页对象                |
| `testcase/network/conftest.py`    | `vpc_page`       | 虚拟私有云                   | VPC页对象（兼具子网/ACL/安全组等操作） |
| `testcase/network/conftest.py`    | `cfw_page`       | 云防火墙                    | 云防火墙CFW页对象               |
| `testcase/network/conftest.py`    | `dc_page`        | 云专线                     | 云专线DC页对象                 |
| `testcase/network/conftest.py`    | `er_page`        | 企业路由器                   | 企业路由器ER页对象               |
| `testcase/network/conftest.py`    | `tm_page`        | 流量镜像                    | 流量镜像TM页对象                |
| `testcase/network/conftest.py`    | `vpn_page`       | 虚拟专用网络                  | 虚拟专用网络VPN页对象             |
| `testcase/network/conftest.py`    | `kms_page`       | 可信密码模块                  | 机密互联-密钥管理(SciKmsPage)页对象 |
| `testcase/database/conftest.py`   | `mysql_page`     | AnhanDB(for MySQL)      | MySQL页对象                 |
| `testcase/database/conftest.py`   | `doris_page`     | 数据仓库 Doris              | Doris页对象                 |
| `testcase/database/conftest.py`   | `pgsql_page`     | AnhanDB(for PostgreSQL) | PostgreSQL页对象            |
| `testcase/database/conftest.py`   | `kingbase_page`  | 人大金仓 KingbaseES         | KingbaseES页对象            |
| `testcase/database/conftest.py`   | `mongodb_page`   | AnhanDB(for MongoDB)    | MongoDB页对象               |
| `testcase/database/conftest.py`   | `xscale_page`    | XScale                  | XScale页对象                |
| `testcase/middleware/conftest.py` | `redis_page`     | AnhanDB(for Redis)      | Redis页对象                 |
| `testcase/middleware/conftest.py` | `kafka_page`     | 分布式消息服务 Kafka           | Kafka页对象                 |
| `testcase/middleware/conftest.py` | `es_page`        | 云搜索服务                   | 云搜索服务CSS(ES)页对象          |
| `testcase/middleware/conftest.py` | `rabbitmq_page`  | 分布式消息服务 RabbitMQ        | RabbitMQ页对象              |
| `testcase/middleware/conftest.py` | `prometheus_page`| 监控服务                    | Prometheus页对象            |
| `testcase/bigdata/conftest.py`    | `emr_page`       | E-MapReduce             | E-MapReduce页对象           |
| `testcase/container/conftest.py`  | `cce_page`       | 云容器引擎                   | 云容器引擎CCE页对象              |
| `testcase/container/conftest.py`  | `scr_page`       | 容器镜像服务                  | 容器镜像服务SCR页对象             |
| `testcase/iam/conftest.py`        | `iam_page`       | 统一身份认证IAM               | IAM页对象（组织树入口，状态已清理）      |
| `testcase/iam/conftest.py`        | `iam_tenant_page`| 运营-租户用户列表              | IAM租户用户列表页对象（扁平列表无组织树）  |
| `testcase/security/conftest.py`   | `apt_page`       | 攻击预警APT                 | 攻击预警APT页对象               |
| `testcase/security/conftest.py`   | `usm_page`       | 云堡垒机高级版USM              | 云堡垒机高级版USM页对象            |
| `testcase/security/conftest.py`   | `ver_page`       | 日志审计VER                 | 日志审计VER页对象               |
| `testcase/security/conftest.py`   | `vdb_page`       | 数据库审计VDB                | 数据库审计VDB页对象              |
| `testcase/storage/conftest.py`    | `sfs_page`       | 文件存储                    | 文件存储SFS页对象               |
| `testcase/storage/conftest.py`    | `oss_page`       | 对象存储                    | 对象存储OSS页对象               |
| `testcase/storage/conftest.py`    | `kms_page`       | 可信密码模块                  | 密钥管理(KmsPage)页对象，未授权时skip |
| `testcase/backup/conftest.py`     | `backup_page`    | 备份                      | 备份页对象                    |


---

### 三、虚机创建 Fixture


| 文件名                            | Fixture名称               | 参数                                                                                                                       | 功能说明                                                                        |
| ------------------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| `testcase/conftest.py`         | `vm`                    | `basic`(name/count/cluster/flavor…) `storage` `network` `manage` `bind_mfip`(默认True) `instances` `inject_dependencies` 等 | **核心fixture**：创建虚机并自动清理。count=1返回字典，count>1返回列表。若引用了vpc fixture则自动复用其网络和子网。 |
| `testcase/network/conftest.py` | `lb_pool_candidate_vms` | `count`: 创建数量（默认2） `cluster`: 集群名称 `name_prefix`: 虚机名称前缀                                                                 | 创建资源池候选虚机（不绑MFIP，内网场景），用于SLB监听器资源池测试                                          |
| `testcase/backup/conftest.py`  | `vm_backup`             | `count`: 创建数量（默认1）                                                                                                       | 创建虚机并补齐备份元数据（源数据MD5、公网IP、MFIP、可用备份节点），用于备份测试                                 |


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
| `testcase/network/conftest.py` | `vpc`     | `count`: 创建数量（默认1） `name`: VPC名称 `subnet_name`: 子网名称 `cidr`: CIDR `network_type`: 网络类型 `enable_ipv6`: 是否启用IPv6 `extra_subnets`: 额外子网 | **核心fixture**：创建VPC并自动清理。count=1返回字典，count>1返回列表。返回包含name、subnet_name、cidr等信息。 |
| `testcase/network/conftest.py` | `vip`     | 无（依赖vpc fixture）                                                                                               | 在vpc的子网中创建虚拟IP                                                                 |
| `testcase/network/conftest.py` | `port`    | `count`: 创建数量（默认1）                                                                                             | 在vpc的子网中创建端口，返回端口IP列表                                                          |
| `testcase/network/conftest.py` | `internal_dns` | 无（依赖vpc fixture）                                                                                          | 创建内网解析域名并自动清理                                                                 |
| `testcase/network/conftest.py` | `internal_dns_record` | 无（依赖internal_dns fixture）                                                                         | 创建内网解析记录并自动清理                                                                 |
| `testcase/network/conftest.py` | `cfw`     | `name` `version`(默认山石引擎-5.5) `cluster`(默认Autotest) `protected_resource`                                       | 创建云防火墙并等待运行中（按业务保留实例，不删除）                                                     |
| `testcase/network/_vpn_gateway_er_fixtures.py` | `er_for_vpn_gateway` | 无（依赖er_page fixture） | 创建开启HA的企业路由器并自动清理；teardown等待40秒确保VPN网关释放后再删ER，供VPN网关连接ER场景使用（需显式import） |


---

### 六、弹性公网IP/NAT Fixture


| 文件名                            | Fixture名称 | 参数                                                           | 功能说明                                       |
| ------------------------------ | --------- | ------------------------------------------------------------ | ------------------------------------------ |
| `testcase/network/conftest.py` | `eip`     | `count`: 分配数量（默认1） `pool`: IP池名称 `method`: 分配方式 `ip`: 指定IP地址 | 分配弹性公网IP并自动释放。count=1返回单个IP，count>1返回IP列表。（`testcase/conftest.py` 亦有同名全局 fixture，network 下就近覆盖） |
| `testcase/network/conftest.py` | `nat`     | `eip`: 关联的EIP `public_ip_pool`: 公网IP池 `desc`: 描述             | 创建NAT网关并自动删除                               |
| `testcase/compute/conftest.py` | `bms_eip_pool` | `count`: 分配数量（默认5） `pool`: IP池名称 `method`: 分配方式          | 为BMS分配小型EIP池并返回最大IP，teardown逐个尽力释放          |


---

### 七、网络安全 Fixture


| 文件名                            | Fixture名称       | 参数                       | 功能说明                            |
| ------------------------------ | --------------- | ------------------------ | ------------------------------- |
| `testcase/network/conftest.py` | `sg`            | `param`: 安全组数量（int，默认1）  | 创建安全组并自动清理，返回安全组名称或名称列表（依赖vpc_page） |
| `testcase/compute/conftest.py` | `sg`            | `param`: 安全组数量（int，默认1）  | compute模块下的同名fixture，复用network底层创建/清理逻辑，自建独立页面 |
| `testcase/network/conftest.py` | `qos`           | 无                        | 创建网络QoS并自动清理                    |
| `testcase/network/conftest.py` | `acl`           | 无                        | 创建网络ACL并自动清理                    |
| `testcase/network/_ca_fixtures.py` | `mtls_certs` | 无（依赖ssh_vm、vm，可选slb）     | 在虚机上预生成localhost/SLB VIP证书，类内共用 |
| `testcase/network/_ca_fixtures.py` | `server_cert` | 无（依赖vpc_page、mtls_certs） | 创建国际服务器证书并自动删除                  |
| `testcase/network/_ca_fixtures.py` | `ca_cert`    | 无（依赖vpc_page、mtls_certs） | 创建CA证书并自动删除                     |


---

### 八、负载均衡 Fixture


| 文件名                            | Fixture名称  | 参数                                                                                       | 功能说明                  |
| ------------------------------ | ---------- | ---------------------------------------------------------------------------------------- | --------------------- |
| `testcase/network/conftest.py` | `slb`      | `version`: "V1"或"V2" `ha_enable`: 是否高可用 `ip_type`: IP分配方式 `cluster`: V2集群名称 `spec`: V2规格 | 创建负载均衡实例并自动清理，返回含name/vip/id的字典 |
| `testcase/network/conftest.py` | `lb`       | `protocol`: 协议 `port`: 端口 `lb_name`: 监听器名称 `pool_name`: 资源池名称 `health_check`: 是否健康检查     | 创建监听器实例并自动清理          |
| `testcase/network/conftest.py` | `ip_group` | `name`: 名称 `ip_addresses`: IP地址列表 `enable_ipv6`: 是否启用IPv6                                | 创建IP地址组并自动清理          |
| `testcase/network/_lb_peer_fixtures.py` | `lb_peer_vms` | 无（依赖vpc返回2个VPC、ssh_host）                                              | 跨VPC场景：在两个VPC下各创建2台虚机并绑MFIP，返回{vpc1, vpc2} |
| `testcase/network/_lb_peer_fixtures.py` | `slb_peer_in_vpc1` | `param`: 版本 V1/V2（默认V2，依赖vpc）                                      | 在vpc[0]下创建负载均衡实例并自动清理 |


---

### 九、数据库实例 Fixture


| 文件名                             | Fixture名称  | 参数  | 功能说明                          |
| ------------------------------- | ---------- | --- | --------------------------- |
| `testcase/database/conftest.py` | `mysql`    | 无   | 创建MySQL集群实例+数据库+用户，自动清理      |
| `testcase/database/conftest.py` | `doris`    | 无   | 创建Doris实例+2个数据库+2个用户，自动清理    |
| `testcase/database/conftest.py` | `pgsql`    | 无   | 创建PostgreSQL单机实例+用户，自动清理     |
| `testcase/database/conftest.py` | `kingbase` | 无   | 创建KingbaseES集群实例+数据库+用户，自动清理 |
| `testcase/database/conftest.py` | `mongodb`  | 无   | 创建MongoDB副本集+分片集群实例，自动清理     |
| `testcase/database/conftest.py` | `xscale`   | 无   | 创建XScale实例并预连接后端计算节点，自动清理    |


---

### 十、中间件实例 Fixture


| 文件名                               | Fixture名称   | 参数  | 功能说明                  |
| --------------------------------- | ----------- | --- | --------------------- |
| `testcase/middleware/conftest.py` | `redis`     | 无   | 创建Redis单机实例+集群实例，自动清理 |
| `testcase/middleware/conftest.py` | `kafka`     | 无   | 创建Kafka实例并自动清理        |
| `testcase/middleware/conftest.py` | `css`       | 无   | 创建云搜索服务CSS集群实例并自动清理   |
| `testcase/middleware/conftest.py` | `rabbitmq`  | 无   | 创建RabbitMQ集群实例并自动清理   |
| `testcase/middleware/conftest.py` | `prometheus`| 无   | 创建Prometheus集群并自动清理   |


---

### 十一、备份 Fixture


| 文件名                           | Fixture名称             | 参数                                | 功能说明               |
| ----------------------------- | --------------------- | --------------------------------- | ------------------ |
| `testcase/backup/conftest.py` | `backup_task`         | `task_count`: 任务数量 `policy`: 备份策略 | 创建备份任务并自动清理（资源型，不执行备份/恢复动作） |
| `testcase/backup/conftest.py` | `cleanup_backup_task` | 无                                 | 测试内显式创建任务的清理登记簿，teardown统一清理 |
| `testcase/backup/conftest.py` | `cleanup_resume_data` | 无                                 | 清理恢复任务和恢复产生的新虚机    |


---

### 十二、存储/密钥 Fixture


| 文件名                            | Fixture名称  | 参数                                          | 功能说明           |
| ------------------------------ | ---------- | ------------------------------------------- | -------------- |
| `testcase/compute/conftest.py` | `image`    | `name`: 镜像名称 `backend`: 存储后端 `image`: 镜像文件名 | 通过SSH创建镜像并自动删除 |
| `testcase/compute/conftest.py` | `pool`     | `node`: 物理机节点 `storage_type`: 存储类型          | 创建存储池并自动清理     |
| `testcase/compute/_ecs_fixtures.py` | `labels`   | `count`: 创建数量                          | 创建标签并自动清理，可与vm联动注入 |
| `testcase/compute/_ecs_fixtures.py` | `affinity` | `policy`: 亲和/反亲和 `name`: 名称           | 创建亲和组并自动清理，可与vm联动注入 |
| `testcase/storage/conftest.py` | `bucket`   | `count`: 创建数量 `name`: 自定义名称 `capacity`: 桶容量 | 创建对象存储专业版桶并自动清理，优先复用 autotest-* 空桶 |
| `testcase/storage/conftest.py` | `oss_bucket` | `count`: 创建数量 `name`: 自定义名称 `region`: 区域 `az_strategy`: 数据冗余存储策略 `storage_class`: 默认存储类别 `bucket_strategy`: 桶策略 `is_encryption`: 是否开启默认加密 `data_read`: 归档数据直读 `tags`: 标签列表 | 创建OSS对象存储桶并自动清理，支持多AZ/私有/加密/标签等完整参数 |
| `testcase/storage/conftest.py` | `kms_key`  | 可通过indirect传入engine参数                       | 创建密钥并自动清理      |
| `testcase/storage/conftest.py` | `sfs_instance` | `count`: 创建数量 `name`: 名称前缀 `protocol`: 文件协议（str 或 list） `cluster`: 集群 `network`: 专有网络 `subnet`: 子网 `volume_type`: 云硬盘类型 `volume_size`: 云硬盘大小 `cpu_cores`: CPU 核数 `ram_gb`: 内存 GiB | 创建文件存储 SFS 实例并自动清理；count=1 返回字典，count>1 返回列表，支持为每个实例指定不同协议 |
| `testcase/storage/conftest.py` | `clean_sfs_instances` | 无（注册表模式） | SFS 实例注册表，测试用例动态登记实例名，fixture yield 后统一清理 |


---

### 十三、辅助 Fixture


| 文件名                            | Fixture名称                      | 参数  | 功能说明                   |
| ------------------------------ | ------------------------------ | --- | ---------------------- |
| `testcase/conftest.py`         | `test_context`                 | 无   | 用于在测试用例各步骤间传递数据的上下文字典  |
| `testcase/conftest.py`         | `cleanup`                      | 无   | 延迟清理注册表，登记零参清理闭包，结束后按LIFO兜底执行（依赖page） |
| `testcase/network/_acl_fixtures.py` | `clean_acl_inbound_rules`      | 无   | 清理ACL入方向规则（function级别） |
| `testcase/network/_acl_fixtures.py` | `clean_acl_outbound_rules`     | 无   | 清理ACL出方向规则（class级别）    |
| `testcase/network/_lb_peer_fixtures.py` | `clean_peer_connect`     | 无   | 对等连接与跨VPC路由规则统一清理注册器（先路由后对等连接） |
| `testcase/network/_lb_fixtures.py` | `clean_lb_listener`         | 无（依赖page、ssh_vm） | 负载均衡监听器与公网IP清理注册器 |
| `testcase/network/_lb_fixtures.py` | `clean_ip_group`            | 无   | IP地址组清理注册器             |


---

### 十四、大数据实例 Fixture


| 文件名                            | Fixture名称 | 参数  | 功能说明                       |
| ------------------------------ | --------- | --- | -------------------------- |
| `testcase/bigdata/conftest.py` | `emr`     | 无   | 创建共享E-MapReduce集群实例并自动清理（class级别） |


---

### 十五、容器 Fixture（class级别）


| 文件名                              | Fixture名称       | 参数                                                                              | 功能说明                                   |
| -------------------------------- | --------------- | ------------------------------------------------------------------------------- | -------------------------------------- |
| `testcase/container/conftest.py` | `cce_cluster`   | `name` `node_count`(默认4) `version` `container_runtime` `network_model` `flavor` 等 | 创建CCE集群并等待就绪，返回控制/计算节点信息及MFIP，自动清理 |
| `testcase/container/conftest.py` | `storage_class` | 无（依赖cce_cluster）                                                                | 在CCE集群下创建云硬盘存储类型(StorageClass)并自动清理 |
| `testcase/container/conftest.py` | `scr_instance`  | `name` `version` `cluster` `network` `subnet` `instance_type` `storage_type` 等   | 创建SCR单机实例并等待就绪，返回实例信息，自动清理       |


---

### 十六、IAM Fixture


| 文件名                       | Fixture名称              | 参数  | 功能说明                                          |
| ------------------------- | ---------------------- | --- | --------------------------------------------- |
| `testcase/iam/conftest.py` | `verify_ctx`           | 无   | session级验证上下文，创建时预热避免首次调用超时                |
| `testcase/iam/conftest.py` | `iam_shared_org`       | 无   | package级IAM顶级组织，整个iam测试包共享，最后清理            |
| `testcase/iam/conftest.py` | `iam_shared_child_org` | 无（依赖iam_shared_org） | package级IAM子组织，先于父组织清理            |
| `testcase/iam/conftest.py` | `iam_shared_user`      | 无（依赖iam_shared_child_org） | package级IAM测试用户，所有用户测试共享   |
| `testcase/iam/conftest.py` | `iam_shared_tenant_user` | 无（依赖iam_shared_child_org） | class级租户测试专用用户，与共享用户隔离   |
| `testcase/iam/conftest.py` | `iam_project`          | 无（依赖共享组织） | class级项目资源，项目管理测试类内共享，自动清理           |
| `testcase/iam/conftest.py` | `iam_batch_users`      | 无（依赖iam_shared_child_org） | function级，在共享子组织下创建2个普通用户并自动删除 |


---

### 十七、安全合规 Fixture（session级别）


| 文件名                            | Fixture名称     | 参数                | 功能说明                          |
| ------------------------------ | ------------- | ----------------- | ----------------------------- |
| `testcase/security/conftest.py` | `security_vpc` | 无                 | 创建安全合规测试专用VPC，session级共享，结束后清理 |
| `testcase/security/conftest.py` | `usm_instance` | 无（依赖security_vpc） | 创建USM实例并自动清理，所有USM测试共享        |
| `testcase/security/conftest.py` | `ver_instance` | 无（依赖security_vpc） | 创建VER实例并自动清理，所有VER测试共享        |
| `testcase/security/conftest.py` | `vdb_instance` | 无（依赖security_vpc） | 创建VDB实例并自动清理，所有VDB操作类测试共享     |


---

### 十八、BMS 裸金属 Fixture


| 文件名                            | Fixture名称                       | 参数  | 功能说明                                       |
| ------------------------------ | ------------------------------- | --- | ------------------------------------------ |
| `testcase/compute/conftest.py` | `bms_env`                       | 无（CLI/配置/ENV 覆盖） | session级，返回BMS回归测试基线环境配置（只读） |
| `testcase/compute/conftest.py` | `bms_instance_name`             | 无（依赖bms_env） | session级，返回BMS操作用例复用的实例名称        |
| `testcase/compute/conftest.py` | `bms_image`                     | 无（依赖ssh_host、bms_env） | 确保BMS镜像存在并返回镜像名称（只读，无清理）   |
| `testcase/compute/conftest.py` | `bms_instance`                  | 工厂函数，可传 name/image_name/system_disk 等 | 返回裸金属实例创建器，封装创建+等待运行中 |
| `testcase/compute/conftest.py` | `bms_regression_requires_instance` | 无（autouse=True） | 仅对带 `bms_regression` 标记的用例生效，校验实例存在否则skip |
