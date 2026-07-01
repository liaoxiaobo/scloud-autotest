import allure
import pytest
import re
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.network import VpcPage, TransferStrategyPage
from sugon_web.pages.network.sci_kms import SciKmsPage
from sugon_web.pages.compute import EcsPage
from sugon_web.common.mfip_helper import MfipHelper


def _resolve_vm_ip_and_mfip(ecs_page, ssh_host, browser, config, vm_name):
    """解析虚机固定IP并绑定MFIP（用于class-scoped自建虚机的SSH连通）。

    从ECS列表行获取虚机ID与固定IP，通过 scli guest show 取得 port_id，
    再经 admin context 调用 SDN API 绑定 MFIP，返回 (fixed_ip, mfip)。

    Args:
        ecs_page: ECS页面对象（已在弹性云服务器列表页且已搜索目标虚机）。
        ssh_host: 直连环境的SSH客户端，用于 guest_show 取 port_id。
        browser: Playwright Browser 实例，用于创建 admin context 绑定MFIP。
        config: 配置对象。
        vm_name: 虚机名称。

    Returns:
        tuple[str, str]: (固定IP, MFIP地址)。
    """
    row_data = ecs_page.get_row_data(vm_name)
    ip_text = row_data.get("IP地址", "")
    fixed_match = re.search(r"固定:\s*(\d+\.\d+\.\d+\.\d+)", ip_text)
    fixed_ip = fixed_match.group(1) if fixed_match else ""
    name_id_text = row_data.get("名称/ID", "")
    vm_id = name_id_text.split(":", 1)[1].strip() if ":" in name_id_text else ""

    guest_info = ssh_host.guest_show(vm_id)
    import json
    ip_address_raw = guest_info.get("ip_address", "{}")
    ip_data = json.loads(ip_address_raw) if ip_address_raw else {}
    port_id = ip_data.get("port_id") or guest_info.get("port_id")
    project_id = guest_info.get("project_id") or guest_info.get("project") or "admin-inner-project"
    if not fixed_ip:
        raise RuntimeError(f"虚机 {vm_name}(id={vm_id}) 未解析到固定IP")
    if not port_id:
        raise RuntimeError(f"虚机 {vm_name}(id={vm_id}) 未取得 port_id，无法绑定MFIP")

    # 先查询是否已绑定 MFIP，避免重复绑定导致“该port已经绑定mfip”
    try:
        mfip = ssh_host.find_mfip(fixed_ip)
        logger.info(f"虚机 {vm_name} 固定IP={fixed_ip}, 已存在MFIP={mfip}，直接复用")
    except RuntimeError:
        mfip = MfipHelper.bind_mfip_with_admin_context(
            browser, config, port_id=port_id, project_id=project_id
        )
        logger.info(f"虚机 {vm_name} 固定IP={fixed_ip}, 已绑定MFIP={mfip}")
    return fixed_ip, mfip


def _is_ssh_reachable(ssh_vm, target_ip: str, timeout: int = 5) -> bool:
    """通过真实 ssh 连接判断 target_ip:22 是否可达。

    不依赖 nc 的 TCP 三次握手，而是禁用公钥自动认证后检测 SSH 协议层返回的
    密码输入提示或认证失败信息。若命令超时且没有任何上述输出，则视为不可达。

    Args:
        ssh_vm: SSH VM 客户端。
        target_ip: 目标 IP 地址。
        timeout: ssh 命令最大等待秒数。

    Returns:
        bool: 可达返回 True，不可达返回 False。
    """
    connect_timeout = max(timeout - 2, 2)
    cmd = (
        f"timeout {timeout} ssh "
        f"-o ConnectTimeout={connect_timeout} "
        f"-o StrictHostKeyChecking=no "
        f"-o UserKnownHostsFile=/dev/null "
        f"-o PubkeyAuthentication=no "
        f"-o NumberOfPasswordPrompts=1 "
        f"root@{target_ip} exit"
    )
    result = ssh_vm.run(
        cmd,
        return_rc=True,
        return_stdout=True,
        return_stderr=True,
        timeout=timeout + 5,
    )
    combined = (result.get("stdout", "") + result.get("stderr", "")).lower()
    reach_markers = (
        "authenticity of host",
        "key fingerprint",
        "password:",
        "permission denied",
        "warning: permanently added",
    )
    return any(marker in combined for marker in reach_markers)


