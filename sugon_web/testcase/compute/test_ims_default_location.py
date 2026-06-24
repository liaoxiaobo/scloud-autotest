import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.testcase.compute._ims_helpers import _cleanup_image, _get_ims_image_url


def _pool_name(ecs_page, pool_info: dict) -> str:
    return ecs_page._ims_pool_name_from_row(pool_info)


def _pool_metadata_flag(pool_info: dict) -> str:
    return (
        pool_info.get("元数据存储池")
        or pool_info.get("是否元数据存储池")
        or pool_info.get("元数据")
        or ""
    ).strip()


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSDefaultLocation:

    @allure.title("镜像管理-删除元数据存储池并迁移元数据")
    def test_ims_delete_metadata_pool_migrate_metadata(self, ecs_page, request):
        image_name = f"ims-default-{random_data()}"
        image_url = _get_ims_image_url("import_image_url")

        request.addfinalizer(lambda: _cleanup_image(ecs_page, image_name))

        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        with allure_step_log("步骤1: 进入镜像管理→私有镜像"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.wait_for_page_ready()

        with allure_step_log(f"步骤2: 导入基础镜像 {image_name}"):
            ecs_page.ims_open_import_dialog()
            ecs_page.ims_import_image(image_name, image_url)
            ecs_page.ims_import_submit()
            ecs_page.wait_for_page_ready()
            ecs_page.close_drawer_if_exists()

        with allure_step_log("步骤3: 验证导入提交成功并等待镜像可用"):
            ecs_page.assert_status(image_name, status="可用", timeout=600, refresh=True)

        with allure_step_log("步骤4: 同步到任意一个非当前存储池"):
            ecs_page.search(image_name)
            row = ecs_page.get_row_data(image_name)
            original_pools = row.get("存储池", "")
            ecs_page.click_action(image_name, "同步存储池")
            target_pool = ecs_page.ims_select_storage_pool(exclude_pools=original_pools)
            ecs_page.dialog_confirm.click()
            ecs_page.assert_popup_success("同步镜像任务提交成功")

        with allure_step_log("步骤5: 等待目标存储池同步完成，确保镜像存在两个存储池"):
            ecs_page.ims_to_detail(image_name)
            ecs_page.ims_click_storage_pool_tab()
            ecs_page.ims_wait_for_pool_appeared(target_pool, timeout=60)
            ecs_page.ims_wait_for_pool_progress(target_pool, progress="100%", timeout=300)
            ecs_page.ims_wait_for_pool_hash_sync(target_pool, timeout=300)
            target_pool_info = ecs_page.ims_get_pool_info(target_pool)
            assert _pool_metadata_flag(target_pool_info) == "否", (
                f"[FieldAssertion] 同步目标存储池应为非元数据存储池 | 期望: 否 | 实际行: {target_pool_info}"
            )
            pool_rows = ecs_page.ims_get_storage_pool_rows()
            assert len(pool_rows) >= 2, f"[FieldAssertion] 镜像未同步到两个存储池 | 实际行: {pool_rows}"

        with allure_step_log("步骤6: 获取元数据存储池为是的存储池，并删除该存储池"):
            metadata_pool_info = ecs_page.ims_get_metadata_pool_info()
            metadata_pool = _pool_name(ecs_page, metadata_pool_info)
            assert metadata_pool, f"[FieldAssertion] 未获取到元数据存储池名称 | 行: {metadata_pool_info}"
            ecs_page.click_action_in_table(metadata_pool, "删除")

        with allure_step_log("步骤7: 校验删除弹窗要求选择新的元数据存储池"):
            dialog = ecs_page.ims_delete_metadata_pool_dialog()
            dialog_text = dialog.inner_text()
            assert metadata_pool in dialog_text, (
                f"[DialogAssertion] 删除弹窗未展示当前元数据存储池 | 期望包含: {metadata_pool} | 实际: {dialog_text}"
            )

        with allure_step_log("步骤8: 在删除弹窗选择目标存储池并确认"):
            new_metadata_pool = ecs_page.ims_select_new_default_pool(target_pool)
            ecs_page.dialog_confirm.click()
            ecs_page.assert_popup_success("删除成功")

        with allure_step_log("步骤9: 校验新的元数据存储池已更新"):
            ecs_page.ims_page_reload()
            ecs_page.ims_click_storage_pool_tab()
            current_metadata_pool = ecs_page.ims_get_default_pool()
            assert current_metadata_pool == new_metadata_pool, (
                f"[FieldAssertion] 元数据存储池未更新 | 期望: {new_metadata_pool} | 实际: {current_metadata_pool}"
            )
