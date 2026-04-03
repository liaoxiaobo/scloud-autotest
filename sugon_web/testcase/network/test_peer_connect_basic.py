import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic("网络服务")
@allure.feature("对等连接")
@allure.story("基本功能验证")
class TestPeerConnectBasic:

    @allure.title("对等连接-创建和删除")
    @pytest.mark.parametrize("vpc", [{"count": 2}], indirect=True)
    def test_peer_connect_create_delete(self, vpc_page, vpc):
        """验证当前账户下可以创建并删除对等连接。"""
        peer_connect_name = f"pc-{random_data()}"
        desc = "对等连接自动化测试"

        with allure_step_log("步骤1: 准备测试数据"):
            requester_vpc = vpc[0]["name"]
            receiver_vpc = vpc[1]["name"]

        with allure_step_log("步骤2: 创建对等连接"):
            vpc_page.peer_connect_create(
                name=peer_connect_name,
                requester_vpc=requester_vpc,
                receiver_vpc=receiver_vpc,
                desc=desc
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 验证对等连接列表数据"):
            vpc_page.assert_list_contain(peer_connect_name)
            row_data = vpc_page.get_row_data(peer_connect_name)
            assert requester_vpc == row_data["本端vpc"], f"本端VPC断言失败: {row_data}"
            assert receiver_vpc == row_data["对端vpc"], f"对端VPC断言失败: {row_data}"
            assert desc == row_data["描述"], f"描述断言失败: {row_data}"
            assert row_data["状态"], f"状态断言失败: {row_data}"

        with allure_step_log("步骤4: 删除对等连接"):
            vpc_page.peer_connect_delete(peer_connect_name)

        with allure_step_log("步骤5: 验证对等连接已删除"):
            vpc_page.assert_deleted(peer_connect_name)

    @allure.title("对等连接-修改名称和描述")
    @pytest.mark.parametrize("vpc", [{"count": 2}], indirect=True)
    def test_peer_connect_edit(self, vpc_page, vpc):
        """验证可以修改对等连接的名称和描述。"""
        peer_connect_name = f"pc-{random_data()}"
        new_name = f"pc-{random_data()}"
        new_desc = "修改后的对等连接描述"

        with allure_step_log("步骤1: 创建对等连接"):
            requester_vpc = vpc[0]["name"]
            receiver_vpc = vpc[1]["name"]
            vpc_page.peer_connect_create(
                name=peer_connect_name,
                requester_vpc=requester_vpc,
                receiver_vpc=receiver_vpc,
                desc="原始描述"
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 修改对等连接名称和描述"):
            vpc_page.peer_connect_edit(
                name=peer_connect_name,
                new_name=new_name,
                new_desc=new_desc
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 验证修改后的列表数据"):
            vpc_page.assert_list_contain(new_name)
            row_data = vpc_page.get_row_data(new_name)
            assert new_desc == row_data["描述"], f"描述断言失败: 期望 '{new_desc}', 实际 '{row_data['描述']}'"
            assert requester_vpc == row_data["本端vpc"], f"本端VPC断言失败: {row_data}"
            assert receiver_vpc == row_data["对端vpc"], f"对端VPC断言失败: {row_data}"

        with allure_step_log("步骤4: 删除对等连接"):
            vpc_page.peer_connect_delete(new_name)

        with allure_step_log("步骤5: 验证对等连接已删除"):
            vpc_page.assert_deleted(new_name)

    @allure.title("对等连接-搜索和重置")
    @pytest.mark.parametrize("vpc", [{"count": 2}], indirect=True)
    def test_peer_connect_search_reset(self, vpc_page, vpc):
        """验证对等连接的搜索和重置功能。"""
        peer_connect_name = f"pc-{random_data()}"

        with allure_step_log("步骤1: 创建对等连接"):
            requester_vpc = vpc[0]["name"]
            receiver_vpc = vpc[1]["name"]
            vpc_page.peer_connect_create(
                name=peer_connect_name,
                requester_vpc=requester_vpc,
                receiver_vpc=receiver_vpc,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 输入名称进行搜索"):
            keyword = peer_connect_name[:-2]
            vpc_page.search(keyword)
            vpc_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤3: 重置搜索条件"):
            vpc_page.btn_reset.click()
            vpc_page.wait_for_page_ready()
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("步骤4: 删除对等连接"):
            vpc_page.peer_connect_delete(peer_connect_name)

        with allure_step_log("步骤5: 验证对等连接已删除"):
            vpc_page.assert_deleted(peer_connect_name)

    @allure.title("对等连接-批量删除")
    @pytest.mark.parametrize("vpc", [{"count": 3}], indirect=True)
    def test_peer_connect_batch_delete(self, vpc_page, vpc):
        """验证对等连接的批量删除功能。"""
        pc_names = []

        with allure_step_log("步骤1: 创建2个对等连接"):
            for i in range(2):
                pc_name = f"pc-{random_data()}"
                pc_names.append(pc_name)
                vpc_page.peer_connect_create(
                    name=pc_name,
                    requester_vpc=vpc[i]["name"],
                    receiver_vpc=vpc[2]["name"],
                )
                vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 批量删除对等连接"):
            vpc_page.peer_connect_delete(pc_names)

        with allure_step_log("步骤3: 验证对等连接已删除"):
            vpc_page.assert_deleted(pc_names)
