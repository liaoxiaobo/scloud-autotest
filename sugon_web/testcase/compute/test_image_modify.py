import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.testcase.compute._ims_helpers import (
    _cleanup_image,
    _get_ims_image_url,
)


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('镜像属性修改功能验证')
class TestImageModify:
    """验证镜像服务中私有镜像的名称、架构、版本修改功能。"""

    @allure.title("镜像-修改名称功能验证")
    def test_image_modify_name(self, ecs_page, ssh_host, request):
        """导入镜像后修改镜像名称，验证列表和详情页名称已更新。"""
        image_name = f"ims-modify-name-centos7.9-x86_64-{random_data()}"
        image_url = _get_ims_image_url("import_image_url")
        new_name = f"ims-modify-name-renamed-centos7.9-x86_64-{random_data()}"

        request.addfinalizer(lambda: _cleanup_image(ecs_page, new_name))
        request.addfinalizer(lambda: _cleanup_image(ecs_page, image_name))

        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        with allure_step_log("步骤1: 进入镜像服务并导入镜像"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.wait_for_page_ready()
            ecs_page.ims_open_import_dialog()
            ecs_page.ims_import_image(
                image_name, image_url,
                image_type="云服务器", os_type="linux",
                version="centos7.9", arch="64位", cpu_arch="x86_64"
            )
            ecs_page.ims_import_submit()
            ecs_page.wait_for_page_ready()
            ecs_page.close_drawer_if_exists()

        with allure_step_log("步骤2: 等待镜像状态变为可用"):
            ecs_page.assert_status(image_name, status="可用", timeout=600, refresh=True)

        with allure_step_log("步骤3: 校验列表字段与导入参数一致"):
            row = ecs_page.get_row_data(image_name)
            assert row.get("名称") == image_name
            ecs_page.ims_to_detail(image_name)
            detail = ecs_page.ims_get_detail_info()
            assert detail.get("名称") == image_name
            assert detail.get("架构") == "x86_64"

        with allure_step_log("步骤4: 修改镜像名称"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)
            ecs_page.ims_open_modify_dialog(image_name)
            ecs_page.ims_modify_image_name(new_name)
            ecs_page.ims_modify_submit()
            ecs_page.assert_popup_success("修改镜像成功")

        with allure_step_log("步骤5: 校验列表和详情页名称已更新"):
            ecs_page.search(new_name)
            row = ecs_page.get_row_data(new_name)
            assert row.get("名称") == new_name
            ecs_page.ims_to_detail(new_name)
            detail = ecs_page.ims_get_detail_info()
            assert detail.get("名称") == new_name

        with allure_step_log("步骤6: 后端校验镜像名称"):
            result = ssh_host.run(
                f"scli image list --format json | python -c \"import sys,json; [print(r['id']) for r in json.load(sys.stdin).get('data',[]) if r['name']=='{new_name}']\"",
                return_rc=True
            )
            assert result["rc"] == 0
            assert result["stdout"].strip() != ""

    @allure.title("镜像-修改架构功能验证")
    def test_image_modify_architecture(self, ecs_page, ssh_host, request):
        """导入镜像后修改架构为aarch64，验证架构和启动类型联动变化。"""
        image_name = f"ims-modify-arch-centos7.9-x86_64-{random_data()}"
        image_url = _get_ims_image_url("import_image_url")

        request.addfinalizer(lambda: _cleanup_image(ecs_page, image_name))

        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        with allure_step_log("步骤1: 进入镜像服务并导入镜像"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.wait_for_page_ready()
            ecs_page.ims_open_import_dialog()
            ecs_page.ims_import_image(
                image_name, image_url,
                image_type="云服务器", os_type="linux",
                version="centos7.9", arch="64位", cpu_arch="x86_64"
            )
            ecs_page.ims_import_submit()
            ecs_page.wait_for_page_ready()
            ecs_page.close_drawer_if_exists()

        with allure_step_log("步骤2: 等待镜像状态变为可用"):
            ecs_page.assert_status(image_name, status="可用", timeout=600, refresh=True)

        with allure_step_log("步骤3: 校验列表字段与导入参数一致"):
            row = ecs_page.get_row_data(image_name)
            assert row.get("名称") == image_name
            ecs_page.ims_to_detail(image_name)
            detail = ecs_page.ims_get_detail_info()
            assert detail.get("架构") == "x86_64"

        with allure_step_log("步骤4: 修改镜像架构为aarch64"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)
            ecs_page.ims_open_modify_dialog(image_name)
            ecs_page.ims_modify_architecture("aarch64")
            ecs_page.ims_modify_submit()
            ecs_page.assert_popup_success("修改镜像成功")

        with allure_step_log("步骤5: 校验架构已修改且启动类型自动变为UEFI"):
            ecs_page.search(image_name)
            row = ecs_page.get_row_data(image_name)
            assert row.get("名称") == image_name
            ecs_page.ims_to_detail(image_name)
            detail = ecs_page.ims_get_detail_info()
            assert detail.get("架构") == "aarch64"
            assert detail.get("启动类型") == "UEFI"

        with allure_step_log("步骤6: 后端校验架构变更"):
            result = ssh_host.run(
                f"scli image show $(scli image list --format json | python -c \"import sys,json; [print(r['id']) for r in json.load(sys.stdin).get('data',[]) if r['name']=='{image_name}']\")",
                return_rc=True
            )
            assert result["rc"] == 0
            assert "aarch64" in result["stdout"]

    @allure.title("镜像-修改版本功能验证")
    def test_image_modify_version(self, ecs_page, ssh_host, request):
        """导入镜像后修改操作系统版本，验证版本信息已更新。"""
        image_name = f"ims-modify-version-centos7.9-x86_64-{random_data()}"
        image_url = _get_ims_image_url("import_image_url")

        request.addfinalizer(lambda: _cleanup_image(ecs_page, image_name))

        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        with allure_step_log("步骤1: 进入镜像服务并导入镜像"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.wait_for_page_ready()
            ecs_page.ims_open_import_dialog()
            ecs_page.ims_import_image(
                image_name, image_url,
                image_type="云服务器", os_type="linux",
                version="centos7.9", arch="64位", cpu_arch="x86_64"
            )
            ecs_page.ims_import_submit()
            ecs_page.wait_for_page_ready()
            ecs_page.close_drawer_if_exists()

        with allure_step_log("步骤2: 等待镜像状态变为可用"):
            ecs_page.assert_status(image_name, status="可用", timeout=600, refresh=True)

        with allure_step_log("步骤3: 校验列表字段与导入参数一致"):
            row = ecs_page.get_row_data(image_name)
            assert row.get("名称") == image_name
            ecs_page.ims_to_detail(image_name)
            detail = ecs_page.ims_get_detail_info()
            assert detail.get("操作系统版本") == "centos7.9"

        with allure_step_log("步骤4: 修改镜像版本为麒麟v10"):
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)
            ecs_page.ims_open_modify_dialog(image_name)
            ecs_page.ims_modify_os_version("linux", "麒麟V10")
            ecs_page.ims_modify_submit()
            ecs_page.assert_popup_success("修改镜像成功")

        with allure_step_log("步骤5: 校验版本信息已修改"):
            ecs_page.search(image_name)
            row = ecs_page.get_row_data(image_name)
            assert row.get("名称") == image_name
            ecs_page.ims_to_detail(image_name)
            detail = ecs_page.ims_get_detail_info()
            assert detail.get("操作系统版本") == "麒麟V10"

        with allure_step_log("步骤6: 后端校验版本变更"):
            result = ssh_host.run(
                f"scli image show $(scli image list --format json | python -c \"import sys,json; [print(r['id']) for r in json.load(sys.stdin).get('data',[]) if r['name']=='{image_name}']\")",
                return_rc=True
            )
            assert result["rc"] == 0
            assert "麒麟V10" in result["stdout"]
