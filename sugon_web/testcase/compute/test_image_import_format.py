import allure
import pytest
import re

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.testcase.compute._ims_helpers import (
    _bind_mfip_for_ecs,
    _cleanup_ecs_and_mfip,
    _cleanup_image,
)
from sugon_web.testcase.compute._ims_network_helpers import (
    get_prepared_ims_network,
    ims_ecs_network_config,
)
from sugon_web.testcase.compute.image_import_format_config import get_image_import_format_url
from sugon_web.testcase.compute._ims_vnc_helpers import (
    install_iso_from_vnc,
    VNC_FINAL_LOGIN_SUCCESS,
    VNC_FINAL_CONSOLE_LOGIN_PROMPT,
)

EXPECTED_DETAIL_IMAGE_TYPE = "弹性云服务器"
EXPECTED_SHARE_MODE = "全局共享"
DEFAULT_BOOT_TYPE = "Legacy"
DEFAULT_IMAGE_FORMAT = "raw"
DEFAULT_ECS_LOGIN_PASSWORD = "admin1234@sugon"
DEFAULT_VNC_PASSWORD = "sugon@20"


def _assert_field(actual: str, expected: str, field: str, source: dict):
    assert actual == expected, (
        f"[FieldAssertion] {field}不匹配 | 期望: {expected} | 实际: {actual} | 来源: {source}"
    )


def _assert_detail_field(detail: dict, field: str, expected: str):
    _assert_field(detail.get(field), expected, f"详情页{field}", detail)


