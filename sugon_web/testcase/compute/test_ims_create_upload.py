import allure
import os
from pathlib import Path

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.testcase.compute._ims_helpers import (
    _bind_mfip_for_ecs,
    _choose_available_host,
    _cleanup_ecs_and_mfip,
    _cleanup_image,
)
from sugon_web.testcase.compute._ims_network_helpers import (
    get_prepared_ims_network,
    ims_ecs_network_config,
)


IMS_UPLOAD_IMAGE_ENV = "SUGON_IMS_UPLOAD_IMAGE_PATH"
PROJECT_UPLOAD_IMAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "test_data"
    / "ims_images"
    / "cirros-0.5.2"
    / "cirros-0.5.2.raw"
)
LOCAL_UPLOAD_IMAGE_PATH = Path(r"C:\Users\Administrator\Downloads\cirros-0.5.2")
EXPECTED_OS_TYPE = "linux"
EXPECTED_OS_BITS = "64位"
EXPECTED_OS_VERSION = "centos7.9"
EXPECTED_CPU_ARCH = "x86_64"
EXPECTED_BOOT_TYPE = "Legacy"
EXPECTED_IMAGE_FORMAT = "raw"
EXPECTED_DETAIL_IMAGE_TYPE = "弹性云服务器"
CIRROS_USERNAME = "cirros"
CIRROS_PASSWORD = "gocubsgo"
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


def _resolve_local_upload_image_path() -> str:
    """获取本地 cirros 上传镜像文件。

    查找优先级：
    1. 环境变量 SUGON_IMS_UPLOAD_IMAGE_PATH（Jenkins 推荐）
    2. 项目固定测试数据目录 sugon_web/testcase/test_data/ims_images/cirros-0.5.2/cirros-0.5.2.raw
    3. 本机 Downloads 路径（本地调试兜底，兼容未带 .raw 后缀）
    """
    env_path = os.environ.get(IMS_UPLOAD_IMAGE_ENV, "").strip()
    candidates = [
        *( [Path(env_path), Path(f"{env_path}.raw")] if env_path else [] ),
        PROJECT_UPLOAD_IMAGE_PATH,
        LOCAL_UPLOAD_IMAGE_PATH,
        Path(f"{LOCAL_UPLOAD_IMAGE_PATH}.raw"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    raise AssertionError(
        "未找到本地 IMS 上传镜像文件。请在 Jenkins 构建前下载到 "
        f"{PROJECT_UPLOAD_IMAGE_PATH}，或设置环境变量 {IMS_UPLOAD_IMAGE_ENV}。已尝试: "
        + ", ".join(str(path) for path in candidates)
    )


def _format_mib(file_path: str) -> str:
    """按页面展示格式把本地文件大小格式化为 MiB。"""
    size_mib = Path(file_path).stat().st_size / 1024 / 1024
    return f"{size_mib:.2f} MiB"


def _assert_detail_field(detail: dict, field: str, expected: str):
    actual = detail.get(field)
    assert actual == expected, (
        f"[FieldAssertion] 详情页{field}不匹配 | 期望: {expected} | 实际: {actual} | 详情: {detail}"
    )


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('业务核心TOP10功能验证')
class TestIMSCreateUpload:

    @allure.title("镜像管理-新建弹性云服务器镜像（标准上传）")
    def test_ims_create_image_upload(self, ecs_page, ops_page, ssh_host, ssh_vm, request):
        image_name = f"cirros-upload-{random_data()}"
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

        with allure_step_log("步骤2.1: 准备本地标准上传镜像文件 cirros-0.5.2.raw"):
            local_image_path = _resolve_local_upload_image_path()
            expected_capacity = _format_mib(local_image_path)

        with allure_step_log(f"步骤2.2: 打开新建镜像对话框并填写基础信息、高级配置 {image_name}"):
            ecs_page.btn_create.click()
            ecs_page.ims_create_private_image(image_name)

        with allure_step_log("步骤2.3: 进入上传镜像文件页"):
            ecs_page.ims_upload_click_next()

        with allure_step_log("步骤2.4: 选择本地 cirros 镜像文件"):
            ecs_page.ims_upload_image_file(local_image_path)

        with allure_step_log("步骤2.5: 等待文件上传中状态出现"):
            ecs_page.ims_wait_upload_file_status("上传中", timeout=30)

        with allure_step_log("步骤2.6: 等待文件上传成功"):
            ecs_page.ims_wait_upload_file_status("上传成功", timeout=300)

        with allure_step_log("步骤2.7: 点击确定提交镜像创建"):
            ecs_page.ims_upload_submit()

        with allure_step_log("步骤3: 验证上传提交成功"):
            ecs_page.assert_popup_success(timeout=30)
            ecs_page.close_drawer_if_exists()

        with allure_step_log("步骤4: 轮询等待镜像状态变为可用"):
            ecs_page.assert_status(image_name, status="可用", timeout=600, refresh=True)

        with allure_step_log("步骤5: 搜索镜像并校验列表字段"):
            ecs_page.search(image_name)
            row = ecs_page.get_row_data(image_name)
            assert row.get("名称") == image_name, f"[FieldAssertion] 镜像名称不匹配 | 期望: {image_name} | 实际: {row.get('名称')}"
            assert row.get("状态") == "可用", f"[FieldAssertion] 镜像状态不匹配 | 期望: 可用 | 实际: {row.get('状态')}"
            assert row.get("操作系统类型") == EXPECTED_OS_TYPE, (
                f"[FieldAssertion] 操作系统类型不匹配 | 期望: {EXPECTED_OS_TYPE} | 实际: {row.get('操作系统类型')}"
            )
            assert row.get("版本") == EXPECTED_OS_VERSION, (
                f"[FieldAssertion] 操作系统版本不匹配 | 期望: {EXPECTED_OS_VERSION} | 实际: {row.get('版本')}"
            )
            assert row.get("CPU架构") == EXPECTED_CPU_ARCH, (
                f"[FieldAssertion] CPU架构不匹配 | 期望: {EXPECTED_CPU_ARCH} | 实际: {row.get('CPU架构')}"
            )

        with allure_step_log("步骤6: 校验详情页字段与创建配置一致"):
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
            _assert_detail_field(detail, "容量", expected_capacity)
            for field, expected in EXPECTED_ADVANCED_DETAIL.items():
                _assert_detail_field(detail, field, expected)
            image_uuid = detail.get("UUID", "")
            assert image_uuid, f"[FieldAssertion] 详情页未获取到镜像UUID | 详情: {detail}"

        with allure_step_log("步骤7: 后端校验镜像属性"):
            result = ssh_host.run(f"scli image show {image_uuid}", return_rc=True)
            assert result["rc"] == 0, f"[BackendAssertion] scli查询失败 | stderr: {result.get('stderr')}"

        with allure_step_log("步骤8: 使用镜像创建ECS"):
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
            ecs_page.assert_status(ecs_vm_name, status="可用", refresh=True)
            fixed_ip, mfip = _bind_mfip_for_ecs(ecs_page, ops_page, ecs_vm_name, network=ims_network["vpc_name"])

        with allure_step_log("步骤9: 登录新建ECS验证系统信息"):
            ssh_vm.connect(mfip, username=CIRROS_USERNAME, pwd=CIRROS_PASSWORD)
            assert "CPU" in ssh_vm.run("lscpu"), "[BackendAssertion] lscpu执行失败"
            assert "MemTotal" in ssh_vm.run("grep MemTotal /proc/meminfo"), "[BackendAssertion] 内存信息获取失败"
