import pytest
import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.testcase.compute._ims_helpers import _bind_mfip_for_ecs, _cleanup_ecs_and_mfip
from sugon_web.testcase.compute._ims_network_helpers import (
    get_prepared_ims_network,
    ims_ecs_network_config,
)


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSEcsSelectSynced:

    @allure.title("镜像管理-ECS选择同步存储池的镜像")
    @pytest.mark.parametrize("image", [{"image": "cirros-0.5.2.raw", "backend": "xbd-test"}], indirect=True)
    def test_ims_ecs_select_synced_image(self, ecs_page, ops_page, image, ssh_vm, request):
        image_name = image.get("name")
        ecs_vm_name = None
        fixed_ip = None
        mfip = None
        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        def _cleanup():
            _cleanup_ecs_and_mfip(ecs_page, ops_page, ecs_vm_name, fixed_ip, mfip)
        request.addfinalizer(_cleanup)

        with allure_step_log("步骤1: 进入私有镜像，同步存储池"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)
            row = ecs_page.get_row_data(image_name)
            original_pools = row.get("存储池", "")
            ecs_page.click_action(image_name, "同步存储池")
            target_pool = ecs_page.ims_get_another_storage_pool(original_pools)
            ecs_page.ims_select_storage_pool(target_pool)
            ecs_page.dialog_confirm.click()
            ecs_page.assert_popup_success("同步镜像任务提交成功")

        with allure_step_log("步骤2: 等待同步完成"):
            ecs_page.ims_to_detail(image_name)
            ecs_page.ims_wait_for_pool_sync(target_pool, timeout=300)

        with allure_step_log("步骤3: 使用同步后的镜像创建ECS"):
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
            ecs_row = ecs_page.get_row_data(ecs_vm_name)
            assert ecs_row.get("镜像名称") == image_name, (
                f"[FieldAssertion] ECS镜像名称不匹配 | 期望: {image_name} | 实际: {ecs_row.get('镜像名称')}"
            )
            pool_text = ecs_row.get("存储池") or ecs_row.get("存储池名称") or ecs_row.get("系统盘存储池") or ""
            assert target_pool in pool_text, (
                f"[FieldAssertion] ECS未使用同步后的存储池镜像 | 期望存储池: {target_pool} | 实际行数据: {ecs_row}"
            )
            fixed_ip, mfip = _bind_mfip_for_ecs(ecs_page, ops_page, ecs_vm_name, network=ims_network["vpc_name"])

        with allure_step_log("步骤4: 登录新建ECS验证"):
            ssh_vm.connect(mfip)
            assert "inet" in ssh_vm.run("ip a")
