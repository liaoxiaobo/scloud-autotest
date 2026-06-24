import pytest
import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.testcase.compute._ims_helpers import _cleanup_image, _get_image_detail


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSModify:

    @allure.title("镜像管理-私有镜像操作-修改")
    @pytest.mark.parametrize("image", [{"image": "cirros-0.5.2.raw", "backend": "xbd-test"}], indirect=True)
    def test_ims_modify_image(self, ecs_page, image, ssh_host, request):
        original_name = image.get("name")
        current_name = original_name
        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        def _cleanup():
            if current_name != original_name:
                _cleanup_image(ecs_page, current_name)
        request.addfinalizer(_cleanup)

        with allure_step_log("步骤1: 进入镜像管理→私有镜像"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(original_name)

        with allure_step_log("步骤2: 不修改直接确定"):
            ecs_page.click_action(original_name, "修改")
            ecs_page.dialog_confirm.click()
            ecs_page.assert_popup_success("修改镜像成功")

        with allure_step_log("步骤3: 修改镜像名称"):
            new_name = f"ims-modify-{random_data()}"
            ecs_page.click_action(original_name, "修改")
            ecs_page.ims_modify_image_name(new_name)
            ecs_page.dialog_confirm.click()
            ecs_page.assert_popup_success("修改镜像成功")
            current_name = new_name

        with allure_step_log("步骤4: 校验名称更新"):
            ecs_page.search(new_name)
            assert ecs_page.get_row_data(new_name).get("名称") == new_name
            ecs_page.ims_to_detail(new_name)
            detail = ecs_page.ims_get_detail_info()
            assert detail.get("名称") == new_name

        with allure_step_log("步骤5: 后端校验名称"):
            detail = _get_image_detail(ssh_host, new_name)
            assert detail.get("name") == new_name

        with allure_step_log("步骤6: 修改操作系统版本和位数"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(new_name)
            ecs_page.click_action(new_name, "修改")
            ecs_page.ims_modify_os_version("linux", "centos7.9", "64位")
            ecs_page.dialog_confirm.click()
            ecs_page.assert_popup_success("修改镜像成功")
