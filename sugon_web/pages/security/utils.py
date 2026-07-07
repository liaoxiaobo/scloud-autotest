"""安全合规模块公共工具函数。"""

from sugon_web.config.config import Config


def get_security_volume_type(stor: str = None) -> str | None:
    """根据当前存储配置返回安全合规模块应选择的云硬盘类型。

    查找优先级：
    1. ``base.yaml`` / ``env.yaml`` 中的 ``security_volume_type_map`` 配置；
    2. 内置已知映射（xbd/xstor/ceph）；
    3. 按约定自动推导为 ``{stor}-type``；
    4. 仍无法确定时返回 None，调用方应 fallback 选择第一个可用选项。

    Args:
        stor: 存储类型，默认读取 Config.get("stor")。

    Returns:
        str | None: 云硬盘类型选项文本，如 "xbd-type" / "xstor-type" / "zbs-type"。
    """
    stor_value = (stor or Config.get("stor") or "").lower().strip()
    if not stor_value:
        return None

    # 1. 配置级映射（支持环境特殊命名，无需改代码）
    type_map = Config.get("security_volume_type_map") or {}
    if stor_value in type_map:
        return type_map[stor_value]

    # 2. 内置已知映射（向后兼容）
    mapping = {
        "xbd": "xbd-type",
        "xstor": "xstor-type",
        "ceph": "ceph-type",
    }
    if stor_value in mapping:
        return mapping[stor_value]

    # 3. 按约定自动推导；若前端命名不符合 {stor}-type，请在 env.yaml 中配置
    return f"{stor_value}-type"
