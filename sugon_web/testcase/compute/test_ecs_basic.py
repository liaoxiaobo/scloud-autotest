import re
import time
import pytest
import allure
from sugon_web.testcase.conftest import ecs_page
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data

@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
@allure.story('基本功能验证')
class TestECSBasic:

    @allure.title(f"弹性云服务器-电源操作功能验证")
    @pytest.mark.parametrize("params", load_data('test_ecs_operations', "test_ecs.yaml"))
    def test_ecs_operations(self, ecs_page, vm, ssh_host,ssh_vm, params):
        ecs_page.goto_service('弹性云服务器')
        name = vm.get("name")
        ecs_id = vm.get("id")

        # operation: 操作; desc: 操作描述; status: 操作后状态; vm_state: 物理机上虚拟机状态
        vm_state = params.get("vm_state")
        operation = params.get("operation")
        desc = params.get("desc")
        staus = params.get("status")

        with allure_step_log(f"步骤1: {name}{operation}"):
            ecs_page.ecs_operations(name, operation)

        with allure_step_log(f"步骤2: 验证{name}{operation}结果"):
            ecs_page.assert_popup_success(f"{name}{desc}", timeout=60)
            ecs_page.assert_status(name, status=staus)
            stdout = ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}"))
            assert stdout.get("vm_state") == vm_state, f"{name}状态变更失败"
            if vm_state == "active":
                time.sleep(5)
                ssh_vm.connect(vm['mfip'])
                ecs_page.assert_ecs_enable(name, ssh_vm)

    @allure.title("弹性云服务器-编辑功能验证")
    def test_ecs_edit(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        new_name = random_data()
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log("步骤1: 编辑弹性云服务器"):
            ecs_page.ecs_edit(name, new_name)

        with allure_step_log("步骤2: 验证编辑结果"):
            ecs_page.assert_popup_success("更新实例成功")
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run("hostname") == name, f"编辑后虚拟机hostname变更，原始主机名:{name},编辑后主机名:{ssh_vm.run('hostname')}"

        with allure_step_log("步骤3: 清理测试数据"):
            ecs_page.ecs_edit(new_name, name)

    @allure.title("弹性云服务器-克隆功能验证")
    def test_ecs_clone(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 虚拟机{name}系统盘写入数据，记录MD5"):
            ssh_vm.connect(vm['mfip'])
            md5 = ssh_vm.create_file(f"/home/{name}")

        with allure_step_log(f"步骤2: 克隆弹性云服务器{name}"):
            clone_name = random_data()
            ecs_page.ecs_clone(name, clone_name, 'Autotest', 'Autotest', {})

        with allure_step_log(f"步骤3: 验证克隆结果{clone_name}"):
            ecs_page.assert_popup_success(f"{name}实例克隆成功")
            image_name = ecs_page.get_row_data(name).get("镜像名称")
            ecs_page.assert_status(clone_name)
            ecs_page.assert_image_name(clone_name, image_name)

            # 克隆后的虚机绑定mfip，验证md5值
            clone_ip = ecs_page.get_row_data(clone_name).get("IP地址").split(':')[1]
            mfip = ecs_page.bind_mfip(clone_ip.strip())
            ssh_vm.connect(mfip)
            md5_new = ssh_vm.run(f"md5sum /home/{name}")
            assert md5_new.count(md5), f"克隆后系统盘数据MD5不一致，原始数据:{md5},克隆后数据:{md5_new}"

        with allure_step_log(f"步骤4: 清理测试数据{clone_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_remove(clone_name)
            ecs_page.ecs_delete(clone_name)
            ecs_page.assert_deleted(clone_name)

    @allure.title("弹性云服务器-重建云服务器功能验证")
    def test_ecs_rebuild(self, ecs_page, vm, ssh_vm):
        image = ecs_page.storage_pool   # 获取存储池同名镜像
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 虚拟机{name}系统盘写入数据，记录MD5"):
            ssh_vm.connect(vm['mfip'])
            ssh_vm.create_file(f"/home/{name}-1")

        with allure_step_log(f"步骤2: 重建云服务器{name}"):
            ecs_page.ecs_rebuild(name, 'centos7.9', '64位', image)

        with allure_step_log("步骤3: 验证重建结果"):
            ecs_page.assert_popup_success(f"{name}实例重建成功")
            ecs_page.assert_status(name, status="重建中")
            ecs_page.assert_status(name)
            ssh_vm.connect(vm['mfip'])
            md5_new = ssh_vm.run(f"md5sum /home/{name}-1")
            assert md5_new.find("No such file or directory"), f"重建后系统盘数据MD5仍然存在，重建后数据:{md5_new}"

    @allure.title("弹性云服务器-修改规格功能验证")
    @pytest.mark.parametrize("spec", load_data('test_ecs_modify_spec', "test_ecs.yaml"))
    def test_ecs_modify_spec(self, ecs_page, vm, ssh_host, spec):
        name = vm.get("name")
        cpu = spec.get("CPU", "2")
        mem = spec.get("Mem", "4")
        ecs_id = vm.get("id")
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: {name}修改规格:{spec.get('desc')}"):
            ecs_page.ecs_modify_spec(name, spec)

        with allure_step_log("步骤2: 验证修改结果"):
            ecs_page.assert_popup_success("调整实例资源配置成功")
            ecs_page.assert_ecs_info(name, "规格", f"{cpu} 核 {mem}.00 GiB")
            stdout = ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}"))
            assert stdout.get("vcpu") == cpu
            assert stdout.get("memory_mb") == str(int(mem) * 1024)

    @allure.title("弹性云服务器-加载/卸载网卡功能验证")
    @pytest.mark.parametrize("network_info", load_data('test_ecs_network', "test_ecs.yaml"))
    def test_ecs_network(self, ecs_page, vm, ssh_vm, network_info):
        name = vm.get("name")
        net = network_info.get("net")
        subnet = network_info.get("subnet")
        mode = network_info.get("mode")
        ipv4 = network_info.get("ipv4")
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: {name}加载网卡: 网络{net}，子网{subnet}"):
            checked_subnet =  ecs_page.ecs_load_network(name, net, subnet, mode, ipv4)

        with allure_step_log("步骤2: 验证加载网卡结果"):
            ecs_page.assert_popup_success(f"{name}实例，连接{subnet}子网成功", timeout=30)
            ips = ecs_page.get_row_data(name).get("IP地址").split(':')
            ip = [item.strip() for item in ips if re.search(fr'{checked_subnet}.\d', item)][0].split(' ')[0].strip()
            ssh_vm.connect(vm['mfip'])
            ssh_vm.ping(ip)

        with allure_step_log(f"步骤3: {name}卸载网卡:{ip}"):
            ecs_page.ecs_uninstall_network(name, ip)

        with allure_step_log("步骤4: 验证加载网卡结果"):
            ecs_page.assert_popup_success(f"断开网络成功", timeout=60)
            ecs_page.assert_ecs_info(name, "IP地址", "")
            ssh_vm.connect(vm['mfip'])
            ssh_vm.ping(ip, connected=False)

    @allure.title("弹性云服务器-绑定/解绑公网IP功能验证")
    def test_ecs_pub_ip(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 云服务器{name}绑定公网IP"):
            pub_ip = ecs_page.ecs_bind_pub_ip(name)

        with (allure_step_log("步骤2: 验证绑定公网IP结果")):
            ecs_page.assert_popup_success(f"执行成功")
            ecs_page.assert_ecs_info(name, "IP地址", pub_ip)
            ssh_vm.connect(vm['mfip'])
            ssh_vm.ping(pub_ip)

        with allure_step_log(f"步骤3: 云服务器{name}解绑公网IP{pub_ip}"):
            ecs_page.ecs_unbind_pub_ip(name, pub_ip)
            ecs_page.assert_popup_success(f"执行成功")

        with allure_step_log("步骤4: 验证解绑公网IP结果"):
            ecs_page.assert_ecs_info_not_contains(name, "IP地址", pub_ip)
            ssh_vm.connect(vm['mfip'])
            ssh_vm.ping(pub_ip, connected=False)

    @allure.title("弹性云服务器-修改密码功能验证")
    def test_ecs_modifypwd(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")

        with allure_step_log(f"步骤1: 云服务器{name}修改密码"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.assert_status(name, refresh=True)
            ecs_page.ecs_modify_pwd(name, "sugon@21", "sugon@21")

        with allure_step_log("步骤2: 验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改密码成功")
            ssh_vm.connect(vm['mfip'], pwd="sugon@21")
            assert ssh_vm.run("hostname") == name, f"修改密码后，无法登录虚拟机"

        with allure_step_log(f"步骤3: 云服务器{name}还原密码"):
            ecs_page.ecs_modify_pwd(name, "admin1234@sugon", "admin1234@sugon")

        with allure_step_log("步骤4: 验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改密码成功")
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run("hostname") == name, f"还原密码后，无法登录虚拟机"

    @allure.title("弹性云服务器-修改主机名功能验证")
    def test_ecs_modify_hostname(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        hostname = random_data()
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 云服务器{name}修改主机名"):
            ecs_page.ecs_modify_hostname(name, hostname)

        with (allure_step_log("步骤2: 验证修改主机名结果")):
            ecs_page.assert_popup_success(f"更新实例成功")
            # 重启虚机，等待主机名变更
            ecs_page.ecs_operations(name, "重启")
            ecs_page.assert_status(name)
            ssh_vm.connect(vm['mfip'])
            ecs_page.wait_for_update(ssh_vm, "hostname", hostname, timeout=90)
            assert ssh_vm.run("hostname") == hostname,\
            f"主机名未变更，修改后期望主机名:{hostname},实际主机名:{ssh_vm.run('hostname')}"

    @allure.title("弹性云服务器-时间同步服务器功能验证")
    def test_ecs_time_synchronize(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        time_server = "100.126.255.250"
        interval = "30"
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 验证时间同步服务器功能"):
            ssh_vm.connect(vm['mfip'])
            # 修改系统时间为一个错误的时间
            ssh_vm.run('date -s "2010-01-01"')
            assert ssh_vm.run("date").count("2010")

        with allure_step_log(f"步骤2: 弹性云服务器{name}配置时间同步服务器"):
            ecs_page.ecs_time_synchronize(name, time_server, interval)

        with allure_step_log("步骤3: 验证时间同步服务器结果"):
            ecs_page.assert_popup_success("修改时间同步服务器成功")
            ecs_page.logger.info(f"等待{interval}秒，等待时间同步完成")
            time.sleep(int(interval))  # 等待时间同步完成
            # 验证时间是否同步成功
            ssh_vm.connect(vm['mfip'])
            expection = time.strftime("%Y", time.localtime())
            ecs_page.wait_for_update(ssh_vm, "date", expection, timeout=150)
            actual = ssh_vm.run("date")
            assert actual.count(expection), f"同步时间服务器失败，期望时间:{expection},实际时间:{actual}"

    @allure.title("弹性云服务器-绑定/解绑亲和组功能验证")
    @pytest.mark.parametrize("vm", [{"count": 3, "bind_mfip": False}], indirect=True)
    def test_ecs_bind_unbind_group(self, ecs_page, vm, ssh_host):
        policy = "亲和"
        if isinstance(vm, list) and len(vm) > 1:
            names = [vm[i].get("name") for i in range(len(vm))]
            ecs_ids = [vm[i].get("id") for i in range(len(vm))]
        else:
            names = [vm.get("name")]
            ecs_ids = vm.get("id")
        group_name = f"{random_data(length=2)}-{policy}"

        with allure_step_log(f"步骤1: 创建{policy}组: {group_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_create_affinity_group(group_name, policy)

        with allure_step_log(f"步骤2: 验证{policy}组创建结果"):
            ecs_page.assert_popup_success("执行成功")
            assert ecs_page.get_row_data(group_name).get("策略") == policy, \
                f"创建亲和组失败，期望策略:{policy},实际策略:{ecs_page.get_row_data(group_name).get('策略')}"

        with allure_step_log(f"步骤3: 云服务器{names}绑定{policy}组并验证绑定结果"):
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_page.ecs_bind_unbind_group(names, "绑定亲和组", group_name)

        with allure_step_log(f"步骤4: 云服务器{names}批量迁移"):
            ecs_page.ecs_batch_migration(names)

        with allure_step_log(f"步骤5: 验证批量迁移结果"):
            nodes = []
            for name in names:
                ecs_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=2)
            for name, ecs_id in zip(names, ecs_ids):
                ecs_page.assert_status(name, status="当前无任务")
                nodes.append(ecs_page.get_row_data(names[0]).get("物理机"))

            if policy == "亲和":
                assert len(set(nodes)) == 1, f"云服务器{name}未迁移到同一节点"
            else:
                assert len(set(nodes)) > 1, f"云服务器{name}未迁移到不同节点"

        with allure_step_log(f"步骤6: 云服务器{names}解绑{policy}组"):
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.ecs_bind_unbind_group(names, "解绑亲和组", group_name)

        with allure_step_log(f"步骤7: 云服务器{names}批量迁移"):
            ecs_page.ecs_batch_migration(names)

        with allure_step_log(f"步骤8: 验证批量迁移结果"):
            nodes = []
            for name, ecs_id in zip(names, ecs_ids):
                ecs_page.assert_status(name, status="当前无任务", refresh=True)
                nodes.append(ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}")).get("node"))
            assert len(set(nodes)) >= 1

        with allure_step_log(f"步骤9: 删除{policy}组: {group_name}"):
            ecs_page.ecs_delete_affinity_group(group_name)
            ecs_page.assert_deleted(group_name, refresh= True)

    @allure.title("弹性云服务器-列表页搜索&重置")
    def test_ecs_search(self, ecs_page, vm):
        ecs_page.goto_submenu("弹性云服务器")

        with allure_step_log("步骤1: 输入名称进行搜索"):
            keyword = vm['name'][:-2]
            ecs_page.search(keyword)
            ecs_page.assert_list_contain(keyword, column_name="名称/ID", exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            ecs_page.btn_reset.click()
            ecs_page.wait_for_page_ready()
            # 断言重置后搜索输入框已清空
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("弹性云服务器-镜像创建功能验证")
    def test_ecs_create_image(self, ecs_page, vm, ssh_vm):
        """测试从现有云服务器创建镜像"""
        name = vm.get("name")
        image_name = random_data(length=10)
        ecs_page.goto_service("弹性云服务器")

        with allure_step_log(f"步骤1: 弹性云服务器{name}新建镜像{image_name}"):
            ssh_vm.connect(vm['mfip'])
            md5 = ssh_vm.create_file(name)
            ecs_page.ecs_create_image(name, image_name)

        with allure_step_log("步骤2: 验证创建结果"):
            ecs_page.assert_popup_success("创建实例镜像成功")
            ecs_page.assert_status(name, "创建镜像中")
            ecs_page.assert_status(name, "当前无任务")
            ecs_page.goto_submenu("镜像服务")
            ecs_page.assert_status(image_name, status="可用", refresh=True)

        with allure_step_log(f"步骤3: 使用镜像{image_name}创建弹性云服务器{name}-1"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.wait_for_operation_complete()
            ecs_page.ecs_create(f"{name}-1", image_name=image_name)
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(f"{name}-1")

        with allure_step_log(f"步骤4: 验证{name}-1 md5值是否一致"):
            ip = ecs_page.get_row_data(f"{name}-1").get("IP地址").split(":")[1].strip()
            mfip_new = ecs_page.bind_mfip(ip)
            ssh_vm.connect(mfip_new)
            assert ssh_vm.run(f"md5sum {name}").count(md5), \
                f"新创建的云服务器的md5值{ssh_vm.run(f'md5sum {name}')}与源云服务器{md5}不一致"

        with allure_step_log("步骤5: 清理测试数据"):
            # 删除测试云服务器
            ecs_page.goto_service("弹性云服务器")
            ecs_page.wait_for_operation_complete()
            ecs_page.ecs_remove(f"{name}-1")
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(f"{name}-1")
            # 删除测试镜像
            ecs_page.goto_submenu("镜像服务")
            ecs_page.ecs_image_delete(image_name)
            ecs_page.assert_deleted(image_name, refresh=True)

    @allure.title("弹性云服务器-创建亲和组功能验证")
    def test_ecs_create_affinity_group(self, ecs_page):
        policy = "亲和"
        name = f"{random_data(length=2)}-{policy}"

        with allure_step_log(f"步骤1: 创建亲和组: {name}"):
            ecs_page.ecs_create_affinity_group(name, policy)

        with allure_step_log("步骤2: 验证创建结果"):
            ecs_page.assert_popup_success("执行成功")
            assert ecs_page.get_row_data(name).get("策略") == policy, \
                f"创建亲和组失败，期望策略:{policy},实际策略:{ecs_page.get_row_data(name).get('策略')}"

        with allure_step_log(f"步骤3: 删除亲和组: {name}"):
            ecs_page.ecs_delete_affinity_group(name)
            ecs_page.assert_deleted(name, refresh=True)


    @allure.title("弹性云服务器-批量操作功能验证")
    @pytest.mark.parametrize("vm", [{"count": 3, "bind_mfip": False}], indirect=True)
    @pytest.mark.parametrize("operations", load_data("test_ecs_batch_operations", "test_ecs.yaml"))
    def test_ecs_batch_operations(self, ecs_page, vm, ssh_host, operations):
        names = [vm[i].get("name") for i in range(len(vm))]
        ecs_ids = [vm[i].get("id") for i in range(len(vm))]
        operation = operations.get("operation")
        status = operations.get("status")
        vm_state = operations.get("vm_state")

        with allure_step_log(f"步骤1: 弹性云服务器{names}{operation}"):
            ecs_page.ecs_batch_operations(names, operation=operation)

        with allure_step_log(f"步骤2: 验证{operation}结果"):
            for name, ecs_id in zip(names, ecs_ids):
                ecs_page.assert_status(name, status=status)
                stdout = ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}"))
                assert stdout.get("vm_state") == vm_state, f"批量操作{operation}失败，期望vm_state:{vm_state},实际vm_state:{stdout.get('vm_state')}"

    @allure.title("弹性云服务器-批量迁移功能验证")
    @pytest.mark.parametrize("vm", [{"count": 3, "bind_mfip": True}], indirect=True)
    def test_ecs_batch_migration(self, ecs_page, vm, ssh_host, ssh_vm):
        """
        测试弹性云服务器的批量热迁移和冷迁移功能
        """
        ecs_page.wait_for_page_ready()
        names = [vm[i].get("name") for i in range(len(vm))]
        ecs_ids = [vm[i].get("id") for i in range(len(vm))]
        pids = []

        with allure_step_log("步骤1: 虚机长ping"):
            for i in range(len(names)):
                ssh_vm.connect(vm[i]['mfip'])
                ssh_vm.run(r"nohup ping 100.126.255.250 -i 1 > /tmp/ping.log 2>&1 &")
                # 然后获取进程ID
                pid_output = ssh_vm.run(r"pgrep -f 'ping 100.126.255.250'")
                # 验证是否成功获取PID
                if not pid_output or not pid_output.strip():
                    raise Exception("无法获取ping进程ID")
                pids.append(pid_output.strip())

        with allure_step_log("步骤2: 批量迁移"):
            ecs_page.ecs_batch_migration(names)

        with allure_step_log("步骤3: 验证迁移结果"):
            for name in names:
                ecs_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=2)

            for name,ecs_id in zip(names,ecs_ids):
                ecs_page.assert_status(name, status="当前无任务")
                # 验证迁移后页面展示的物理机节点 和 通过gova show 获取的物理机节点是否一致
                expect_node = ecs_page.get_row_data(name).get("物理机")
                assert ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}")).get("node") == expect_node
            # 验证虚机长ping 迁移丢包率
            for i in range(len(names)):
                ssh_vm.connect(vm[i]['mfip'])
                ssh_vm.run(f"kill -2 {pids[i]}")
                ping_output = ssh_vm.run("cat /tmp/ping.log")
                loss = re.search(r"transmitted, (.*?) received", ping_output).group(1)
                send = re.search(r"(.*?) packets transmitted,", ping_output).group(1)
                assert int(send) - int(loss) <= 5

    @allure.title("弹性云服务器-系统盘扩容功能验证")
    def test_ecs_expand_system_disk(self, ecs_page, vm, ssh_host, ssh_vm):
        """测试弹性云服务器系统盘扩容功能"""
        name = vm.get("name")
        ecs_id  = vm.get("id")
        new_size = "110"

        with allure_step_log(f"步骤1: 扩容云服务器{name}系统盘至{new_size}GiB"):
            ecs_page.ecs_expand_system_disk(name, new_size)

        with allure_step_log("步骤2: 验证扩容结果"):
            ecs_page.assert_ecs_info(name, "系统盘", f"容量(GiB):{new_size}")

            # 验证扩容后页面展示的系统盘大小 和 通过gova show 获取的系统盘大小是否一致
            stdout = ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}"))
            assert stdout.get("root_gb") == new_size, \
                f"扩容系统盘失败，期望系统盘大小:{new_size}GiB,实际系统盘大小:{stdout.get('root_gb')}GiB"

            # 验证扩容后页面展示的系统盘大小 和 虚机中的系统盘大小是否一致
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"lsblk | grep '^vda' | awk '{{print $4}}'").count(new_size), \
                f"扩容系统盘失败，云服务器{name}系统盘大小不一致"

    @allure.title("弹性云服务器-挂载/卸载云硬盘功能验证")
    def test_ecs_mount_unmount_volume(self, ecs_page, vm, volume, ssh_vm):
        """测试云硬盘的挂载和卸载功能"""

        ecs_page.goto_service('弹性云服务器')
        vm_name = vm.get("name")
        volume_name = volume.get("name")
        disk_name = ""

        with allure_step_log(f"步骤1: 挂载云硬盘{volume_name}到服务器{vm_name}"):
            ecs_page.ecs_mount_to_server(volume_name, vm_name)

        with allure_step_log(f"步骤2: 验证挂载结果"):
            ecs_page.assert_popup_success(f"挂载云硬盘到虚拟机{vm_name}成功")
            assert ecs_page.get_row_data(vm_name).get("挂载云硬盘") == volume_name
            assert ecs_page.get_row_data(vm["name"]).get("挂载云硬盘").split(" ")[-1] == volume_name

            # 云硬盘页面验证 云硬盘状态=正在使用
            ecs_page.goto_service("云硬盘")
            ecs_page.goto_submenu("云硬盘")
            ecs_page.assert_status(volume["name"], status="正在使用", refresh=True)

            # 验证挂载后页面展示的挂载信息 和 虚机中的挂载信息是否一致
            disk_name = ecs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"lsblk | grep {disk_name}") != ""

        with allure_step_log(f"步骤3: 从服务器{vm_name}卸载云硬盘{volume_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_unmount_from_server(volume_name, vm_name)

        with allure_step_log(f"步骤4: 验证卸载结果"):
            assert ecs_page.get_row_data(vm_name).get("挂载云硬盘") == "--"
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"lsblk | grep {disk_name}") == ""

    @allure.title("弹性云服务器-热迁移功能验证")
    def test_ecs_hot_migration(self, ecs_page, vm, ssh_vm, ssh_host):
        """
        测试弹性云服务器的热迁移功能
        """
        ecs_page.goto_service('弹性云服务器')
        name = vm.get("name")
        ecs_id = vm.get("id")

        with allure_step_log("步骤1: 虚机长ping"):
            ssh_vm.connect(vm['mfip'])
            ssh_vm.run(r"nohup ping 100.126.255.250 -i 1 > /tmp/ping.log 2>&1 &")
            # 然后获取进程ID
            pid_output = ssh_vm.run(r"pgrep -f 'ping 100.126.255.250'")
            # 验证是否成功获取PID
            if not pid_output or not pid_output.strip():
                raise Exception("无法获取ping进程ID")
            pid = pid_output.strip()

        with allure_step_log("步骤2: 热迁移"):
            check_node = ecs_page.ecs_hot_migration(name, "master01")

        with allure_step_log("步骤3: 验证迁移结果"):
            ecs_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=2)
            ecs_page.assert_status(name, status="当前无任务")

            # 验证迁移后页面展示的物理机节点 和 通过gova show 获取的物理机节点是否一致
            expect_node = ecs_page.get_row_data(name).get("物理机")
            assert expect_node == check_node, f"热迁移失败，期望迁移至节点:{check_node},实际迁移至节点:{expect_node}"
            assert ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}")).get("node") == check_node

            # 验证长ping迁移丢包率
            ssh_vm.connect(vm['mfip'])
            ssh_vm.run(f"kill -2 {pid}")
            ping_output = ssh_vm.run("cat /tmp/ping.log")
            loss = re.search(r"transmitted, (.*?) received", ping_output).group(1)
            send = re.search(r"(.*?) packets transmitted,", ping_output).group(1)
            assert int(send) - int(loss) <= 5

    @allure.title("弹性云服务器-冷迁移功能验证")
    def test_ecs_cold_migration(self, ecs_page, vm, ssh_vm, ssh_host):
        """
        测试弹性云服务器的热迁移功能
        """
        ecs_page.goto_service('弹性云服务器')
        ecs_page.wait_for_page_ready()
        name = vm.get("name")
        ecs_id = vm.get("id")
        with allure_step_log("步骤1: 冷迁移"):
            check_node = ecs_page.ecs_cold_migration(name, "master01")

        with allure_step_log("步骤2: 验证迁移结果"):
            ecs_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=2)
            ecs_page.assert_status(name, status="当前无任务")

            # 验证迁移后页面展示的物理机节点 和 通过gova show 获取的物理机节点是否一致
            expect_node = ecs_page.get_row_data(name).get("物理机")
            assert expect_node == check_node, f"热迁移失败，期望迁移至节点:{check_node},实际迁移至节点:{expect_node}"
            assert ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}")).get("node") == check_node

            # 验证迁移后虚机的可用性
            ssh_vm.connect(vm['mfip'])
            ecs_page.assert_ecs_enable(name, ssh_vm)

    @allure.title("弹性云服务器-CPU QoS修改功能验证")
    @pytest.mark.parametrize("qos_data", load_data('test_ecs_cpu_qos', "test_ecs.yaml"))
    def test_ecs_cpu_qos(self, ecs_page, vm, ssh_host, qos_data):
        """测试云服务器CPU QoS修改功能"""
        name = vm.get("name")
        ecs_id = vm.get("id")
        priority = qos_data.get("priority")
        ceiling = qos_data.get("ceiling")

        with allure_step_log("步骤1: 修改云服务器CPU QoS"):
            ecs_page.ecs_modify_cpu_qos(name, priority, ceiling)

        with allure_step_log("步骤2: 验证修改结果"):
            stdout = ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}"))
            # exception: CPU QoS修改成功后，gova show 获取的CPU QoS信息
            #        K: "quota:cpu_quota"、"quota:cpu_shares"、"quota:cpu_period"
            for k, v in qos_data.get("expection").items():
                assert v == stdout.get(k), f"修改云服务器CPU QoS失败，期望{k}:{v},实际{k}:{stdout.get(k)}"

    @allure.title("弹性云服务器-挂载CD-ROM功能验证")
    def test_ecs_mount_cdrom(self, ecs_page, vm, ssh_vm):
        """测试弹性云服务器挂载CD-ROM功能"""
        name = vm.get("name")
        with allure_step_log("步骤1: 为云服务器挂载CD-ROM"):
            ecs_page.ecs_mount_cdrom(name)

        with allure_step_log(f"步骤2: 验证虚机{name}挂载CD-ROM结果"):
            ecs_page.assert_popup_success(f"挂载CD-ROM到虚拟机{name}成功")
            ecs_page.assert_status(name, status="挂载CD-ROM中")
            ecs_page.assert_status(name, status="当前无任务")

            # 验证CD-ROM已成功挂载
            cdrom_name = ecs_page.get_row_data(name).get("挂载云硬盘")
            assert cdrom_name.startswith("cdrom-")

            # 验证云硬盘状态
            ecs_page.goto_service("云硬盘")
            ecs_page.goto_submenu("云硬盘")
            ecs_page.assert_status(cdrom_name, status="正在使用", refresh=True)

        with allure_step_log(f"步骤3: 后台验证虚机{name}挂载CD-ROM结果"):
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"lsblk | grep sr | awk '{{print $4}}'").count("20G")
            ssh_vm.run(f"mkdir /mnt/{name}")
            ssh_vm.run(f"mount /dev/sr0 /mnt/{name}")
            assert ssh_vm.run(f"ls /mnt/{name}") != ""

        with allure_step_log(f"步骤4: 卸载CD-ROM"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_unmount_cdrom(name, cdrom_name)

        with allure_step_log(f"步骤5: 验证虚机{name}卸载CD-ROM结果"):
            ecs_page.assert_popup_success(f"从虚拟机{name}卸载CD-ROM成功")
            assert ecs_page.get_row_data(name).get("挂载云硬盘") == "--"
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"ls /mnt/{name}") == ""

    @allure.title("弹性云服务器-批量设置启动顺序功能验证")
    @pytest.mark.parametrize("vm", [{"count": 2, "bind_mfip": False}], indirect=True)
    @pytest.mark.parametrize("operation",["关机","启动"])
    def test_ecs_batch_set_boot_order(self, ecs_page, vm, operation):
        names = [[vm[i].get("name")] for i in range(len(vm))]
        delay = "20"
        with allure_step_log(f"步骤1: 批量设置{operation}顺序"):
            for i, name in enumerate(names, start=1):
                if operation == "关机":
                    ecs_page.ecs_batch_set_shutdown_order(name, i, delay)
                else:
                    ecs_page.ecs_batch_set_startup_order(name, i, delay)

        with allure_step_log(f"步骤2: 进入云服务器详情页面验证顺序及{operation}延迟"):
            for i, name in enumerate(names, start=1):
                ecs_page.assert_ecs_details_info(name, info_items={f"{operation}顺序": str(i), f"{operation}延迟时间(秒)": delay})
                ecs_page.ecs_back_to_list()

        with allure_step_log(f"步骤3: 批量{operation}"):
            names = [name[0] for name in names]
            ecs_page.ecs_batch_operations(names, f"批量{operation}")
            ecs_page.assert_popup_success(f"执行成功")

        with allure_step_log(f"步骤4: 验证{operation}结果"):
            for name in names:
                if operation == "关机":
                    ecs_page.assert_status(name, status="电源关闭中", refresh=True, refresh_interval=1)
                    ecs_page.assert_status(name, status="关机", refresh_interval=1)
                else:
                    ecs_page.assert_status(name, status="电源打开中", refresh=True, refresh_interval=1)
                    ecs_page.assert_status(name)
                time.sleep(int(delay)/2)

    @allure.title("弹性云服务器-修改密码及登录VNC功能验证")
    def test_ecs_modify_vncpwd(self, ecs_page, vm):
        ecs_page.goto_service('弹性云服务器')
        name = vm.get("name")
        with allure_step_log(f"步骤1: 云服务器{name}修改VNC密码"):
            ecs_page.ecs_modify_vnc_pwd(name, "sugon@21", "sugon@21")

        with allure_step_log("步骤2: 验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改vnc密码成功")
            ecs_page.ecs_vnc(name, "sugon@21")

        with allure_step_log(f"步骤3: 云服务器{name}还原VNC密码"):
            ecs_page.ecs_modify_vnc_pwd(name, "sugon@20", "sugon@20")

        with allure_step_log("步骤4: 验证还原密码结果"):
            ecs_page.assert_popup_success(f"修改vnc密码成功")

    @allure.title("弹性云服务器-设置启动顺序功能验证")
    @pytest.mark.parametrize("volume", [{"count": 1, "empty": False}], indirect=True)
    def test_ecs_set_boot_order(self, ecs_page, vm, volume):
        """测试设置云服务器启动顺序功能"""
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')
        volume_name = volume.get("name")
        with allure_step_log("步骤1: 挂载云硬盘到"):
            ecs_page.ecs_mount_to_server(volume_name, name)

        with allure_step_log("步骤2: 设置云服务器启动顺序"):
            ecs_page.ecs_set_boot_order(name, [{"磁盘": "30G"}])

        with allure_step_log("步骤3: 验证启动顺序设置结果"):
            ecs_page.assert_popup_success("设置实例启动顺序成功")
            ecs_page.ecs_operations(name, "强制重启")
            ecs_page.assert_popup_success(f"{name}实例强制重启成功", timeout=60)

        with allure_step_log("步骤4: 验证云服务器详情页中的启动顺序信息"):
            ecs_page.ecs_vnc(name)