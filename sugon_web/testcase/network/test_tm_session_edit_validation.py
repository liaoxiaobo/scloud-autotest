import time
import random

import pytest
import allure
from sugon_web.pages.network import VpcPage
from sugon_web.pages.ops import OpsPage
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data


def _create_vpc(vpc_page):
    """创建VPC，返回VPC信息字典。"""
    vpc_name = f"tm-vpc-{random_data()}"
    subnet_name = f"autotest-{random_data()}"
    cidr = f"10.{random.randint(1, 254)}.{random.randint(0, 254)}.0/24"
    vpc_page.goto_service("虚拟私有云")
    vpc_page.vpc_create(name=vpc_name, subnet_name=subnet_name, cidr=cidr)
    vpc_page.assert_popup_success(timeout=30000)
    return {"name": vpc_name, "subnet_name": subnet_name, "cidr": cidr}


def _create_vm(ecs_page, vpc_name, subnet_name, vm_name_prefix="tm-"):
    """在指定VPC下创建VM，返回VM信息字典（含name, ip, project）。"""
    vm_name = f"{vm_name_prefix}{random_data()}"
    ecs_page.goto_service("弹性云服务器")
    ecs_page.ecs_create(
        basic={"name": vm_name, "count": 1, "cluster": "Autotest", "flavor": {"base": "ecs.c6.Autotest"}},
        storage={"storage_pool": "xstor-test", "image": {"source": "镜像", "name": "xstor-test"}, "system_disk": 25},
        network={"networks": [{"network": vpc_name, "subnet": subnet_name}]},
        manage={"login_type": "密码登录", "login_pwd": "admin1234@sugon", "vnc_pwd": "sugon@20"},
    )
    ecs_page.assert_popup_success(timeout=120000)
    ecs_page.assert_status(vm_name, status="运行", timeout=300)
    row_data = ecs_page.get_row_data(vm_name)
    ip_raw = row_data.get("IP地址", "")
    ip = ip_raw.split("固定: ")[-1].strip() if "固定: " in ip_raw else ip_raw.strip()
    project = row_data.get("项目名称", "")
    return {"name": vm_name, "ip": ip, "project": project}


def _bind_mfip(ops_page, project, network, vm_ip):
    """为指定VM绑定MFIP，返回MFIP地址。"""
    ops_page.goto_service("基础设施")
    ops_page.goto_submenu("平台网络")
    ops_page.mfip_create(project=project, network=network, ip=vm_ip)
    ops_page.assert_popup_success(timeout=30000)
    ops_page.mfip_search(vm_ip)
    row_data = ops_page.get_row_data(vm_ip)
    return row_data.get("管理IP地址")


