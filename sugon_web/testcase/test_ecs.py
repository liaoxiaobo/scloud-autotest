from tokenize import group

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
            ecs_page.assert_status(name, status="当前无任务", timeout=300)

        with allure.step("清理测试数据"):
            ecs_page.ecs_remove(name)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(name)

    @allure.title(f"弹性云服务器-电源操作功能验证")
    @pytest.mark.parametrize("params", load_data('test_ecs_operations', "ecs_operation_data.yaml"))
    def test_ecs_operations(self, ecs_page, _ecs, params):
        name = _ecs.get("name")
        operation = params.get("operation")
        desc = params.get("desc")
        staus = params.get("status")
        with allure.step(f"{name}{operation}"):
            ecs_page.ecs_operations(name, operation)
            ecs_page.assert_popup_success(f"{name}{desc}", timeout=60)
            ecs_page.assert_status(name, status=staus)

    @allure.title("弹性云服务器-编辑功能验证")
    def test_ecs_edit(self, ecs_page, _ecs):
        name = _ecs.get("name")
        newname = random_data('string', 5)
        with allure.step("编辑弹性云服务器"):
            ecs_page.ecs_edit(name, newname)

        with allure.step("验证创建结果"):
            ecs_page.assert_popup_success("更新实例成功")

        with allure.step("清理测试数据"):
            ecs_page.ecs_edit(newname, name)

    @allure.title("弹性云服务器-登录VNC功能验证")
    def _test_ecs_vnc(self, ecs_page, _ecs):
        name = _ecs.get("name")
        with allure.step("登录VNC"):
            ecs_page.ecs_vnc(name, "sugon@20")

    @allure.title("弹性云服务器-克隆功能验证")
    def test_ecs_clone(self, ecs_page, _ecs):
        name = _ecs.get("name")
        with allure.step(f"克隆弹性云服务器{name}"):
            clone_name = random_data('string', 5)
            ecs_page.ecs_clone(name, clone_name, 'Autotest', 'Autotest', {})

        with allure.step(f"验证克隆结果{clone_name}"):
            ecs_page.assert_popup_success(f"{name}实例克隆成功")
            image_name = ecs_page.get_row_data(name).get("镜像名称")
            ecs_page.assert_image_name(clone_name, image_name)
            ecs_page.assert_status(name, status="当前无任务", timeout=300)

        with allure.step(f"清理测试数据{clone_name}"):
            ecs_page.ecs_remove(clone_name)
            ecs_page.ecs_delete(clone_name)
            ecs_page.assert_deleted(clone_name)

    @allure.title("弹性云服务器-重建云服务器功能验证")
    def test_ecs_rebuild(self, ecs_page, _ecs):
        name = _ecs.get("name")
        with allure.step("重建云服务器"):
            ecs_page.ecs_rebuild(name, 'centos', '64位', 'xbd')

        with allure.step("验证重建结果"):
            ecs_page.assert_popup_success(f"{name}实例重建成功")
            ecs_page.assert_status(name, status="当前无任务", timeout=300)

    @allure.title("弹性云服务器-修改规格功能验证")
    @pytest.mark.parametrize("spec", load_data('test_ecs_modify_spec', "ecs_operation_data.yaml"))
    def test_ecs_modify_spec(self, ecs_page, _ecs, spec):
        name = _ecs.get("name")
        cpu = spec.get("CPU", "2")
        mem = spec.get("Mem", "4")
        with allure.step(f"{name}修改规格:{spec.get('desc')}"):
            ecs_page.ecs_modify_spec(name, spec)
        with allure.step("验证重建结果"):
            ecs_page.assert_popup_success("调整实例资源配置成功")
            ecs_page.assert_ecs_info(name, "规格", f"{cpu} 核 {mem}.00 GiB")

    @allure.title("弹性云服务器-加载/卸载网卡功能验证")
    @pytest.mark.parametrize("network_info", load_data('test_ecs_network', "ecs_operation_data.yaml"))
    def test_ecs_network(self, ecs_page, _ecs, network_info):
        name = _ecs.get("name")
        ip = _ecs.get("ip")
        net = network_info.get("net")
        mode = network_info.get("mode")
        ipv4 = network_info.get("ipv4")
        # 确保虚拟机稳定运行
        ecs_page.assert_status(name, status="运行")
        # 单例调试，关机虚拟机，确保网卡卸载正常
        with allure.step(f"云服务器{name}关机"):
            ecs_page.ecs_operations(name, "关机")
            ecs_page.assert_popup_success(f"{name}实例关机成功", timeout=60)
            ecs_page.assert_status(name, status="关机")

        with allure.step(f"{name}卸载网卡:{ip}"):
            ecs_page.ecs_uninstall_network(name, ip)
        with allure.step("验证加载网卡结果"):
            ecs_page.assert_popup_success(f"断开网络成功", timeout=60)
            ecs_page.assert_ecs_info(name, "IP地址", "")

        with allure.step(f"{name}加载网卡:网络{net}，子网{ip}"):
            ecs_page.ecs_load_network(name, net, ip[:3], mode, ipv4)
        with allure.step("验证加载网卡结果"):
            ecs_page.assert_popup_success(f"{name}实例，连接{net}子网成功", timeout=30)

        with allure.step(f"云服务器{name}启动"):
            ecs_page.ecs_operations(name, "启动")
            ecs_page.assert_popup_success(f"{name}实例启动成功", timeout=60)
            ecs_page.assert_status(name, status="运行")

    @allure.title("弹性云服务器-绑定/解绑公网IP功能验证")
    def test_ecs_pub_ip(self, ecs_page, _ecs):
        name = _ecs.get("name")
        with allure.step(f"云服务器{name}绑定公网IP"):
            pub_ip = ecs_page.ecs_bind_pub_ip(name)
        with allure.step("验证绑定公网IP结果"):
            ecs_page.assert_popup_success(f"执行成功")
            ecs_page.assert_ecs_info(name, "IP地址", pub_ip)

        with allure.step(f"云服务器{name}解绑公网IP{pub_ip}"):
            ecs_page.ecs_unbind_pub_ip(name, pub_ip)
            ecs_page.assert_popup_success(f"执行成功")
        with allure.step("验证解绑公网IP结果"):
            ecs_page.assert_ecs_info_not_contains(name, "IP地址", pub_ip)

    @allure.title("弹性云服务器-修改密码功能验证")
    def test_ecs_modifypwd(self, ecs_page, _ecs):
        name = _ecs.get("name")
        with allure.step(f"云服务器{name}修改密码"):
            ecs_page.assert_status(name, status="运行")
            ecs_page.ecs_modify_pwd(name, "sugon@21", "sugon@21")
        with allure.step("验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改密码成功")

        with allure.step(f"云服务器{name}还原密码"):
            ecs_page.ecs_modify_pwd(name, "sugon@20", "sugon@20")
        with allure.step("验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改密码成功")

    @allure.title("弹性云服务器-修改密码功能验证")
    def test_ecs_modify_vncpwd(self, ecs_page, _ecs):
        name = _ecs.get("name")
        with allure.step(f"云服务器{name}修改VNC密码"):
            ecs_page.assert_status(name, status="运行")
            ecs_page.ecs_modify_vnc_pwd(name, "sugon@21", "sugon@21")
        with allure.step("验证修改密码结果"):
            ecs_page.assert_popup_success(f"修改vnc密码成功")

        with allure.step(f"云服务器{name}还原VNC密码"):
            ecs_page.ecs_modify_vnc_pwd(name, "sugon@20", "sugon@20")
        with allure.step("验证还原密码结果"):
            ecs_page.assert_popup_success(f"修改vnc密码成功")

    @allure.title("弹性云服务器-修改主机名功能验证")
    def test_ecs_modify_hostname(self, ecs_page, _ecs):
        name = _ecs.get("name")
        hostname = random_data(4)
        with allure.step(f"云服务器{name}修改主机名"):
            ecs_page.assert_status(name, status="运行")
            ecs_page.ecs_modify_hostname(name, hostname)
        with allure.step("验证修改主机名结果"):
            ecs_page.assert_popup_success(f"更新实例成功")

    @allure.title("弹性云服务器-时间同步服务器功能验证")
    def test_ecs_time_synchronize(self, ecs_page, _ecs):
        name = _ecs.get("name")
        time_server = "100.126.255.250"
        interval = "7200"
        with allure.step(f"弹性云服务器{name}配置时间同步服务器"):
            ecs_page.assert_status(name, status="运行")
            ecs_page.ecs_time_synchronize(name, time_server, interval)
            ecs_page.assert_popup_success("修改时间同步服务器成功")

    @allure.title("弹性云服务器-绑定/解绑亲和组功能验证")
    @pytest.mark.parametrize("params", load_data('test_ecs_bind_unbind_group', "ecs_operation_data.yaml"))
    def test_ecs_bind_unbind_group(self, ecs_page, _ecs, params):
        name = _ecs.get("name")
        operation = params.get("operation")
        group_name = params.get("group_name")
        with allure.step(f"云服务器{name}{operation}"):
            ecs_page.assert_status(name, status="运行")
            ecs_page.ecs_bind_unbind_group(name, operation, group_name)
        with allure.step(f"验证{operation}结果"):
            ecs_page.assert_popup_success(f"{name}实例{operation}成功")
