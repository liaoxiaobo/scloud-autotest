from sugon_web.utils.logger import allure_step_log


def ensure_sg_ingress_allow_all(sg_page, sg_name):
    """确保 ACL 场景使用的安全组具备基础入方向放行规则。"""
    with allure_step_log(f"前置步骤: 在安全组 {sg_name} 中放开所有入方向流量"):
        rules = sg_page.sg_get_all_rules(sg_name=sg_name)
        has_ipv4 = any(rule.get("方向", "") == "入口" and rule.get("以太网类型", "") == "IPv4" for rule in rules)
        has_ipv6 = any(rule.get("方向", "") == "入口" and rule.get("以太网类型", "") == "IPv6" for rule in rules)

        if not has_ipv4:
            sg_page.sg_rule_create(
                sg_name=sg_name,
                direction="入口",
                protocol="所有",
                ip_version="IPv4",
                remote_type="CIDR",
                from_list=False,
                detail_mode=True,
            )
        if not has_ipv6:
            sg_page.sg_rule_create(
                sg_name=sg_name,
                direction="入口",
                protocol="所有",
                ip_version="IPv6",
                remote_type="CIDR",
                from_list=False,
                detail_mode=True,
            )


def _normalize_acl_vm_list(vm_data):
    """将 vm fixture 返回值标准化为列表。"""
    return vm_data if isinstance(vm_data, list) else [vm_data]


def _get_acl_subnet_pair(vpc_data):
    """提取 ACL 场景要求的主子网和附加子网信息。"""
    extra_subnets = vpc_data.get("extra_subnets", [])
    if not extra_subnets:
        raise ValueError("ACL 场景要求 vpc fixture 至少提供一个额外子网")

    return vpc_data["subnet_name"], extra_subnets[0]


def _tag_acl_vms(vm_list, sub1_name, sub2_name):
    """按子网为虚机打上 ACL 场景角色标签。"""
    sub1_vms = [item for item in vm_list if item["subnet"] == sub1_name]
    sub2_vms = [item for item in vm_list if item["subnet"] == sub2_name]
    if len(sub1_vms) + len(sub2_vms) != len(vm_list):
        unknown_vms = [item["name"] for item in vm_list if item["subnet"] not in {sub1_name, sub2_name}]
        raise ValueError(f"ACL 场景发现未知子网虚机: {unknown_vms}")

    tagged_vms = []
    for index, item in enumerate(sub1_vms):
        tag = "A" if len(sub1_vms) == 1 else f"A-{index}"
        tagged_vms.append({"tag": tag, **item})
    for index, item in enumerate(sub2_vms):
        tag = "B" if len(sub2_vms) == 1 else f"B-{index}"
        tagged_vms.append({"tag": tag, **item})
    return tagged_vms


def build_acl_env(acl_name, vpc_data, vm_data):
    """组装 ACL 测试场景所需的环境数据。"""
    vm_list = _normalize_acl_vm_list(vm_data)
    sub1_name, sub2_data = _get_acl_subnet_pair(vpc_data)

    return {
        "acl_name": acl_name,
        "vpc_name": vpc_data["name"],
        "sub1_name": sub1_name,
        "sub2_name": sub2_data["name"],
        "cidr1": vpc_data["cidr"],
        "cidr2": sub2_data["cidr"],
        "vms": _tag_acl_vms(vm_list, sub1_name, sub2_data["name"]),
    }


def build_acl_pair_env(acl_name, vpc_data, vm_sg_binding, sg_page):
    """组装带安全组前置的 ACL 双子网场景环境数据。"""
    sg_name = vm_sg_binding["sg"]
    ensure_sg_ingress_allow_all(sg_page, sg_name)

    env = build_acl_env(acl_name, vpc_data, vm_sg_binding["vm"])
    env["sg_name"] = sg_name
    return env