def _assert_tcpdump_direction(ssh_vm, vm1_mfip, vm3_mfip, vm2_ip, expected):
    """在VM1上抓包并验证流量方向。

    采用后台tcpdump + 前台ping的并行模式，确保抓包期间有流量产生。

    Args:
        expected: 期望的流量方向，"both"(双向)、"egress"(出向)、"ingress"(入向)、"none"(无)。
    """
    if expected == "none":
        # 关闭状态：先ping再抓包（验证抓不到）
        ssh_vm.connect(vm3_mfip)
        ping_result = ssh_vm.run(f"ping -c 10 {vm2_ip}", return_rc=True)
        assert ping_result["rc"] == 0, f"[BackendAssertion] ping命令执行失败"

        ssh_vm.connect(vm1_mfip)
        dump_result = ssh_vm.run("timeout 15 tcpdump -i eth1 icmp -nvv -c 10", return_rc=True, timeout=20)
        stdout = dump_result.get("stdout", "").lower()
        assert "echo request" not in stdout and "echo reply" not in stdout, \
            f"[BackendAssertion] 关闭状态下不应抓到ICMP包: {stdout}"
        return

    # 开启状态：后台启动tcpdump -> ping -> 读取结果
    ssh_vm.connect(vm1_mfip)
    ssh_vm.run("rm -f /tmp/tcpdump_result.txt")
    result = ssh_vm.run(
        "nohup tcpdump -i eth1 icmp -nvv -c 10 > /tmp/tcpdump_result.txt 2>&1 &",
        return_rc=True,
    )
    assert result["rc"] == 0, f"[BackendAssertion] 启动tcpdump失败"
    time.sleep(2)

    # 在VM3上向VM2发起ping
    ssh_vm.connect(vm3_mfip)
    ping_result = ssh_vm.run(f"ping -c 10 {vm2_ip}", return_rc=True)
    assert ping_result["rc"] == 0, f"[BackendAssertion] ping命令执行失败"

    # 在VM1上读取抓包结果
    ssh_vm.connect(vm1_mfip)
    tcpdump_output = ""
    for _ in range(30):
        result = ssh_vm.run("cat /tmp/tcpdump_result.txt", return_rc=True)
        if result["rc"] == 0:
            tcpdump_output = result["stdout"]
            if "ICMP" in tcpdump_output:
                break
        time.sleep(2)

    stdout = tcpdump_output.lower()
    has_request = "echo request" in stdout
    has_reply = "echo reply" in stdout

    if expected == "both":
        assert has_request, f"[BackendAssertion] 全部流量模式下应抓到ICMP request: {stdout}"
        assert has_reply, f"[BackendAssertion] 全部流量模式下应抓到ICMP reply: {stdout}"
    elif expected == "egress":
        assert has_reply, f"[BackendAssertion] 出向流量模式下应抓到ICMP reply: {stdout}"
        assert not has_request, f"[BackendAssertion] 出向流量模式下不应抓到ICMP request: {stdout}"
    elif expected == "ingress":
        assert has_request, f"[BackendAssertion] 入向流量模式下应抓到ICMP request: {stdout}"
        assert not has_reply, f"[BackendAssertion] 入向流量模式下不应抓到ICMP reply: {stdout}"


