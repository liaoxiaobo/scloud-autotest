import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('传输策略组')
@allure.story('不同协议加密规则新建功能验证')
class TestTransferStrategyEncryptRuleMultiProtocolCreate:
    """传输策略组不同协议加密规则新建功能验证。

    4个场景共享同一传输策略组 group1 和密钥 sm4-ossl1，
    通过 class-scoped fixture 共享资源，批次末统一清理。
    """

    @pytest.fixture(scope="class", autouse=True)
    def shared_resources(self, request, browser_context, config):
        """Class-scoped fixture：创建共享的传输策略组和密钥，供4个场景复用。

        Yields:
            dict: 包含 strategy_name（传输策略组名称）和 key_name（密钥名称）。
        """
        from sugon_web.conftest import _create_logged_in_page
        from sugon_web.pages.network import TransferStrategyPage
        from sugon_web.pages.kms import KmsPage

        page = _create_logged_in_page(browser_context, config)
        transfer_page = TransferStrategyPage(page)
        kms_page = KmsPage(page)

        strategy_name = "group1"
        key_name = f"sm4-ossl1-{random_data()}"

        try:
            # 1. 确保传输策略组存在
            with allure_step_log(f"前置: 确保传输策略组 {strategy_name} 存在"):
                transfer_page.goto_service("虚拟私有云")
                transfer_page.goto_submenu("机密互联")
                transfer_page.wait_for_page_ready()
                if not transfer_page.transfer_strategy_exists(strategy_name):
                    transfer_page.transfer_strategy_create(name=strategy_name)
                    transfer_page.assert_popup_success(timeout=10000)

            # 2. 创建密钥（OPENSSL纯软 + SM4）
            with allure_step_log(f"前置: 创建密钥 {key_name}"):
                kms_page.goto_service("可信密码模块")
                kms_page.kms_create(
                    name=key_name,
                    engine="OPENSSL纯软",
                    key_type="SM4 (用途：加解密，包括系统盘、数据盘、网卡等)",
                    desc="测试密钥-传输策略组加密规则用",
                )
                kms_page.assert_popup_success(timeout=10000)

            yield {"strategy_name": strategy_name, "key_name": key_name}

        finally:
            # 关闭 setup 阶段创建的页面，避免页面泄露
            page.close()

            # 清理阶段：先删规则，再删策略组，最后删密钥
            with allure_step_log("Class Teardown: 清理共享资源"):
                # 重新创建页面用于清理
                page = _create_logged_in_page(browser_context, config)
                transfer_page = TransferStrategyPage(page)
                kms_page = KmsPage(page)

                # 3. 删除传输策略组（会级联删除加密规则）
                with allure_step_log(f"清理: 删除传输策略组 {strategy_name}"):
                    try:
                        transfer_page._ensure_list_page()
                        transfer_page.wait_for_page_ready()
                        transfer_page.search(strategy_name)
                        transfer_page.wait_for_page_ready()
                        transfer_page.transfer_strategy_delete(strategy_name)
                        transfer_page.assert_deleted(strategy_name, timeout=30000)
                    except Exception as e:
                        logger.warning(f"清理传输策略组 {strategy_name} 失败: {e}")

                # 4. 删除密钥
                with allure_step_log(f"清理: 删除密钥 {key_name}"):
                    try:
                        kms_page.goto_service("可信密码模块")
                        kms_page.kms_delete(key_name)
                        kms_page.assert_deleted(key_name, timeout=30000)
                    except Exception as e:
                        logger.warning(f"清理密钥 {key_name} 失败: {e}")

                page.close()

    @allure.title("传输策略组-加密规则TCP新建验证")
    def test_encrypt_rule_tcp(self, transfer_strategy_page, shared_resources):
        """测试TCP协议加密规则创建。

        用例422128：协议TCP，IP版本IPv4，远端CIDR 10.0.0.0/24。
        """
        strategy_name = shared_resources["strategy_name"]
        key_name = shared_resources["key_name"]
        protocol = "TCP"
        ip_version = "IPv4"
        remote_cidr = "10.0.0.0/24"

        with allure_step_log("步骤1: 进入传输策略组模块"):
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤2: 进入策略组详情页并切换到加密规则tab"):
            transfer_strategy_page.goto_transfer_strategy_detail(strategy_name)
            transfer_strategy_page.wait_for_page_ready()
            tab = transfer_strategy_page.get_by_role("tab", name="加密规则")
            tab.click()
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤3-9: 创建TCP加密规则"):
            rule_info = transfer_strategy_page.encrypt_rule_create(
                key_name=key_name,
                remote_cidr=remote_cidr,
                protocol=protocol,
                ip_version=ip_version,
            )

        with allure_step_log("步骤3-9: 断言创建操作成功"):
            transfer_strategy_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤4: 确认策略组名称显示"):
            assert rule_info["strategy_name"] == strategy_name, \
                f"[FieldAssertion] 策略组名称不匹配 | 期望: {strategy_name} | 实际: {rule_info['strategy_name']}"

        with allure_step_log("步骤10: 加密规则列表校验"):
            transfer_strategy_page.assert_list_contain(remote_cidr, column_name="对端CIDR")
            row_data = transfer_strategy_page.get_encrypt_rule_row_data(remote_cidr)
            assert row_data.get("对端CIDR") == remote_cidr, \
                f"[FieldAssertion] 对端CIDR不匹配 | 期望: {remote_cidr} | 实际: {row_data.get('对端CIDR')}"
            assert row_data.get("密钥名称") == key_name, \
                f"[FieldAssertion] 密钥名称不匹配 | 期望: {key_name} | 实际: {row_data.get('密钥名称')}"
            assert row_data.get("IP协议") == protocol, \
                f"[FieldAssertion] IP协议不匹配 | 期望: {protocol} | 实际: {row_data.get('IP协议')}"
            assert row_data.get("IP版本") == ip_version, \
                f"[FieldAssertion] IP版本不匹配 | 期望: {ip_version} | 实际: {row_data.get('IP版本')}"

        with allure_step_log("清理: 删除本场景创建的加密规则"):
            transfer_strategy_page.encrypt_rule_delete(remote_cidr)
            transfer_strategy_page.assert_deleted(remote_cidr, timeout=30000)

    @allure.title("传输策略组-加密规则UDP新建验证")
    def test_encrypt_rule_udp(self, transfer_strategy_page, shared_resources):
        """测试UDP协议加密规则创建。

        用例1422128：协议UDP，IP版本IPv4，远端CIDR 10.0.1.0/24。
        """
        strategy_name = shared_resources["strategy_name"]
        key_name = shared_resources["key_name"]
        protocol = "UDP"
        ip_version = "IPv4"
        remote_cidr = "10.0.1.0/24"

        with allure_step_log("步骤1: 进入传输策略组模块"):
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤2: 进入策略组详情页并切换到加密规则tab"):
            transfer_strategy_page.goto_transfer_strategy_detail(strategy_name)
            transfer_strategy_page.wait_for_page_ready()
            tab = transfer_strategy_page.get_by_role("tab", name="加密规则")
            tab.click()
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤3-9: 创建UDP加密规则"):
            rule_info = transfer_strategy_page.encrypt_rule_create(
                key_name=key_name,
                remote_cidr=remote_cidr,
                protocol=protocol,
                ip_version=ip_version,
            )

        with allure_step_log("步骤3-9: 断言创建操作成功"):
            transfer_strategy_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤4: 确认策略组名称显示"):
            assert rule_info["strategy_name"] == strategy_name, \
                f"[FieldAssertion] 策略组名称不匹配 | 期望: {strategy_name} | 实际: {rule_info['strategy_name']}"

        with allure_step_log("步骤10: 加密规则列表校验"):
            transfer_strategy_page.assert_list_contain(remote_cidr, column_name="对端CIDR")
            row_data = transfer_strategy_page.get_encrypt_rule_row_data(remote_cidr)
            assert row_data.get("对端CIDR") == remote_cidr, \
                f"[FieldAssertion] 对端CIDR不匹配 | 期望: {remote_cidr} | 实际: {row_data.get('对端CIDR')}"
            assert row_data.get("密钥名称") == key_name, \
                f"[FieldAssertion] 密钥名称不匹配 | 期望: {key_name} | 实际: {row_data.get('密钥名称')}"
            assert row_data.get("IP协议") == protocol, \
                f"[FieldAssertion] IP协议不匹配 | 期望: {protocol} | 实际: {row_data.get('IP协议')}"
            assert row_data.get("IP版本") == ip_version, \
                f"[FieldAssertion] IP版本不匹配 | 期望: {ip_version} | 实际: {row_data.get('IP版本')}"

        with allure_step_log("清理: 删除本场景创建的加密规则"):
            transfer_strategy_page.encrypt_rule_delete(remote_cidr)
            transfer_strategy_page.assert_deleted(remote_cidr, timeout=30000)

    @allure.title("传输策略组-加密规则ICMP新建验证")
    def test_encrypt_rule_icmp(self, transfer_strategy_page, shared_resources):
        """测试ICMP协议加密规则创建。

        用例2422128：协议ICMP，IP版本IPv4，远端CIDR 10.0.2.0/24。
        """
        strategy_name = shared_resources["strategy_name"]
        key_name = shared_resources["key_name"]
        protocol = "ICMP"
        ip_version = "IPv4"
        remote_cidr = "10.0.2.0/24"

        with allure_step_log("步骤1: 进入传输策略组模块"):
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤2: 进入策略组详情页并切换到加密规则tab"):
            transfer_strategy_page.goto_transfer_strategy_detail(strategy_name)
            transfer_strategy_page.wait_for_page_ready()
            tab = transfer_strategy_page.get_by_role("tab", name="加密规则")
            tab.click()
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤3-9: 创建ICMP加密规则"):
            rule_info = transfer_strategy_page.encrypt_rule_create(
                key_name=key_name,
                remote_cidr=remote_cidr,
                protocol=protocol,
                ip_version=ip_version,
            )

        with allure_step_log("步骤3-9: 断言创建操作成功"):
            transfer_strategy_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤4: 确认策略组名称显示"):
            assert rule_info["strategy_name"] == strategy_name, \
                f"[FieldAssertion] 策略组名称不匹配 | 期望: {strategy_name} | 实际: {rule_info['strategy_name']}"

        with allure_step_log("步骤10: 加密规则列表校验"):
            transfer_strategy_page.assert_list_contain(remote_cidr, column_name="对端CIDR")
            row_data = transfer_strategy_page.get_encrypt_rule_row_data(remote_cidr)
            assert row_data.get("对端CIDR") == remote_cidr, \
                f"[FieldAssertion] 对端CIDR不匹配 | 期望: {remote_cidr} | 实际: {row_data.get('对端CIDR')}"
            assert row_data.get("密钥名称") == key_name, \
                f"[FieldAssertion] 密钥名称不匹配 | 期望: {key_name} | 实际: {row_data.get('密钥名称')}"
            assert row_data.get("IP协议") == protocol, \
                f"[FieldAssertion] IP协议不匹配 | 期望: {protocol} | 实际: {row_data.get('IP协议')}"
            assert row_data.get("IP版本") == ip_version, \
                f"[FieldAssertion] IP版本不匹配 | 期望: {ip_version} | 实际: {row_data.get('IP版本')}"

        with allure_step_log("清理: 删除本场景创建的加密规则"):
            transfer_strategy_page.encrypt_rule_delete(remote_cidr)
            transfer_strategy_page.assert_deleted(remote_cidr, timeout=30000)

    @allure.title("传输策略组-加密规则IPv6新建验证")
    def test_encrypt_rule_ipv6(self, transfer_strategy_page, shared_resources):
        """测试IPv6（全部协议）加密规则创建。

        用例3422128：协议全部，IP版本IPv6，远端CIDR 2001:db8::/64。
        """
        strategy_name = shared_resources["strategy_name"]
        key_name = shared_resources["key_name"]
        protocol = "全部"
        ip_version = "IPv6"
        remote_cidr = "2001:db8::/64"

        with allure_step_log("步骤1: 进入传输策略组模块"):
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤2: 进入策略组详情页并切换到加密规则tab"):
            transfer_strategy_page.goto_transfer_strategy_detail(strategy_name)
            transfer_strategy_page.wait_for_page_ready()
            tab = transfer_strategy_page.get_by_role("tab", name="加密规则")
            tab.click()
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤3-9: 创建IPv6加密规则"):
            rule_info = transfer_strategy_page.encrypt_rule_create(
                key_name=key_name,
                remote_cidr=remote_cidr,
                protocol=protocol,
                ip_version=ip_version,
            )

        with allure_step_log("步骤3-9: 断言创建操作成功"):
            transfer_strategy_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤4: 确认策略组名称显示"):
            assert rule_info["strategy_name"] == strategy_name, \
                f"[FieldAssertion] 策略组名称不匹配 | 期望: {strategy_name} | 实际: {rule_info['strategy_name']}"

        with allure_step_log("步骤10: 加密规则列表校验"):
            transfer_strategy_page.assert_list_contain(remote_cidr, column_name="对端CIDR")
            row_data = transfer_strategy_page.get_encrypt_rule_row_data(remote_cidr)
            assert row_data.get("对端CIDR") == remote_cidr, \
                f"[FieldAssertion] 对端CIDR不匹配 | 期望: {remote_cidr} | 实际: {row_data.get('对端CIDR')}"
            assert row_data.get("密钥名称") == key_name, \
                f"[FieldAssertion] 密钥名称不匹配 | 期望: {key_name} | 实际: {row_data.get('密钥名称')}"
            assert row_data.get("IP协议") == protocol, \
                f"[FieldAssertion] IP协议不匹配 | 期望: {protocol} | 实际: {row_data.get('IP协议')}"
            assert row_data.get("IP版本") == ip_version, \
                f"[FieldAssertion] IP版本不匹配 | 期望: {ip_version} | 实际: {row_data.get('IP版本')}"

        with allure_step_log("清理: 删除本场景创建的加密规则"):
            transfer_strategy_page.encrypt_rule_delete(remote_cidr)
            transfer_strategy_page.assert_deleted(remote_cidr, timeout=30000)
