import re
import time

from sugon_web.pages.network import VpcPage
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log, logger


IMS_ACL_NAME = "ims-acl"
IMS_SECURITY_GROUP_NAME = "ims-default"
IMS_VPC_PREFIX = "ims-vpc-autotest"


def _as_vpc_page(page_obj) -> VpcPage:
    """从现有页面对象或 Playwright page 构造 VpcPage。"""
    page = getattr(page_obj, "page", page_obj)
    return VpcPage(page)


def _row_exists(vpc_page: VpcPage, submenu_name: str, row_name: str) -> bool:
    vpc_page.goto_service("虚拟私有云")
    vpc_page.goto_submenu(submenu_name)
    try:
        return vpc_page.get_row_by_name(row_name) is not None
    except Exception:
        return False


def _sg_rule_exists(rules: list[dict], direction: str, protocol: str = "所有") -> bool:
    for rule in rules:
        if rule.get("方向") != direction:
            continue
        protocol_text = rule.get("IP协议") or rule.get("协议") or ""
        if protocol in protocol_text or protocol_text in [protocol, "全部", "ALL"]:
            return True
    return False


def _ensure_ims_security_group_allow_all(vpc_page: VpcPage):
    """确保 IMS 专用安全组存在，并放通 IPv4 入/出口。"""
    if _row_exists(vpc_page, "安全组", IMS_SECURITY_GROUP_NAME):
        logger.info(f"IMS安全组 {IMS_SECURITY_GROUP_NAME} 已存在，复用")
    else:
        vpc_page.sg_create(IMS_SECURITY_GROUP_NAME, desc="IMS自动化专用安全组")

    rules = vpc_page.sg_get_all_rules(sg_name=IMS_SECURITY_GROUP_NAME)
    for direction in ["入口", "出口"]:
        if _sg_rule_exists(rules, direction):
            logger.info(f"IMS安全组 {IMS_SECURITY_GROUP_NAME} 已存在 {direction} IPv4 放通规则")
            continue
        try:
            vpc_page.sg_rule_create(
                sg_name=IMS_SECURITY_GROUP_NAME,
                protocol="所有",
                direction=direction,
                remote_type="CIDR",
                ip_version="IPv4",
                cidr="0.0.0.0/0",
                description="IMS自动化放通规则",
                from_list=True,
            )
        except AssertionError as exc:
            if "已存在" in str(exc):
                logger.warning(f"IMS安全组 {IMS_SECURITY_GROUP_NAME} {direction} IPv4 放通规则已存在，跳过: {exc}")
                continue
            raise


def _ensure_ims_acl_allow_all(vpc_page: VpcPage):
    """确保 IMS 专用 ACL 存在并启用，入/出方向均允许 IPv4 全部流量。"""
    if _row_exists(vpc_page, "网络ACL", IMS_ACL_NAME):
        logger.info(f"IMS ACL {IMS_ACL_NAME} 已存在，复用")
    else:
        vpc_page.acl_create(IMS_ACL_NAME, desc="IMS自动化专用ACL")

    try:
        acl_data = vpc_page.get_row_data(IMS_ACL_NAME)
        if acl_data and str(acl_data.get("状态", "")) == "关闭":
            vpc_page.acl_enable(IMS_ACL_NAME)
    except Exception as exc:
        logger.warning(f"检查/开启 IMS ACL {IMS_ACL_NAME} 状态失败，继续补规则: {exc}")

    for direction in ["入方向", "出方向"]:
        try:
            vpc_page.acl_rule_create(
                IMS_ACL_NAME,
                direction=direction,
                ip_version="IPv4",
                policy="允许",
                protocol="全部",
                source_ip="0.0.0.0/0",
                dest_ip="0.0.0.0/0",
                description="IMS自动化放通规则",
            )
        except Exception as exc:
            logger.warning(f"IMS ACL {IMS_ACL_NAME} 创建 {direction} 放通规则失败，可能已存在: {exc}")


