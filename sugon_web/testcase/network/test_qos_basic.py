import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('网络服务')
@allure.feature('网络QoS')
@allure.story('基本功能验证')
class TestQosBasic:

    @allure.title("验证新建与删除网络QoS功能")
    def test_qos_create_delete(self, vpc_page):
        """验证网络QoS支持单条新建和删除"""
        qos_name = f"qos-{random_data()}"
        send_rate = 30
        recv_rate = 60
        desc = f"{qos_name}基础创建删除"

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
                f"网络QoS名称校验失败，期望: {qos_name}，实际: {row_data.get('名称')}"
            assert str(send_rate) in row_data.get("发送速率", ""), \
                f"发送速率校验失败，期望包含: {send_rate}，实际: {row_data.get('发送速率')}"
            assert str(recv_rate) in row_data.get("接收速率", ""), \
                f"接收速率校验失败，期望包含: {recv_rate}，实际: {row_data.get('接收速率')}"
            assert desc in row_data.get("描述", ""), \
                f"描述校验失败，期望包含: {desc}，实际: {row_data.get('描述')}"

        with allure_step_log("步骤3: 删除网络QoS"):
            vpc_page.qos_delete(qos_name)

        with allure_step_log("步骤4: 验证网络QoS已删除"):
            vpc_page.assert_deleted(qos_name)

    @allure.title("验证搜索与重置网络QoS功能")
    def test_qos_search_reset(self, vpc_page, qos):
        """验证网络QoS搜索与重置"""
        qos_name = qos["name"]
        keyword = qos_name[:-2]

        with allure_step_log(f"步骤1: 搜索网络QoS: {keyword}"):
            vpc_page.qos_search(keyword)
            vpc_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            vpc_page.qos_search_reset()
            assert vpc_page._input_search.input_value() == "", \
                f"重置后搜索框未清空，实际值: {vpc_page._input_search.input_value()}"

        with allure_step_log("步骤3: 验证重置后列表恢复正常"):
            vpc_page.assert_list_contain(qos_name)

    @allure.title("验证编辑网络QoS功能")
    def test_qos_edit(self, vpc_page, qos):
        """验证网络QoS支持修改名称、速率和描述"""
        old_name = qos["name"]
        new_name = f"{old_name}-edit"
        new_send_rate = 80
        new_recv_rate = 120
        new_desc = f"{new_name}修改后的描述"

        with allure_step_log(f"步骤1: 修改网络QoS: {old_name} -> {new_name}"):
            vpc_page.qos_edit(
                name=old_name,
                new_name=new_name,
                new_send_rate=new_send_rate,
                new_recv_rate=new_recv_rate,
                new_desc=new_desc
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证修改结果"):
            row_data = vpc_page.get_row_data(new_name)
            assert row_data.get("名称") == new_name, \
                f"网络QoS名称修改失败，期望: {new_name}，实际: {row_data.get('名称')}"
            assert str(new_send_rate) in row_data.get("发送速率", ""), \
                f"发送速率修改失败，期望包含: {new_send_rate}，实际: {row_data.get('发送速率')}"
            assert str(new_recv_rate) in row_data.get("接收速率", ""), \
                f"接收速率修改失败，期望包含: {new_recv_rate}，实际: {row_data.get('接收速率')}"
            assert new_desc in row_data.get("描述", ""), \
                f"描述修改失败，期望包含: {new_desc}，实际: {row_data.get('描述')}"

        qos["name"] = new_name

    @allure.title("验证批量删除网络QoS功能")
    def test_qos_batch_delete(self, vpc_page):
        """验证网络QoS支持批量删除"""
        base_name = random_data()
        qos_names = [f"qos-{base_name}-{i}" for i in range(2)]

        with allure_step_log("步骤1: 创建2条网络QoS数据"):
            for index, name in enumerate(qos_names, start=1):
                vpc_page.qos_create(
                    name=name,
                    send_rate=20 * index,
                    recv_rate=40 * index,
                    desc=f"{name}批量删除测试"
                )
                vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 批量删除网络QoS"):
            vpc_page.qos_delete(qos_names)

        with allure_step_log("步骤3: 验证网络QoS已批量删除"):
            vpc_page.assert_deleted(qos_names)
