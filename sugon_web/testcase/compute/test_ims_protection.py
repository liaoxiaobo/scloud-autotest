import pytest
import allure

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.testcase.compute._ims_helpers import _get_image_detail


def _restore_protection_state(ecs_page, image_name):
    """恢复镜像为未受保护状态。"""
    try:
        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"
        ecs_page.goto_submenu("镜像服务")
        ecs_page.search(image_name)
        ecs_page.ims_open_modify_dialog(image_name)
        ecs_page.ims_set_protected(False)
        ecs_page.dialog_confirm.click()
        ecs_page.assert_popup_success("修改镜像成功")
    except Exception as exc:
        logger.warning(f"恢复镜像未受保护失败: {image_name}, {exc}")


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSProtection:

    @allure.title("镜像管理-私有镜像操作-修改保护状态")
    @pytest.mark.parametrize("image", [{"image": "cirros-0.5.2.raw", "backend": "xbd-test"}], indirect=True)
    def test_ims_modify_protection(self, ecs_page, image, ssh_host, request):
        image_name = image.get("name")
        protected_set = False
        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        def _cleanup():
            if protected_set:
                with allure_step_log("步骤8: 恢复镜像为未受保护"):
                    _restore_protection_state(ecs_page, image_name)
        request.addfinalizer(_cleanup)

        with allure_step_log("步骤1: 进入镜像服务，搜索预置镜像"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)
            assert ecs_page.get_row_data(image_name).get("名称") == image_name
            if not ecs_page.ims_has_action(image_name, "修改"):
                pytest.skip("当前UI视图未提供修改保护状态入口")

        with allure_step_log("步骤2: 打开修改弹窗，设置为受保护"):
            ecs_page.ims_open_modify_dialog(image_name)
            ecs_page.ims_set_protected(True)
            ecs_page.dialog_confirm.click()
            ecs_page.assert_popup_success("修改镜像成功")
            protected_set = True

        with allure_step_log("步骤5: 进入镜像详情页校验保护状态"):
            ecs_page.ims_to_detail(image_name)
            detail = ecs_page.ims_get_detail_info()
            assert detail.get("是否受保护") == "受保护", (
                f"[FieldAssertion] 详情页高级配置是否受保护不匹配 | "
                f"期望: 受保护 | 实际: {detail.get('是否受保护')} | 详情: {detail}"
            )

        with allure_step_log("步骤6: 回到镜像列表，检查删除按钮状态"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)
            assert ecs_page.ims_is_delete_disabled(image_name), (
                f"[ActionAssertion] 受保护镜像的删除操作未置灰或仍可用 | 镜像: {image_name}"
            )

        with allure_step_log("步骤7: 后端校验 protected 字段"):
            detail = _get_image_detail(ssh_host, image_name)
            assert detail.get("protected") == "1", (
                f"[BackendAssertion] 后端 protected 字段不为1 | "
                f"期望: 1 | 实际: {detail.get('protected')} | 详情: {detail}"
            )
