import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('传输策略组')
@allure.story('加密规则新建功能验证')
class TestTransferStrategyEncryptRuleCreate:
    """传输策略组加密规则新建功能验证。

    场景1：加密规则新建可用性验证（用例422127）
    """

    @allure.title("传输策略组-加密规则新建可用性验证")
    def test_transfer_strategy_encrypt_rule_create(self, transfer_strategy_page, kms_page):
        """测试传输策略组加密规则新建功能。

        前置条件（均由用例自建 self-provision，不依赖环境预置）：
        1. 传输策略组（随机命名，含 autotest 关键词）
        2. SM4 密钥（OPENSSL纯软，随机命名，用完即删）

        步骤：
        1. 进入传输策略组模块（机密互联子菜单）
        2. 进入策略组详情页，切换到加密规则tab
        3. 点击新建按钮，打开规则创建弹窗
        4. 确认策略组名称显示正确
        5. 选择协议为"全部"
        6. 选择密钥 sm4-ossl1
        7. 选择IP版本为"IPv4"
        8. 输入远端CIDR 10.0.0.0/24
        9. 点击确定提交
        10. 在加密规则列表中校验新增规则信息

        清理：
        1. 删除加密规则
        2. 删除传输策略组
        3. 删除密钥
        """
        strategy_name = f"sci-tsg-autotest-{random_data()}"
        key_name = f"sm4-ossl-{random_data()}"  # 自建 SM4 密钥（OPENSSL纯软），用完即删
        remote_cidr = random_data("cidr")  # 使用随机CIDR避免重复创建冲突
        protocol = "全部"
        ip_version = "IPv4"

        # 前置：创建 SM4 密钥（OPENSSL纯软），供加密规则选择（kms_create 无 @submenu，需先导航）
        with allure_step_log(f"前置: 创建密钥 {key_name}"):
            kms_page.goto_service("可信密码模块")
            kms_page.goto_submenu("密钥管理")
            kms_page.wait_for_page_ready()
            kms_page.kms_create(
                name=key_name,
                engine="OPENSSL纯软",
                key_type="SM4 (用途：加解密，包括系统盘、数据盘、网卡等)",
                desc="自动化测试-加密规则新建",
            )
            kms_page.assert_popup_success(timeout=10000)

        # 步骤1：进入传输策略组模块
        with allure_step_log("步骤1: 进入传输策略组模块"):
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()

        # 前置：确保策略组存在（若不存在则创建）
        with allure_step_log(f"前置: 确保传输策略组 {strategy_name} 存在"):
            if not transfer_strategy_page.transfer_strategy_exists(strategy_name):
                transfer_strategy_page.transfer_strategy_create(name=strategy_name)
                transfer_strategy_page.assert_popup_success(timeout=10000)

        # 步骤2：进入策略组详情页，切换到加密规则tab
        with allure_step_log("步骤2: 进入策略组详情页并切换到加密规则tab"):
            transfer_strategy_page.goto_transfer_strategy_detail(strategy_name)
            transfer_strategy_page.wait_for_page_ready()
            transfer_strategy_page.assert_tab_visible("加密规则")
            tab = transfer_strategy_page.get_by_role("tab", name="加密规则")
            tab.click()
            transfer_strategy_page.wait_for_page_ready()

        # 步骤3-9：创建加密规则
        with allure_step_log("步骤3-9: 创建加密规则"):
            rule_info = transfer_strategy_page.encrypt_rule_create(
                key_name=key_name,
                remote_cidr=remote_cidr,
                protocol=protocol,
                ip_version=ip_version,
            )

        # P0：断言创建操作成功
        with allure_step_log("步骤3-9: 断言创建操作成功"):
            transfer_strategy_page.assert_popup_success(timeout=10000)

        # P1：确认策略组名称显示正确（步骤4）
        with allure_step_log("步骤4: 确认策略组名称显示"):
            assert rule_info["strategy_name"] == strategy_name, \
                f"[FieldAssertion] 策略组名称不匹配 | 期望: {strategy_name} | 实际: {rule_info['strategy_name']}"

        # 步骤10：规则列表校验
        with allure_step_log("步骤10: 加密规则列表校验"):
            # P0：列表中存在新增规则
            transfer_strategy_page.assert_list_contain(remote_cidr, column_name="对端CIDR")
            # P1：回读字段值校验
            row_data = transfer_strategy_page.get_encrypt_rule_row_data(remote_cidr)
            assert row_data.get("对端CIDR") == remote_cidr, \
                f"[FieldAssertion] 对端CIDR不匹配 | 期望: {remote_cidr} | 实际: {row_data.get('对端CIDR')}"
            assert row_data.get("密钥名称") == key_name, \
                f"[FieldAssertion] 密钥名称不匹配 | 期望: {key_name} | 实际: {row_data.get('密钥名称')}"
            # 校验IP协议
            assert row_data.get("IP协议") == protocol, \
                f"[FieldAssertion] IP协议不匹配 | 期望: {protocol} | 实际: {row_data.get('IP协议')}"
            # 校验IP版本
            assert row_data.get("IP版本") == ip_version, \
                f"[FieldAssertion] IP版本不匹配 | 期望: {ip_version} | 实际: {row_data.get('IP版本')}"

        # 清理：按顺序清理资源
        # 清理1：删除加密规则
        with allure_step_log("清理1: 删除加密规则"):
            transfer_strategy_page.encrypt_rule_delete(remote_cidr)
            transfer_strategy_page.assert_deleted(remote_cidr, timeout=30000)

        # 清理2：删除传输策略组
        with allure_step_log("清理2: 删除传输策略组"):
            # 返回列表页
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()
            transfer_strategy_page.transfer_strategy_delete(strategy_name)
            transfer_strategy_page.assert_deleted(strategy_name, timeout=30000)

        # 清理3：删除自建密钥
        with allure_step_log(f"清理3: 删除密钥 {key_name}"):
            kms_page.goto_service("可信密码模块")
            kms_page.goto_submenu("密钥管理")
            kms_page.wait_for_page_ready()
            kms_page.search(key_name)
            kms_page.wait_for_page_ready()
            kms_page.kms_delete(key_name)
            kms_page.assert_deleted(key_name, timeout=30000)
