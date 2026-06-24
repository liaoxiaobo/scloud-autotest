import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.testcase.compute._ims_helpers import (
    _bind_mfip_for_ecs,
    _choose_available_host,
    _cleanup_ecs_and_mfip,
    _cleanup_image,
    _get_ims_image_url,
)
from sugon_web.testcase.compute._ims_network_helpers import (
    get_prepared_ims_network,
    ims_ecs_network_config,
)

EXPECTED_OS_TYPE = "linux"
EXPECTED_OS_BITS = "64位"
EXPECTED_OS_VERSION = "centos7.9"
EXPECTED_CPU_ARCH = "x86_64"
EXPECTED_BOOT_TYPE = "Legacy"
EXPECTED_IMAGE_FORMAT = "raw"
EXPECTED_DETAIL_IMAGE_TYPE = "弹性云服务器"
EXPECTED_ADVANCED_DETAIL = {
    "机密镜像": "关闭",
    "加密引擎": "--",
    "密钥类型": "--",
    "密钥UUID": "--",
    "海光特性": "否",
    "机密内存": "关闭",
    "是否受保护": "未受保护",
    "网卡多队列": "开启",
}


def _assert_detail_field(detail: dict, field: str, expected: str):
    actual = detail.get(field)
    assert actual == expected, (
        f"[FieldAssertion] 详情页{field}不匹配 | 期望: {expected} | 实际: {actual} | 详情: {detail}"
    )


def _assert_detail_field_present(detail: dict, field: str):
    actual = detail.get(field, "")
    assert actual and actual not in {"-", "--"}, (
        f"[FieldAssertion] 详情页{field}为空或无效 | 实际: {actual} | 详情: {detail}"
    )


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSImport:

    @allure.title("镜像管理-导入弹性云服务器镜像")
    def test_ims_import_image(self, ecs_page, ops_page, ssh_host, ssh_vm, request):
        image_name = f"ims-import-{random_data()}"
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

        with allure_step_log(f"步骤2: 导入镜像 {image_name}"):
            ecs_page.ims_open_import_dialog()
            ecs_page.ims_import_image(image_name, image_url)
            ecs_page.ims_import_submit()
            ecs_page.wait_for_page_ready()
            ecs_page.close_drawer_if_exists()

        with allure_step_log("步骤3: 验证导入提交成功"):
            ecs_page.assert_status(image_name, status="可用", timeout=600, refresh=True)

        with allure_step_log("步骤4: 轮询等待镜像可用"):
            ecs_page.assert_status(image_name, status="可用", timeout=600, refresh=True)

        with allure_step_log("步骤5: 校验列表和详情字段"):
            ecs_page.search(image_name)
            row = ecs_page.get_row_data(image_name)
            assert row.get("名称") == image_name, (
                f"[FieldAssertion] 镜像名称不匹配 | 期望: {image_name} | 实际: {row.get('名称')}"
            )
            assert row.get("状态") == "可用", (
                f"[FieldAssertion] 镜像状态不匹配 | 期望: 可用 | 实际: {row.get('状态')}"
            )
            assert row.get("操作系统类型") == EXPECTED_OS_TYPE, (
                f"[FieldAssertion] 操作系统类型不匹配 | 期望: {EXPECTED_OS_TYPE} | 实际: {row.get('操作系统类型')}"
            )
            assert row.get("版本") == EXPECTED_OS_VERSION, (
                f"[FieldAssertion] 操作系统版本不匹配 | 期望: {EXPECTED_OS_VERSION} | 实际: {row.get('版本')}"
            )
            assert row.get("CPU架构") == EXPECTED_CPU_ARCH, (
                f"[FieldAssertion] CPU架构不匹配 | 期望: {EXPECTED_CPU_ARCH} | 实际: {row.get('CPU架构')}"
            )
            ecs_page.ims_to_detail(image_name)
            detail = ecs_page.ims_get_detail_info()
            _assert_detail_field(detail, "名称", image_name)
            _assert_detail_field(detail, "状态", "可用")
            _assert_detail_field(detail, "操作系统类型", EXPECTED_OS_TYPE)
            _assert_detail_field(detail, "操作系统位数", EXPECTED_OS_BITS)
            _assert_detail_field(detail, "操作系统版本", EXPECTED_OS_VERSION)
            _assert_detail_field(detail, "架构", EXPECTED_CPU_ARCH)
            _assert_detail_field(detail, "镜像类型", EXPECTED_DETAIL_IMAGE_TYPE)
            _assert_detail_field(detail, "镜像格式", EXPECTED_IMAGE_FORMAT)
            _assert_detail_field(detail, "启动类型", EXPECTED_BOOT_TYPE)
            _assert_detail_field_present(detail, "容量")
            for field, expected in EXPECTED_ADVANCED_DETAIL.items():
                _assert_detail_field(detail, field, expected)
            image_uuid = detail.get("UUID", "")
            assert image_uuid, f"[FieldAssertion] 详情页未获取到镜像UUID | 详情: {detail}"

        with allure_step_log("步骤6: 后端校验"):
            result = ssh_host.run(f"scli image show {image_uuid}", return_rc=True)
            assert result["rc"] == 0, f"[BackendAssertion] scli查询失败 | stderr: {result.get('stderr')}"
            backend_detail = ssh_host.parse_table_output(result.get("stdout", ""))
            assert backend_detail.get("id") == image_uuid, (
                f"[BackendAssertion] 后端镜像ID不匹配 | 期望: {image_uuid} | 实际: {backend_detail.get('id')}"
            )
            assert backend_detail.get("name") == image_name, (
                f"[BackendAssertion] 后端镜像名称不匹配 | 期望: {image_name} | 实际: {backend_detail.get('name')}"
            )
            assert backend_detail.get("disk_format") == EXPECTED_IMAGE_FORMAT, (
                f"[BackendAssertion] 后端镜像格式不匹配 | 期望: {EXPECTED_IMAGE_FORMAT} | 实际: {backend_detail.get('disk_format')}"
            )

        with allure_step_log("步骤7: 使用镜像创建ECS"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.service_name = "弹性云服务器"
            ecs_vm_name = f"ecs-from-{image_name}"
            host = _choose_available_host(ssh_host)
            basic = {"name": ecs_vm_name}
            if host:
                basic["host"] = host
            ims_network = get_prepared_ims_network(ecs_page)
            ecs_page.ecs_create(
                basic=basic,
                storage={"image": {"source": "镜像", "name": image_name}},
                network=ims_ecs_network_config(ims_network),
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(ecs_vm_name, refresh=True)
            fixed_ip, mfip = _bind_mfip_for_ecs(ecs_page, ops_page, ecs_vm_name, network=ims_network["vpc_name"])

        with allure_step_log("步骤8: 登录新建ECS验证"):
            ssh_vm.connect(mfip)
            assert "CPU" in ssh_vm.run("lscpu"), "[BackendAssertion] lscpu执行失败"
