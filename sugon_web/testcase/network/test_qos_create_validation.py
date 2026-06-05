import allure
import pytest
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('网络服务')
@allure.feature('网络QoS')
@allure.story('新建功能验证')
class TestQosCreateValidation:

    @allure.title("网络QoS-新建功能验证-{qos_params[case_name]}")
    @pytest.mark.parametrize("qos_params", [
        {
            "case_name": "指定速率",
            "name": "test-qos-1",
            "send_rate": 1000,
            "recv_rate": 500,
            "desc": "As-_中文！@#《》",
        },
        {
            "case_name": "全部不限制",
            "name": "test-不限制",
            "send_rate": None,
            "recv_rate": None,
            "desc": "As-_中文！@#《》",
        },
        {
            "case_name": "发送不限制接收限速",
            "name": "test-发送不限制",
            "send_rate": None,
            "recv_rate": 1,
            "desc": "As-_中文！@#《》",
        },
        {
            "case_name": "发送限速接收不限制",
            "name": "test-发送不限制",
            "send_rate": 4000,
            "recv_rate": None,
            "desc": "As-_中文！@#《》",
        },
    ])
    def test_qos_create_validation(self, vpc_page, qos_params):
        """验证网络QoS新建功能，覆盖不同速率组合场景"""
        base_name = qos_params["name"]
        send_rate = qos_params["send_rate"]
        recv_rate = qos_params["recv_rate"]
        desc = qos_params["desc"]
        qos_name = f"{base_name}-{random_data()}"

        expected_send = "不限制" if send_rate is None else f"{send_rate}Mbps"
        expected_recv = "不限制" if recv_rate is None else f"{recv_rate}Mbps"

        with allure_step_log("步骤1: 新建网络QoS"):
            vpc_page.qos_create(
                name=qos_name,
                send_rate=send_rate,
                recv_rate=recv_rate,
                desc=desc
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证网络QoS列表数据"):
            row_data = vpc_page.get_row_data(qos_name)
            assert row_data.get("名称") == qos_name, \
                f"[FieldAssertion] 网络QoS名称校验失败 | 期望: {qos_name} | 实际: {row_data.get('名称')}"
            assert expected_send in row_data.get("发送速率", ""), \
                f"[FieldAssertion] 发送速率校验失败 | 期望包含: {expected_send} | 实际: {row_data.get('发送速率')}"
            assert expected_recv in row_data.get("接收速率", ""), \
                f"[FieldAssertion] 接收速率校验失败 | 期望包含: {expected_recv} | 实际: {row_data.get('接收速率')}"
            assert desc in row_data.get("描述", ""), \
                f"[FieldAssertion] 描述校验失败 | 期望包含: {desc} | 实际: {row_data.get('描述')}"

        with allure_step_log("步骤3: 删除网络QoS"):
            vpc_page.qos_delete(qos_name)

        with allure_step_log("步骤4: 验证网络QoS已删除"):
            vpc_page.assert_deleted(qos_name)
