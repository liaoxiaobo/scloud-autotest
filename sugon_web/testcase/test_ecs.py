import re
import time
import pytest
import allure
from sugon_web.utils.util import random_data, load_data


@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
class TestECS:

    @allure.title("弹性云服务器-创建功能验证")
    def test_ecs_create(self, ecs_page):
        name = random_data()

        with allure.step("创建云服务器"):
            ecs_page.ecs_create(name=name)

        with allure.step("验证创建结果"):
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(name)

        with allure.step("清理测试数据"):
            ecs_page.ecs_remove(name)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(name)

    @allure.title(f"弹性云服务器-电源操作功能验证")
    @pytest.mark.parametrize("params", load_data('test_ecs_operations', "test_ecs.yaml"))
    def test_ecs_operations(self, ecs_page, vm, ssh_host,ssh_vm, params):
        ecs_page.goto_service('弹性云服务器')
        name = vm.get("name")
        ecs_id = vm.get("id").split(':')[1]
        vm_state = params.get("vm_state")
        operation = params.get("operation")
        desc = params.get("desc")
        staus = params.get("status")
        with allure.step(f"步骤1: {name}{operation}"):
            ecs_page.ecs_operations(name, operation)
        with allure.step(f"步骤2: 验证{name}{operation}结果"):
            ecs_page.assert_popup_success(f"{name}{desc}", timeout=60)
            ecs_page.assert_status(name, status=staus)
            stdout = ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}"))
            assert stdout.get("vm_state") == vm_state, f"{name}状态变更失败"
            if vm_state == "active":
                ssh_vm.connect(vm['mfip'])
                ecs_page.assert_ecs_enable(name, ssh_vm)

    @allure.title("弹性云服务器-编辑功能验证")
    def test_ecs_edit(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        new_name = random_data()
        ecs_page.goto_service('弹性云服务器')
        with allure.step("步骤1: 编辑弹性云服务器"):
            ecs_page.ecs_edit(name, new_name)

        with allure.step("步骤2: 验证编辑结果"):
            ecs_page.assert_popup_success("更新实例成功")
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run("hostname") == name, f"编辑后虚拟机hostname变更，原始主机名:{name},编辑后主机名:{ssh_vm.run('hostname')}"

        with allure.step("步骤3: 清理测试数据"):
            ecs_page.ecs_edit(new_name, name)

    @allure.title("弹性云服务器-登录VNC功能验证")
    def _test_ecs_vnc(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        with allure.step("步骤1: 登录VNC"):
            ecs_page.ecs_vnc(name, "sugon@20")

    @allure.title("弹性云服务器-克隆功能验证")
    def test_ecs_clone(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')
        with allure.step(f"步骤1: 虚拟机{name}系统盘写入数据，记录MD5"):
            ssh_vm.connect(vm['mfip'])
            ssh_vm.run("dd if=/dev/zero of=/home/test1 bs=4k count=1048576")
            md5 = ssh_vm.run("md5sum /home/test1")

        with allure.step(f"步骤2: 克隆弹性云服务器{name}"):
            clone_name = random_data()
            ecs_page.ecs_clone(name, clone_name, 'Autotest', 'Autotest', {})

        with allure.step(f"步骤3: 验证克隆结果{clone_name}"):
            ecs_page.assert_popup_success(f"{name}实例克隆成功")
            image_name = ecs_page.get_row_data(name).get("镜像名称")
            ecs_page.assert_status(clone_name)
            ecs_page.assert_image_name(clone_name, image_name)
            clone_ip = ecs_page.get_row_data(clone_name).get("IP地址").split(':')[1]
            mfip = ecs_page.bind_mfip(clone_ip.strip())
            ssh_vm.connect(mfip)
            md5_new = ssh_vm.run("md5sum /home/test1")
            assert md5 == md5_new, f"克隆后系统盘数据MD5不一致，原始数据:{md5},克隆后数据:{md5_new}"

        with allure.step(f"步骤4: 清理测试数据{clone_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_remove(clone_name)
            ecs_page.ecs_delete(clone_name)
            ecs_page.assert_deleted(clone_name)

    @allure.title("弹性云服务器-重建云服务器功能验证")
    def test_ecs_rebuild(self, ecs_page, vm, ssh_vm):
        image = ecs_page.storage_pool   # 获取存储池同名镜像
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')
        with allure.step(f"步骤1: 虚拟机{name}系统盘写入数据，记录MD5"):
            ssh_vm.connect(vm['mfip'])
            ssh_vm.run("dd if=/dev/zero of=/home/test1 bs=4k count=1048576")
        with allure.step(f"步骤2: 重建云服务器{name}"):
            ecs_page.ecs_rebuild(name, 'centos7.9', '64位', image)

        with allure.step("步骤3: 验证重建结果"):
            ecs_page.assert_popup_success(f"{name}实例重建成功")
            ecs_page.assert_status(name, status="重建中")
            ecs_page.assert_status(name)
            ssh_vm.connect(vm['mfip'])
            md5_new = ssh_vm.run("md5sum /home/test1")
            assert md5_new.find("No such file or directory"), f"重建后系统盘数据MD5仍然存在，重建后数据:{md5_new}"

    @allure.title("弹性云服务器-修改规格功能验证")
    @pytest.mark.parametrize("spec", load_data('test_ecs_modify_spec', "test_ecs.yaml"))
    def test_ecs_modify_spec(self, ecs_page, vm, ssh_host, spec):
        name = vm.get("name")
        cpu = spec.get("CPU", "2")
        mem = spec.get("Mem", "4")
        ecs_id = vm.get("id").split(':')[1]
        ecs_page.goto_service('弹性云服务器')
        with allure.step(f"步骤1: {name}修改规格:{spec.get('desc')}"):
            ecs_page.ecs_modify_spec(name, spec)
        with allure.step("步骤2: 验证重建结果"):
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

        with allure.step(f"步骤1: {name}加载网卡: 网络{net}，子网{subnet}"):
            ecs_page.ecs_load_network(name, net, subnet, mode, ipv4)
        with allure.step("步骤2: 验证加载网卡结果"):
            ecs_page.assert_popup_success(f"{name}实例，连接{subnet}子网成功", timeout=30)
            ips = ecs_page.get_row_data(name).get("IP地址").split(':')
            ip = [item.strip() for item in ips if re.search(r'10\.228\.43\.\d', item)][0].split(' ')[0].strip()
            ssh_vm.connect(vm['mfip'])
            ssh_vm.ping(ip)

        with allure.step(f"步骤3: {name}卸载网卡:{ip}"):
            ecs_page.ecs_uninstall_network(name, ip)
        with allure.step("步骤4: 验证加载网卡结果"):
            ecs_page.assert_popup_success(f"断开网络成功", timeout=60)
            ecs_page.assert_ecs_info(name, "IP地址", "")
            ssh_vm.connect(vm['mfip'])
            ssh_vm.ping(ip, connected=False)

    @allure.title("弹性云服务器-绑定/解绑公网IP功能验证")
    def test_ecs_pub_ip(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')
        with allure.step(f"步骤1: 云服务器{name}绑定公网IP"):
            pub_ip = ecs_page.ecs_bind_pub_ip(name)
        with (allure.step("步骤2: 验证绑定公网IP结果")):
            ecs_page.assert_popup_success(f"执行成功")
            ecs_page.assert_ecs_info(name, "IP地址", pub_ip)
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"ping -c 3 {pub_ip}").count(
                "3 received, 0% packet loss"), f"加载公网IP后，无法ping通IP:{pub_ip}"

        with allure.step(f"步骤3: 云服务器{name}解绑公网IP{pub_ip}"):
            ecs_page.ecs_unbind_pub_ip(name, pub_ip)
            ecs_page.assert_popup_success(f"执行成功")
        with allure.step("步骤4: 验证解绑公网IP结果"):
            ecs_page.assert_ecs_info_not_contains(name, "IP地址", pub_ip)
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"ping -c 3 {pub_ip}").count(
                "0 received, 100% packet loss"), f"卸载公网IP后，仍可ping通IP:{pub_ip}"

    @allure.title("弹性云服务器-修改密码功能验证")
    def test_ecs_modifypwd(self, ecs_page, vm):
        name = vm.get("name")
        with allure.step(f"云服务器{name}修改密码"):
            ecs_page.assert_status(name)
            ecs_page.ecs_modify_pwd(name, "sugon@21", "sugon@21")
        with allure.step("验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改密码成功")

        with allure.step(f"云服务器{name}还原密码"):
            ecs_page.ecs_modify_pwd(name, "admin1234@sugon", "admin1234@sugon")
        with allure.step("验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改密码成功")

    @allure.title("弹性云服务器-修改密码功能验证")
    def test_ecs_modify_vncpwd(self, ecs_page, vm):
        name = vm.get("name")
        with allure.step(f"云服务器{name}修改VNC密码"):
            ecs_page.assert_status(name)
            ecs_page.ecs_modify_vnc_pwd(name, "sugon@21", "sugon@21")
        with allure.step("验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改vnc密码成功")

        with allure.step(f"云服务器{name}还原VNC密码"):
            ecs_page.ecs_modify_vnc_pwd(name, "sugon@20", "sugon@20")
        with allure.step("验证还原密码结果"):
            ecs_page.assert_popup_success(f"修改vnc密码成功")

    @allure.title("弹性云服务器-修改主机名功能验证")
    def test_ecs_modify_hostname(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        hostname = random_data()
        ecs_page.goto_service('弹性云服务器')
        with allure.step(f"步骤1: 云服务器{name}修改主机名"):
            ecs_page.ecs_modify_hostname(name, hostname)
        with (allure.step("步骤2: 验证修改主机名结果")):
            ecs_page.assert_popup_success(f"更新实例成功")
            ssh_vm.connect(vm['mfip'])
            ecs_page.wait_for_update(ssh_vm.run("hostname",return_rc=True), hostname, timeout=120)
            assert ssh_vm.run("hostname") == hostname,\
            f"主机名未变更，修改后期望主机名:{hostname},实际主机名:{ssh_vm.run('hostname')}"

    @allure.title("弹性云服务器-时间同步服务器功能验证")
    def test_ecs_time_synchronize(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        time_server = "100.126.255.250"
        interval = "30"
        ecs_page.goto_service('弹性云服务器')
        with allure.step(f"步骤1: 验证时间同步服务器功能"):
            ssh_vm.connect(vm['mfip'])
            # 修改系统时间为一个错误的时间
            ssh_vm.run('date -s "2010-01-01"')
            assert ssh_vm.run("date").count("2010")
        with allure.step(f"步骤2: 弹性云服务器{name}配置时间同步服务器"):
            ecs_page.ecs_time_synchronize(name, time_server, interval)
        with allure.step("步骤3: 验证时间同步服务器结果"):
            ecs_page.assert_popup_success("修改时间同步服务器成功")
            ecs_page.logger.info(f"等待{interval}秒，等待时间同步完成")
            time.sleep(int(interval))  # 等待时间同步完成
            ssh_vm.connect(vm['mfip'])
            expection = time.strftime("%Y", time.localtime())
            ecs_page.wait_for_update(ssh_vm.run("date", return_rc=True), expection, timeout=30)
            actual = ssh_vm.run("date")
            assert actual.count(expection), f"同步时间服务器失败，期望时间:{expection},实际时间:{actual}"

    @allure.title("弹性云服务器-绑定/解绑亲和组功能验证")
    @pytest.mark.parametrize("params", load_data('test_ecs_bind_unbind_group', "test_ecs.yaml"))
    def test_ecs_bind_unbind_group(self, ecs_page, vm, params):
        name = vm.get("name")
        operation = params.get("operation")
        group_name = params.get("group_name")
        with allure.step(f"步骤1: 云服务器{name}{operation}"):
            ecs_page.assert_status(name)
            ecs_page.ecs_bind_unbind_group(name, operation, group_name)
        with allure.step(f"步骤2: 验证{operation}结果"):
            ecs_page.assert_popup_success(f"{name}实例{operation}成功")

    @allure.title("弹性云服务器-列表页搜索&重置")
    def test_ecs_search(self, ecs_page, vm):

        with allure.step("步骤1: 输入名称进行搜索"):
            ecs_page.goto_submenu("弹性云服务器")
            keyword = vm['name'][:-2]
            ecs_page.search(keyword)
            ecs_page.assert_list_contain(keyword, column_name="名称/ID", exact_match=False)

        with allure.step("步骤2: 重置搜索条件"):
            ecs_page.btn_reset.click()
            ecs_page.wait_for_page_ready()
            # 断言重置后搜索输入框已清空
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
@allure.story('回收站功能验证')
class TestEcsRecycle:

    @allure.title("回收站-恢复弹性云服务器")
    def test_ecs_recycle_recover(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')
        with allure.step(f"步骤1: 虚拟机{name}系统盘写入数据，记录MD5"):
            ssh_vm.connect(vm['mfip'])
            md5 = ssh_vm.create_file(name)

        with allure.step(f"步骤2: 删除云服务器{name}"):
            ecs_page.ecs_remove(name)
            time.sleep(3)
            ecs_page.assert_deleted(name)

        with allure.step("步骤3: 恢复弹性云服务器"):
            ecs_page.goto_submenu("回收站")
            ecs_page.ecs_recover(name)
            ecs_page.assert_popup_success(f"移出回收站成功")
            ecs_page.assert_deleted(name)

        with allure.step("步骤4: 验证恢复结果"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.wait_for_operation_complete()
            ecs_page.assert_status(name, refresh=True)
            ssh_vm.connect(vm['mfip'])
            ecs_page.assert_ecs_enable(name, ssh_vm, timeout=90)
            assert ssh_vm.run(f"md5sum {name}").count(md5), "恢复后系统盘数据MD5不一致"
            assert ssh_vm.create_file(name) is not None, "恢复后系统盘数据不能写入"

    @allure.title("回收站-列表页搜索&重置")
    def test_ecs_recycle_search(self, ecs_page, vm):
        name = vm.get("name")
        with allure.step(f"步骤1: 删除云服务器{name}"):
            ecs_page.ecs_remove(name)
            time.sleep(1)
            ecs_page.assert_deleted(name)

        with allure.step("步骤2: 输入名称进行搜索"):
            ecs_page.goto_submenu("回收站")
            keyword = vm['name'][:-2]
            ecs_page.search(keyword)
            ecs_page.assert_list_contain(keyword, exact_match=False)

        with allure.step("步骤3: 重置搜索条件"):
            ecs_page.btn_reset.click()
            ecs_page.wait_for_page_ready()
            # 断言重置后搜索输入框已清空
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure.step("步骤4: 恢复弹性云服务器"):
            ecs_page.goto_submenu("回收站")
            ecs_page.ecs_recover(name)
            ecs_page.assert_popup_success(f"移出回收站成功")
            ecs_page.assert_deleted(name)
            ecs_page.goto_service('弹性云服务器')
            ecs_page.assert_status(name, refresh=True)

    @allure.title("回收站-删除弹性云服务器")
    def test_ecs_recycle_remove(self, ecs_page, ssh_host):
        name = random_data()
        with allure.step("步骤1: 创建云服务器并验证创建结果"):
            ecs_page.ecs_create(name=name)
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(name)
            ecs_id = ecs_page.get_row_data(name).get("名称/ID").split(':')[1]

        with allure.step(f"步骤2: 删除云服务器{name}"):
            ecs_page.ecs_remove(name)
            ecs_page.wait_for_operation_complete()
            ecs_page.assert_deleted(name)

        with allure.step("步骤2: 验证删除结果"):
            ecs_page.ecs_recover_delete(name)
            ecs_page.assert_deleted(name)
            assert ssh_host.run(f"gova show {ecs_id}").count("不存在或已删除"), f"删除后云服务器{name}仍存在"


    @allure.title("回收站-批量删除弹性云服务器")
    def test_ecs_recycle_batch_remove(self, ecs_page, ssh_host):
        """测试弹性云服务器批量删除功能"""

        # 批量创建弹性云服务器用于测试
        ecs_names = []
        ids = []
        with allure.step("步骤1: 批量创建弹性云服务器"):
            base_name = random_data()
            ecs_page.ecs_create(
                base_name,
                count=3
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")

            # 生成批量创建的云硬盘名称列表
            for i in range(3):
                name = f"{base_name}-{i}"
                ecs_names.append(name)
                ids.append(ecs_page.get_row_data(name).get("名称/ID").split(':')[1])

            # 验证所有弹性云服务器创建成功
            for name, ecs_id in zip(ecs_names, ids):
                ecs_page.assert_status(name)
                stdout = ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}"))
                assert stdout.get("vm_state") == "active", f"{name}后台状态不是active，状态为:{stdout.get('vm_state')}"

        # 批量回收弹性云服务器
        with allure.step("步骤2: 批量回收弹性云服务器"):
            ecs_page.ecs_batch_operations(ecs_names, "批量删除")

        # 批量删除回收站中的弹性云服务器
        with allure.step("步骤3: 批量删除回收站中的弹性云服务器"):
            ecs_page.ecs_recover_batch_delete(ecs_names)

        with allure.step("步骤4: 验证删除结果"):
            ecs_page.wait_for_operation_complete()
            # 验证弹性云服务器已彻底删除
            for name, ecs_id in zip(ecs_names, ids):
                ecs_page.assert_deleted(name)
                assert ssh_host.run(f"gova show {ecs_id}").count("不存在或已删除"), f"删除后云服务器{name}仍存在"

@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
@allure.story('快照基本功能验证')
class TestECSS:

    @allure.title("弹性云服务器-创建&删除快照")
    def test_ecs_system_snapshot(self, ecs_page, vm, ssh_host):
        """测试创建云服务器快照"""
        snapshot_name = f"snapshot_{vm['name']}"

        with allure.step("步骤1: 创建系统盘快照"):
            ecs_page.ecss_create(
                name=vm['name'],
                snapshot_name=snapshot_name,
                desc="系统盘快照测试"
            )
            ecs_page.assert_popup_success("创建实例快照成功")
            ecs_page.assert_status(vm['name'], status="当前无任务")

        with allure.step("步骤2: 验证快照创建成功"):
            # 切换到快照页面
            ecs_page.goto_submenu("快照")
            ecs_page.assert_status(snapshot_name, status="可用", refresh=True)

            # 验证快照属性
            snapshot_data = ecs_page.get_row_data(snapshot_name)
            assert snapshot_data["是否快照数据卷"] == "否"
            assert snapshot_data["是否启动源"] == "是"

        with allure.step("步骤3: 删除系统盘快照"):
            # 删除快照
            ecs_page.ecss_delete(snapshot_name)

        with allure.step("步骤4: 验证快照已删除"):
            ecs_page.assert_deleted(snapshot_name, refresh=True)    # 刷新页面，确保删除成功
            assert ssh_host.run(f"glance image-list| grep {snapshot_name}") == "", "底层未删除成功"

    @allure.title("弹性云服务器-批量删除快照")
    def test_ecs_batch_snapshot(self, ecs_page, vm, ssh_host):
        """测试批量删除云服务器快照"""
        snapshot_names = []

        with allure.step("步骤1: 批量创建快照"):
            # 创建多个快照
            for i in range(3):
                snapshot_name = f"snapshot_{random_data()}"
                snapshot_names.append(snapshot_name)

                ecs_page.ecss_create(
                    name=vm["name"],
                    snapshot_name=snapshot_name,
                )
                ecs_page.assert_popup_success("创建实例快照成功")
                ecs_page.assert_status(vm["name"], status="当前无任务")

        with allure.step("步骤2: 验证所有快照创建成功"):
            # 切换到快照页面
            ecs_page.goto_submenu("快照")
            ecs_page.assert_status(snapshot_names, status="可用", refresh=True)

        with allure.step("步骤3: 批量删除快照"):
            # 批量删除快照
            ecs_page.ecss_delete(snapshot_names)

        with allure.step("步骤4: 验证所有快照已删除"):
            ecs_page.assert_deleted(snapshot_names, refresh=True)
            assert ssh_host.run(f"glance image-list| grep {snapshot_name}") == "", "底层未删除成功"

    @allure.title("弹性云服务器-修改快照")
    @pytest.mark.parametrize("params", load_data('test_modify'))
    def test_ecss_modify(self, ecs_page, ecss: dict, params):
        """测试云服务器快照修改功能"""

        new_name = ecss["name"] + params["name_suffix"]
        new_desc = params["new_desc"]

        with allure.step("步骤1: 修改云服务器快照的名称和描述"):
            ecs_page.ecss_edit(ecss["name"], new_name, new_desc)
            ecs_page.assert_popup_success("修改快照成功")

        with allure.step("步骤2: 验证修改结果"):
            ecs_page.assert_list_contain(new_name)
            # 获取修改后的快照数据并验证
            snapshot_data = ecs_page.get_row_data(new_name)
            assert snapshot_data["描述"] == new_desc

    @allure.title("弹性云服务器-还原快照")
    def test_ecss_restore(self, ecs_page, vm, ecss: dict, ssh_vm):
        """测试云服务器快照还原功能"""

        with allure.step("步骤1: 虚机打快照后，在root目录下写测试文件"):
            # 连接虚拟机
            ssh_vm.connect(vm['mfip'])

            # 在root目录下创建测试文件
            test_file = "/root/test_restore_file.txt"
            ssh_vm.create_file(test_file)
            ssh_vm.file_exist(test_file)

        with allure.step("步骤2: 虚机还原快照"):

            # 还原快照
            ecs_page.ecss_restore(ecss["name"])
            ecs_page.assert_popup_success(f"{vm['name']}实例还原快照成功")

        with allure.step("步骤3: 页面验证快照还原结果"):
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.assert_status(vm['name'], status="快照还原中")
            ecs_page.assert_status(vm['name'], status="当前无任务")
            data = ecs_page.get_row_data(vm['name'])
            assert data["镜像名称"] == ecss["name"]

        with allure.step("步骤4: 验证虚机内测试文件已不存在"):
            # 重新连接虚拟机
            ssh_vm.connect(vm['mfip'])
            ssh_vm.file_not_exist(test_file)

        with allure.step("步骤5: 重建虚机并删除快照"):
            image = ecs_page.storage_pool  # 获取存储池同名镜像
            if ecs_page.env["stor"] not in ["usan", "local", "nfs"]:     # 虚机有快照时，不支持重建
                ecs_page.ecs_rebuild(vm['name'], 'centos7.9', '64位', image)
                ecs_page.assert_status(vm['name'], status="当前无任务")
                ecs_page.page.wait_for_timeout(5000)    # 延迟5秒，再去清理快照数据

    @allure.title("云服务器快照-列表页搜索&重置")
    def test_ecss_search(self, ecs_page, ecss: dict):

        with allure.step("步骤1: 输入名称进行搜索"):
            keyword = ecss['name'][:-2]
            ecs_page.search(keyword)

        with allure.step("步骤2: 验证搜索结果"):
            ecs_page.assert_list_contain(keyword, exact_match=False)

        with allure.step("步骤3: 重置搜索条件"):
            ecs_page.search(random_data())
            ecs_page.btn_reset.click()
            ecs_page.wait_for_page_ready()

        with allure.step("步骤4: 验证重置结果"):
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"
            assert len(ecs_page.table_rows) > 0, "重置后列表数据为空"

    @allure.title("快照策略-创建&删除")
    @pytest.mark.parametrize("params", load_data('test_create_policies'))
    def test_ecss_policy_create(self, ecs_page, params):
        """测试云服务器快照策略创建功能"""
        # 提取参数
        name = params.get("name")
        enabled = params.get("enabled")
        hours = params.get("hours")
        cycle_days = params.get("cycle_days")
        retention_type = params.get("retention_type")
        retention_value = params.get("retention_value", 1)
        snapshot_data_disk = params.get("snapshot_data_disk")

        # 创建快照策略
        with allure.step("步骤1: 创建快照策略"):
            ecs_page.ecss_policy_create(
                name=name,
                enabled=enabled,
                hours=hours,
                cycle_days=cycle_days,
                retention_type=retention_type,
                retention_value=retention_value,
                snapshot_data_disk=snapshot_data_disk
            )

            # 验证创建结果
            ecs_page.assert_popup_success("执行成功")

        with allure.step("步骤2: 删除快照策略"):
            ecs_page.ecss_policy_delete([name])
            ecs_page.assert_popup_success("删除策略成功")
            ecs_page.assert_deleted(name)

    @allure.title("快照策略-批量删除")
    def test_ecss_policy_batch_delete(self, ecs_page):

        policy_names = []
        with allure.step("步骤1: 创建多个快照策略"):
            for i in range(3):
                name = random_data()
                policy_names.append(name)
                ecs_page.ecss_policy_create(
                    name=name,
                    hours=[0, 1, 2],
                    enabled=True,
                    cycle_days=1,
                    retention_type="按数量",
                    retention_value=5
                )
                ecs_page.assert_popup_success("执行成功")

        with allure.step("步骤2: 批量删除快照策略"):
            ecs_page.ecss_policy_delete(policy_names)
            # evs_page.assert_popup_success()

        with allure.step("步骤3: 验证快照策略已删除"):
            ecs_page.assert_deleted(policy_names)

    @allure.title("快照策略-列表页搜索&重置")
    def test_ecss_policy_search(self, ecs_page, ecss_policy):
        """测试云服务器快照策略搜索功能"""

        with allure.step("步骤1: 输入名称进行搜索"):
            keyword = ecss_policy["name"][:-2]  # 取策略名称的前几个字符作为关键词
            ecs_page.search(keyword)
            ecs_page.assert_list_contain(keyword, exact_match=False, column_name="名称/ID")

        with allure.step("步骤2: 重置搜索条件"):
            ecs_page.btn_reset.click()
            ecs_page.wait_for_page_ready()
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"


