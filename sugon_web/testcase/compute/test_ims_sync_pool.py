import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.testcase.compute._ims_helpers import (
    _bind_mfip_for_ecs,
    _cleanup_ecs_and_mfip,
    _cleanup_image,
    _get_ims_image_url,
)
from sugon_web.testcase.compute._ims_network_helpers import (
    get_prepared_ims_network,
    ims_ecs_network_config,
)


def _pool_metadata_flag(pool_info: dict) -> str:
    return (
        pool_info.get("元数据存储池")
        or pool_info.get("是否元数据存储池")
        or pool_info.get("元数据")
        or ""
    ).strip()


def _pool_hash_value(pool_info: dict) -> str:
    return (pool_info.get("Hash") or pool_info.get("Hash值") or "").strip()


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSSyncPool:

    @allure.title("镜像管理-私有镜像同步存储池")
    def test_ims_sync_storage_pool(self, ecs_page, ops_page, ssh_vm, request):
        image_name = f"ims-sync-{random_data()}"
        image_url = _get_ims_image_url("import_image_url")
        ecs_vm_name = None
        fixed_ip = None
        mfip = None

        def _cleanup():
            _cleanup_ecs_and_mfip(ecs_page, ops_page, ecs_vm_name, fixed_ip, mfip)
            _cleanup_image(ecs_page, image_name)
        request.addfinalizer(_cleanup)

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

        with allure_step_log("步骤4: 从同步存储池弹窗选择任意可选存储池"):
            ecs_page.search(image_name)
            row = ecs_page.get_row_data(image_name)
            original_pools = row.get("存储池", "")
            ecs_page.click_action(image_name, "同步存储池")
            target_pool = ecs_page.ims_select_storage_pool(exclude_pools=original_pools)
            ecs_page.dialog_confirm.click()
            ecs_page.assert_popup_success("同步镜像任务提交成功")

        with allure_step_log("步骤5: 进入详情页存储池页签，校验目标存储池开始同步"):
            ecs_page.ims_to_detail(image_name)
            ecs_page.ims_click_storage_pool_tab()
            pool_info = ecs_page.ims_wait_for_pool_appeared(target_pool, timeout=60)
            metadata_flag = _pool_metadata_flag(pool_info)
            assert metadata_flag == "否", (
                f"[FieldAssertion] 同步目标存储池不应为元数据存储池 | 期望: 否 | 实际: {metadata_flag} | 行: {pool_info}"
            )
            status = pool_info.get("状态", "")
            if status == "同步中":
                assert _pool_hash_value(pool_info) in {"", "-", "--"}, (
                    f"[FieldAssertion] 同步中目标存储池Hash应暂未生成 | 实际行: {pool_info}"
                )
            else:
                assert status == "可用" and _pool_hash_value(pool_info) not in {"", "-", "--"}, (
                    f"[FieldAssertion] 目标存储池未处于同步中或已完成状态 | 实际行: {pool_info}"
                )

        with allure_step_log("步骤6: 等待目标存储池同步进度达到100%"):
            pool_info = ecs_page.ims_wait_for_pool_progress(target_pool, progress="100%", timeout=300)
            progress = (pool_info.get("进度") or "").strip()
            assert progress == "100%" or _pool_hash_value(pool_info) not in {"", "-", "--"}, (
                f"[FieldAssertion] 目标存储池同步进度未达到100%且Hash未生成 | 实际行: {pool_info}"
            )
            metadata_flag = _pool_metadata_flag(pool_info)
            assert metadata_flag == "否", (
                f"[FieldAssertion] 同步目标存储池元数据标识不正确 | 期望: 否 | 实际: {metadata_flag} | 行: {pool_info}"
            )

        with allure_step_log("步骤7: 等待同步完成，校验目标存储池Hash已生成"):
            ecs_page.ims_wait_for_pool_hash_sync(target_pool, timeout=300)
            pool_info = ecs_page.ims_get_pool_info(target_pool)
            hash_value = _pool_hash_value(pool_info)
            assert hash_value and hash_value not in {"-", "--"}, (
                f"[FieldAssertion] 同步后存储池Hash为空 | 存储池: {target_pool} | 实际行: {pool_info}"
            )
            metadata_flag = _pool_metadata_flag(pool_info)
            assert metadata_flag == "否", (
                f"[FieldAssertion] 同步完成后目标存储池元数据标识不正确 | 期望: 否 | 实际: {metadata_flag} | 行: {pool_info}"
            )

        with allure_step_log("步骤8: 校验列表中包含同步后的存储池"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)
            row = ecs_page.get_row_data(image_name)
            assert target_pool in row.get("存储池", ""), (
                f"[FieldAssertion] 镜像列表未展示同步后的存储池 | 期望: {target_pool} | 实际行: {row}"
            )

        with allure_step_log("步骤9: 使用同步后的存储池镜像创建ECS"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.service_name = "弹性云服务器"
            ecs_vm_name = f"ecs-from-{image_name}"
            ims_network = get_prepared_ims_network(ecs_page)
            ecs_page.ecs_create(
                basic={"name": ecs_vm_name},
                storage={"image": {"source": "镜像", "name": image_name}, "storage_pool": target_pool},
                network=ims_ecs_network_config(ims_network),
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(ecs_vm_name)
            fixed_ip, mfip = _bind_mfip_for_ecs(ecs_page, ops_page, ecs_vm_name, network=ims_network["vpc_name"])

        with allure_step_log("步骤10: 登录新建ECS验证"):
            ssh_vm.connect(mfip)
            assert "inet" in ssh_vm.run("ip a")
