import json
import re
from typing import Any

from sugon_web.pages.compute import EcsPage
from sugon_web.utils.logger import logger

from .types import VmMetadata


def _parse_vm_ip_address(ip_text: str) -> dict[str, str]:
    """解析 ECS 列表页 IP地址 列的文本。

    格式示例：
    - '10.238.88.6  固定: 10.238.88.6'
    - '10.238.88.6  固定: 10.238.88.6  公网: 172.22.1.1'
    - '10.238.88.6  固定: 10.238.88.6  2000:c003::d05  固定: 2000:c003::d05'
    - '10.238.88.6  固定: 10.238.88.6  2000:c003::d05  固定: 2000:c003::d05  公网: 172.22.1.1'
    """
    result = {"ip": "", "ipv6": "", "public_ip": ""}

    # 提取公网IP
    pub_match = re.search(r"公网:\s*(\d+\.\d+\.\d+\.\d+)", ip_text)
    if pub_match:
        result["public_ip"] = pub_match.group(1)

    # 提取所有"固定:"后面的IP地址
    fixed_ips = re.findall(r"固定:\s*([0-9a-fA-F:.]+)", ip_text)
    for ip in fixed_ips:
        if ":" in ip:
            result["ipv6"] = ip
        else:
            result["ip"] = ip

    # 兜底：如果固定标签解析失败，用正则直接提取第一个IPv4作为ip
    if not result["ip"]:
        ipv4_match = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", ip_text)
        if ipv4_match:
            result["ip"] = ipv4_match.group(1)

    return result


def _build_vm_metadata(
    row_data: dict[str, str],
    vm_name: str,
    *,
    network: str = "",
    subnet: str = "",
    ssh_host: Any = None,
) -> VmMetadata:
    """根据 ECS 列表行数据构建单台虚机元数据。

    Args:
        row_data: ``get_row_data`` 返回的行字典。
        vm_name: 虚机名称。
        network: 所属网络名称，fixture 场景使用。
        subnet: 所属子网名称，fixture 场景使用。
        ssh_host: 已连接的 SSH 后端客户端，可选；用于回填 ``port_id`` / ``project_id``。

    Returns:
        VmMetadata: 包含 IP、ID、公网 IP、宿主机、规格、镜像、项目、网络/子网及
        SSH 回填字段的虚机元数据。
    """
    ip_parsed = _parse_vm_ip_address(row_data.get("IP地址", ""))
    name_id_text = row_data.get("名称/ID", "")
    vm_id = name_id_text.split(":", 1)[1].strip() if ":" in name_id_text else ""

    metadata: VmMetadata = {
        "name": vm_name,
        "id": vm_id,
        "ip": ip_parsed["ip"],
        "ipv6": ip_parsed["ipv6"],
        "public_ip": ip_parsed["public_ip"],
        "host": row_data.get("物理机", ""),
        "flavor": row_data.get("规格", ""),
        "image": row_data.get("镜像名称", ""),
        "project": row_data.get("项目名称", ""),
        "network": network,
        "subnet": subnet,
        "mfip": None,
    }

    if ssh_host is not None and vm_id:
        try:
            guest_info = ssh_host.guest_show(vm_id)
            ip_address_raw = guest_info.get("ip_address", "{}")
            ip_data = json.loads(ip_address_raw) if ip_address_raw else {}
            port_id = ip_data.get("port_id") or guest_info.get("port_id")
            project_id = guest_info.get("project_id") or guest_info.get("project")
            if port_id:
                metadata["port_id"] = port_id
            if project_id:
                metadata["project_id"] = project_id
            logger.info(
                f"VM {vm_id} 元数据回填: port_id={port_id}, project_id={project_id}"
            )
        except Exception as exc:
            logger.warning(f"VM {vm_id} 通过 SSH 获取 port_id/project_id 失败: {exc}")

    return metadata


def _collect_vm_fixture_metadata(
    ecs_page: EcsPage,
    vm_names: list[str],
    network: str,
    subnet: str,
    ssh_host: Any = None,
) -> list[VmMetadata]:
    """收集 vm fixture 所需的虚机元数据。"""
    metadata_list: list[VmMetadata] = []
    for vm_name in vm_names:
        row_data = ecs_page.get_row_data(vm_name)
        metadata_list.append(
            _build_vm_metadata(
                row_data,
                vm_name,
                network=network,
                subnet=subnet,
                ssh_host=ssh_host,
            )
        )
    return metadata_list
