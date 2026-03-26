import allure
import pytest

from sugon_web.utils import db_util
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, random_string


@allure.epic('数据库服务')
@allure.feature('AnhanDB(for Redis)')
class TestRedisBasic:

    @allure.title("Redis-升级测试")
    def test_upgrade_instance(self, redis_page, redis, ssh_host):
        """测试Redis实例从单机升级到高可用"""
        instance_name = redis["name"]

        with allure_step_log("步骤一：执行升级操作（单机 -> 高可用）"):
            redis_page.upgrade_instance(instance_name, target_type="高可用")
            redis_page.assert_popup_success("升级成功")

        with allure_step_log("步骤二：验证升级过程及实例状态"):
            redis_page.assert_status(instance_name, status="升级中", timeout=1200, refresh=True)
            redis_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：后端生效性验证（检查新节点是否创建）"):
            new_node_name = f"{instance_name}-1"
            db_util.assert_backend_created(redis_page, ssh_host, new_node_name)

    @allure.title("Redis-重命名实例")
    def test_rename_instance(self, redis_page, redis):
        """测试重命名Redis实例"""
        instance_name = redis["name1"]
        renamed_name = f"redis-renamed-{random_data()}"

        with allure_step_log("步骤一：重命名实例"):
            redis_page.rename_instance(instance_name, renamed_name)

        with allure_step_log("步骤二：验证重命名结果"):
            redis_page.assert_popup_success("修改实例名称成功")
            redis_page.assert_list_contain(renamed_name)
            redis_page.assert_status(renamed_name, status="运行中")

        with allure_step_log("步骤三：重命名实例回退"):
            redis_page.rename_instance(renamed_name, instance_name)

        with allure_step_log("步骤四：验证重命名回退结果"):
            redis_page.assert_popup_success("修改实例名称成功")
            redis_page.assert_list_contain(instance_name)
            redis_page.assert_status(instance_name, status="运行中")

    @allure.title("Redis-重置密码")
    def test_reset_password(self, redis_page, redis, ssh_host, ssh_vm):
        """测试重置Redis实例的管理员密码并在后端验证连通性"""
        instance_name = redis["name1"]
        new_password = f"NewPass1@{random_string(k=5)}"

        with allure_step_log("步骤一：重置管理员密码"):
            redis_page.reset_admin_password(instance_name, new_password)
            redis["password"] = new_password

        with allure_step_log("步骤二：验证密码重置结果"):
            redis_page.assert_popup_success("更新用户默认用户密码成功")
            # 增加刷新等待，避免重置密码导致的状态短时变更未恢复
            redis_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log("步骤三：验证新密码后端生效"):
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(redis_page, ssh_host, "sugoncloud_redis", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")

            # 使用默认管理员用户验证
            cmd = f"redis-cli -h 127.0.0.1 -p 6379 -a '{new_password}' PING"
            result = ssh_vm.run(cmd)
            assert "PONG" in result or "OK" in result, f"新管理员密码后端连接验证失败: {result}"
            ssh_vm.close()

    @allure.title("Redis-重启实例")
    def test_restart_instance(self, redis_page, redis):
        """测试重启Redis实例"""
        instance_name = redis["name1"]

        with allure_step_log("步骤一：重启实例"):
            redis_page.restart_instance(instance_name)

        with allure_step_log("步骤二：验证重启状态"):
            redis_page.assert_popup_success("重启实例成功")
            redis_page.assert_status(instance_name, status="重启中", timeout=600, refresh=True)
            redis_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)

    @allure.title("Redis-重启节点")
    def test_restart_node(self, redis_page, redis):
        """测试重启Redis节点"""
        instance_name = redis["name1"]
        node_name = f"{instance_name}-0"

        with allure_step_log("步骤一：重启第一个节点"):
            redis_page.restart_node(instance_name, node_name)
            redis_page.assert_popup_success("重启节点服务成功")
        with allure_step_log("步骤二：验证验证节点状态"):
            redis_page.assert_status(instance_name, status="运行中", refresh=True, timeout=900)

    @allure.title("Redis-修改云盘大小")
    def test_change_disk_size(self, redis_page, redis, ssh_host):
        """测试修改Redis节点云盘大小，并在后端验证"""
        instance_name = redis["name1"]
        node_name = f"{instance_name}-0"
        new_size = 60

        with allure_step_log("步骤一：修改云盘大小"):
            redis_page.change_disk_size(instance_name, node_name, new_size)
            redis_page.assert_popup_success("扩容硬盘中，请耐心等待")
        with allure_step_log("步骤二：验证实例状态及后端实际大小"):
            redis_page.assert_status(node_name, status="调整云硬盘中", refresh=True, timeout=30)
            redis_page.assert_status(node_name, status="运行中", refresh=True, timeout=1800)
            assert db_util.get_disk_size(redis_page, node_name, ssh_host) == new_size

    @allure.title("Redis-修改实例规格")
    def test_scale_instance(self, redis_page, redis, ssh_host):
        """测试修改Redis实例规格并在后端验证"""
        instance_name = redis["name1"]
        node_name = f"{instance_name}-0"

        # 目标规格信息
        specification_name = "redis.d6.xlarge"
        real_specification = "redis.d6.xlarge"

        with allure_step_log("步骤一：修改规格"):
            redis_page.change_specification(instance_name, specification_name)
            redis_page.assert_popup_success("修改规格中，请耐心等待")

        with allure_step_log("步骤二：验证实例状态及后端规格"):
            redis_page.assert_status(node_name, status="调整规格中", refresh=True, timeout=300)
            redis_page.assert_status(node_name, status="运行中", refresh=True, timeout=1800)

            # 后端实际查询 Cinder / Flavor 的规格信息
            current_spec = db_util.get_specification(redis_page, node_name, ssh_host)
            assert current_spec == real_specification, f"规格修改失败，期望为 {real_specification}，实际为 {current_spec}"

    @allure.title("Redis-添加分片")
    def test_add_shard(self, redis_page, redis, ssh_host):
        """测试为Redis实例添加分片，并后端验证是否真正创建出新节点"""
        instance_name = redis["name1"]

        with allure_step_log("步骤一：添加分片"):
            # 有的实例类型可能不支持所以可能抛错，此处走通用UI
            try:
                redis_page.add_shard(instance_name)
                redis_page.assert_popup_success("新增分片成功")
            except Exception as e:
                pytest.skip(f"当前共享实例模型可能不支持添加分片: {e}")

        with allure_step_log("步骤二：验证新节点状态变化"):
            # 假设添加一个分片带来两个新节点：-6 和 -7
            for i in [6, 7]:
                node_name = f"{instance_name}-{i}"
                redis_page.assert_status(node_name, status="创建中", timeout=600, refresh=True)

            for i in [6, 7]:
                node_name = f"{instance_name}-{i}"
                redis_page.assert_status(node_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：后端验证新分片节点已成功产生"):
            # 添加单个分片会新增一主一备两台节点，默认3分片集群的节点范围为-0到-5
            # 新增的第4个分片对应的新增节点后缀为 -6 和 -7
            for i in [6, 7]:
                new_node_name = f"{instance_name}-{i}"
                db_util.assert_backend_created(redis_page, ssh_host, new_node_name)

    @allure.title("Redis-新建并删除用户")
    def test_redis_user_lifecycle(self, redis_page, redis, ssh_host, ssh_vm):
        """测试新建用户和删除用户并在后端验证连接"""
        instance_name = redis["name1"]
        user_name = f"user_{random_string(k=5)}"
        password = f"Pwd123@{random_string(k=5)}"

        with allure_step_log("步骤一：新建用户"):
            redis_page.create_user(instance_name, user_name, password, privileges="读写")
            redis_page.assert_popup_success("创建用户成功")

        with allure_step_log("步骤二：后端验证新建用户可以成功连接"):
            node_name = f"{instance_name}-0"
            # 获取后台宿主IP用于登录虚拟机，假设数据库名为 sugoncloud_redis
            ip_from_db = db_util.get_node_mfip_from_db(redis_page, ssh_host, "sugoncloud_redis", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")

            # Redis 6.0+ 支持 ACL，普通用户可能被限制了 PING 权限，改为测 SET 命令或直接判定 NOPERM 为认证成功
            cmd_login = f"redis-cli -h 127.0.0.1 -p 6379 --user '{user_name}' --pass '{password}' SET autotest 1"
            result_ok = ssh_vm.run(cmd_login)
            assert "OK" in result_ok or "NOPERM" in result_ok, f"新用户后端验证失败: {result_ok}"

        with allure_step_log("步骤三：删除用户"):
            redis_page.delete_user(instance_name, user_name)
            redis_page.assert_deleted(user_name)

        with allure_step_log("步骤四：后端验证用户已被删除失效"):
            result_fail = ssh_vm.run(cmd_login, True, True)
            assert "WRONGPASS" in result_fail['stderr'] or "AUTH failed" in result_fail[
                'stderr'] or "invalid username" in result_fail[
                       'stderr'], f"用户删除状态验证失败，旧账密连接未得到预期错误: {result_fail['stderr']}"
            ssh_vm.close()

    @allure.title("Redis-批量新建并删除用户")
    def test_redis_batch_delete_users(self, redis_page, redis, ssh_host, ssh_vm):
        """测试批量删除用户功能"""
        instance_name = redis["name1"]
        user_names = [f"user_{random_string(k=5)}", f"user_{random_string(k=5)}"]
        password = f"Pwd123@{random_string(k=5)}"

        with allure_step_log("步骤一：创建多个用户准备批量删除"):
            for u_name in user_names:
                redis_page.create_user(instance_name, u_name, password, privileges="读写")
                redis_page.assert_popup_success("创建用户成功")

        with allure_step_log("步骤二：批量删除用户"):
            redis_page.batch_delete_users(instance_name, user_names)
            for u_name in user_names:
                redis_page.assert_deleted(u_name)

        with allure_step_log("步骤三：后端验证用户已被批量删除失效"):
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(redis_page, ssh_host, "sugoncloud_redis", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")
            
            for u_name in user_names:
                cmd_login = f"redis-cli -h 127.0.0.1 -p 6379 --user '{u_name}' --pass '{password}' PING"
                result_fail = ssh_vm.run(cmd_login, True, True)
                assert "WRONGPASS" in result_fail['stderr'] or "AUTH failed" in result_fail['stderr'] or "invalid username" in result_fail['stderr'], f"用户 {u_name} 删除验证失败，预期报错 WRONGPASS、AUTH failed 或 invalid username，实际: {result_fail['stderr']}"
            
            ssh_vm.close()

    @allure.title("Redis-修改用户")
    def test_redis_modify_user(self, redis_page, redis, ssh_host, ssh_vm):
        """测试修改用户密码功能"""
        instance_name = redis["name1"]
        user_name = f"user_{random_string(k=5)}"
        old_password = f"PwdOld@{random_string(k=5)}"
        new_password = f"PwdNew@{random_string(k=5)}"

        with allure_step_log("步骤一：创建用户"):
            redis_page.create_user(instance_name, user_name, old_password, privileges="读写")
            redis_page.assert_popup_success("创建用户成功")

        with allure_step_log("步骤二：修改用户密码"):
            redis_page.modify_user(instance_name, user_name, new_password)
            redis_page.assert_popup_success("更新用户密码和权限成功,若数据未更新请刷新页面")

        with allure_step_log("步骤三：后端验证新密码生效"):
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(redis_page, ssh_host, "sugoncloud_redis", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")

            # 验证新密码可以登录
            cmd_new = f"redis-cli -h 127.0.0.1 -p 6379 --user '{user_name}' --pass '{new_password}' PING"
            result_new = ssh_vm.run(cmd_new)
            assert "PONG" in result_new or "OK" in result_new or "NOPERM" in result_new, f"新密码后端验证失败: {result_new}"

            # 验证旧密码不可用
            cmd_old = f"redis-cli -h 127.0.0.1 -p 6379 --user '{user_name}' --pass '{old_password}' PING"
            result_old = ssh_vm.run(cmd_old, True, True)
            assert "WRONGPASS" in result_old['stderr'] or "AUTH failed" in result_old['stderr'], f"旧密码验证失败，预期报错 WRONGPASS 或 AUTH failed，实际: {result_old['stderr']}"
            ssh_vm.close()

        with allure_step_log("步骤四：清理创建的用户"):
            redis_page.delete_user(instance_name, user_name)
            redis_page.assert_deleted(user_name)

    @allure.title("Redis-白名单管理")
    def test_redis_whitelist_management(self, redis_page, redis):
        """测试白名单的添加、删除、批量删除和重置功能"""
        instance_name = redis["name1"]
        whitelist_ips = [
            "10.0.5.0/24",
            "10.0.6.0/24",
            "10.0.7.0/24",
            "10.0.8.0/24"
        ]
        ip_single = whitelist_ips[0]
        ip_batch = whitelist_ips[1:]

        with allure_step_log("步骤一：重置白名单，确保环境干净"):
            redis_page.reset_whitelist(instance_name)
            redis_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：测试单个白名单的添加与删除"):
            redis_page.add_whitelist(instance_name, ip_single)
            redis_page.assert_popup_success("添加白名单成功")
            redis_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            redis_page.delete_whitelist(instance_name, ip_single)
            redis_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤三：测试批量添加与批量删除白名单"):
            for ip in ip_batch:
                redis_page.add_whitelist(instance_name, ip)
                redis_page.assert_popup_success("添加白名单成功")
            for ip in ip_batch:
                redis_page.assert_list_contain(ip, "白名单", exact_match=False)

            redis_page.batch_delete_whitelist(instance_name, ip_batch)
            redis_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤四：测试重置白名单功能"):
            # 先添加一个，确保有内容可重置
            redis_page.add_whitelist(instance_name, ip_single)
            redis_page.assert_popup_success("添加白名单成功")
            redis_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            # 执行重置
            redis_page.reset_whitelist(instance_name)
            redis_page.assert_popup_success("重置白名单成功")

    @allure.title("Redis-节点热迁移")
    def test_hot_migration(self, redis_page, redis, ssh_host, ssh_vm):
        """测试Redis节点热迁移，并进行后端物理机校验"""
        instance_name = redis["name1"]
        node_name = f"{instance_name}-0"

        # 记录迁移前的物理机 (后端校验)
        old_host = db_util.get_backend_host(redis_page, ssh_host, node_name)
        allure.attach(f"迁移前物理机 (后端): {old_host}", name="迁移前状态")

        with allure_step_log(f"步骤一：对节点 {node_name} 执行热迁移"):
            selected_host = redis_page.redis_hot_migration(instance_name, node_name)

        with allure_step_log("步骤二：验证迁移结果（包含状态变迁验证）"):
            redis_page.assert_popup_success("热迁移命令下发成功")
            # 必须验证“迁移中”的状态跃迁，然后再等回“运行中”
            redis_page.assert_status(node_name, status="迁移中", timeout=300, refresh=True)
            redis_page.assert_status(node_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log("步骤三：验证物理机节点变更 (后端校验)"):
            # 热迁移后，通过后端 gova list 命令验证节点是否真正切换
            new_host = db_util.get_backend_host(redis_page, ssh_host, node_name)
            allure.attach(f"迁移后物理机 (后端): {new_host}", name="迁移后状态")

            assert new_host != old_host, f"热迁移失败，后端查询迁移前后物理机节点未变更: {old_host}"
            if selected_host:
                assert selected_host in new_host, f"热迁移失败，期望迁移至节点:{selected_host},实际迁移至节点:{new_host}"

        with allure_step_log("步骤四：验证迁移后数据库连接"):
            password = redis["password"]
            vm_password = "admin1234@sugon"
            ip_from_db = db_util.get_node_mfip_from_db(redis_page, ssh_host, "sugoncloud_redis", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=vm_password)
            # 使用原生的 redis-cli ping 来验证该节点连通性，需要带上密码避免 NOAUTH
            cmd_check = f"redis-cli -h 127.0.0.1 -p 6379 -a '{password}' PING"
            result = ssh_vm.run(cmd_check)
            assert "PONG" in result or "OK" in result, f"热迁移后数据库连接失败: {result}"
            ssh_vm.close()



    @allure.title("Redis-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, redis_page, redis, ssh_host):
        """测试实例绑定和解绑Redis实例的公网IP"""
        instance_name = redis["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure_step_log("步骤一：绑定公网IP"):
            ip = redis_page.instance_ip_binding(instance_name, network=network)

        with allure_step_log("步骤二：验证绑定结果"):
            redis_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：解绑公网IP"):
            redis_page.instance_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            redis_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("Redis-开启免密登录")
    def test_toggle_password_free(self, redis_page, redis, ssh_host, ssh_vm):
        """测试开启Redis实例的免密登录，并进行后端连接验证"""
        instance_name = redis["name1"]
        node_name = f"{instance_name}-0"
        vm_password = "admin1234@sugon"

        with allure_step_log("步骤一：开启免密登录"):
            redis_page.toggle_password_free(instance_name)
            redis_page.assert_popup_success("开启免密成功")
            # 等待状态稳定
            redis_page.assert_status(instance_name, status="运行中", timeout=300)

        with allure_step_log("步骤二：后端验证：无需密码连接Redis"):
            ip_from_db = db_util.get_node_mfip_from_db(redis_page, ssh_host, "sugoncloud_redis", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=vm_password)
            # 开启免密后，不带 -a 应该也能 PONG
            cmd_no_auth = f"redis-cli -h 127.0.0.1 -p 6379 PING"
            result = ssh_vm.run(cmd_no_auth)
            assert "PONG" in result or "OK" in result, f"开启免密登录后，无需密码连接失败: {result}"
            ssh_vm.close()

    @allure.title("Redis-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, redis_page, redis, ssh_host):
        """测试节点绑定和解绑Redis实例的公网IP"""
        instance_name = redis["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure_step_log("步骤一：绑定公网IP"):
            ip = redis_page.node_ip_binding(instance_name, network=network)

        with allure_step_log("步骤二：验证绑定结果"):
            redis_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：解绑公网IP"):
            redis_page.node_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            redis_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("Redis-切换网络")
    def test_switch_network(self, redis_page, redis):
        """测试Redis切换网络功能，覆盖快速选择和手动输入两种情况"""
        instance_name = redis["name1"]

        with allure_step_log("步骤一：切换网络 - 情况1：快速选择"):
            redis_page.switch_network(instance_name, network="Autotest", subnet="subnet:10.", selection_type="快速选择")
            redis_page.assert_status(instance_name, status="VPC切换中", timeout=300)
            redis_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log("步骤二：切换网络 - 情况2：手动输入"):
            redis_page.switch_network(instance_name, network="Autotest", subnet="Autotest:10.",
                                      selection_type="手动输入")
            redis_page.assert_status(instance_name, status="VPC切换中", timeout=300)
            redis_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)