@allure.epic('网络服务')
@allure.feature('流量镜像')
@allure.story('镜像会话修改及生效性验证')
@pytest.mark.parametrize("vpc", [{"name_prefix": "tm_"}], indirect=True)
@pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "name_prefix": "tm_"}], indirect=True)
class TestTMSessionEditValidation:
    """镜像会话-修改-云内实例验证（用例407253）"""

    @allure.title("镜像会话-修改-云内实例验证")
    def test_tm_session_edit_validation(self, tm_page, ecs_page, vpc, vm, ssh_vm):
        """验证流量镜像镜像会话的修改功能及生效性。

        前置资源：
        - fixture vpc+vm: VPC1 + VM1（目的实例，自动MFIP）
        - 测试体内: VPC2 + VM2（镜像源）+ VM3（发起ping，手动MFIP）
        """
        vm1_name = vm["name"]
        vm1_mfip = vm.get("mfip")

        tm_name = f"tm-inside-{random_data()}"
        session_name = f"tm-session-{random_data()}"
        new_session_name = f"{session_name}-modified"
        new_desc = "这是autotest修改之后的描述"

        vpc2_info = None
        vm2_info = None
        vm3_info = None
        session_modified = False

        try:
            # ========== 前置准备 ==========
            with allure_step_log("前置: 创建VPC2"):
                vpc_page = VpcPage(tm_page.page)
                vpc2_info = _create_vpc(vpc_page)

            with allure_step_log("前置: 创建VM2（镜像源）"):
                vm2_info = _create_vm(ecs_page, vpc2_info["name"], vpc2_info["subnet_name"])

            with allure_step_log("前置: 创建VM3（发起ping）并绑定MFIP"):
                vm3_info = _create_vm(ecs_page, vpc2_info["name"], vpc2_info["subnet_name"])
                ops_page = OpsPage(tm_page.page)
                vm3_mfip = _bind_mfip(ops_page, vm3_info["project"], vpc2_info["name"], vm3_info["ip"])
                vm3_info["mfip"] = vm3_mfip

            with allure_step_log("前置: 创建云内实例类型流量镜像"):
                tm_page.goto_service("流量镜像")
                tm_page.goto_submenu("流量镜像")
                tm_page.tm_create_inner_ecs(name=tm_name, server_name=vm1_name)
                tm_page.assert_popup_success(timeout=10000)
                tm_page.assert_list_contain(tm_name, column_name="名称")
                tm_page.assert_status(tm_name, status="正常")

            with allure_step_log("前置: 创建镜像会话（全部流量-开启）"):
                tm_page.goto_tm_session_tab(tm_name)
                tm_page.tm_session_create(
                    name=session_name,
                    enabled=True,
                    vpc_name=vpc2_info["name"],
                    subnet_name=vpc2_info["subnet_name"],
                    vm_name=vm2_info["name"],
                    vm_ip=vm2_info["ip"],
                    direction="全部流量",
                )
                tm_page.assert_popup_success(timeout=10000)
                tm_page.assert_list_contain(session_name, column_name="名称")

            # ========== 初始状态抓包验证（全部流量） ==========
            with allure_step_log("步骤1: 初始状态抓包验证（全部流量-双向）"):
                assert vm1_mfip, "[BackendAssertion] VM1未绑定MFIP"
                assert vm3_info.get("mfip"), "[BackendAssertion] VM3未绑定MFIP"
                _assert_tcpdump_direction(ssh_vm, vm1_mfip, vm3_info["mfip"], vm2_info["ip"], "both")

            # ========== 修改名称和描述 ==========
            with allure_step_log("步骤2: 修改镜像会话名称和描述"):
                original_data = tm_page.tm_session_edit(
                    session_name,
                    new_name=new_session_name,
                    new_desc=new_desc,
                )
                tm_page.assert_popup_success(timeout=10000)
                # P1: 断言初始值正确
                assert original_data["name"] == session_name, \
                    f"[FieldAssertion] 初始名称不匹配: 期望 {session_name}, 实际 {original_data['name']}"

                session_modified = True

            with allure_step_log("步骤3: 列表页验证名称和描述修改成功"):
                tm_page.page.wait_for_timeout(3000)
                tm_page.assert_list_contain(new_session_name, column_name="名称")
                row_data = tm_page.get_row_data(new_session_name)
                actual_name = row_data.get("名称", "")
                actual_desc = row_data.get("描述", "")
                assert actual_name == new_session_name, \
                    f"[FieldAssertion] 列表页名称不匹配: 期望 {new_session_name}, 实际 {actual_name}"
                assert actual_desc == new_desc, \
                    f"[FieldAssertion] 列表页描述不匹配: 期望 {new_desc}, 实际 {actual_desc}"

            # ========== 修改为关闭状态 ==========
            with allure_step_log("步骤4: 修改是否开启为关闭状态"):
                time.sleep(10)
                original_data = tm_page.tm_session_edit(
                    new_session_name,
                    enabled=False,
                )
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤5: 列表页验证关闭状态 + 抓包验证镜像不生效"):
                tm_page.page.wait_for_timeout(3000)
                row_data = tm_page.get_row_data(new_session_name)
                assert "否" in row_data.get("是否开启", ""), \
                    f"[FieldAssertion] 是否开启不匹配: 期望 否, 实际 {row_data.get('是否开启')}"
                _assert_tcpdump_direction(ssh_vm, vm1_mfip, vm3_info["mfip"], vm2_info["ip"], "none")

            # ========== 修改为开启 + 出向流量 ==========
            with allure_step_log("步骤6: 修改是否开启为开启，方向为出向流量"):
                time.sleep(10)
                original_data = tm_page.tm_session_edit(
                    new_session_name,
                    enabled=True,
                    direction="出向流量",
                )
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤7: 列表页验证开启和出向 + 抓包验证出向流量"):
                tm_page.page.wait_for_timeout(3000)
                row_data = tm_page.get_row_data(new_session_name)
                assert "是" in row_data.get("是否开启", ""), \
                    f"[FieldAssertion] 是否开启不匹配: 期望 是, 实际 {row_data.get('是否开启')}"
                assert "出向流量" in row_data.get("方向", ""), \
                    f"[FieldAssertion] 方向不匹配: 期望 出向流量, 实际 {row_data.get('方向')}"
                _assert_tcpdump_direction(ssh_vm, vm1_mfip, vm3_info["mfip"], vm2_info["ip"], "egress")

            # ========== 修改为入向流量 ==========
            with allure_step_log("步骤8: 修改方向为入向流量"):
                time.sleep(10)
                tm_page.tm_session_edit(
                    new_session_name,
                    direction="入向流量",
                )
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤9: 列表页验证入向 + 抓包验证入向流量"):
                tm_page.page.wait_for_timeout(3000)
                row_data = tm_page.get_row_data(new_session_name)
                assert "入向流量" in row_data.get("方向", ""), \
                    f"[FieldAssertion] 方向不匹配: 期望 入向流量, 实际 {row_data.get('方向')}"
                _assert_tcpdump_direction(ssh_vm, vm1_mfip, vm3_info["mfip"], vm2_info["ip"], "ingress")

            # ========== 修改为全部流量 ==========
            with allure_step_log("步骤10: 修改方向为全部流量"):
                time.sleep(10)
                tm_page.tm_session_edit(
                    new_session_name,
                    direction="全部流量",
                )
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤11: 列表页验证全部流量 + 抓包验证双向流量"):
                tm_page.page.wait_for_timeout(3000)
                row_data = tm_page.get_row_data(new_session_name)
                assert "全部流量" in row_data.get("方向", ""), \
                    f"[FieldAssertion] 方向不匹配: 期望 全部流量, 实际 {row_data.get('方向')}"
                _assert_tcpdump_direction(ssh_vm, vm1_mfip, vm3_info["mfip"], vm2_info["ip"], "both")

        finally:
            # ========== 清理 ==========
            with allure_step_log("清理: 镜像会话"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.goto_tm_session_tab(tm_name)
                    delete_target = new_session_name if session_modified else session_name
                    tm_page.tm_session_delete(delete_target)
                    tm_page.assert_deleted(delete_target, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理镜像会话失败: {e}")

            with allure_step_log("清理: 流量镜像实例"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.tm_delete(tm_name)
                    tm_page.assert_deleted(tm_name, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理流量镜像实例失败: {e}")

            with allure_step_log("清理: 解绑MFIP（VM3）"):
                try:
                    if vm3_info and vm3_info.get("ip"):
                        ops_page = OpsPage(tm_page.page)
                        ops_page.goto_service("基础设施")
                        ops_page.goto_submenu("平台网络")
                        ops_page.mfip_delete(vm3_info["ip"])
                        ops_page.assert_deleted(vm3_info["ip"], timeout=30000)
                except Exception as e:
                    logger.warning(f"解绑MFIP失败: {e}")

            with allure_step_log("清理: 弹性云服务器（VM2、VM3）"):
                for vm_info in [vm2_info, vm3_info]:
                    try:
                        if vm_info and vm_info.get("name"):
                            ecs_page.goto_service("弹性云服务器")
                            ecs_page.goto_submenu("弹性云服务器")
                            ecs_page.ecs_remove(vm_info["name"])
                            ecs_page.assert_deleted(vm_info["name"], timeout=60000)
                    except Exception as e:
                        logger.warning(f"移除ECS {vm_info.get('name')} 失败: {e}")

            with allure_step_log("清理: 从回收站彻底删除ECS（VM2、VM3）"):
                for vm_info in [vm2_info, vm3_info]:
                    try:
                        if vm_info and vm_info.get("name"):
                            ecs_page.goto_submenu("回收站")
                            ecs_page.ecs_delete(vm_info["name"])
                            ecs_page.assert_deleted(vm_info["name"], timeout=60000)
                    except Exception as e:
                        logger.warning(f"从回收站删除ECS {vm_info.get('name')} 失败: {e}")

            with allure_step_log("清理: VPC2"):
                try:
                    if vpc2_info and vpc2_info.get("name"):
                        vpc_page = VpcPage(tm_page.page)
                        vpc_page.goto_service("虚拟私有云")
                        vpc_page.goto_submenu("虚拟私有云")
                        vpc_page.vpc_delete(vpc2_info["name"])
                        vpc_page.assert_deleted(vpc2_info["name"], timeout=30000)
                except Exception as e:
                    logger.warning(f"清理VPC2失败: {e}")

            # VM1和VPC1由fixture teardown自动清理
