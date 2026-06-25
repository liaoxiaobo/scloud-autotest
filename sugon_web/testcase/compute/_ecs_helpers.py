from typing import Any

from sugon_web.common.mfip_helper import MfipHelper
from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data

from .vm_fixture.metadata_collector import _build_vm_metadata


def create_labels(ecs_page, *, count=1):
    """批量创建标签并返回实际标签名列表。"""
    label_names = []
    for _ in range(count):
        name = f"label-{random_data()}"
        label_name = ecs_page.create_label(name)
        ecs_page.assert_popup_success("新建标签成功")
        label_names.append(label_name)
        logger.info(f"已创建标签: {label_name}")
    return label_names


def delete_labels(ecs_page, label_names):
    """批量删除标签，供标签类 fixture 统一清理使用。"""
    if not label_names:
        return

    ecs_page.goto_service("弹性云服务器")
    ecs_page.goto_submenu("标签")
    ecs_page.batch_delete_label(label_names)
    logger.info(f"标签清理完成: {label_names}")


def collect_vm_metadata(
    ecs_page: Any,
    ssh_host: Any,
    vm_name: str,
) -> dict[str, Any]:
    """收集指定虚机的元数据（含 ``port_id`` / ``project_id``）。

    适用于 fixture 创建的虚机以及用例中动态创建、克隆、恢复的虚机。
    调用前需确保 ``ecs_page`` 已处于 ECS 列表页（或能定位到该虚机行）。

    Args:
        ecs_page: ECS 页面对象。
        ssh_host: 已连接的 SSH 后端客户端，需支持 ``guest_show`` 方法。
        vm_name: 虚机名称。

    Returns:
        包含以下键的字典：
        - ``name`` (str): 虚机名称
        - ``id`` (str): 虚机 ID
        - ``ip`` (str): 固定 IPv4
        - ``ipv6`` (str): 固定 IPv6（如有）
        - ``public_ip`` (str): 公网 IP（如有）
        - ``host`` (str): 物理机
        - ``flavor`` (str): 规格
        - ``image`` (str): 镜像名称
        - ``project`` (str): 项目名称
        - ``network`` (str): 网络名称
        - ``subnet`` (str): 子网名称
        - ``mfip`` (str | None): MFIP（默认 None）
        - ``port_id`` (str | None): 网卡端口 ID（SSH 可用时填充）
        - ``project_id`` (str | None): 项目 ID（SSH 可用时填充）
    """
    row_data = ecs_page.get_row_data(vm_name)
    return dict(_build_vm_metadata(row_data, vm_name, ssh_host=ssh_host))


def bind_vm_mfip(
    ecs_page: Any,
    ssh_host: Any,
    browser: Any,
    config: Any,
    vm_name: str,
) -> str:
    """收集虚机元数据并在 admin 上下文中绑定 MFIP，返回分配的 MFIP 地址。

    封装 ``collect_vm_metadata`` + ``MfipHelper.bind_mfip_with_admin_context``
    的固定组合，避免在用例中重复书写。绑定后不负责 ``ssh_vm.connect``，
    由调用方按需自行连接。

    Args:
        ecs_page: ECS 页面对象，需已能定位到 ``vm_name`` 所在行。
        ssh_host: 已连接的 SSH 后端客户端，用于查询 port_id/project_id。
        browser: Playwright Browser 实例，用于创建 admin context。
        config: 测试配置对象。
        vm_name: 虚机名称。

    Returns:
        系统分配的 MFIP 地址。
    """
    meta = collect_vm_metadata(ecs_page, ssh_host, vm_name)
    return MfipHelper.bind_mfip_with_admin_context(
        browser, config, meta["port_id"],
        project_id=meta.get("project_id", "admin-inner-project"),
    )