@allure.epic('网络服务')
@allure.feature('传输策略组')
@allure.story('可信传输生效性验证-东西向流量-开机状态绑定-openssl纯软-tcp')
class TestTransferStrategyOpensslSoftTcpEffectiveness:
    """可信传输生效性验证-东西向流量-开机状态绑定-openssl纯软-tcp。

    用例422160：验证同VPC下开启机密互联的VM之间TCP流量加密生效，
    未开启机密互联的VM之间TCP流量被拦截（SSH失败），但ping和UDP正常。
    所有前置资源通过class-scoped fixture共享创建，批次末统一清理。
    """

    @pytest.fixture(scope="class", autouse=True)
    def shared_resources(self, request, browser_context, config, ssh_host):
        """Class-scoped fixture：创建共享的VPC、VM、传输策略组、密钥、加密规则。

        Yields:
            dict: 包含所有共享资源的名称和元数据。
        """
        page = _create_logged_in_page(browser_context, config)
        vpc_page = VpcPage(page)
        ecs_page = EcsPage(page)
        transfer_page = TransferStrategyPage(page)
        kms_page = SciKmsPage(page)

        vpc_name = "sci_vpc1"
        vpc_cidr = "176.176.20.0/24"
        strategy_name = "ossl_group1_autotest"
        key_name = "sm4-ossl1_autotest"
        vm1_name = "sci_ecs1"
        vm2_name = "sci_ecs2"
        vm3_name = "sci_ecs3"

        result = {
            "vpc_name": vpc_name,
            "vpc_cidr": vpc_cidr,
            "strategy_name": strategy_name,
            "key_name": key_name,
            "vm1_name": vm1_name,
            "vm2_name": vm2_name,
            "vm3_name": vm3_name,
        }

        try:
            # 0. 预清理：若回收站中存在同名VM，先彻底删除，避免"实例名称已存在回收站中"导致创建失败
            with allure_step_log("前置: 预清理回收站中可能存在的同名VM"):
                for vm_name in [vm1_name, vm2_name, vm3_name]:
                    try:
                        ecs_page.goto_service("弹性云服务器")
                        ecs_page.goto_submenu("回收站")
                        ecs_page.wait_for_page_ready()
                        ecs_page.search(vm_name)
                        ecs_page.wait_for_page_ready()
                        try:
                            row_data = ecs_page.get_row_data(vm_name)
                            if row_data and row_data.get("名称") == vm_name:
                                ecs_page.ecs_recover_delete(vm_name, delete_volume=True, release_ip=True)
                                ecs_page.assert_deleted(vm_name, timeout=30000)
                                logger.info(f"预清理: 从回收站彻底删除VM {vm_name}")
                        except AssertionError:
                            pass
                    except Exception as e:
                        logger.debug(f"预清理回收站VM {vm_name} 时出错: {e}")

            # 1. 创建VPC
            with allure_step_log(f"前置: 创建VPC {vpc_name}"):
                vpc_page.goto_service("虚拟私有云")
                vpc_page.goto_submenu("虚拟私有云")
                vpc_page.wait_for_page_ready()
                try:
                    vpc_page.search(vpc_name)
                    vpc_page.wait_for_page_ready()
                    row_data = vpc_page.get_row_data(vpc_name)
                    if row_data and row_data.get("名称") == vpc_name:
                        logger.info(f"VPC {vpc_name} 已存在，跳过创建")
                    else:
                        raise AssertionError("VPC不存在")
                except AssertionError:
                    vpc_page.vpc_create(
                        name=vpc_name,
                        subnet_name=f"{vpc_name}-subnet",
                        cidr=vpc_cidr,
                    )
                    vpc_page.assert_popup_success("创建虚拟私有云成功")
                    vpc_page.assert_status(vpc_name)

            # 2. 创建传输策略组
            with allure_step_log(f"前置: 确保传输策略组 {strategy_name} 存在"):
                transfer_page.goto_service("虚拟私有云")
                transfer_page.goto_submenu("机密互联")
                transfer_page.wait_for_page_ready()
                if not transfer_page.transfer_strategy_exists(strategy_name):
                    transfer_page.transfer_strategy_create(name=strategy_name)
                    transfer_page.assert_popup_success(timeout=10000)

            # 3. 创建密钥
            with allure_step_log(f"前置: 确保密钥 {key_name} 存在"):
                kms_page.goto_service("可信密码模块")
                kms_page.goto_submenu("密钥管理")
                kms_page.wait_for_page_ready()
                kms_page.search(key_name)
                kms_page.wait_for_page_ready()
                try:
                    row_data = kms_page.get_row_data(key_name)
                    if row_data and row_data.get("名称") == key_name:
                        logger.info(f"密钥 {key_name} 已存在，跳过创建")
                    else:
                        raise AssertionError("密钥不存在")
                except AssertionError:
                    kms_page.kms_create(
                        name=key_name,
                        engine="OPENSSL纯软",
                        key_type="SM4 (用途：加解密，包括系统盘、数据盘、网卡等)",
                        desc="自动化测试密钥",
                    )
                    kms_page.assert_popup_success(timeout=10000)

            # 4. 创建加密规则（TCP协议）
            with allure_step_log(f"前置: 确保加密规则存在"):
                transfer_page.goto_service("虚拟私有云")
                transfer_page.goto_submenu("机密互联")
                transfer_page.wait_for_page_ready()
                transfer_page.goto_transfer_strategy_detail(strategy_name)
                transfer_page.wait_for_page_ready()
                tab = transfer_page.get_by_role("tab", name="加密规则")
                tab.click()
                transfer_page.wait_for_page_ready()

                try:
                    # 使用Page Object方法检查加密规则是否已存在
                    if transfer_page.encrypt_rule_exists(vpc_cidr):
                        logger.info(f"加密规则 {vpc_cidr} 已存在，跳过创建")
                    else:
                        raise AssertionError("规则不存在")
                except AssertionError:
                    transfer_page.encrypt_rule_create(
                        key_name=key_name,
                        remote_cidr=vpc_cidr,
                        protocol="TCP",
                        ip_version="IPv4",
                    )
                    transfer_page.assert_popup_success(timeout=10000)

            # 5. 创建3台VM（逐一创建，非批量）
            # VM1: 开启机密互联
            with allure_step_log(f"前置: 创建VM {vm1_name}"):
                ecs_page.goto_service("弹性云服务器")
                ecs_page.goto_submenu("弹性云服务器")
                ecs_page.wait_for_page_ready()
                try:
                    ecs_page.search(vm1_name)
                    ecs_page.wait_for_page_ready()
                    row_data = ecs_page.get_row_data(vm1_name)
                    if row_data and vm1_name in row_data.get("名称/ID", ""):
                        logger.info(f"VM {vm1_name} 已存在，跳过创建")
                    else:
                        raise AssertionError("VM不存在")
                except AssertionError:
                    ecs_page.ecs_create(
                        basic={"name": vm1_name, "count": 1, "cluster": "Autotest"},
                        network={"networks": [{"network": vpc_name, "subnet": f"{vpc_name}-subnet", "ip_allocation": "手动分配", "ip_index": 0, "enable_confidential_interconnect": True}]},
                    )
                    ecs_page.assert_popup_success(timeout=30000)
                    ecs_page.assert_status(vm1_name, status="运行", timeout=600)
                result["vm1_ip"], result["vm1_mfip"] = _resolve_vm_ip_and_mfip(
                    ecs_page, ssh_host, browser_context.browser, config, vm1_name
                )

            # VM2: 开启机密互联
            with allure_step_log(f"前置: 创建VM {vm2_name}"):
                ecs_page.goto_service("弹性云服务器")
                ecs_page.goto_submenu("弹性云服务器")
                ecs_page.wait_for_page_ready()
                try:
                    ecs_page.search(vm2_name)
                    ecs_page.wait_for_page_ready()
                    row_data = ecs_page.get_row_data(vm2_name)
                    if row_data and vm2_name in row_data.get("名称/ID", ""):
                        logger.info(f"VM {vm2_name} 已存在，跳过创建")
                    else:
                        raise AssertionError("VM不存在")
                except AssertionError:
                    ecs_page.ecs_create(
                        basic={"name": vm2_name, "count": 1, "cluster": "Autotest"},
                        network={"networks": [{"network": vpc_name, "subnet": f"{vpc_name}-subnet", "ip_allocation": "手动分配", "ip_index": 0, "enable_confidential_interconnect": True}]},
                    )
                    ecs_page.assert_popup_success(timeout=30000)
                    ecs_page.assert_status(vm2_name, status="运行", timeout=600)
                result["vm2_ip"], result["vm2_mfip"] = _resolve_vm_ip_and_mfip(
                    ecs_page, ssh_host, browser_context.browser, config, vm2_name
                )

            # VM3: 普通VM，不开启机密互联
            with allure_step_log(f"前置: 创建VM {vm3_name}"):
                ecs_page.goto_service("弹性云服务器")
                ecs_page.goto_submenu("弹性云服务器")
                ecs_page.wait_for_page_ready()
                try:
                    ecs_page.search(vm3_name)
                    ecs_page.wait_for_page_ready()
                    row_data = ecs_page.get_row_data(vm3_name)
                    if row_data and vm3_name in row_data.get("名称/ID", ""):
                        logger.info(f"VM {vm3_name} 已存在，跳过创建")
                    else:
                        raise AssertionError("VM不存在")
                except AssertionError:
                    ecs_page.ecs_create(
                        basic={"name": vm3_name, "count": 1, "cluster": "Autotest"},
                        network={"networks": [{"network": vpc_name, "subnet": f"{vpc_name}-subnet"}]},
                    )
                    ecs_page.assert_popup_success(timeout=30000)
                    ecs_page.assert_status(vm3_name, status="运行", timeout=600)
                result["vm3_ip"], result["vm3_mfip"] = _resolve_vm_ip_and_mfip(
                    ecs_page, ssh_host, browser_context.browser, config, vm3_name
                )

            yield result

        finally:
            # 清理阶段：按CSV要求的顺序
            # 1. 解绑传输策略组
            # 2. 删除传输策略组（连带删除加密规则）
            # 3. 删除VM（先移到回收站，再从回收站彻底删除）
            # 4. 删除VPC
            with allure_step_log("Class Teardown: 清理共享资源"):
                page = _create_logged_in_page(browser_context, config)
                ecs_page = EcsPage(page)
                vpc_page = VpcPage(page)
                transfer_page = TransferStrategyPage(page)

                # 1. 解绑传输策略组
                with allure_step_log(f"清理: 解绑VM的传输策略组"):
                    for vm_name in [vm1_name, vm2_name]:
                        try:
                            ecs_page.goto_service("弹性云服务器")
                            ecs_page.goto_submenu("弹性云服务器")
                            ecs_page.wait_for_page_ready()
                            ecs_page.ecs_nic_set_transfer_strategy(vm_name, strategy_name="不加密")
                            ecs_page.assert_popup_success(timeout=10000)
                        except Exception as e:
                            logger.warning(f"解绑 {vm_name} 传输策略组失败: {e}")

                # 2. 删除传输策略组
                with allure_step_log(f"清理: 删除传输策略组 {strategy_name}"):
                    try:
                        transfer_page.goto_service("虚拟私有云")
                        transfer_page.goto_submenu("机密互联")
                        transfer_page.wait_for_page_ready()
                        transfer_page.transfer_strategy_delete(strategy_name)
                        transfer_page.assert_deleted(strategy_name, timeout=30000)
                    except Exception as e:
                        logger.warning(f"删除传输策略组 {strategy_name} 失败: {e}")

                # 3. 删除VM（先移到回收站，再从回收站彻底删除）
                with allure_step_log(f"清理: 删除VM"):
                    for vm_name in [vm1_name, vm2_name, vm3_name]:
                        try:
                            # 先移到回收站
                            ecs_page.goto_service("弹性云服务器")
                            ecs_page.goto_submenu("弹性云服务器")
                            ecs_page.wait_for_page_ready()
                            ecs_page.ecs_remove(vm_name)
                            ecs_page.assert_deleted(vm_name, timeout=30000)
                        except Exception as e:
                            logger.warning(f"移动VM {vm_name} 到回收站失败: {e}")

                    # 从回收站彻底删除
                    for vm_name in [vm1_name, vm2_name, vm3_name]:
                        try:
                            ecs_page.goto_submenu("回收站")
                            ecs_page.wait_for_page_ready()
                            ecs_page.ecs_recover_delete(vm_name, delete_volume=True, release_ip=True)
                            ecs_page.assert_deleted(vm_name, timeout=30000)
                        except Exception as e:
                            logger.warning(f"从回收站彻底删除VM {vm_name} 失败: {e}")

                # 4. 删除VPC
                with allure_step_log(f"清理: 删除VPC {vpc_name}"):
                    try:
                        vpc_page.goto_service("虚拟私有云")
                        vpc_page.goto_submenu("虚拟私有云")
                        vpc_page.wait_for_page_ready()
                        vpc_page.vpc_delete(vpc_name)
                        vpc_page.assert_deleted(vpc_name, timeout=30000)
                    except Exception as e:
                        logger.warning(f"删除VPC {vpc_name} 失败: {e}")

                page.close()

    @allure.title("可信传输-生效性验证-东西向流量-开机状态绑定-openssl纯软-tcp")
    def test_transfer_strategy_openssl_soft_tcp_effectiveness(
        self, ecs_page, transfer_strategy_page, ssh_vm, shared_resources
    ):
        """验证可信传输生效性-东西向流量-开机状态绑定-openssl纯软-tcp。

        用例422160：
        1. 为sci_ecs1和sci_ecs2绑定传输策略组
        2. 验证传输策略组关联实例
        3. sci_ecs1与sci_ecs2连通性验证（应成功）
        4. sci_ecs1与sci_ecs3连通性验证（SSH应失败，ping和UDP应成功）
        """
        vm1_name = shared_resources["vm1_name"]
        vm2_name = shared_resources["vm2_name"]
        vm3_name = shared_resources["vm3_name"]
        strategy_name = shared_resources["strategy_name"]
        vm1_ip = shared_resources.get("vm1_ip", "")
        vm2_ip = shared_resources.get("vm2_ip", "")
        vm3_ip = shared_resources.get("vm3_ip", "")
        vm1_mfip = shared_resources.get("vm1_mfip", "")
        vm2_mfip = shared_resources.get("vm2_mfip", "")
        vm3_mfip = shared_resources.get("vm3_mfip", "")

        # 步骤1：为sci_ecs1绑定传输策略组
        with allure_step_log(f"步骤1: 为 {vm1_name} 绑定传输策略组 {strategy_name}"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_page.ecs_nic_set_transfer_strategy(vm1_name, strategy_name=strategy_name)
            ecs_page.assert_popup_success(timeout=10000)

        # 断言网卡列表字段
        with allure_step_log(f"步骤1-1: 断言 {vm1_name} 网卡列表字段"):
            ecs_page.ecs_nic_assert_transfer_strategy(vm1_name, expected_strategy=strategy_name)

        # 步骤2：为sci_ecs2绑定传输策略组
        with allure_step_log(f"步骤2: 为 {vm2_name} 绑定传输策略组 {strategy_name}"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_page.ecs_nic_set_transfer_strategy(vm2_name, strategy_name=strategy_name)
            ecs_page.assert_popup_success(timeout=10000)

        # 断言网卡列表字段
        with allure_step_log(f"步骤2-1: 断言 {vm2_name} 网卡列表字段"):
            ecs_page.ecs_nic_assert_transfer_strategy(vm2_name, expected_strategy=strategy_name)

        # 步骤3：验证传输策略组关联实例
        with allure_step_log(f"步骤3: 验证传输策略组关联实例"):
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()
            transfer_strategy_page.goto_transfer_strategy_detail(strategy_name)
            transfer_strategy_page.wait_for_page_ready()
            tab = transfer_strategy_page.get_by_role("tab", name="关联实例")
            tab.click()
            transfer_strategy_page.wait_for_page_ready()

            # 断言关联实例列表显示sci_ecs1和sci_ecs2
            transfer_strategy_page.assert_list_contain(vm1_name)
            transfer_strategy_page.assert_list_contain(vm2_name)

            # 断言状态为"运行"
            row1 = transfer_strategy_page.get_row_data(vm1_name)
            assert row1.get("状态", "") == "运行", (
                f"[FieldAssertion] 关联实例状态 | 期望: 运行 | 实际: {row1.get('状态', '')}"
            )
            row2 = transfer_strategy_page.get_row_data(vm2_name)
            assert row2.get("状态", "") == "运行", (
                f"[FieldAssertion] 关联实例状态 | 期望: 运行 | 实际: {row2.get('状态', '')}"
            )

        # 步骤4：sci_ecs1与sci_ecs2连通性验证（同VPC + 机密互联）
        with allure_step_log(f"步骤4: {vm1_name} 与 {vm2_name} 连通性验证"):
            # 虚机绑定MFIP后可能存在生效时延，先等待3分钟再尝试SSH连接
            logger.info("虚机已绑定MFIP，等待180秒让MFIP网络路径生效...")
            ecs_page.page.wait_for_timeout(180000)
            logger.info("180秒等待结束，开始尝试SSH连接")

            # 使用ssh_vm连接vm1的MFIP
            ssh_vm.connect(vm1_mfip)

            # 子步骤1：ping测试
            with allure_step_log(f"子步骤4-1: ping测试 {vm2_ip}"):
                result = ssh_vm.run(f"ping -c 4 {vm2_ip}", return_rc=True)
                assert result["rc"] == 0, f"[BackendAssertion] ping {vm2_ip} 失败: {result.get('stderr', '')}"
                assert "0% packet loss" in result["stdout"] or "4 received" in result["stdout"], (
                    f"[BackendAssertion] ping丢包 | 期望: 0%丢包 | 实际: {result['stdout']}"
                )

            # 子步骤2：TCP 22端口连通性测试（验证TCP流量被加密放行）
            # 使用真实 ssh 连接探测，有指纹/密码提示即代表 SSH 协议层可达
            with allure_step_log(f"子步骤4-2: TCP 22端口连通性测试 {vm2_ip}"):
                assert _is_ssh_reachable(ssh_vm, vm2_ip), (
                    f"[BackendAssertion] TCP 22 端口 {vm2_ip} 不可达"
                )
                logger.info(f"TCP 22 端口 {vm2_ip} SSH 可达，符合预期（TCP被加密放行）")

            # 子步骤3：UDP连通性验证（nc）
            with allure_step_log(f"子步骤4-3: UDP连通性验证"):
                # 直连vm2的MFIP，在vm2上启动nc服务端（输出落盘，便于校验收到数据）
                ssh_vm.connect(vm2_mfip)
                ssh_vm.run("pkill -f 'nc -4 -u -l 2389' || true", return_rc=True)
                ssh_vm.run("rm -f /tmp/nc_recv.txt", return_rc=True)
                result = ssh_vm.run(
                    "nohup nc -4 -u -l 2389 > /tmp/nc_recv.txt 2>&1 &",
                    return_rc=True, wait_for_exit=False
                )
                assert result["rc"] == 0, f"[BackendAssertion] 在 {vm2_name} 启动nc服务端失败"

                # 轮询等待nc服务端启动
                for _ in range(30):
                    check = ssh_vm.run("ps aux | grep 'nc -4 -u -l 2389' | grep -v grep", return_rc=True)
                    if check["rc"] == 0 and "2389" in check["stdout"]:
                        break
                    ssh_vm.run("sleep 2", return_rc=True)
                else:
                    raise AssertionError(f"[BackendAssertion] {vm2_name} nc服务端未在60秒内启动")

                # 直连vm1的MFIP，在vm1上启动nc客户端发送数据
                ssh_vm.connect(vm1_mfip)
                result = ssh_vm.run(f"echo testdata | nc -4 -u -w 3 {vm2_ip} 2389", return_rc=True)
                assert result["rc"] == 0, f"[BackendAssertion] {vm1_name} nc客户端发送数据失败"

                # 回到vm2校验服务端是否收到数据
                ssh_vm.connect(vm2_mfip)
                ssh_vm.run("sleep 2", return_rc=True)
                recv = ssh_vm.run("cat /tmp/nc_recv.txt", return_rc=True)
                assert "testdata" in recv["stdout"], (
                    f"[BackendAssertion] {vm2_name} 服务端未收到UDP数据 | 实际: {recv['stdout']}"
                )
                logger.info(f"{vm1_name}->{vm2_name} UDP连通性验证完成，服务端已收到数据")

                # 清理nc进程
                ssh_vm.run("pkill -f 'nc -4 -u -l 2389' || true", return_rc=True)
                ssh_vm.run("rm -f /tmp/nc_recv.txt", return_rc=True)
                ssh_vm.connect(vm1_mfip)

        # 步骤5：sci_ecs1与sci_ecs3连通性验证（同VPC + 非机密互联）
        with allure_step_log(f"步骤5: {vm1_name} 与 {vm3_name} 连通性验证（非机密互联）"):
            # 子步骤1：ping测试（应成功）
            with allure_step_log(f"子步骤5-1: ping测试 {vm3_ip}"):
                ssh_vm.connect(vm1_mfip)
                result = ssh_vm.run(f"ping -c 4 {vm3_ip}", return_rc=True)
                assert result["rc"] == 0, f"[BackendAssertion] ping {vm3_ip} 失败"
                assert "0% packet loss" in result["stdout"] or "4 received" in result["stdout"], (
                    f"[BackendAssertion] ping丢包 | 期望: 0%丢包 | 实际: {result['stdout']}"
                )

            # 子步骤2：TCP 22端口连通性测试（应失败，因为sci_ecs3未开启机密互联，TCP被拦截）
            # 使用真实 ssh 连接探测，无指纹/密码提示即代表被拦截
            with allure_step_log(f"子步骤5-2: TCP 22端口连通性测试 {vm3_ip}（应失败）"):
                assert not _is_ssh_reachable(ssh_vm, vm3_ip), (
                    f"[BackendAssertion] TCP 22 端口应被拦截但实际 SSH 可达"
                )
                logger.info(f"TCP 22 端口 {vm3_ip} 不可达，符合预期（TCP被拦截）")

            # 子步骤3：UDP连通性验证（应成功，UDP不受TCP加密规则影响）
            with allure_step_log(f"子步骤5-3: UDP连通性验证（应成功）"):
                # 直连vm3的MFIP（经跳板机，不走被拦截的vm1->vm3 TCP），启动nc服务端
                ssh_vm.connect(vm3_mfip)
                ssh_vm.run("pkill -f 'nc -4 -u -l 2389' || true", return_rc=True)
                ssh_vm.run("rm -f /tmp/nc_recv.txt", return_rc=True)
                result = ssh_vm.run(
                    "nohup nc -4 -u -l 2389 > /tmp/nc_recv.txt 2>&1 &",
                    return_rc=True, wait_for_exit=False
                )
                assert result["rc"] == 0, f"[BackendAssertion] 在 {vm3_name} 启动nc服务端失败"

                # 轮询等待nc服务端启动
                for _ in range(30):
                    check = ssh_vm.run("ps aux | grep 'nc -4 -u -l 2389' | grep -v grep", return_rc=True)
                    if check["rc"] == 0 and "2389" in check["stdout"]:
                        break
                    ssh_vm.run("sleep 2", return_rc=True)
                else:
                    raise AssertionError(f"[BackendAssertion] {vm3_name} nc服务端未在60秒内启动")

                # 直连vm1的MFIP，在vm1上启动nc客户端发送数据（UDP，应可达）
                ssh_vm.connect(vm1_mfip)
                result = ssh_vm.run(f"echo testdata | nc -4 -u -w 3 {vm3_ip} 2389", return_rc=True)
                assert result["rc"] == 0, f"[BackendAssertion] {vm1_name} nc客户端发送数据失败"

                # 回到vm3校验服务端是否收到数据（UDP不受TCP加密规则影响，应收到）
                ssh_vm.connect(vm3_mfip)
                ssh_vm.run("sleep 2", return_rc=True)
                recv = ssh_vm.run("cat /tmp/nc_recv.txt", return_rc=True)
                assert "testdata" in recv["stdout"], (
                    f"[BackendAssertion] {vm3_name} 服务端未收到UDP数据 | 实际: {recv['stdout']}"
                )
                logger.info(f"{vm1_name}->{vm3_name} UDP连通性验证完成（UDP不受TCP规则影响）")

                # 清理nc进程
                ssh_vm.run("pkill -f 'nc -4 -u -l 2389' || true", return_rc=True)
                ssh_vm.run("rm -f /tmp/nc_recv.txt", return_rc=True)
                ssh_vm.connect(vm1_mfip)
