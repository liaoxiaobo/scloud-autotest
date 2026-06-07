import time
import random

import pytest
import allure
from sugon_web.pages.network import VpcPage
from sugon_web.pages.ops import OpsPage
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


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
    rows = ops_page.get_rows_by_text(vm_ip)
    last_row = rows.last
    row_data = ops_page.get_row_data_by_locator(last_row)
    return row_data.get("管理IP地址")


@allure.epic('网络服务')
@allure.feature('流量镜像')
@allure.story('云内实例生效性验证')
@pytest.mark.parametrize("vpc", [{"name_prefix": "tm_"}], indirect=True)
@pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "name_prefix": "tm_"}], indirect=True)
class TestTMInnerInstanceValidation:
    """流量镜像-云内实例-镜像会话生效性验证（用例407249）"""

    @allure.title("流量镜像-云内实例-镜像会话生效性验证")
    def test_tm_inner_instance_validation(self, tm_page, ecs_page, vpc, vm, ssh_vm):
        """验证流量镜像云内实例类型的镜像会话生效性。

        前置资源：
        - fixture vpc+vm: VPC1 + VM1（目的实例，自动MFIP）
        - 测试体内: VPC2 + VM2（镜像源）+ VM3（发起ping）
        """
        vm1_name = vm["name"]
        vm1_mfip = vm.get("mfip")

        tm_name = f"tm-inside-{random_data()}"
        session_name = f"tm-session-{random_data()}"
        vpc2_info = None
        vm2_info = None
        vm3_info = None

        try:
            # 前置: 创建VPC2 + VM2 + VM3
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

            # 步骤1: 创建云内实例类型流量镜像
            with allure_step_log("步骤1: 创建云内实例类型流量镜像"):
                tm_page.goto_service("流量镜像")
                tm_page.goto_submenu("流量镜像")
                tm_page.tm_create_inner_ecs(name=tm_name, server_name=vm1_name)
                tm_page.assert_popup_success(timeout=10000)
                tm_page.assert_list_contain(tm_name, column_name="名称")
                tm_page.assert_status(tm_name, status="正常")

            # 步骤2: 创建镜像会话
            with allure_step_log("步骤2: 创建镜像会话"):
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

            with allure_step_log("步骤3: 验证镜像会话列表页"):
                tm_page.assert_list_contain(session_name, column_name="名称")
                row_data = tm_page.get_row_data(session_name)
                assert "全部流量" in row_data.get("方向", ""), f"[FieldAssertion] 方向不匹配: {row_data.get('方向')}"
                assert "在线" in row_data.get("状态", ""), f"[FieldAssertion] 状态不匹配: {row_data.get('状态')}"
                assert "是" in row_data.get("是否开启", ""), f"[FieldAssertion] 是否开启不匹配: {row_data.get('是否开启')}"

            # 步骤4: 在目的实例VM1上启动tcpdump抓包
            with allure_step_log("步骤4: 在目的实例VM1上启动tcpdump抓包"):
                assert vm1_mfip, f"[BackendAssertion] VM1未绑定MFIP，无法SSH连接"
                ssh_vm.connect(vm1_mfip)
                # 清理旧文件
                ssh_vm.run("rm -f /tmp/tcpdump_result.txt")
                # 后台启动tcpdump
                result = ssh_vm.run(
                    "nohup tcpdump -i eth1 icmp -nvv -c 10 > /tmp/tcpdump_result.txt 2>&1 &",
                    return_rc=True,
                )
                assert result["rc"] == 0, f"[BackendAssertion] 启动tcpdump失败: {result.get('stderr', '')}"
                # 等待进程启动
                time.sleep(2)

            # 步骤5: 在VM3上向VM2发起ping
            with allure_step_log("步骤5: 在VM3上向VM2发起ping"):
                assert vm3_info.get("mfip"), f"[BackendAssertion] VM3未绑定MFIP"
                ssh_vm.connect(vm3_info["mfip"])
                result = ssh_vm.run(
                    f"ping -c 10 {vm2_info['ip']}",
                    return_rc=True,
                )
                assert result["rc"] == 0, f"[BackendAssertion] ping命令执行失败: {result.get('stderr', '')}"
                stdout = result["stdout"]
                assert "0% packet loss" in stdout or "10 received" in stdout, \
                    f"[BackendAssertion] ping未全部收到回复: {stdout}"

            # 步骤6: 在VM1上验证抓包结果
            with allure_step_log("步骤6: 在VM1上验证抓包结果"):
                ssh_vm.connect(vm1_mfip)
                # 轮询等待抓包结果
                tcpdump_output = ""
                for _ in range(30):  # 最多60秒
                    result = ssh_vm.run("cat /tmp/tcpdump_result.txt", return_rc=True)
                    if result["rc"] == 0:
                        tcpdump_output = result["stdout"]
                        if "ICMP" in tcpdump_output:
                            break
                    time.sleep(2)
                else:
                    raise AssertionError("[BackendAssertion] 60秒内未在VM1上抓到ICMP包")

                logger.info(f"tcpdump输出: {tcpdump_output}")

                # 断言双向ICMP流量（P2业务逻辑断言）
                stdout_lower = tcpdump_output.lower()
                has_request = "echo request" in stdout_lower
                has_reply = "echo reply" in stdout_lower
                assert has_request, f"[BackendAssertion] 未抓到ICMP请求包(echo request): {tcpdump_output}"
                assert has_reply, f"[BackendAssertion] 未抓到ICMP响应包(echo reply): {tcpdump_output}"

        finally:
            # 清理顺序：镜像会话 -> 流量镜像实例 -> MFIP -> ECS -> VPC
            with allure_step_log("清理: 镜像会话"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.goto_tm_session_tab(tm_name)
                    tm_page.tm_session_delete(session_name)
                    tm_page.assert_deleted(session_name, timeout=30000)
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
