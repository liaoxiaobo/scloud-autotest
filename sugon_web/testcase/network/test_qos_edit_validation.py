import allure
import pytest
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('网络QoS')
@allure.story('修改功能验证')
class TestQosEditValidation:

    @allure.title("网络QoS-修改功能验证-{edit_params[case_name]}")
    @pytest.mark.parametrize("edit_params", [
        {
            "case_name": "修改为全部不限制",
            "new_name": "test-qos-不限制",
            "new_send_rate": None,
            "new_recv_rate": None,
            "expected_send": "不限制",
            "expected_recv": "不限制",
        },
        {
            "case_name": "修改为指定速率",
            "new_name": "test-qos-1",
            "new_send_rate": 1,
            "new_recv_rate": 4000,
            "expected_send": "1Mbps",
            "expected_recv": "4000Mbps",
        },
    ])
    def test_qos_edit_validation(self, vpc_page, edit_params):
        """验证网络QoS修改功能，覆盖不同速率组合场景"""
        base_qos_name = f"qos1-{random_data()}"
        new_name = f"{edit_params['new_name']}-{random_data()}"
        new_send_rate = edit_params["new_send_rate"]
        new_recv_rate = edit_params["new_recv_rate"]
        expected_send = edit_params["expected_send"]
        expected_recv = edit_params["expected_recv"]
        desc = "As-_中文！@#《》"

        with allure_step_log("步骤1: 新建前置网络QoS"):
            vpc_page.qos_create(
                name=base_qos_name,
                send_rate=100,
                recv_rate=400,
                desc="预置QoS"
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 修改网络QoS"):
            vpc_page.qos_edit(
                name=base_qos_name,
                new_name=new_name,
                new_send_rate=new_send_rate,
                new_recv_rate=new_recv_rate,
                new_desc=desc
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 验证网络QoS列表数据"):
            row_data = vpc_page.get_row_data(new_name)
            assert row_data.get("名称") == new_name, \
                f"[FieldAssertion] 网络QoS名称校验失败 | 期望: {new_name} | 实际: {row_data.get('名称')}"
            assert expected_send in row_data.get("发送速率", ""), \
                f"[FieldAssertion] 发送速率校验失败 | 期望包含: {expected_send} | 实际: {row_data.get('发送速率')}"
            assert expected_recv in row_data.get("接收速率", ""), \
                f"[FieldAssertion] 接收速率校验失败 | 期望包含: {expected_recv} | 实际: {row_data.get('接收速率')}"
            assert desc in row_data.get("描述", ""), \
                f"[FieldAssertion] 描述校验失败 | 期望包含: {desc} | 实际: {row_data.get('描述')}"

        with allure_step_log("步骤4: 删除网络QoS"):
            vpc_page.qos_delete(new_name)

        with allure_step_log("步骤5: 验证网络QoS已删除"):
            vpc_page.assert_deleted(new_name)
