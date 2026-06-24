import allure
import re

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.testcase.compute._ims_helpers import _cleanup_image, _resolve_ims_upload_image_path


def _get_row_hash(row: dict) -> str:
    return (row.get("Hash") or row.get("Hash值") or "").strip()


def _get_metadata_flag(row: dict) -> str:
    return (
        row.get("元数据存储池")
        or row.get("是否元数据存储池")
        or row.get("元数据")
        or ""
    ).strip()


def _get_image_uuid_from_list_output(output: str, image_name: str) -> str:
    """从 `scli image list | grep <image>` 输出中提取镜像 UUID。"""
    for line in output.splitlines():
        if image_name not in line:
            continue
        match = re.search(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", line)
        if match:
            return match.group(0)
    raise AssertionError(f"未从 scli image list 输出中解析到镜像 UUID | image={image_name} | output={output}")


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSImageHash:

    @allure.title("镜像管理-标准上传镜像Hash值与后端一致")
    def test_ims_upload_image_hash(self, ecs_page, ssh_host, request):
        image_name = f"cirros-upload-{random_data()}"
        ecs_page.goto_service("弹性云服务器")
        ecs_page.service_name = "弹性云服务器"

        request.addfinalizer(lambda: _cleanup_image(ecs_page, image_name))

        with allure_step_log(f"步骤1: 按标准上传流程新建 cirros 镜像 {image_name}"):
            ecs_page.goto_submenu("镜像服务")
            local_image_path = _resolve_ims_upload_image_path(config_key="upload_image_url")
            ecs_page.btn_create.click()
            ecs_page.ims_create_private_image(image_name)
            ecs_page.ims_upload_click_next()
            ecs_page.ims_upload_image_file(local_image_path)
            ecs_page.ims_wait_upload_file_status("上传中", timeout=30)
            ecs_page.ims_wait_upload_file_status("上传成功", timeout=300)
            ecs_page.ims_upload_submit()
            ecs_page.assert_popup_success(timeout=30)
            ecs_page.close_drawer_if_exists()
            ecs_page.assert_status(image_name, status="可用", timeout=600, refresh=True)

        with allure_step_log("步骤2: 进入上传镜像详情→存储池页签"):
            ecs_page.search(image_name)
            ecs_page.ims_to_detail(image_name)
            ecs_page.ims_click_storage_pool_tab()

        with allure_step_log("步骤3: 校验详情页元数据存储池为是且Hash有值"):
            pool_info = ecs_page.ims_get_metadata_pool_info()
            page_hash = _get_row_hash(pool_info)
            assert _get_metadata_flag(pool_info) == "是", (
                f"[FieldAssertion] 元数据存储池字段不为'是' | 实际行: {pool_info}"
            )
            assert page_hash not in ["", "-", "--"], (
                f"[FieldAssertion] 存储池Hash为空 | 实际行: {pool_info}"
            )
            assert pool_info.get("状态") == "可用", (
                f"[FieldAssertion] 存储池状态不为可用 | 实际行: {pool_info}"
            )

        with allure_step_log("步骤4: 通过 scli image list | grep cirros 获取镜像UUID"):
            list_result = ssh_host.run(f"scli image list | grep {image_name}", return_rc=True)
            assert list_result["rc"] == 0, (
                f"[BackendAssertion] scli image list 未找到镜像 {image_name} | "
                f"stdout: {list_result.get('stdout')} | stderr: {list_result.get('stderr')}"
            )
            image_uuid = _get_image_uuid_from_list_output(list_result.get("stdout", ""), image_name)

        with allure_step_log("步骤5: 校验页面Hash与后端os_hash_value一致"):
            backend_detail = ssh_host.parse_table_output(ssh_host.run(f"scli image show {image_uuid}"))
            backend_hash = backend_detail.get("os_hash_value", "").strip()
            assert backend_hash, (
                f"[BackendAssertion] scli image show 未返回 os_hash_value | uuid: {image_uuid} | detail: {backend_detail}"
            )
            assert page_hash == backend_hash, (
                f"[FieldAssertion] 页面存储池Hash与后端os_hash_value不一致 | "
                f"页面Hash: {page_hash} | 后端os_hash_value: {backend_hash} | uuid: {image_uuid}"
            )
