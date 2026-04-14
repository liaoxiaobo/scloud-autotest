import allure
import pytest
from sugon_web.utils.logger import allure_step_log


@allure.epic('网络服务')
@allure.feature('弹性公网IP')
@allure.story('基本功能验证')
class TestEipBasic:

    @allure.title("弹性公网IPv4-快速选择分配")
    def test_eip_allocate_by_quick_select(self, vpc_page):
        """测试通过快速选择方式分配弹性公网IPv4"""

        with allure_step_log("步骤1: 通过快速选择方式分配1个弹性公网IPv4"):
            created_ips = vpc_page.eip_allocate(method="快速选择")
            assert len(created_ips) == 1, f"分配公网IP数量异常，期望: 1，实际: {len(created_ips)}"
            eip = created_ips[0]

        with allure_step_log("步骤2: 验证快速选择分配结果"):
            vpc_page.search(eip)
            vpc_page.assert_list_contain(eip, column_name="IP地址", exact_match=False)

    @allure.title("弹性公网IPv4-手动输入分配")
    def test_eip_allocate_by_manual_input(self, vpc_page):
        """测试通过手动输入方式分配弹性公网IPv4"""

        with allure_step_log("步骤1: 通过手动输入方式分配1个弹性公网IPv4"):
            created_ips = vpc_page.eip_allocate(method="手动输入")
            assert len(created_ips) == 1, f"分配公网IP数量异常，期望: 1，实际: {len(created_ips)}"
            eip = created_ips[0]

        with allure_step_log("步骤2: 验证手动输入分配结果"):
            vpc_page.search(eip)
            vpc_page.assert_list_contain(eip, column_name="IP地址", exact_match=False)

    @allure.title("弹性公网IPv4-释放")
    @pytest.mark.parametrize("eip", [{"method": "手动输入"}], indirect=True)
    def test_eip_release(self, vpc_page, eip):
        """测试释放单个弹性公网IPv4"""

        with allure_step_log("步骤1: 验证待释放的弹性公网IPv4已存在"):
            vpc_page.search(eip)
            vpc_page.assert_list_contain(eip, column_name="IP地址", exact_match=False)

        with allure_step_log("步骤2: 释放弹性公网IPv4"):
            vpc_page.eip_release(eip)

        with allure_step_log("步骤3: 验证弹性公网IPv4已释放"):
            vpc_page.assert_deleted(eip)

    @allure.title("弹性公网IPv4-搜索和重置")
    @pytest.mark.parametrize("eip", [{"method": "手动输入"}], indirect=True)
    def test_eip_search_reset(self, vpc_page, eip):
        """测试弹性公网IPv4搜索与重置"""

        with allure_step_log("步骤1: 搜索指定弹性公网IPv4"):
            vpc_page.search(eip)
            row_text = vpc_page.get_row_by_name(eip).inner_text()
            assert eip in row_text, f"搜索结果校验失败，期望包含: {eip}，实际行内容: {row_text}"

        with allure_step_log("步骤2: 重置搜索条件"):
            vpc_page.btn_reset.click()
            search_input = vpc_page.get_by_role("textbox", name="搜索（公网IP）")
            assert search_input.input_value() == "", "重置后搜索框未清空"
            assert len(vpc_page.table_rows) > 0, "重置后公网IP列表为空"

    @allure.title("弹性公网IPv4-批量释放")
    def test_eip_batch_release(self, vpc_page):
        """测试勾选列表页前两行弹性公网IPv4并批量释放"""

        with allure_step_log("步骤1: 获取列表页前两条弹性公网IPv4"):
            eips = vpc_page.get_eip_list()
            assert len(eips) >= 2, f"当前列表页弹性公网IPv4数量不足2条，实际: {len(eips)}"
            target_eips = eips[:2]

        with allure_step_log("步骤2: 批量释放前两条弹性公网IPv4"):
            vpc_page.eip_release(target_eips)

        with allure_step_log("步骤3: 验证前两条弹性公网IPv4已释放"):
            vpc_page.assert_deleted(target_eips)