def _find_reusable_ims_vpc(vpc_page: VpcPage) -> dict:
    vpc_page.goto_service("虚拟私有云")
    vpc_page.goto_submenu("虚拟私有云")
    try:
        vpc_page.search(IMS_VPC_PREFIX)
    except Exception as exc:
        logger.warning(f"搜索 IMS VPC 失败，尝试直接读取列表: {exc}")

    rows = vpc_page.page.locator(".el-table__body-wrapper:visible tbody tr").filter(has_text=IMS_VPC_PREFIX)
    if rows.count() == 0:
        return {}

    text = rows.first.inner_text()
    match = re.search(r"ims-vpc-autotest[-\w]*", text)
    if not match:
        return {}

    vpc_name = match.group(0)
    row_data = {}
    try:
        row_data = vpc_page.get_row_data(vpc_name)
    except Exception as exc:
        logger.warning(f"读取可复用 IMS VPC {vpc_name} 行数据失败，使用默认子网命名: {exc}")

    return {
        "vpc_name": vpc_name,
        "subnet_name": f"{vpc_name}-subnet",
        "cidr": row_data.get("网段") or row_data.get("CIDR") or row_data.get("IPv4网段") or "",
        "acl_name": IMS_ACL_NAME,
        "security_group": IMS_SECURITY_GROUP_NAME,
    }


def prepare_ims_network(page_obj) -> dict:
    """准备 IMS 镜像服务创建 ECS 使用的专用 VPC/ACL/安全组。"""
    vpc_page = _as_vpc_page(page_obj)
    _ensure_ims_acl_allow_all(vpc_page)
    _ensure_ims_security_group_allow_all(vpc_page)

    reusable_vpc = _find_reusable_ims_vpc(vpc_page)
    if reusable_vpc:
        logger.info(f"IMS网络前置已存在，复用: {reusable_vpc}")
        return reusable_vpc

    timestamp = time.strftime("%Y%m%d%H%M%S")
    vpc_name = f"{IMS_VPC_PREFIX}-{timestamp}"
    subnet_name = f"{vpc_name}-subnet"
    cidr = random_data("cidr")

    vpc_page.goto_service("虚拟私有云")
    vpc_page.goto_submenu("虚拟私有云")
    vpc_page.vpc_create(
        name=vpc_name,
        subnet_name=subnet_name,
        cidr=cidr,
        desc="IMS自动化专用VPC",
        subnet_desc="IMS自动化专用子网",
        network_type="Geneve",
        acl_policy=IMS_ACL_NAME,
    )
    vpc_page.assert_popup_success("创建虚拟私有云成功")
    vpc_page.assert_status(vpc_name)
    network_env = {
        "vpc_name": vpc_name,
        "subnet_name": subnet_name,
        "cidr": cidr,
        "acl_name": IMS_ACL_NAME,
        "security_group": IMS_SECURITY_GROUP_NAME,
    }
    logger.info(f"IMS网络前置创建完成: {network_env}")
    return network_env


def get_prepared_ims_network(page_obj) -> dict:
    """读取已准备好的 IMS 网络前置，未准备时给出明确失败信息。"""
    vpc_page = _as_vpc_page(page_obj)
    missing = []
    if not _row_exists(vpc_page, "网络ACL", IMS_ACL_NAME):
        missing.append(f"网络ACL {IMS_ACL_NAME}")
    if not _row_exists(vpc_page, "安全组", IMS_SECURITY_GROUP_NAME):
        missing.append(f"安全组 {IMS_SECURITY_GROUP_NAME}")

    reusable_vpc = _find_reusable_ims_vpc(vpc_page)
    if not reusable_vpc:
        missing.append(f"VPC {IMS_VPC_PREFIX}*")
    if missing:
        raise AssertionError(
            "IMS网络前置未准备完成，请先执行 test_ims_000_network_prepare.py；缺失: "
            + ", ".join(missing)
        )
    return reusable_vpc


def ims_ecs_network_config(network_env: dict) -> dict:
    """转换为 ecs_create 可使用的 network 参数。"""
    return {
        "networks": [
            {
                "network": network_env["vpc_name"],
                "subnet": network_env["subnet_name"],
            }
        ],
        "security_groups": [network_env["security_group"]],
    }
