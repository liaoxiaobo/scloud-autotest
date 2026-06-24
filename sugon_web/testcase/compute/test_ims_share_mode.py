import pytest
import allure

from sugon_web.utils.logger import allure_step_log, logger


def _restore_share_mode_global(ecs_page, image_name):
    """恢复镜像共享模式为全局共享。"""
    try:
        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"
        ecs_page.goto_submenu("镜像服务")
        ecs_page.search(image_name)
        ecs_page.ims_click_action_if_available(image_name, "设置共享模式")
        ecs_page.ims_set_share_mode("全局共享")
        ecs_page.dialog_confirm.click()
        ecs_page.assert_popup_success("设置共享镜像成功")
    except Exception as exc:
        logger.warning(f"恢复镜像全局共享失败: {image_name}, {exc}")


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSShareMode:

    @allure.title("镜像管理-设置共享模式")
    @pytest.mark.parametrize("image", [{"image": "cirros-0.5.2.raw", "backend": "xbd-test"}], indirect=True)
    def test_ims_share_mode(self, ecs_page, image, request):
        image_name = image.get("name")
        share_mode_changed = False
        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        def _cleanup():
            if share_mode_changed:
                with allure_step_log("步骤7: 恢复为全局共享"):
                    _restore_share_mode_global(ecs_page, image_name)
        request.addfinalizer(_cleanup)

        with allure_step_log("步骤1: 进入镜像服务，搜索预置镜像"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)
            assert ecs_page.get_row_data(image_name).get("名称") == image_name
            if not ecs_page.ims_has_action(image_name, "设置共享模式"):
                pytest.skip("当前UI视图未提供设置共享模式入口")

        with allure_step_log("步骤2: 点击设置共享模式，选择不共享"):
            assert ecs_page.ims_click_action_if_available(image_name, "设置共享模式")
            ecs_page.ims_set_share_mode("不共享")
            ecs_page.dialog_confirm.click()
            ecs_page.assert_popup_success("设置共享镜像成功")
            share_mode_changed = True

        with allure_step_log("步骤5: 在镜像列表校验共享模式"):
            row = ecs_page.get_row_data(image_name)
            assert row.get("共享模式") == "不共享", (
                f"[FieldAssertion] 镜像列表共享模式不匹配 | "
                f"期望: 不共享 | 实际: {row.get('共享模式')} | 行: {row}"
            )

        with allure_step_log("步骤6: 进入镜像详情页校验共享模式"):
            ecs_page.ims_to_detail(image_name)
            detail = ecs_page.ims_get_detail_info()
            assert detail.get("共享模式") == "不共享", (
                f"[FieldAssertion] 详情页共享模式不匹配 | "
                f"期望: 不共享 | 实际: {detail.get('共享模式')} | 详情: {detail}"
            )
