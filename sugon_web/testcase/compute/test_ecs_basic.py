import re
import time
import pytest
import allure
from sugon_web.common.mfip_helper import MfipHelper
from sugon_web.config.config import Config
from sugon_web.testcase.compute._ecs_helpers import collect_vm_metadata
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data, load_data, retry_check
from sugon_web.utils.decorators import skip_stor, skip_if_nodes_less_than, skip_arch


@allure.story('基本功能验证')
class TestECSBasic:

    @allure.title("弹性云服务器-电源操作")
    @pytest.mark.parametrize("params", load_data('test_ecs_operations', "test_ecs.yaml"))
    def test_ecs_operations(self, ecs_page, vm, ssh_host, ssh_vm, params):
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
            ssh_host.assert_guest_fields(ecs_id, {"vm_state": vm_state}, f"{name}状态变更失败")
            if vm_state == "active":
                time.sleep(5)
                ssh_vm.connect(vm['mfip'])
                ecs_page.assert_ecs_enable(name, ssh_vm)

    @allure.title("弹性云服务器-关机和启动")
    def test_ecs_off_start(self, ecs_page, vm, ssh_host, ssh_vm):
        name = vm.get("name")
        ecs_id = vm.get("id")
        ecs_page.goto_service('弹性云服务器')
        with allure_step_log(f"步骤1: {name}关机"):
            ecs_page.ecs_operations(name, "关机")

        with allure_step_log(f"步骤2: 验证{name}关机结果"):
            ecs_page.assert_popup_success(f"{name}实例关机任务下发成功", timeout=60)
            ecs_page.assert_status(name, status="关机")
            ssh_host.assert_guest_fields(ecs_id, {"vm_state": "stopped"}, f"{name}状态变更失败")

        with allure_step_log(f"步骤3: {name}启动"):
            ecs_page.ecs_operations(name, "启动")

        with allure_step_log(f"步骤4: 验证{name}启动结果"):
            ecs_page.assert_popup_success(f"{name}实例启动任务下发成功")
            ecs_page.assert_status(name)
            ssh_host.assert_guest_fields(ecs_id, {"vm_state": "active"}, f"{name}状态变更失败")
            time.sleep(5)
            ssh_vm.connect(vm['mfip'])
            ecs_page.assert_ecs_enable(name, ssh_vm)

    @allure.title("弹性云服务器-挂起和恢复运行")
    def test_ecs_suspend_resume(self, ecs_page, vm, ssh_host, ssh_vm):
        name = vm.get("name")
        ecs_id = vm.get("id")
        ecs_page.goto_service('弹性云服务器')
        with allure_step_log(f"步骤1: {name}挂起"):
            ecs_page.ecs_operations(name, "挂起")

        with allure_step_log(f"步骤2: 验证{name}挂起结果"):
            ecs_page.assert_popup_success(f"{name}实例挂起任务下发成功", timeout=60)
            ecs_page.wait_for_source_complete(name)
            ecs_page.assert_status(name, status="挂起")
            ssh_host.assert_guest_fields(ecs_id, {"vm_state": "suspended"}, f"{name}状态变更失败")

        with allure_step_log(f"步骤3: {name}恢复运行"):
            ecs_page.ecs_operations(name, "恢复运行")

        with allure_step_log(f"步骤4: 验证{name}恢复运行结果"):
            ecs_page.assert_popup_success(f"{name}实例恢复运行任务下发成功")
            # ecs_page.wait_for_source_complete(name)
            ecs_page.assert_status(name)
            ssh_host.assert_guest_fields(ecs_id, {"vm_state": "active"}, f"{name}状态变更失败")
            time.sleep(5)
            ssh_vm.connect(vm['mfip'])
            ecs_page.assert_ecs_enable(name, ssh_vm)

    @allure.title("弹性云服务器-暂停和取消暂停")
    def test_ecs_pause_resume(self, ecs_page, vm, ssh_host, ssh_vm):
        name = vm.get("name")
        ecs_id = vm.get("id")
        ecs_page.goto_service('弹性云服务器')
        with allure_step_log(f"步骤1: {name}暂停"):
            ecs_page.ecs_operations(name, "暂停")

        with allure_step_log(f"步骤2: 验证{name}暂停结果"):
            ecs_page.assert_popup_success(f"{name}实例暂停任务下发成功", timeout=60)
            ecs_page.assert_status(name, status="暂停")
            ssh_host.assert_guest_fields(ecs_id, {"vm_state": "paused"}, f"{name}状态变更失败")

        with allure_step_log(f"步骤3: {name}取消暂停"):
            ecs_page.ecs_operations(name, "取消暂停")

        with allure_step_log(f"步骤4: 验证{name}取消暂停结果"):
            ecs_page.assert_popup_success(f"{name}实例恢复运行任务下发成功")
            ecs_page.wait_for_source_complete(name)
            ecs_page.assert_status(name)
            ssh_host.assert_guest_fields(ecs_id, {"vm_state": "active"}, f"{name}状态变更失败")
            time.sleep(5)
            ssh_vm.connect(vm['mfip'])
            ecs_page.assert_ecs_enable(name, ssh_vm)

    @allure.title("弹性云服务器-重置状态")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}}], indirect=True)
    def test_ecs_reset_status(self, ecs_page, vm, ssh_vm, ssh_host):
        """弹性云服务器-重置状态功能验证"""
        name = vm.get("name")
        ecs_id = vm.get("id")
        mfip = vm.get("mfip")
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 修改云服务器{name}状态为错误，重置状态"):
            sql_statement = f"UPDATE instances SET vm_state = 'error' WHERE uuid = '{ecs_id}'"
            ssh_host.run_sql("gova", sql_statement)
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.btn_refresh.click()
            ecs_page.ecs_operations(name, "重置状态")
            ecs_page.assert_popup_success(f"{name}实例重置状态任务下发成功")

        with allure_step_log(f"步骤2: 验证重置状态结果"):
            ecs_page.assert_status(name)
            ssh_host.assert_guest_fields(ecs_id, {"vm_state": "active"}, "重置状态验证失败")
            ssh_vm.connect(mfip)
            ecs_page.assert_ecs_enable(name, ssh_vm)

    @allure.title("弹性云服务器-编辑")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}}], indirect=True)
    def test_ecs_edit(self, ecs_page, vm, ssh_vm):
        new_name = random_data(length=4)
        name = vm.get("name")
        mfip = vm.get("mfip")
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log("步骤1: 编辑弹性云服务器"):
            ecs_page.ecs_edit(name, new_name)

        with allure_step_log("步骤2: 验证编辑结果"):
            ecs_page.assert_popup_success("更新实例成功")
            ssh_vm.connect(mfip)
            retry_check(lambda: ssh_vm.run("hostname"), expected=name, max_retries=3, interval=30)

        with allure_step_log("步骤3: 验证虚拟机hostname"):
            ecs_page.ecs_edit(new_name, name)

    @allure.title("弹性云服务器-克隆")
    def test_ecs_clone(self, ecs_page, vm, ssh_vm, admin_browser_context, config, ssh_host):
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
            ecs_page.wait_for_source_complete(clone_name)
            ecs_page.assert_status(clone_name)
            ecs_page.assert_image_name(clone_name, image_name)

            # 克隆后的虚机绑定mfip，验证md5值
            clone_meta = collect_vm_metadata(ecs_page, ssh_host, clone_name)
            mfip = MfipHelper.bind_mfip_with_admin_context(
                admin_browser_context, config, clone_meta["port_id"],
                project_id=clone_meta.get("project_id", "admin-inner-project"),
            )
            ssh_vm.connect(mfip)
            md5_new = ssh_vm.run(f"md5sum /home/{name}")
            assert md5 in md5_new, f"克隆后系统盘数据MD5不一致，原始数据:{md5},克隆后数据:{md5_new}"

        with allure_step_log(f"步骤4: 清理测试数据{clone_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_remove(clone_name)
            ecs_page.ecs_delete(clone_name)
            ecs_page.assert_deleted(clone_name)

    @allure.title("弹性云服务器-重建")
    def test_ecs_rebuild(self, ecs_page, vm, ssh_vm):
        image = ecs_page.storage_pool   # 获取存储池同名镜像
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 虚拟机{name}系统盘写入数据，记录MD5"):
            ssh_vm.connect(vm['mfip'])
            ssh_vm.create_file(f"/home/{name}-1")

        with allure_step_log(f"步骤2: 重建云服务器{name}"):
            ecs_page.ecs_rebuild(name, image)

        with allure_step_log("步骤3: 验证重建结果"):
            ecs_page.assert_popup_success(f"{name}实例重建成功")
            ecs_page.assert_status(name)
            ssh_vm.connect(vm['mfip'])
            md5_new = ssh_vm.run(f"md5sum /home/{name}-1")
            assert md5_new.find("No such file or directory"), f"重建后系统盘数据MD5仍然存在，重建后数据:{md5_new}"

    @allure.title("弹性云服务器-绑定和解绑公网IP")
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

    @allure.title("弹性云服务器-修改规格")
    @pytest.mark.parametrize("spec", load_data('test_ecs_modify_spec', "test_ecs.yaml"))
    def test_ecs_modify_spec(self, ecs_page, vm, ssh_host, spec):
        name = vm.get("name")
        cpu = spec.get("CPU", "2")
        mem = spec.get("Mem", "4")
        ecs_id = vm.get("id")
        need_shutdown = spec.get("shutdown", False)
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: {name}修改规格:{spec.get('desc')}"):
            if need_shutdown:
                ecs_page.ecs_operations(name, "关机")
                ecs_page.assert_status(name, "关机")
            ecs_page.ecs_modify_spec(name, spec)
            if need_shutdown:
                ecs_page.ecs_operations(name, "启动")
                ecs_page.assert_status(name)

        with allure_step_log("步骤2: 验证修改结果"):
            ecs_page.assert_ecs_info(name, "规格", f"{cpu} 核 {mem}.00 GiB")
            ssh_host.assert_guest_fields(ecs_id, {"vcpu": cpu, "memory_mb": str(int(mem) * 1024)}, f"{name}修改规格失败")

    @allure.title("弹性云服务器-修改CPU QoS")
    @pytest.mark.parametrize("qos_data", load_data('test_ecs_cpu_qos', "test_ecs.yaml"))
    def test_ecs_cpu_qos(self, ecs_page, vm, ssh_host, qos_data):
        """测试云服务器CPU QoS修改功能"""
        name = vm.get("name")
        ecs_id = vm.get("id")
        priority = qos_data.get("priority")
        ceiling = qos_data.get("ceiling")

        with allure_step_log("步骤1: 修改云服务器CPU QoS"):
            ecs_page.ecs_modify_cpu_qos(name, priority, ceiling)
            ecs_page.assert_popup_success(f"设置cpu-qos成功")

        with allure_step_log("步骤2: 验证修改结果"):
            stdout = ssh_host.guest_show(ecs_id)
            # exception: CPU QoS修改成功后，scli guest show 获取的CPU QoS信息
            #        K: "quota:cpu_quota"、"quota:cpu_shares"、"quota:cpu_period"
            for k, v in qos_data.get("expection").items():
                assert v == stdout.get(k), f"修改云服务器CPU QoS失败，期望{k}:{v},实际{k}:{stdout.get(k)}"

    @allure.title("弹性云服务器-设置启动顺序")
    @pytest.mark.parametrize("volume", [{"count": 1, "empty": False}], indirect=True)
    def test_ecs_set_boot_order(self, ecs_page, vm, volume):
        """测试设置云服务器启动顺序功能"""
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')
        volume_name = volume.get("name")
        with allure_step_log(f"步骤1: 挂载云硬盘{volume_name}到云服务器{name}"):
            ecs_page.ecs_mount_to_server(volume_name, name)

        with allure_step_log(f"步骤2: 设置云服务器{name}启动顺序"):
            ecs_page.ecs_set_boot_order(name, [{"磁盘": "30G"}])

        with allure_step_log("步骤3: 验证启动顺序设置结果"):
            ecs_page.assert_popup_success("设置实例启动顺序成功")
            ecs_page.ecs_operations(name, "强制重启")
            ecs_page.wait_for_source_complete(name)
            ecs_page.assert_status(name)

        with allure_step_log("步骤4: 云服务器登录vnc验证启动顺序"):
            ecs_page.ecs_vnc(name)

        with allure_step_log(f"步骤5: 从服务器{name}卸载云硬盘{volume_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_unmount_from_server(volume_name, name)
            ecs_page.assert_popup_success(f"从虚拟机{name}分离云硬盘")

    @allure.title("弹性云服务器-修改密码")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}}], indirect=True)
    def test_ecs_modifypwd(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        mfip = vm.get("mfip")
        # ecs_page.goto_submenu('弹性云服务器')

        with allure_step_log(f"步骤1: 云服务器{name}修改密码"):
            # ecs_page.assert_status(name, refresh=True)
            ecs_page.ecs_modify_pwd(name, "sugon@21", "sugon@21")

        with allure_step_log("步骤2: 验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改密码成功")
            ssh_vm.connect(mfip, pwd="sugon@21")
            assert ssh_vm.run("hostname") == name, f"修改密码后，无法登录虚拟机"

    @allure.title("弹性云服务器-修改主机名")
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

    @allure.title("弹性云服务器-修改VNC显卡类型")
    @pytest.mark.parametrize("vnc_type", ["VGA", "QXL", "None", "Virtio"])
    def test_ecs_modify_vnc_type(self, ecs_page, vm, ssh_vm, ssh_host, vnc_type):
        """测试修改云服务器的VNC显卡类型功能"""
        name = vm.get("name")
        ecs_id = vm.get("id")[:18]
        node = vm.get("host").split(".")[0]
        ecs_page.goto_service('弹性云服务器')

        architecture = Config.get("architecture")
        if architecture == "aarch64" and vnc_type == "QXL":
            pytest.skip("aarch64架构不支持QXL显卡类型")

        with allure_step_log(f"步骤1: 修改云服务器 {name} 的VNC显卡类型为 {vnc_type}"):
            ecs_page.ecs_modify_vnc_type(name, vnc_type)

        with allure_step_log("步骤2: 验证修改结果"):
            ecs_page.assert_popup_success("修改VNC显卡类型成功")

        with allure_step_log("步骤3: 验证VNC登录"):
            ecs_page.ecs_operations(name, "强制重启")
            ecs_page.assert_popup_success(f"{name}实例强制重启任务下发成功", timeout=60)
            ssh_vm.connect(vm['mfip'])
            ecs_page.assert_ecs_enable(name, ssh_vm)
            ecs_page.assert_ecs_details_info([name], info_items={"VNC显卡类型": vnc_type})

        with allure_step_log("步骤4: 验证虚机xml"):
            cmd = f"ssh -o StrictHostKeyChecking=no {node} 'docker exec -i nova_libvirt virsh dumpxml {ecs_id} |grep {vnc_type.lower()}'"
            assert ssh_host.run(cmd)

    @allure.title("弹性云服务器-修改CPU模式")
    @pytest.mark.parametrize("cpu_mode,custom_value", [["host-passthrough",""], ["自定义", "custom_Dhyana"]])
    @skip_arch('aarch64')
    def test_ecs_modify_cpu_mode(self, ecs_page, vm, ssh_host, cpu_mode, custom_value):
        """
        测试弹性云服务器CPU模式修改功能
        """
        name = vm.get("name")
        ecs_id = vm.get("id")[:18]
        node = vm.get("host").split(".")[0]
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 修改云服务器{name}的CPU模式为{cpu_mode}"):
            ecs_page.ecs_modify_cpu_mode(name, cpu_mode, custom_value )

        with allure_step_log(f"步骤2: 验证CPU模式修改结果"):
            ecs_page.wait_for_source_complete(name)
            ecs_page.assert_status(name)
            cpu_mode = "host-passthrough" if cpu_mode == "host-passthrough" else custom_value
            ecs_page.assert_ecs_details_info([name], info_items={"CPU模式": cpu_mode})

        with allure_step_log("步骤3: 验证虚机xml"):
            cmd = f"""ssh -o StrictHostKeyChecking=no {node} 'docker exec -i nova_libvirt virsh dumpxml {ecs_id} |grep "cpu mode="'"""
            expected_mode = "host-passthrough" if cpu_mode == "host-passthrough" else "custom"
            output = ssh_host.run(cmd)
            assert expected_mode in output, f"CPU模式验证失败: 期望 '{expected_mode}', 实际 '{output}'"

    @allure.title("弹性云服务器-时间同步服务器")
    def test_ecs_time_synchronize(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        time_server = "100.126.255.250"
        interval = "30"
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 验证时间同步服务器功能"):
            ssh_vm.connect(vm['mfip'])
            # 修改系统时间为一个错误的时间
            ssh_vm.run('date -s "2010-01-01"')
            assert "2010" in ssh_vm.run("date")

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
            assert expection in actual, f"同步时间服务器失败，期望时间:{expection},实际时间:{actual}"

    @allure.title("弹性云服务器-创建镜像")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "bind_mfip": True}], indirect=True)
    def test_ecs_create_image(self, ecs_page, vm, ssh_vm, admin_browser_context, config, ssh_host):
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
            # ecs_page.assert_status(name, "创建镜像中")
            ecs_page.wait_for_source_complete(name)
            ecs_page.goto_submenu("镜像服务")
            ecs_page.assert_status(image_name, status="可用", timeout=600, refresh=True)

        with allure_step_log(f"步骤3: 使用镜像{image_name}创建弹性云服务器{name}-1"):
            ecs_page.goto_service("弹性云服务器")
            image_vm = f"{name}-image"
            ecs_page.ecs_create(
                basic={"name": image_vm},
                storage={"image": {"source": "镜像", "name": image_name}},
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            # ecs_page.wait_for_source_complete(image_vm)
            ecs_page.assert_status(image_vm)

        with allure_step_log(f"步骤4: 验证{image_vm} md5值是否一致"):
            image_meta = collect_vm_metadata(ecs_page, ssh_host, image_vm)
            mfip_new = MfipHelper.bind_mfip_with_admin_context(
                admin_browser_context, config, image_meta["port_id"],
                project_id=image_meta.get("project_id", "admin-inner-project"),
            )
            ssh_vm.connect(mfip_new)
            assert md5 in ssh_vm.run(f"md5sum {name}"), f"新创建的云服务器的md5值{ssh_vm.run(f'md5sum {name}')}与源云服务器{md5}不一致"

        with allure_step_log("步骤5: 清理测试数据"):
            # 删除测试云服务器
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_remove(image_vm)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(image_vm)
            # 删除测试镜像
            ecs_page.goto_submenu("镜像服务")
            ecs_page.ecs_image_delete(image_name)
            ecs_page.assert_deleted(image_name, refresh=True)

    @allure.title("弹性云服务器-热迁移（手动指定节点）")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 2}, "bind_mfip": True}], indirect=True)
    @skip_if_nodes_less_than(2)
    def test_ecs_hot_migration_manual(self, ecs_page, vm, ssh_vm, ssh_host):
        """
        测试弹性云服务器的热迁移功能
        """
        ecs_page.goto_service('弹性云服务器')
        names = [vm[i].get("name") for i in range(len(vm))]
        ips = [vm[i].get("ip") for i in range(len(vm))]
        ecs_ids = [vm[i].get("id") for i in range(len(vm))]
        mfips = [vm[i].get("mfip") for i in range(len(vm))]

        with allure_step_log("步骤1: 虚机长ping"):
            ssh_vm.connect(mfips[0])
            ssh_vm.run(fr"nohup ping {ips[1]} -i 1 > /tmp/ping.log 2>&1 &")
            # 然后获取进程ID
            pid_output = ssh_vm.run(fr"pgrep -f 'ping {ips[1]}'")
            # 验证是否成功获取PID
            if not pid_output or not pid_output.strip():
                raise Exception("无法获取ping进程ID")
            pid = pid_output.strip()

        with allure_step_log("步骤2: 热迁移"):
            check_node = ecs_page.ecs_hot_migration(names[1], target_host="master01", m_type="手动指定")
            ecs_page.assert_popup_success("热迁移命令下发成功")

        with allure_step_log("步骤3: 验证迁移结果"):
            # ecs_page.assert_status(names[1], status="迁移中", refresh=True, refresh_interval=2)
            ecs_page.wait_for_source_complete(names[1])
            ecs_page.assert_status(names[1])

            # 验证迁移后页面展示的物理机节点 和 通过gova show 获取的物理机节点是否一致
            expect_node = ecs_page.get_row_data(names[1]).get("物理机")
            assert expect_node == check_node, f"热迁移失败，期望迁移至节点:{check_node},实际迁移至节点:{expect_node}"
            ssh_host.assert_guest_node(ecs_ids[1], check_node, "热迁移失败")

            # 验证长ping迁移丢包率
            ssh_vm.connect(mfips[0])
            ssh_vm.run(f"kill -2 {pid}")
            ping_output = ssh_vm.run("cat /tmp/ping.log")
            received = re.search(r"transmitted, (.*?) received", ping_output).group(1)
            send = re.search(r"(.*?) packets transmitted,", ping_output).group(1)
            loss = int(send) - int(received)
            assert loss <= 10, f"长ping迁移丢包数超高，期望丢包率小于10，实际丢包数:{loss}"

    @allure.title("弹性云服务器-热迁移（系统分配）")
    @skip_if_nodes_less_than(2)
    def test_ecs_hot_migration(self, ecs_page, vm, ssh_host):
        """
        测试弹性云服务器热迁移 系统分配功能
        """
        name = vm.get("name")
        host = vm.get("host")
        ecs_id = vm.get("id")

        with allure_step_log("步骤1: 热迁移"):
            ecs_page.ecs_hot_migration(name)
            ecs_page.assert_popup_success("热迁移命令下发成功")

        with allure_step_log("步骤2: 验证迁移结果"):
            ecs_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=2)
            ecs_page.wait_for_source_complete(name)
            new_host = ecs_page.get_row_data(name).get("物理机")
            assert new_host != host, f"热迁移失败，迁移前节点:{host}, 迁移后节点:{new_host}"
            ssh_host.assert_guest_node(ecs_id, new_host, "热迁移失败")
            vm.update({"host": new_host})

    @allure.title("弹性云服务器-冷迁移")
    @skip_stor("local")
    @skip_if_nodes_less_than(2)
    def test_ecs_cold_migration(self, ecs_page, vm, ssh_vm, ssh_host):
        """
        测试弹性云服务器的冷迁移功能
        """
        ecs_page.goto_service('弹性云服务器')
        name = vm.get("name")
        ecs_id = vm.get("id")
        with allure_step_log("步骤1: 冷迁移"):
            check_node = ecs_page.ecs_cold_migration(name, m_type="手动指定", cluster="Autotest", target_host="master01")
            ecs_page.assert_popup_success("冷迁移命令下发成功")

        with allure_step_log("步骤2: 验证迁移结果"):
            # ecs_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=2)
            ecs_page.wait_for_source_complete(name)
            ecs_page.assert_status(name)

            # 验证迁移后页面展示的物理机节点 和 通过gova show 获取的物理机节点是否一致
            expect_node = ecs_page.get_row_data(name).get("物理机")
            assert expect_node == check_node, f"冷迁移失败，期望迁移至节点:{check_node},实际迁移至节点:{expect_node}"
            ssh_host.assert_guest_node(ecs_id, check_node, "冷迁移失败")
            vm.update({"host": check_node})

            # 验证迁移后虚机的可用性
            ssh_vm.connect(vm['mfip'])
            ecs_page.assert_ecs_enable(name, ssh_vm)

    @allure.title("弹性云服务器-挂载和卸载云硬盘")
    def test_ecs_mount_unmount_volume(self, ecs_page, evs_page, vm, volume, ssh_vm):
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

            # 云硬盘页面验证 云硬盘状态=正在使用
            evs_page.goto_service("云硬盘")
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_status(volume["name"], status="正在使用", refresh=True)

            # 验证挂载后页面展示的挂载信息 和 虚机中的挂载信息是否一致
            disk_name = evs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"lsblk | grep {disk_name}") != ""

        with allure_step_log(f"步骤3: 从服务器{vm_name}卸载云硬盘{volume_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_unmount_from_server(volume_name, vm_name)
            ecs_page.assert_popup_success(f"从虚拟机{vm_name}分离云硬盘")

        with allure_step_log(f"步骤4: 验证卸载结果"):
            assert ecs_page.get_row_data(vm_name).get("挂载云硬盘") == "--"
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"lsblk | grep {disk_name}") == ""

    @allure.title("弹性云服务器-系统盘扩容")
    def test_ecs_expand_system_disk(self, ecs_page, vm, ssh_host, ssh_vm):
        """测试弹性云服务器系统盘扩容功能"""
        name = vm.get("name")
        ecs_id  = vm.get("id")
        new_size = "30"
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 扩容云服务器{name}系统盘至{new_size}GiB"):
            ecs_page.ecs_expand_system_disk(name, new_size)
            ecs_page.assert_popup_success(f"{name}实例扩容成功")

        with allure_step_log("步骤2: 验证扩容结果"):
            ecs_page.assert_ecs_info(name, "系统盘", f"容量(GiB):{new_size}")
            assert new_size in ecs_page.get_row_data(name).get("系统盘")
            ecs_page.assert_ecs_details_info(name, {"系统盘": new_size})

            # 验证扩容后页面展示的系统盘大小 和 通过 scli guest show 获取的系统盘大小是否一致
            stdout = ssh_host.assert_guest_fields(ecs_id, {"root_gb": new_size}, "扩容系统盘失败")
            root_dev = stdout.get("root_dev")
            assert stdout.get("root_gb") == new_size, \
                f"扩容系统盘失败，期望系统盘大小:{new_size}GiB,实际系统盘大小:{stdout.get('root_gb')}GiB"

            # 验证扩容后页面展示的系统盘大小 和 虚机中的系统盘大小是否一致
            ssh_vm.connect(vm['mfip'])
            assert new_size in ssh_vm.run(f"lsblk | grep '^{root_dev}' | awk '{{print $4}}'"), \
                f"扩容系统盘失败，云服务器{name}系统盘大小不一致"

    @allure.title("弹性云服务器-挂载CD-ROM")
    def test_ecs_mount_cdrom(self, ecs_page, evs_page, image, vm, ssh_vm):
        """测试弹性云服务器挂载CD-ROM功能"""
        name = vm.get("name")
        iso_name = image.get("name")
        with allure_step_log("步骤1: 为云服务器挂载CD-ROM"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_mount_cdrom(name, iso_name)

        with allure_step_log(f"步骤2: 验证虚机{name}挂载CD-ROM结果"):
            ecs_page.assert_popup_success(f"挂载CD-ROM到虚拟机{name}成功")
            ecs_page.wait_for_source_complete(name)
            ecs_page.assert_status(name)

            # 验证CD-ROM已成功挂载
            cdrom_name = ecs_page.get_row_data(name).get("挂载云硬盘")
            assert cdrom_name.startswith("cdrom-")

            # 验证云硬盘状态
            evs_page.goto_service("云硬盘")
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_status(cdrom_name, status="正在使用", refresh=True)

        with allure_step_log(f"步骤3: 后台验证虚机{name}挂载CD-ROM结果"):
            ssh_vm.connect(vm['mfip'])
            assert "20G" in ssh_vm.run(f"lsblk | grep sr | awk '{{print $4}}'")
            disk = ssh_vm.run(f"lsblk | grep sr | grep 20G | awk '{{print $1}}'")
            ssh_vm.run(f"mkdir /mnt/{name}")
            ssh_vm.run(f"mount /dev/{disk} /mnt/{name}")
            assert ssh_vm.run(f"ls /mnt/{name}") != ""

        with allure_step_log(f"步骤4: 卸载CD-ROM"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_unmount_cdrom(name, cdrom_name)

        with allure_step_log(f"步骤5: 验证虚机{name}卸载CD-ROM结果"):
            ecs_page.assert_popup_success(f"从虚拟机{name}卸载CD-ROM成功")
            assert ecs_page.get_row_data(name).get("挂载云硬盘") == "--"
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"ls /mnt/{name}") == ""
            ssh_vm.run(f"umount /mnt/{name}")

    @allure.title("弹性云服务器-挂载和卸载裸磁盘")
    def test_ecs_mount_bare_disk(self, ecs_page, pool, ssh_vm):
        vm_name = pool.get("name")
        pool_name = pool.get("pool_name")

        with allure_step_log(f"步骤1: {vm_name}挂载裸磁盘"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_mount_bare_disk(vm_name, pool_name)
            ecs_page.assert_popup_success(f"{vm_name}实例挂载主机设备成功")

        with allure_step_log(f"步骤2: 验证挂载裸磁盘结果"):
            ssh_vm.connect(pool.get("mfip"))
            assert ssh_vm.run(f"lsblk | grep sda | awk '{{print $4}}'") == pool.get("disk_size")

        with allure_step_log(f"步骤3: {vm_name}卸载裸磁盘{pool_name}"):
            ecs_page.ecs_unmount_bare_disk(vm_name)
            ecs_page.assert_popup_success(f"{vm_name}实例卸载主机设备成功")

        with allure_step_log(f"步骤4: 验证卸载裸磁盘结果"):
            assert ssh_vm.run(f"lsblk | grep sda") == ""

    @allure.title("弹性云服务器-批量操作")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 3}, "bind_mfip": False}], indirect=True)
    @pytest.mark.parametrize("operations", load_data("test_ecs_batch_operations", "test_ecs.yaml"))
    def test_ecs_batch_operations(self, ecs_page, vm, ssh_host, operations):
        names = [vm[i].get("name") for i in range(len(vm))]
        ecs_ids = [vm[i].get("id") for i in range(len(vm))]
        operation = operations.get("operation")
        status = operations.get("status")
        vm_state = operations.get("vm_state")
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 弹性云服务器{names}{operation}"):
            ecs_page.ecs_batch_operations(names, operation=operation)

        with allure_step_log(f"步骤2: 验证{operation}结果"):
            for name, ecs_id in zip(names, ecs_ids):
                ecs_page.wait_for_source_complete(name, loading_timeout=15)
                ecs_page.assert_status(name, status=status)
                stdout = ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}"))
                ssh_host.assert_guest_fields(ecs_id, {"vm_state": vm_state}, f"批量操作{operation}失败")

    @allure.title("弹性云服务器-批量迁移")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 3}, "bind_mfip": False}], indirect=True)
    @skip_if_nodes_less_than(2)
    def test_ecs_batch_migration(self, ecs_page, vm, ssh_host):
        """
        测试弹性云服务器的批量热迁移和冷迁移功能
        场景1: 环境节点充足时，批量迁移准确下发，虚机状态变为迁移中，迁移完成后节点变更
        场景2: 环境节点不足时，批量迁移命令准确下发，页面虚机状态不会变更，节点也不会变更
        """
        names = [vm[i].get("name") for i in range(len(vm))]
        ecs_ids = [vm[i].get("id") for i in range(len(vm))]
        pre_nodes = [vm[i].get("host") for i in range(len(vm))]
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log("步骤1: 批量迁移"):
            ecs_page.ecs_batch_migration(names)
            ecs_page.assert_popup_success(f"批量热迁移命令下发成功")

        with allure_step_log("步骤2: 检查迁移是否开始执行"):
            migration_started = False
            try:
                for name in names:
                    ecs_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=1, timeout=15)
                migration_started = True
                ecs_page.logger.info("迁移已开始执行，虚机状态已变为迁移中")
            except Exception as e:
                ecs_page.logger.info(f"迁移未开始执行（可能节点不足）: {str(e)}")

        if migration_started:
            with allure_step_log("步骤3: 验证迁移结果（节点充足场景）"):
                for name in names:
                    ecs_page.wait_for_source_complete(name, complete_timeout=90)
                    ecs_page.assert_status(name)

                for name, ecs_id in zip(names, ecs_ids):
                    # ecs_page.assert_status(name)
                    expect_node = ecs_page.get_row_data(name).get("物理机")
                    ssh_host.assert_guest_node(ecs_id, expect_node, "批量迁移失败")
        else:
            with allure_step_log("步骤3: 验证迁移结果（节点不足场景）"):
                first_event = ecs_page.get_first_event_data(names[0])
                event_name = first_event.get("事件名称", "")
                event_info = first_event.get("事件消息", "")
                assert "热迁移" in event_name, f"事件名称应包含'热迁移', 实际: {event_name}"
                assert "资源不足" in event_info or "没有可用节点" in event_info, f"事件信息应包含'资源不足'或'没有可用节点', 实际: {event_info}"
                ecs_page.logger.info(f"事件列表验证通过: 事件名称={event_name}, 事件消息={event_info}")
                for name, ecs_id, pre_node in zip(names, ecs_ids, pre_nodes):
                    current_node = ecs_page.get_row_data(name).get("物理机")
                    assert current_node == pre_node, f"节点不足时迁移不应执行，但节点已变更: {pre_node} -> {current_node}"
                    ssh_host.assert_guest_node(ecs_id, pre_node, "节点不足时迁移不应执行")

    @allure.title("弹性云服务器-批量设置启动和关机顺序")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 2}, "bind_mfip": False}], indirect=True)
    @pytest.mark.parametrize("operation",["关机","启动"])
    def test_ecs_batch_set_boot_order(self, ecs_page, vm, operation):
        names = [[vm[i].get("name")] for i in range(len(vm))]
        delay = "20"
        ecs_page.goto_service('弹性云服务器')
        with allure_step_log(f"步骤1: 批量设置{operation}顺序"):
            for i, name in enumerate(names, start=1):
                if operation == "关机":
                    ecs_page.ecs_batch_set_shutdown_order(name, i, delay)
                    ecs_page.assert_popup_success("执行成功")
                else:
                    ecs_page.ecs_batch_set_startup_order(name, i, delay)
                    ecs_page.assert_popup_success("执行成功")

        with allure_step_log(f"步骤2: 进入云服务器详情页面验证顺序及{operation}延迟"):
            for i, name in enumerate(names, start=1):
                ecs_page.assert_ecs_details_info(name, info_items={f"{operation}顺序": str(i), f"{operation}延迟时间(秒)": delay})

        with allure_step_log(f"步骤3: 批量{operation}"):
            names = [name[0] for name in names]
            ecs_page.ecs_batch_operations(names, f"批量{operation}")
            ecs_page.assert_popup_success(f"执行成功")

        with allure_step_log(f"步骤4: 验证{operation}结果"):
            final_status = "关机" if operation == "关机" else "运行"
            for name in names:
                ecs_page.assert_status(name, status=final_status, refresh=True, refresh_interval=1)
                if name != names[-1]:  # 最后一个服务器不执行延迟
                    time.sleep(int(delay) / 2)

    @allure.title("弹性云服务器-修改密码并登录VNC")
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

    @allure.title("弹性云服务器-安装和卸载工具")
    def test_ecs_install_uninstall_tools(self, ecs_page, vm, ssh_vm):
        """云服务器安装工具&卸载工具功能验证

        Args:
            ecs_page: 云服务器页面对象
            vm: 虚拟机信息字典，包含name等信息
        """
        name = vm.get("name")
        # 导航到弹性云服务器页面
        ecs_page.goto_submenu('弹性云服务器')

        with allure_step_log(f"步骤1: 为云服务器{name}安装工具-页面ISO安装"):
            # 调用安装工具方法
            ecs_page.search(name)
            ecs_page.ecs_install_tools(name)
            ecs_page.assert_ecs_tools_installed(name)
            ecs_page.close_dialog_if_exists()
            ecs_page.wait_for_source_complete(name)
            ecs_page.assert_status(name)
            assert ecs_page.get_row_data(name).get("挂载云硬盘").startswith("cdrom-")

        with allure_step_log(f"步骤2: 为云服务器{name}安装工具-虚机控制台安装"):
            # 验证工具安装结果
            ssh_vm.connect(vm['mfip'])
            ssh_vm.run("mkdir /mnt/cdrom")
            # 挂载设备并检查结果
            mounted = False
            for device in ["/dev/sr0", "/dev/sr1"]:
                output = ssh_vm.run(f"mount {device} /mnt/cdrom", return_stderr=True, return_rc=True)
                if output.get("rc") == 0 and "mounting read-only" in output.get("stderr", ""):
                    mounted = True
                    break
            if not mounted:
                raise AssertionError(f"挂载CD-ROM失败：已尝试挂载 /dev/sr0 和 /dev/sr1，但未找到有效的CD-ROM设备")
            ssh_vm.run(r"cd /mnt/cdrom/linux && bash ./stools.sh")
            assert "active (running)" in ssh_vm.run("systemctl status fs-proxy")

        with allure_step_log(f"步骤3: 为云服务器 {name} 卸载工具"):
            # 调用卸载工具方法
            ssh_vm.run("cd ~ && umount /mnt/cdrom")
            ecs_page.ecs_uninstall_tools(name)
            ecs_page.btn_refresh.click()
            assert ecs_page.get_row_data(name).get("挂载云硬盘") == "--"

    @allure.title("弹性云服务器-搜索和重置")
    def test_ecs_search(self, ecs_page, vm):
        ecs_page.goto_service("弹性云服务器")

        with allure_step_log("步骤1: 输入名称进行搜索"):
            keyword = vm['name'][:-2]
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.search(keyword)
            ecs_page.assert_list_contain(keyword, column_name="名称/ID", exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            ecs_page.btn_reset.click()
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("弹性云服务器-Agent版本设置")
    @pytest.mark.parametrize("agent_conf", load_data("test_ecs_agent_conf", "test_ecs.yaml"))
    def test_ecs_agent_conf(self, ecs_page, ssh_vm, vm, agent_conf):
        ecs_page.goto_service("弹性云服务器")
        name = vm.get("name")

        with allure_step_log(f"步骤1: 修改Agent版本设置"):
            ecs_page.ecs_agent_version(name, agent_conf)
            ecs_page.assert_popup_success(f"agent版本配置成功")

        with allure_step_log(f"步骤2: 验证Agent版本设置结果"):
            except_agent_version = {}
            for conf in agent_conf:
                for agent_type, agent_version in conf.items():
                    except_agent_version[f"{agent_type}"] = agent_version
            ecs_page.assert_ecs_details_info(name, info_items=except_agent_version)

    @allure.title("弹性云服务器-批量Agent版本设置")
    @pytest.mark.parametrize("agent_conf", load_data("test_ecs_batch_modify_agent", "test_ecs.yaml"))
    @pytest.mark.parametrize("vm", [{"basic": {"count": 3}, "bind_mfip": False}], indirect=True)
    def test_ecs_batch_modify_agent(self, ecs_page, vm, agent_conf):
        ecs_page.goto_service("弹性云服务器")
        names = [vm[i].get("name") for i in range(len(vm))]

        with allure_step_log(f"步骤1: 批量修改Agent版本设置"):
            ecs_page.ecs_batch_agent_version(names, agent_conf)
            ecs_page.assert_popup_success(f"agent版本配置成功")

        with allure_step_log(f"步骤2: 验证Agent版本设置结果"):
            except_agent_version = {}
            for conf in agent_conf:
                for agent_type, agent_version in conf.items():
                    except_agent_version[f"{agent_type}"] = agent_version
            ecs_page.assert_ecs_details_info(names, info_items=except_agent_version)

    @allure.title("弹性云服务器-加载和卸载网卡")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "bind_mfip": True}], indirect=True)
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
            time.sleep(10)
            ssh_vm.connect(vm['mfip'])
            ssh_vm.ping(ip)

        with allure_step_log(f"步骤3: {name}卸载网卡:{ip}"):
            ecs_page.ecs_uninstall_network(name, ip)

        with allure_step_log("步骤4: 验证加载网卡结果"):
            ecs_page.assert_popup_success(f"断开网络成功", timeout=60)
            ecs_page.assert_ecs_info(name, "IP地址", "")
            time.sleep(10)
            ssh_vm.connect(vm['mfip'])
            ssh_vm.ping(ip, connected=False)
