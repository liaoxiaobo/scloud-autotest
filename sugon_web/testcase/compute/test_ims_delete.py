import pytest
import allure

from sugon_web.utils.logger import allure_step_log


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSDelete:

    @allure.title("镜像管理-私有镜像操作-删除")
    @pytest.mark.parametrize("image", [{"image": "cirros-0.5.2.raw", "backend": "xbd-test"}], indirect=True)
    def test_ims_delete_image(self, ecs_page, image, ssh_host):
        image_name = image.get("name")
        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        with allure_step_log("步骤1: 进入私有镜像"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)

        with allure_step_log("步骤2: 取消删除验证"):
            ecs_page.click_action(image_name, "删除")
            ecs_page.dialog_cancel.click()
            assert ecs_page.get_row_data(image_name) is not None

        with allure_step_log("步骤3: 删除未被使用的镜像"):
            ecs_page.click_action(image_name, "删除")
            ecs_page.dialog_confirm.click()
            ecs_page.assert_deleted(image_name, refresh=True)

        with allure_step_log("步骤4: 后端确认"):
            result = ssh_host.run(f"scli image list | grep {image_name}", return_rc=True)
            assert result["rc"] != 0 or image_name not in result["stdout"]
