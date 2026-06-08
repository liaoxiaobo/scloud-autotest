import allure
import pytest

from sugon_web.pages.storage.oss import OosPage
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@pytest.fixture
def oos_page(page):
    """创建OSS页面对象并导航到OSS服务。"""
    oos = OosPage(page)
    oos.goto_service("对象存储")
    return oos


@allure.epic("存储服务")
@allure.feature("对象存储")
@allure.story("桶管理-新建桶")
class TestOSSBucketCreate:
    """对象存储OSS-新建桶验证。"""

    @allure.title("对象存储-新建桶并完整验证")
    def test_oss_001_bucket_create(self, oos_page, ssh_host):
        import time
        timestamp = time.strftime("%m%d%H%M", time.localtime())
        bucket_name = f"oss-{timestamp}-{random_data(length=4)}"
        tag_key = "key1"
        tag_value = "vaule1"

        with allure_step_log("步骤1: 导航到对象存储OSS桶列表"):
            oos_page.goto_submenu("桶操作")
            oos_page.wait_for_page_ready()

        with allure_step_log("步骤2: 创建OSS桶（完整配置）"):
            oos_page.oos_bucket_create_full(
                name=bucket_name,
                available_zone="单AZ存储",
                storage_class="标准存储",
                bucket_strategy="私有",
                encryption=True,
                data_read=False,
                tags=[{"key": tag_key, "value": tag_value}],
                capacity="10",
            )
            oos_page.assert_popup_success()

        with allure_step_log("步骤3: 列表页验证桶信息"):
            oos_page.goto_submenu("桶操作")
            oos_page.assert_list_contain(bucket_name, column_name="桶名称")
            row_data = oos_page.get_row_data(bucket_name)
            assert row_data.get("桶名称") == bucket_name, \
                f"桶名称不匹配，期望 {bucket_name}，实际 {row_data.get('桶名称')}"

        with allure_step_log("步骤4: 详情页验证标签和配置"):
            oos_page.oos_bucket_enter_detail(bucket_name)
            oos_page.oos_bucket_detail_assert_tag(tag_key, tag_value)
            oos_page.oos_bucket_detail_assert_config(bucket_name)

        with allure_step_log("步骤5: OSS存储侧验证（SSH后端）"):
            # 多路径探测 weed 可执行文件
            find_result = ssh_host.run(
                'find /opt /usr -name weed -type f 2>/dev/null | head -1',
                return_rc=True,
            )
            weed_path = find_result["stdout"].strip()

            if weed_path:
                result = ssh_host.run(
                    f'{weed_path} shell',
                    return_rc=True,
                )
                assert result["rc"] == 0, f"weed shell 执行失败: {result.get('stderr', '')}"
                assert bucket_name in result["stdout"], \
                    f"桶 {bucket_name} 未在 weed shell 输出中找到"
            else:
                import logging
                logging.getLogger(__name__).warning(
                    "当前环境未找到 weed 可执行文件，跳过 OSS 后端验证"
                )

        with allure_step_log("步骤6: 清理测试数据"):
            oos_page.goto_service("对象存储", force=True)
            oos_page.goto_submenu("桶操作")
            oos_page.obs_bucket_delete(bucket_name)
            oos_page.assert_deleted(bucket_name)