@allure.epic('计算服务')
@allure.feature('镜像服务 IMS')
@allure.story('镜像导入多格式验证')
class TestImageImportFormat:
    """验证导入 VMDK/VHD/VHDX/QCOW2/ISO 六种格式镜像并创建云服务器。"""

    @allure.title("镜像导入格式验证-{params[format]}")
    @pytest.mark.parametrize(
        "params",
        [
            {
                "format": "VMDK",
                "os_type": "linux",
                "version": "centos7.9",
                "arch": "64位",
                "cpu_arch": "x86_64",
            },
            {
                "format": "VHD",
                "os_type": "linux",
                "version": "centos7.9",
                "arch": "64位",
                "cpu_arch": "x86_64",
            },
            {
                "format": "VHDX",
                "os_type": "linux",
                "version": "centos7.9",
                "arch": "64位",
                "cpu_arch": "x86_64",
            },
            {
                "format": "QCOW2",
                "os_type": "linux",
                "version": "centos7.9",
                "arch": "64位",
                "cpu_arch": "x86_64",
            },
            {
                "format": "ISO_Kylin",
                "os_type": "linux",
                "version": "麒麟V10",
                "arch": "64位",
                "cpu_arch": "x86_64",
                "name_prefix": "kyliniso",
                "boot_type": "Legacy",
                "expected_image_format": "iso",
                "ecs_image_source": "ISO",
                "ecs_system_disk": 50,
                "vnc_install": True,
                "vnc_kernel_desc": "麒麟89.19内核",
                "vnc_boot_keys": ["Enter"],
                "vnc_install_timeout": 7200,
                "vnc_min_install_seconds": 900,
                "vnc_stable_seconds": 300,
                "vnc_expected_final_state": VNC_FINAL_CONSOLE_LOGIN_PROMPT,
                "vnc_expected_final_desc": "安装完成后停在文本控制台 localhost login: 提示页",
                "ecs_login_password": "admin1234@sugon",
                "vnc_login_username": "root",
                "vnc_login_password": "admin1234@sugon",
            },
            {
                "format": "ISO_Anolis",
                "os_type": "linux",
                "version": "Anolis OS8.6",
                "arch": "64位",
                "cpu_arch": "x86_64",
                "name_prefix": "anolis",
                "boot_type": "Legacy",
                "expected_image_format": "iso",
                "ecs_image_source": "ISO",
                "ecs_system_disk": 20,
                "vnc_install": True,
                "vnc_kernel_desc": "龙蜥5.10.134-18内核",
                "vnc_restart_before_vnc": True,
                "vnc_boot_prompt_mode": True,
                "vnc_boot_keys": ["ArrowUp", "ArrowUp"],
                "vnc_install_timeout": 7200,
                "vnc_min_install_seconds": 900,
                "vnc_stable_seconds": 300,
                "vnc_expected_final_state": VNC_FINAL_CONSOLE_LOGIN_PROMPT,
                "vnc_expected_final_desc": "安装完成后停在文本控制台 localhost login: 提示页",
            },
        ],
        ids=["VMDK", "VHD", "VHDX", "QCOW2", "ISO_Kylin", "ISO_Anolis"],
    )
    @pytest.mark.slow
    def test_image_import_format_and_create_ecs(self, ecs_page, ops_page, ssh_host, ssh_vm, params, request):
        """导入指定格式镜像，验证可用后创建ECS并校验实例内部配置。"""
        image_name = f"{params.get('name_prefix', 'ims-import-' + params['format'].lower())}-{random_data()}"
        image_url = get_image_import_format_url(params["format"])
        expected_boot_type = params.get("boot_type", DEFAULT_BOOT_TYPE)
        expected_image_format = params.get("expected_image_format", DEFAULT_IMAGE_FORMAT)
        expected_storage_pool = params.get("storage_pool")
        if not expected_storage_pool and expected_image_format == "iso":
            expected_storage_pool = ecs_page.storage_pool
        ecs_image_source = params.get("ecs_image_source", "镜像")
        ecs_system_disk = params.get("ecs_system_disk")
        ecs_login_password = params.get("ecs_login_password", DEFAULT_ECS_LOGIN_PASSWORD)
        ecs_vm_name = None
        fixed_ip = None
        mfip = None
        cleanup_done = False

        def _cleanup_created_resources():
            nonlocal cleanup_done
            if cleanup_done:
                return
            cleanup_done = True
            with allure_step_log("步骤10: 清理测试数据"):
                _cleanup_ecs_and_mfip(ecs_page, ops_page, ecs_vm_name, fixed_ip, mfip)
                _cleanup_image(ecs_page, image_name)

        request.addfinalizer(_cleanup_created_resources)

        with allure_step_log(f"步骤1: 进入私有镜像模块"):
            ecs_page.ims_goto_service()
            ecs_page.wait_for_page_ready()

        with allure_step_log(f"步骤2: 导入{params['format']}镜像 {image_name}"):
            ecs_page.ims_open_import_dialog()
            ecs_page.ims_import_image(
                name=image_name,
                url=image_url,
                image_type="云服务器",
                os_type=params["os_type"],
                version=params["version"],
                arch=params["arch"],
                cpu_arch=params["cpu_arch"],
                storage_pool=expected_storage_pool,
                boot_type=expected_boot_type,
            )
            ecs_page.ims_import_submit()

        with allure_step_log("步骤3: 验证导入提交成功"):
            ecs_page.wait_for_page_ready()
            ecs_page.close_drawer_if_exists()
            ecs_page.close_dialog_if_exists()

        with allure_step_log("步骤4: 轮询等待镜像状态变为可用"):
            ecs_page.assert_status(image_name, status="可用", timeout=1800, refresh=True)

        with allure_step_log("步骤4b: 等待镜像状态稳定"):
            ecs_page.wait_for_page_ready()
            ecs_page.wait_for_operation_complete()

        with allure_step_log("步骤4c: 二次确认镜像状态仍为可用"):
            ecs_page.assert_status(image_name, status="可用", timeout=60, refresh=True)

        with allure_step_log("步骤5: 校验镜像列表字段与导入配置一致"):
            ecs_page.search(image_name)
            row = ecs_page.get_row_data(image_name)
            _assert_field(row.get("名称"), image_name, "镜像列表名称", row)
            _assert_field(row.get("状态"), "可用", "镜像列表状态", row)
            _assert_field(row.get("操作系统类型"), params["os_type"], "镜像列表操作系统类型", row)
            _assert_field(row.get("版本"), params["version"], "镜像列表操作系统版本", row)
            _assert_field(row.get("CPU架构"), params["cpu_arch"], "镜像列表CPU架构", row)
            if expected_storage_pool:
                _assert_field(row.get("存储池"), expected_storage_pool, "镜像列表存储池", row)

        with allure_step_log("步骤6: 校验镜像详情字段与导入配置一致"):
            ecs_page.ims_to_detail(image_name)
            detail = ecs_page.ims_get_detail_info()
            _assert_detail_field(detail, "名称", image_name)
            _assert_detail_field(detail, "状态", "可用")
            _assert_detail_field(detail, "操作系统类型", params["os_type"])
            _assert_detail_field(detail, "操作系统位数", params["arch"])
            _assert_detail_field(detail, "操作系统版本", params["version"])
            _assert_detail_field(detail, "架构", params["cpu_arch"])
            _assert_detail_field(detail, "镜像类型", EXPECTED_DETAIL_IMAGE_TYPE)
            _assert_detail_field(detail, "镜像格式", expected_image_format)
            _assert_detail_field(detail, "启动类型", expected_boot_type)
            _assert_detail_field(detail, "共享模式", EXPECTED_SHARE_MODE)
            image_uuid = detail.get("UUID", "")
            assert image_uuid, f"[FieldAssertion] 详情页未获取到镜像UUID | 详情: {detail}"

            if expected_storage_pool:
                ecs_page.ims_click_storage_pool_tab()
                pool_info = ecs_page.ims_get_pool_info(expected_storage_pool)
                _assert_field(
                    ecs_page._ims_pool_name_from_row(pool_info),
                    expected_storage_pool,
                    "详情页存储池",
                    pool_info,
                )

        with allure_step_log("步骤7: 后端校验镜像属性"):
            result = ssh_host.run(f"scli image show {image_uuid}", return_rc=True)
            assert result["rc"] == 0, (
                f"[BackendAssertion] scli查询镜像失败 | stderr: {result.get('stderr', '')}"
            )
            backend_detail = ssh_host.parse_table_output(result.get("stdout", ""))
            if backend_detail.get("disk_format"):
                assert backend_detail.get("disk_format") == expected_image_format, (
                    "[BackendAssertion] 后端镜像格式不匹配 | "
                    f"期望: {expected_image_format} | 实际: {backend_detail.get('disk_format')}"
                )
            stores_match = re.search(r"stores\s+\|\s+(\S+)", result["stdout"])
            image_storage_pool = stores_match.group(1) if stores_match else ecs_page.storage_pool
            logger.info(f"镜像存储池: {image_storage_pool}")

        with allure_step_log(f"步骤8: 使用{ecs_image_source}来源创建云服务器"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_vm_name = f"ecs-from-{image_name}"
            ims_network = get_prepared_ims_network(ecs_page)
            storage_config = {
                "image": {"source": ecs_image_source, "name": image_name},
                "storage_pool": image_storage_pool,
            }
            if ecs_system_disk:
                storage_config["system_disk"] = ecs_system_disk
            ecs_page.ecs_create(
                basic={"name": ecs_vm_name},
                storage=storage_config,
                network=ims_ecs_network_config(ims_network),
                manage={
                    "login_type": "密码登录",
                    "login_pwd": ecs_login_password,
                    "vnc_pwd": DEFAULT_VNC_PASSWORD,
                },
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(ecs_vm_name)
            ecs_row = ecs_page.get_row_data(ecs_vm_name)
            _assert_field(ecs_row.get("镜像名称"), image_name, "云服务器列表镜像名称", ecs_row)
            if ecs_image_source == "ISO":
                assert ecs_row.get("挂载云硬盘", "").startswith("cdrom"), (
                    f"[FieldAssertion] ISO来源云服务器未挂载CD-ROM | 实际行: {ecs_row}"
                )
            else:
                fixed_ip, mfip = _bind_mfip_for_ecs(
                    ecs_page,
                    ops_page,
                    ecs_vm_name,
                    network=ims_network["vpc_name"],
                )

        if params.get("vnc_install"):
            kernel_desc = params.get("vnc_kernel_desc", "指定内核")
            final_desc = params.get("vnc_expected_final_desc", "安装后登录成功")
            with allure_step_log(f"步骤9: 进入VNC选择{kernel_desc}安装并等待{final_desc}"):
                install_iso_from_vnc(
                    ecs_page,
                    ecs_vm_name,
                    vncpwd=DEFAULT_VNC_PASSWORD,
                    restart_before_vnc=params.get("vnc_restart_before_vnc", False),
                    boot_interrupt_keys=params.get("vnc_boot_interrupt_keys"),
                    boot_device_keys=params.get("vnc_boot_device_keys"),
                    boot_keys=params.get("vnc_boot_keys"),
                    boot_prompt_mode=params.get("vnc_boot_prompt_mode", False),
                    install_timeout=params.get("vnc_install_timeout", 3600),
                    min_install_seconds=params.get("vnc_min_install_seconds", 900),
                    stable_seconds=params.get("vnc_stable_seconds", 300),
                    login_username=params.get("vnc_login_username", "root"),
                    login_password=params.get("vnc_login_password", "admin1234@sugon"),
                    expected_final_state=params.get(
                        "vnc_expected_final_state",
                        VNC_FINAL_LOGIN_SUCCESS,
                    ),
                )
        elif ecs_image_source == "ISO":
            with allure_step_log("步骤9: 验证ISO来源云服务器创建完成并挂载CD-ROM"):
                ecs_page.search(ecs_vm_name)
                ecs_row = ecs_page.get_row_data(ecs_vm_name)
                _assert_field(ecs_row.get("镜像名称"), image_name, "云服务器列表镜像名称", ecs_row)
                assert ecs_row.get("挂载云硬盘", "").startswith("cdrom"), (
                    f"[FieldAssertion] ISO来源云服务器未挂载CD-ROM | 实际行: {ecs_row}"
                )
        else:
            with allure_step_log("步骤9: 验证实例内部配置"):
                ssh_vm.connect(mfip)
                cpu_result = ssh_vm.run("lscpu", return_rc=True)
                assert cpu_result["rc"] == 0, "[BackendAssertion] lscpu执行失败"
                assert "CPU" in cpu_result["stdout"], "[BackendAssertion] lscpu输出不含CPU信息"

                mem_result = ssh_vm.run("grep MemTotal /proc/meminfo", return_rc=True)
                assert mem_result["rc"] == 0, "[BackendAssertion] 内存信息获取失败"
                assert "MemTotal" in mem_result["stdout"], "[BackendAssertion] 内存信息输出异常"

                disk_result = ssh_vm.run("fdisk -l", return_rc=True)
                assert disk_result["rc"] == 0, "[BackendAssertion] 磁盘信息获取失败"
                assert "Disk" in disk_result["stdout"], "[BackendAssertion] fdisk输出不含磁盘信息"

                net_result = ssh_vm.run("ip a", return_rc=True)
                assert net_result["rc"] == 0, "[BackendAssertion] 网卡信息获取失败"
                assert "inet" in net_result["stdout"], "[BackendAssertion] ip a输出不含IP信息"

        _cleanup_created_resources()
