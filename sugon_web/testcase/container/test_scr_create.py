import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data, load_data


@allure.epic('容器服务')
@allure.feature('容器镜像服务SCR')
class TestSCRCreate:
    """SCR 实例创建数据驱动测试类。"""

    @allure.title("实例管理-创建 SCR 实例(instance_type={params[instance_type]}, storage_type={params[storage_type]})")
    @pytest.mark.parametrize("params", load_data("test_scr_create", data_file='test_scr.yaml'))
    def test_scr_create(self, scr_page, ssh_host, params):
        """数据驱动创建 SCR 单机/高可用实例，验证 UI 状态及后台虚机规格。"""
        instance_name = f"scr-{random_data(length=4)}"
        flavor = "4C8G"
        instance_type = params["instance_type"]
        storage_type = params.get("storage_type")

        with allure_step_log(f"步骤1: 创建 SCR {instance_type} 实例 ({instance_name})"):
            create_kwargs = {
                "name": instance_name,
                "instance_type": instance_type,
                "flavor": flavor,
            }
            if storage_type:
                create_kwargs["storage_type"] = storage_type
            scr_page.scr_create(**create_kwargs)

            popup_text = scr_page.get_popup_message()
            if "S3" in popup_text and ("失败" in popup_text or "缺少" in popup_text):
                pytest.skip(f"环境未配置 S3 存储: {popup_text}")

            scr_page.assert_popup_success()

        with allure_step_log("步骤2: 验证实例列表中存在新创建的实例"):
            scr_page.goto_service(scr_page.service_name)
            scr_page.goto_submenu("实例管理")
            scr_page.assert_list_contain(instance_name, column_name="名称")

        with allure_step_log("步骤3: 验证实例状态收敛到运行中"):
            scr_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure_step_log("步骤4: 回读实例字段并验证类型"):
            row_data = scr_page.get_row_data(instance_name)
            assert row_data, f"未获取到实例 {instance_name} 的列表数据"
            type_mapping = {"ALONE": "单机", "HA": "高可用", "CLUSTER": "集群"}
            expected_type = type_mapping.get(instance_type, instance_type)
            assert expected_type in row_data.get("类型", ""), (
                f"实例类型不一致: 期望 {expected_type}, 实际 {row_data.get('类型', '')}"
            )

        with allure_step_log("步骤5: SSH 后台验证虚机规格"):
            flavor_specs = {
                "4C8G": {"vcpu": "4", "memory_mb": "8192"},
            }
            expected = flavor_specs.get(flavor)
            if expected:
                ssh_host.assert_guest_fields(
                    instance_name,
                    expected,
                    f"{instance_name} 后端虚机规格验证失败"
                )

        with allure_step_log("步骤6: 清理测试数据"):
            scr_page.goto_service(scr_page.service_name)
            scr_page.goto_submenu("实例管理")
            scr_page.scr_delete(instance_name)
            scr_page.assert_deleted(instance_name, timeout=600)
            ssh_host.wait_vm_deleted(instance_name, timeout=600)

    @allure.title("实例管理-批量删除 SCR 实例")
    def test_scr_batch_delete(self, scr_page, ssh_host):
        """创建两个临时 SCR 实例后批量删除，验证 UI 列表和后台虚机均清理。"""
        instance_names = []

        with allure_step_log("步骤1: 创建两个临时实例"):
            for _ in range(2):
                name = f"scr-{random_data(length=4)}"
                instance_names.append(name)
                scr_page.scr_create(name=name, instance_type="ALONE", flavor="4C8G")
                scr_page.assert_popup_success()

        with allure_step_log("步骤2: 等待实例状态收敛到运行中"):
            for name in instance_names:
                scr_page.assert_status(name, status="运行中", timeout=1200)

        with allure_step_log("步骤3: 批量删除实例"):
            scr_page.scr_batch_delete(instance_names)
            for name in instance_names:
                scr_page.assert_deleted(name, timeout=600)

        with allure_step_log("步骤4: 后台验证虚机已删除"):
            for name in instance_names:
                ssh_host.wait_vm_deleted(name, timeout=600)
