import allure
import pytest

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.network import TransferStrategyPage
from sugon_web.pages.network.sci_kms import SciKmsPage


# 四条有序加密规则的固定配置（协议 -> 远端CIDR），创建顺序即生成顺序ID 1~4
# 顺序：全部(id=1) -> TCP(id=2) -> UDP(id=3) -> ICMP(id=4)
_RULE_DEFS = [
    {"protocol": "全部", "remote_cidr": "10.0.0.0/24", "logical_id": 1},
    {"protocol": "TCP", "remote_cidr": "10.0.1.0/24", "logical_id": 2},
    {"protocol": "UDP", "remote_cidr": "10.0.2.0/24", "logical_id": 3},
    {"protocol": "ICMP", "remote_cidr": "10.0.3.0/24", "logical_id": 4},
]


def _enter_encrypt_rule_tab(transfer_page, strategy_name):
    """进入指定策略组详情页并切换到加密规则tab。

    Args:
        transfer_page: 传输策略组页面对象。
        strategy_name: 策略组名称。
    """
    transfer_page.goto_transfer_strategy_detail(strategy_name)
    transfer_page.wait_for_page_ready()
    tab = transfer_page.get_by_role("tab", name="加密规则")
    tab.click()
    transfer_page.wait_for_page_ready()


def _order_by_logical_id(transfer_page, cidr_to_id):
    """读取当前加密规则列表顺序，并映射为逻辑ID序列。

    以每条规则唯一的远端CIDR为锚点读取列表行顺序，再映射回逻辑ID（1~4），
    用于断言移动后的排序结果。

    Args:
        transfer_page: 传输策略组页面对象。
        cidr_to_id: 远端CIDR -> 逻辑ID 的映射字典。

    Returns:
        list[int]: 按列表当前行顺序排列的逻辑ID序列。
    """
    cidr_order = transfer_page.get_encrypt_rule_order(column="对端CIDR")
    return [cidr_to_id[c] for c in cidr_order if c in cidr_to_id]


@allure.epic('网络服务')
@allure.feature('传输策略组')
@allure.story('加密规则-移动规则可用性验证')
class TestTransferStrategyMoveRule:
    """传输策略组-加密规则tab-移动规则可用性验证。

    用例422133：在策略组加密规则tab下，对四条有序规则（id 1~4，协议依次为
    全部/TCP/UDP/ICMP）执行"移动规则"操作（最前/最后/之前/之后），逐步断言
    列表顺序，并验证刷新后顺序持久化。前置策略组、密钥、四条规则均由 class-scoped
    fixture 自建（self-provision），批次末按"先删策略组（连带删规则）、再删密钥"清理。
    """

    @pytest.fixture(scope="class", autouse=True)
    def shared_resources(self, request, browser_context, config):
        """Class-scoped fixture：自建策略组、密钥、四条有序加密规则并统一清理。

        Yields:
            dict: 包含 strategy_name、key_name、cidr_to_id（CIDR->逻辑ID映射）。
        """
        page = _create_logged_in_page(browser_context, config)
        transfer_page = TransferStrategyPage(page)
        kms_page = SciKmsPage(page)

        strategy_name = f"sort-tsg-{random_data()}"
        key_name = f"sm4-sort-{random_data()}"
        cidr_to_id = {r["remote_cidr"]: r["logical_id"] for r in _RULE_DEFS}

        result = {
            "strategy_name": strategy_name,
            "key_name": key_name,
            "cidr_to_id": cidr_to_id,
        }

        try:
            # 1. 自建传输策略组（先查、不存在则创建）
            with allure_step_log(f"前置: 确保传输策略组 {strategy_name} 存在"):
                transfer_page.goto_service("虚拟私有云")
                transfer_page.goto_submenu("机密互联")
                transfer_page.wait_for_page_ready()
                if not transfer_page.transfer_strategy_exists(strategy_name):
                    transfer_page.transfer_strategy_create(name=strategy_name)
                    transfer_page.assert_popup_success(timeout=10000)

            # 2. 自建密钥（OPENSSL纯软 / SM4，先查、不存在则创建）
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
                        desc="自动化测试-移动规则",
                    )
                    kms_page.assert_popup_success(timeout=10000)

            # 3. 按固定顺序自建四条加密规则，确保顺序ID为 1、2、3、4
            with allure_step_log("前置: 按顺序自建四条加密规则(全部/TCP/UDP/ICMP)"):
                transfer_page.goto_service("虚拟私有云")
                transfer_page.goto_submenu("机密互联")
                transfer_page.wait_for_page_ready()
                _enter_encrypt_rule_tab(transfer_page, strategy_name)
                for rule in _RULE_DEFS:
                    if transfer_page.encrypt_rule_exists(rule["remote_cidr"]):
                        logger.info(f"加密规则 {rule['remote_cidr']} 已存在，跳过创建")
                        continue
                    transfer_page.encrypt_rule_create(
                        key_name=key_name,
                        remote_cidr=rule["remote_cidr"],
                        protocol=rule["protocol"],
                        ip_version="IPv4",
                    )
                    transfer_page.assert_popup_success(timeout=10000)

            yield result

        finally:
            # 清理顺序：先删策略组（连带删除其下加密规则），再删密钥
            with allure_step_log("Class Teardown: 清理共享资源"):
                cleanup_page = _create_logged_in_page(browser_context, config)
                transfer_cleanup = TransferStrategyPage(cleanup_page)
                kms_cleanup = SciKmsPage(cleanup_page)

                with allure_step_log(f"清理: 删除传输策略组 {strategy_name}"):
                    try:
                        transfer_cleanup.goto_service("虚拟私有云")
                        transfer_cleanup.goto_submenu("机密互联")
                        transfer_cleanup.wait_for_page_ready()
                        transfer_cleanup.transfer_strategy_delete(strategy_name)
                        transfer_cleanup.assert_deleted(strategy_name, timeout=30000)
                    except Exception as e:
                        logger.warning(f"删除传输策略组 {strategy_name} 失败: {e}")

                with allure_step_log(f"清理: 删除密钥 {key_name}"):
                    try:
                        kms_cleanup.goto_service("可信密码模块")
                        kms_cleanup.goto_submenu("密钥管理")
                        kms_cleanup.wait_for_page_ready()
                        kms_cleanup.search(key_name)
                        kms_cleanup.wait_for_page_ready()
                        kms_cleanup.kms_delete(key_name)
                        kms_cleanup.assert_deleted(key_name, timeout=30000)
                    except Exception as e:
                        logger.warning(f"删除密钥 {key_name} 失败: {e}")

                cleanup_page.close()

    @allure.title("传输策略组-加密规则-移动规则可用性验证")
    def test_transfer_strategy_encrypt_rule_move(self, transfer_strategy_page, shared_resources):
        """加密规则移动规则可用性验证（用例422133）。

        步骤：
        1-2. 进入策略组详情加密规则tab，确认初始顺序为 1、2、3、4
        3-4. 将 id=3 移动到"最前"，断言顺序 3、1、2、4
        5-6. 将处于第1位的 id=3 移动到"最后"，断言顺序 1、2、4、3
        7. 将第3位 ICMP(id=4) 移动到"2 之前"，断言顺序 1、4、2、3
        8. 将第1位 全部(id=1) 移动到"3 之后"，断言顺序 4、2、3、1
        9. 刷新列表，断言顺序仍为 4、2、3、1（移动结果持久化）
        """
        transfer_page = transfer_strategy_page
        strategy_name = shared_resources["strategy_name"]
        cidr_to_id = shared_resources["cidr_to_id"]
        # 逻辑ID -> 远端CIDR 反向映射，便于按逻辑ID定位被移动/目标规则
        id_to_cidr = {v: k for k, v in cidr_to_id.items()}

        # 步骤1-2：进入策略组详情-加密规则tab，确认初始顺序 1、2、3、4
        with allure_step_log("步骤1-2: 进入加密规则tab并确认初始顺序为 1、2、3、4"):
            transfer_page.goto_service("虚拟私有云")
            transfer_page.goto_submenu("机密互联")
            transfer_page.wait_for_page_ready()
            _enter_encrypt_rule_tab(transfer_page, strategy_name)
            transfer_page.assert_tab_visible("加密规则")
            order = _order_by_logical_id(transfer_page, cidr_to_id)
            assert order == [1, 2, 3, 4], (
                f"[FieldAssertion] 加密规则初始顺序 | 期望: [1, 2, 3, 4] | 实际: {order}"
            )

        # 步骤3-4：将 id=3 (UDP) 移动到"最前"，断言顺序 3、1、2、4
        with allure_step_log("步骤3-4: 将 id=3 移动到最前，断言顺序 3、1、2、4"):
            transfer_page.encrypt_rule_move(id_to_cidr[3], direction="最前")
            order = _order_by_logical_id(transfer_page, cidr_to_id)
            assert order == [3, 1, 2, 4], (
                f"[FieldAssertion] 移动到最前后顺序 | 期望: [3, 1, 2, 4] | 实际: {order}"
            )

        # 步骤5-6：将处于第1位的 id=3 移动到"最后"，断言顺序 1、2、4、3
        with allure_step_log("步骤5-6: 将 id=3 移动到最后，断言顺序 1、2、4、3"):
            transfer_page.encrypt_rule_move(id_to_cidr[3], direction="最后")
            order = _order_by_logical_id(transfer_page, cidr_to_id)
            assert order == [1, 2, 4, 3], (
                f"[FieldAssertion] 移动到最后后顺序 | 期望: [1, 2, 4, 3] | 实际: {order}"
            )

        # 步骤7：将第3位 ICMP(id=4) 移动到"2 之前"，断言顺序 1、4、2、3
        with allure_step_log("步骤7: 将 id=4 移动到目标规则2之前，断言顺序 1、4、2、3"):
            target_id_2 = transfer_page.get_encrypt_rule_id(id_to_cidr[2])
            transfer_page.encrypt_rule_move(id_to_cidr[4], direction="之前", target_id=target_id_2)
            order = _order_by_logical_id(transfer_page, cidr_to_id)
            assert order == [1, 4, 2, 3], (
                f"[FieldAssertion] 移动到目标之前后顺序 | 期望: [1, 4, 2, 3] | 实际: {order}"
            )

        # 步骤8：将第1位 全部(id=1) 移动到"3 之后"，断言顺序 4、2、3、1
        with allure_step_log("步骤8: 将 id=1 移动到目标规则3之后，断言顺序 4、2、3、1"):
            target_id_3 = transfer_page.get_encrypt_rule_id(id_to_cidr[3])
            transfer_page.encrypt_rule_move(id_to_cidr[1], direction="之后", target_id=target_id_3)
            order = _order_by_logical_id(transfer_page, cidr_to_id)
            assert order == [4, 2, 3, 1], (
                f"[FieldAssertion] 移动到目标之后后顺序 | 期望: [4, 2, 3, 1] | 实际: {order}"
            )

        # 步骤9：刷新列表，断言顺序持久化仍为 4、2、3、1
        with allure_step_log("步骤9: 刷新列表，断言顺序持久化为 4、2、3、1"):
            _enter_encrypt_rule_tab(transfer_page, strategy_name)
            order = _order_by_logical_id(transfer_page, cidr_to_id)
            assert order == [4, 2, 3, 1], (
                f"[FieldAssertion] 刷新后顺序持久化 | 期望: [4, 2, 3, 1] | 实际: {order}"
            )
