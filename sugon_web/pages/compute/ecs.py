import os
import random
import re
import time
from pathlib import Path
from time import sleep
from typing import Any, NotRequired, TypedDict
import allure
import pytest
from playwright.sync_api import expect


from sugon_web.pages.ops import OpsPage
from sugon_web.common.base import submenu
from sugon_web.utils.logger import logger
from sugon_web.utils.util import random_data
from sugon_web.config.config import Config


# ECS 创建流程的结构化配置定义，用于约束 basic/storage/network/manage/advanced
# 五个配置分组的字段类型，便于调用方按统一结构传参。
EcsBasicConfig = TypedDict(
    "EcsBasicConfig",
    {
        "name": str,
        "count": int,
        "cluster": str,
        "host": str,
        "flavor": dict[str, Any],
        "labels": list[str],
    },
    total=False,
)

# 单块数据盘配置，描述卷类型、容量和创建数量。
EcsStorageDiskConfig = TypedDict(
    "EcsStorageDiskConfig",
    {
        "vol_type": str,
        "size": str,
        "count": str,
    },
    total=False,
)

# 镜像来源配置，统一描述镜像/ISO/快照等来源信息。
EcsImageConfig = TypedDict(
    "EcsImageConfig",
    {
        "source": str,
        "name": str,
        "os_version": str,
    },
    total=False,
)

# 存储分组配置，包含存储池、镜像、系统盘和数据盘列表。
EcsStorageConfig = TypedDict(
    "EcsStorageConfig",
    {
        "storage_pool": str,
        "encryption_key": str,
        "image": EcsImageConfig,
        "system_disk": int,
        "data_disks": list[EcsStorageDiskConfig],
    },
    total=False,
)

# 单张网卡配置，描述要绑定的网络与子网。
EcsNetworkItemConfig = TypedDict(
    "EcsNetworkItemConfig",
    {
        "network": str,
        "subnet": str,
    },
    total=False,
)

# 网络分组配置，支持多网卡、安全组以及 IPv6 分配选项。
EcsNetworkConfig = TypedDict(
    "EcsNetworkConfig",
    {
        "networks": list[EcsNetworkItemConfig],
        "security_groups": list[str],
        "enable_ipv6": bool,
    },
    total=False,
)

# 管理分组配置，定义登录方式、登录凭据和 VNC 密码。
EcsManageConfig = TypedDict(
    "EcsManageConfig",
    {
        "login_type": str,
        "login_pwd": str,
        "login_key": str,
        "vnc_pwd": str,
    },
    total=False,
)

# 高级分组配置，汇总亲和组、QoS、注入、主机名等高级能力。
EcsAdvancedConfig = TypedDict(
    "EcsAdvancedConfig",
    {
        "affinity": list[str],
        "acceleration": bool,
        "priority": str,
        "ceiling": str,
        "injection": list[str],
        "hostname": str,
        "vnc_type": str,
        "sound_type": str
    },
    total=False,
)

# ECS 标准创建请求，统一聚合五个分组配置供页面填写流程消费。
EcsCreateRequest = TypedDict(
    "EcsCreateRequest",
    {
        "basic": EcsBasicConfig,
        "storage": EcsStorageConfig,
        "network": EcsNetworkConfig,
        "manage": EcsManageConfig,
        "advanced": EcsAdvancedConfig,
    },
    total=False,
)

def _config_get(config: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    """按顺序读取配置键，兼容新旧字段名。"""
    if not config:
        return default
    for key in keys:
        if key in config and config[key] not in (None,):
            return config[key]
    return default


def _validate_section_config(section_name: str, config: dict[str, Any] | None) -> dict[str, Any]:
    """校验单个配置分组是否为字典类型。"""
    if config is None:
        return {}
    if not isinstance(config, dict):
        raise TypeError(f"{section_name!r} must be a dict, got {type(config).__name__}")
    return dict(config)


def _normalize_standard_ecs_create_request(
    basic: EcsBasicConfig | None,
    storage: EcsStorageConfig | None,
    network: EcsNetworkConfig | None,
    manage: EcsManageConfig | None,
    advanced: EcsAdvancedConfig | None,
) -> EcsCreateRequest:
    """规范化标准分组方式的 ECS 创建请求。"""
    # 标准调用方式下，分别校验各分组配置，统一转成可安全读写的 dict。
    return {
        "basic": _validate_section_config("basic", basic),
        "storage": _validate_section_config("storage", storage),
        "network": _validate_section_config("network", network),
        "manage": _validate_section_config("manage", manage),
        "advanced": _validate_section_config("advanced", advanced),
    }


def _normalize_ecs_create_request(
    basic: EcsBasicConfig | None = None,
    storage: EcsStorageConfig | None = None,
    network: EcsNetworkConfig | None = None,
    manage: EcsManageConfig | None = None,
    advanced: EcsAdvancedConfig | None = None,
) -> EcsCreateRequest:
    """规范化 ECS 创建入参。"""
    return _normalize_standard_ecs_create_request(
        basic,
        storage,
        network,
        manage,
        advanced,
    )


class EcsPageBase(OpsPage):
    @submenu("弹性云服务器")
    def ecs_create(
        self,
        basic: EcsBasicConfig | None = None,
        storage: EcsStorageConfig | None = None,
        network: EcsNetworkConfig | None = None,
        manage: EcsManageConfig | None = None,
        advanced: EcsAdvancedConfig | None = None,
    ) -> dict[str, Any]:
        """创建云服务器

        仅支持分组字典传参:
        ecs_create(basic={}, storage={}, network={}, manage={}, advanced={})
        """
        request = _normalize_ecs_create_request(
            basic=basic,
            storage=storage,
            network=network,
            manage=manage,
            advanced=advanced,
        )

        # 点击创建按钮
        self.btn_create.click()
        # 填写基本信息
        basic_info = self._basic_info(request["basic"])
        # 填写存储信息
        self._storage_info(request["storage"])
        # 填写网络信息
        self._network_info(request["network"])
        # 填写管理信息
        self._manage_info(request["manage"])
        # 填写高级配置
        self._advanced_info(request["advanced"])

        # 点击创建按钮
        self.get_by_text("立即创建").click()
        logger.info(f"云服务器创建请求已提交: {basic_info.get('name')}，数量: {basic_info.get('count')}")
        return basic_info

    def _basic_info(self, basic):
        """填写弹性云服务器基本信息
        Args:
            basic: 基本配置信息
                {
                "count": 1,
                "cluster": "Autotest",
                "host": "master02",
                "flavor": {"base": "ecs.m6.xlarge"}
                "flavor": {"custom": {"cpu": "2", "mem": "4"}}
                }
        """
        if basic:
            logger.info(f"basic信息: {basic}")
            name = _config_get(basic, "name", default=random_data('string', 4))
            count = _config_get(basic, "count", default=1)
        else:
            name = random_data('string', 4)
            count = 1
        # 填写名称
        self.get_by_role("textbox", name="请输入名称").first.fill(name)

        # 设置创建数量（如果大于1）
        if count > 1:
            self.get_by_role("spinbutton").first.fill(str(count))

        # 选择规格
        flavor_info = _config_get(basic, "flavor", default={"base": "ecs.c6.Autotest"})
        self._select_flavor(flavor_info)

        # 选择集群
        cluster_name = _config_get(basic, "cluster", default="Autotest")
        self._select_cluster(cluster_name)

        # 选择物理机
        host = _config_get(basic, "host", default="")
        if host:
            self._select_physical_host(host)

        # 选择标签
        labels = _config_get(basic, "labels", default=[])
        if labels:
            self._select_label(labels)
        return {"name": name, "count": count}

    def _storage_info(self, storage):
        """填写弹性云服务器存储配置
        Args:
            storage: 基本配置信息
                {
                "storage_pool": xstor/usan,
                "encryption_key": "UUID",
                "image":{
                    source: "镜像" / "空启动" / "快照" / "ISO"
                    name: "镜像名称" / "快照名称" / "ISO名称"
                    os_version: 操作系统版本，默认为"centos7.9"
                    },
                "system_disk": 25,
                "data_disks": [
                    {"vol_type": "ceph-type", "size": "20", "count": "1"},
                    {"vol_type": "usan-type", "size": "20", "count": "1"},
                    ]
                }
        """
        if storage:
            logger.info(f"storage信息: {storage}")
        # 选择存储池
        storage_pool = _config_get(storage, "storage_pool", default=self.storage_pool)
        self._select_storage_pool(storage_pool)

        # 选择密钥
        encryption_key = _config_get(storage, "encryption_key", default="")
        if encryption_key and self.storage_pool in ["xstor-test", "usan-test"]:
            self._enable_encryption(encryption_key)

        # 选择镜像
        image_info = _config_get(storage, "image", default={"source": "镜像", "name": "", "os_version": "centos7.9"})
        self._select_image(image_info)

        # 设置系统盘大小（云硬盘来源时不需要设置）
        image_source = _config_get(image_info, "source", default="镜像")
        if image_source != "云硬盘":
            size = _config_get(storage, "system_disk", default=25)
            self._set_sys_volume(size)

        # 设置数据盘
        data_disks = _config_get(storage, "data_disks", default=[])
        self._set_data_volumes(data_disks)

    def _network_info(self, network):
        """填写弹性云服务器网络配置

        Args:
            network: 网络配置字典，包含networks列表
        """
        if network:
            logger.info(f"network信息: {network}")
        networks = network.get("networks") if network and network.get("networks") else [{"network": "Autotest","subnet": "Autotest(10"}]

        for i, net_config in enumerate(networks):
            if i == 0:
                # 第一个网卡直接选择
                self._select_single_network(net_config)
            else:
                # 后续网卡点击"添加网卡"后选择
                self.get_by_text("添加网卡").click()
                self._select_single_network(net_config)
        security_groups = _config_get(network, "security_groups", default=[])
        if security_groups:
            self._select_security_group(security_groups)

        # 选择分配IPv6
        if network and network.get("enable_ipv6"):
            self.get_by_role("textbox", name="请选择是否分配IPv6地址").click()
            self.get_by_text("自动分配IPv6地址").nth(2).click()
            logger.info("已勾选自动分配IPv6地址")
    def _manage_info(self, manage):
        """填写管理配置

        Args:
            manage: 管理配置字典
        """
        # 选择登录方式
        if manage:
            logger.info(f"manage信息: {manage}")
            login_type = manage.get("login_type")

            login_pwd = manage.get("login_pwd")
            login_key = manage.get("login_key")
            vnc_pwd = manage.get("vnc_pwd")
        else:
            login_type = "密码登录"
            login_pwd = "admin1234@sugon"
            vnc_pwd = "sugon@20"

        self.get_by_role("radio", name=login_type).click()
        if login_type == "密钥对登录":
            if not login_key:
                raise ValueError("密钥对登录需要提供login_key参数")
            self._set_login_key(login_key)
        elif login_type == "密码+密钥对":
            if not login_key or not login_pwd:
                raise ValueError("密码+密钥对登录需要同时提供login_key和login_pwd参数")
            self._set_login_key(login_key)
            self._set_login_pwd(login_pwd)
        else:
            if not login_pwd:
                raise ValueError("密码登录需要提供login_pwd参数")
            self._set_login_pwd(login_pwd)
        self._set_vnc_pwd(vnc_pwd)
        logger.info(f"登录方式: {login_type} 设置成功")

    def _advanced_info(self, advanced):
        """填写高级配置
        Args:
            advanced: 高级配置字典
        """
        if advanced:
            logger.info(f"advanced信息: {advanced}")
        # 设置CPU亲和组
        affinity = advanced.get("affinity") if advanced and advanced.get("affinity") else None
        if affinity:

            self._set_cpu_affinity(affinity)
            logger.info(f"亲和组: {affinity} 设置成功")

        # 设置硬件密码加速
        acceleration = advanced.get("acceleration") if advanced and advanced.get("acceleration") else None
        if acceleration:
            self._set_hardware_acceleration()
            logger.info(f"硬件密码加速: {acceleration} 设置成功")

        # 设置CPU QoS优先级
        qos_priority = advanced.get("priority") if advanced and advanced.get("priority") else None
        if qos_priority:
            self._set_qos_priority(qos_priority)
            logger.info(f"CPU QoS优先级: {qos_priority} 设置成功")

        # 设置CPU QoS 上限
        qos_ceiling = advanced.get("ceiling") if advanced and advanced.get("ceiling") else None
        if qos_ceiling:
            self._set_qos_ceiling(qos_ceiling)
            logger.info(f"CPU QoS 上限: {qos_ceiling} 设置成功")

        # 设置代码注入
        injection = advanced.get("injection") if advanced and advanced.get("injection") else []
        if injection:
            self._set_injection(injection)

        # 设置主机名
        hostname = advanced.get("hostname") if advanced and advanced.get("hostname") else None
        if hostname:
            self._set_hostname(hostname)
            logger.info(f"已设置主机名: {hostname}")

        # 设置VNC显卡类型
        vnc_type = advanced.get("vnc_type") if advanced and advanced.get("vnc_type") else None
        if vnc_type:
            self._set_vnc_type(vnc_type)

        # 设置声卡类型
        sound_type = None
        if advanced:
            sound_type = advanced.get("sound_type")
        if sound_type:
            self._set_sound_type(sound_type)
            logger.info(f"已设置声卡类型为: {sound_type}")

    def _select_flavor(self, flavor_info: dict):
        """选择规格
        Args:
            flavor_info: 规格信息
            {"base": "ecs.c6.Autotest"}
            {"custom": {"cpu": "2", "mem": "4"}}
        """
        # 根据规格类型选择不同的处理方式
        flavor_type = flavor_info.keys()
        logger.info(f"规格: {list(flavor_type)[0]}")
        if "custom" in flavor_type:
            # 选择自定义规格
            self.get_by_role("radio", name="自定义规格").click()
            flavor = _config_get(flavor_info, "custom", default={})
            # 填写CPU和内存
            cpu = _config_get(flavor, "cpu", default="")
            mem = _config_get(flavor, "mem", default="")
            logger.info(f"CPU: {cpu}, 内存: {mem}")
            self.locator("div:nth-child(4) > .el-form-item__content > .el-input > .el-input__inner").fill(cpu)
            self.locator("div:nth-child(5) > .el-form-item__content > .el-input > .el-input__inner").fill(mem)
        else:
            # 选择基础规格
            self.get_by_role("radio", name="基础规格").click()
            # 点击选择计算规格按钮
            self.get_by_text("选择计算规格").first.click()

            # 搜索选择规格
            flavor = _config_get(flavor_info, "base")
            flavor_type = flavor.split(".")[1][0]

            self.search(flavor)
            if flavor_type == "c":
                finally_type = "计算型"
                self.get_by_text(finally_type).click()
            elif flavor_type == "m":
                finally_type = "内存型"
                self.get_by_text(finally_type).click()
            elif flavor_type == "s":
                finally_type = "通用型"
                self.get_by_text(finally_type).click()
            else:
                logger.error(f"未知的规格类型: {flavor}")
            logger.info(f"规格类型分类: {finally_type}")
            # 选择指定规格
            self.get_by_role("row").filter(has_text=re.compile(rf"{re.escape(flavor)}")).get_by_role("radio").first.click()

            # 确认选择
            self.get_by_role("dialog").get_by_text("确定").click()
            logger.info(f"已选择规格类型: {flavor}")


    def _select_cluster(self, cluster_name):
        """选择集群

        Args:
            cluster_name: 集群名称，默认为"Autotest"
        """
        self.get_by_role("textbox", name="请选择集群").click()
        self.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(cluster_name)}$")).click()
        self.logger.info(f"已选择集群: {cluster_name}")

    def _select_physical_host(self, host):
        """选择物理机

        Args:
            host: 物理机名称
        """
        self.get_by_text("选择物理机").first.click()
        self.get_by_placeholder("请输入搜索内容").fill(host)
        self.get_by_role("dialog").get_by_text("搜索").click()
        try:
            self.get_by_role("radio", name=f"{host}.cloud.local").click()
        except:
            raise Exception(f"未找到物理机: {host} 或 未启用")
        self.get_by_role("dialog").get_by_text("确定").click()
        self.logger.info(f"已选择物理机: {host}")

    def _select_label(self, labels: list):
        """选择标签

        Args:
            labels: 标签列表
        """
        self.get_by_text("标签设置").first.click()
        self.select_rows_by_names(labels)
        self.get_by_role("dialog").get_by_text("确定").click()
        self.logger.info(f"已选择物理机: {labels}")

    def _select_storage_pool(self, image_name):
        """选择存储池"""
        image_name = image_name or self.storage_pool

        # 选择存储池
        self.get_by_role("textbox", name="请选择", exact=True).nth(2).click()
        self.page.wait_for_load_state("networkidle")
        self.get_by_text(self.storage_pool, exact=True).click()
        logger.info(f"已选择存储池: {self.storage_pool}")

    def _enable_encryption(self, encryption_key):
        """启用加密并选择密钥

        Args:
            encryption_key: 加密密钥ID
        """
        # 打开加密开关
        self.page.locator("form div").filter(has_text="加密").get_by_role("switch").locator("span").click()

        # 选择密钥
        self.get_by_text("选择密钥").first.click()

        # 选择指定的密钥
        self.get_by_role("radio", name=encryption_key).click()

        # 确认密钥选择
        self.page.locator("section").get_by_text("确定").first.click()

        # 等待页面加载完成
        self.page.wait_for_timeout(1000)

    def _select_image(self, image_info):
        """选择镜像，支持多种来源方式
        Args:
            image_info: {
                source: "镜像" / "空启动" / "快照" / "ISO" / "云硬盘"
                name: "镜像名称" / "快照名称" / "ISO名称"
                os_version: 操作系统版本，默认为"centos7.9"
            }
        """
        image_name = _config_get(image_info, "name", default="") or self.storage_pool
        image_source = _config_get(image_info, "source", default="镜像")
        os_version = _config_get(image_info, "os_version")
        logger.info(f"开始选择镜像: image_source={image_source}, image_name={image_name}, os={os_version}")

        try:
            # 选择镜像来源
            self.get_by_role("textbox", name="请选择", exact=True).nth(3).click()
            self.locator("li").filter(has_text=re.compile(rf"^{image_source}$")).click()
            logger.info(f"已选择来源: {image_source}")

            # 根据不同来源执行不同的选择逻辑
            if image_source == "镜像":
                self._select_from_pool_image(image_name, os_version)
            elif image_source == "快照":
                self._select_snapshot_image(image_name)
            elif image_source == "ISO":
                self._select_iso_image(image_name)
            elif image_source == "云硬盘":
                self._select_cloud_disk_image(image_name)
            elif image_source == "空启动":
                pass
            else:
                logger.warning(f"不支持的镜像来源: {image_source}，使用默认镜像方式")

        except Exception as e:
            logger.error(f"选择镜像失败: {str(e)}")
            raise e

    def _select_from_pool_image(self, image_name, os_version):
        """来源选择 镜像"""
        logger.info("使用存储池镜像")
        # image_name = image_name or self.storage_pool

        # 选择操作系统版本
        self.get_by_role("textbox", name="请选择操作系统版本").click()
        self.get_by_text(os_version).click()

        # 选择64位
        self.get_by_role("textbox", name="请选择操作系统位数").click()
        self.get_by_role("listitem").filter(has_text=re.compile(r"^64位$")).click()

        # 选择具体镜像
        self.get_by_role("textbox", name="请选择镜像").click()
        expect(self.get_by_title(image_name, exact=True)).to_be_visible()
        self.get_by_title(image_name, exact=True).click()
        logger.info(f"已选择存储池镜像: {image_name}")

    def _select_snapshot_image(self, snapshot_name):
        """来源选择 快照"""
        logger.info(f"使用快照: {snapshot_name}")

        # 选择快照
        if snapshot_name:
            # 定位并选择快照行
            self.get_by_text("选择快照").first.click()
            row = self.get_row_by_name(snapshot_name)
            row.get_by_role("radio").click()
            self.dialog_confirm.click()
            logger.info(f"已选择快照: {snapshot_name}")

    def _select_iso_image(self, iso_name, **kwargs):
        """来源选择 ISO"""
        logger.info(f"使用ISO镜像: {iso_name}")

        if iso_name:
            # 定位并选择ISO行
            self.get_by_text("选择ISO").first.click()
            self.get_by_role("dialog").get_by_text("重置").click() # 重置一下，避免hover的tips遮挡选择
            row = self.get_row_by_name(iso_name)
            row.get_by_role("radio").click()
            self.dialog_confirm.click()
            logger.info(f"已选择ISO镜像: {iso_name}")

    def _select_cloud_disk_image(self, cloud_disk_name):
        """来源选择 云硬盘

        Args:
            cloud_disk_name: 云硬盘名称
        """
        # 点击"选择云硬盘"按钮
        self.get_by_text("选择云硬盘").first.click()

        if cloud_disk_name:
            row = self.get_row_by_name(cloud_disk_name)
            row.get_by_role("radio").click()
            # 点击确定按钮
            self.dialog_confirm.click()
            logger.info(f"已选择云硬盘: {cloud_disk_name}")

    def _set_sys_volume(self, size, mode="厚置备"):
        """系统盘配置"""
        if re.search(r'xbd|ustor', self.storage_pool):
            self.get_by_role("textbox", name="请选择", exact=True).nth(4).click()
            self.get_by_text(mode).click()
        self.get_by_role("spinbutton").nth(1).fill(str(size))

    def _set_data_volumes(self, data_disks):
        """数据盘配置

        Args:
            data_disks: 数据盘配置列表
                [
                    {"vol_type": "xstor-type", "size": 120, "count": 1},
                    {"vol_type": "thin-provision", "size": 20, "count": 2}
                ]
        """
        for idx, vol in enumerate(data_disks, start=1):
            # 点击添加数据盘
            self.get_by_text("添加数据盘").click()

            vol_type = vol.get("vol_type")
            vol_size = vol.get("size")
            vol_count = vol.get("count", 1)

            # 定位当前添加的数据盘行（最后一个数据盘行）
            data_rows = self.get_by_role("row", name=re.compile(r"数据盘"))
            # data_rows = self.locator(".el-form-item__content .el-table__row")

            current_row = data_rows.nth(-1)  # 获取最后一行（当前行）
            logger.info(f"当前是第 {idx} 个数据盘")

            # 选择云硬盘类型
            # current_row.get_by_role("placeholder", name="请选择类型").click()
            loc = current_row.locator(".el-select").first
            # loc.scroll_into_view_if_needed()

            # loc.click()
            # loc.click(force=True)
            loc.evaluate("el => el.click()")

            # 等待下拉列表出现并定位选项
            dropdown_list = self.page.locator(".el-select-dropdown:visible .el-select-dropdown__item")
            dropdown_list.first.wait_for(state="visible", timeout=3000)
            # 查找并选择对应的云硬盘类型
            logger.info(f"查找数据盘类型: {vol_type}")
            items_count = dropdown_list.count()
            found = False
            for i in range(items_count):
                try:
                    if vol_type in dropdown_list.nth(i).inner_text(timeout=1000):
                        logger.info(f"找到并点击数据盘类型: {vol_type}")
                        dropdown_list.nth(i).click()
                        found = True
                        break
                except Exception as e:
                    logger.warning(f"获取选项 {i} 文本失败: {e}")
                    continue
            if not found:
                error_msg = f"未找到匹配的数据盘类型: {vol_type}"
                raise AssertionError(error_msg)

            # 设置数据盘大小 - 使用多种定位方式
            self.get_by_role("spinbutton").nth(idx*2).fill(vol_size)
            self.get_by_role("spinbutton").nth(idx*2+1).fill(vol_count)

            logger.info(f"设置数据盘: 类型={vol_type}, 大小={vol_size}GiB, 数量={vol_count}")

    def _select_single_network(self, net_config):
        """选择单个网卡配置

        Args:
            net_config: 网卡配置字典
                - network: 网络名称
                - subnet: 子网名称
        """
        network_name = net_config.get("network")
        subnet_name = net_config.get("subnet")

        # 选择网络
        self.get_by_role("textbox", name="请选择网络").click()
        self.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(network_name)}$")).click()
        logger.info(f"选择网络: {network_name}")

        # 选择子网
        self.get_by_role("textbox", name="请选择子网").click()
        self.get_by_role("listitem").filter(has_text=re.compile(rf"{re.escape(subnet_name)}")).locator("span").click()
        logger.info(f"选择子网: {subnet_name}")

    def _select_security_group(self, security_group):
        if security_group:
            self.locator("div").filter(has_text=re.compile(r"^default$")).locator("i").click()
            for group in security_group:
                self.locator(".el-select__input").first.click()
                self.locator("li").filter(has_text=group).click()
            self.page.keyboard.press("Escape") # 收起下拉列表
            logger.info(f"选择安全组: {security_group}")

    def _set_login_pwd(self, login_pwd):
        """设置登录密码"""
        self.get_by_role("textbox", name="请输入密码").fill(login_pwd)
        self.locator("div").filter(has_text=re.compile(r"^确认登录密码$")).get_by_role("textbox").fill(login_pwd)

    def _set_login_key(self, login_key):
        """设置密钥对"""
        self.get_by_placeholder("请选择", exact=True).nth(4).click()
        self.get_by_text(login_key, exact=True).click()

    def _set_vnc_pwd(self, vnc_pwd):
        """设置vnc密码"""
        self.get_by_role("textbox", name="VNC密码最长为8位").fill(vnc_pwd)
        self.locator("div").filter(has_text=re.compile(r"^确认VNC密码$")).get_by_role("textbox").fill(vnc_pwd)

    def _set_cpu_affinity(self, affinities: list):
        """设置CPU亲和组"""
        self.get_by_placeholder("请选择亲和组").locator("xpath=../preceding-sibling::div[1]").click()
        for affinity in affinities:
            self.get_by_text(affinity).click()
        self.get_by_title("刷新").nth(2).click() # 刷新, 收起下拉项

    def _set_hardware_acceleration(self):
        """设置硬件加速"""
        self.locator("span").filter(has_text="硬件密码加速").locator("xpath=../following-sibling::div/div").click()

    def _set_qos_priority(self, priority):
        """设置QoS优先级

        Args:
            priority: 优先级，可选值：低/中/高
        """
        # 点击相应的优先级选项
        self.locator("label").filter(has_text=priority).click()
        logger.info(f"已设置QoS优先级为: {priority}")

    def _set_qos_ceiling(self, ceiling):
        """设置CPU权重

        Args:
            ceiling: CPU权重值，如 "0.8"
        """
        # 定位第三个spinbutton并输入权重值
        self.get_by_role("spinbutton").nth(2).fill(str(ceiling))
        logger.info(f"已设置CPU QoS上限为: {ceiling}")


    def _set_injection(self, injection):
        """设置注入模式

        Args:
            injection: 注入模式，可选值：
                云监控: 默认选中
                云安全
        """
        # 先取消勾选所有注入模式（清空默认选择）
        all_modes = ["云监控", "云安全"]
        for mode in all_modes:
            loc = self.locator("label").filter(has_text=mode)
            if loc.is_checked():
                loc.click()  # 取消勾选

        for mode in injection:
            if mode in ["云监控", "云安全"]:
                loc = self.locator("label").filter(has_text=mode)
                if not loc.is_checked():
                    loc.click()
            else:
                raise AssertionError(f"未知的注入模式: {mode}")
        logger.info(f"已设置注入模式为: {injection}")

    def _set_hostname(self, name):
        """设置实例名称

        Args:
            name: 实例名称
        """
        # 定位第二个名称输入框
        self.get_by_placeholder("请输入名称").nth(1).fill(name)
        logger.info(f"已设置主机名为: {name}")

    def _set_vnc_type(self, vnc_type):
        """设置VNC显卡类型

        Args:
            vnc_type: VNC显卡类型，如 "VGA"
        """
        self.get_by_placeholder("请选择VNC显卡类型").click()
        self.locator("li").filter(has_text=vnc_type).click()
        logger.info(f"已设置VNC显卡类型为: {vnc_type}")

    def vm_pre_data(self, ssh_vm, vols: dict):
        """虚机预置数据"""
        vols = vols or {}
        md5_dict = {}
        image_path = "/offlinePackage/image_download/support-fsagent/"

        # 通过 lsblk 判断系统盘和数据盘, 获取父设备名，排除分区号
        # 解决 guest os 内核内的行为，os 内部枚举设备的时候具有不稳定性
        sys_disk = ssh_vm.run("lsblk -no PKNAME,MOUNTPOINT | grep -w '/' | awk '{print $1}'", check_rc=True).strip()
        if not sys_disk:
            # 如果没找到父设备名，根分区可能直接在磁盘上
            sys_disk = ssh_vm.run("lsblk -no NAME,MOUNTPOINT | grep -w '/' | awk '{print $1}'", check_rc=True).strip()
        logger.info(f"识别到系统盘: {sys_disk}")

        # 统一处理所有盘 (系统盘 + 数据盘)
        actual_disks_output = ssh_vm.run(r"""lsblk -dn -o NAME,TYPE | awk '$2 == "disk" {print $1}'""", check_rc=True)
        actual_disks = list(dict.fromkeys(disk.strip() for disk in actual_disks_output.splitlines() if disk.strip()))
        if sys_disk and sys_disk not in actual_disks:
            actual_disks.insert(0, sys_disk)

        if actual_disks:
            target_vols = [sys_disk] + [vol for vol in actual_disks if vol != sys_disk]
        else:
            target_vols = [sys_disk] + sorted(vol for vol in vols.keys() if vol != sys_disk)

        if set(vols.keys()) != set(target_vols):
            logger.warning(f"vols磁盘列表与虚机实际磁盘不一致，vols={sorted(vols.keys())}, actual={target_vols}")

        root_file = "IMAGE_CDB_20220910.qcow2"
        root_dir = "/cbr_test_root"

        data_vols = [vol for vol in target_vols if vol != sys_disk]
        for vol_name in target_vols:
            if vol_name == sys_disk:
                # 系统盘: 直接写数据到预定目录，不用分区/格式化/挂载
                curr_file = root_file
                curr_dir = root_dir
                ssh_vm.run(f"mkdir -p {curr_dir}", check_rc=True)
                logger.info(f"处理系统盘: {vol_name}, 写入文件: {curr_file}")
            else:
                # 数据盘: 需要格式化、挂载后再写数据
                vol_dir = f"/cbr_test_{vol_name}"
                # 根据盘名选择对应的镜像文件
                curr_file = "CentOS-7-aarch64-Minimal-2009.iso" if vol_name == data_vols[0] else "cn_windows_7_professional_x64_dvd_x15-65791.iso"
                curr_dir = vol_dir
                logger.info(f"处理数据盘: {vol_name}, 写入文件: {curr_file}")

                # 格式化并挂载数据盘
                ssh_vm.run(f"mkfs.xfs -f /dev/{vol_name}", check_rc=True)
                ssh_vm.run(f"mkdir -p {curr_dir}", check_rc=True)
                ssh_vm.run(f"mount /dev/{vol_name} {curr_dir}", check_rc=True)

                # 写入开机自启动
                uuid = ssh_vm.run(rf"""blkid|grep /dev/{vol_name}|awk -F" " '{{print $2}}'|awk -F'"' '{{print $2}}'""", check_rc=True).strip()
                ssh_vm.run(f"""echo "UUID={uuid} {curr_dir} xfs defaults 0 0" >> /etc/fstab""", check_rc=True)

            # 统一在目标目录下建立路径并写入数据
            wget_cmd = f"cd {curr_dir} && curl -O --max-time 300 {Config.get('image_source')}{image_path}{curr_file}"
            ssh_vm.run(wget_cmd, timeout=180, get_pty=False, check_rc=True)
            ssh_vm.run(f"cd {curr_dir} && sync && md5sum {curr_file} > cbr_test_{vol_name}_md5.txt", check_rc=True)

            # 获取 MD5 值并存入字典
            md5_val = ssh_vm.run(f"cd {curr_dir} && md5sum {curr_file} | awk '{{print $1}}'", check_rc=True)
            key = 'root' if vol_name == sys_disk else vol_name
            md5_dict[key] = {
                'md5': md5_val.strip(),
                'dir': curr_dir,
                'file': curr_file
            }

        return md5_dict


    def ecs_batch_bind_labels(self, names: list, label_names: list):
        logger.info(f"绑定标签{label_names}到云服务器{names}")
        self.select_rows_by_names(names)
        self.get_by_role("button", name="更多操作").click()
        self._click_batch_operation_option("批量标签设置")
        self.get_by_placeholder("请选择标签").click()
        for label_name in label_names:
            self.locator("li").filter(has_text=label_name).click()
        self.locator("form i").nth(3).click()
        self.dialog_confirm.click()
        logger.info(f"标签{label_names}绑定到云服务器{names}成功")

    @submenu("弹性云服务器")
    def ecs_remove(self, names):
        """回收云服务器资源，支持单个和批量操作

        Args:
            names: 云服务器名称（字符串）或云服务器名称列表（列表）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击更多操作按钮
            self.get_by_role("button", name="更多操作 ").click()

            # 点击批量删除选项
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_action(names, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成


    @submenu("弹性云服务器")
    def ecs_edit(self, name: str, newname: str):
        """修改指定云服务器名称
        Args:
            name: 云服务器名称
            newname: 新的云服务器名称
        """
        self.click_action(name, "编辑")
        self.get_by_role("textbox", name="请输入实例名称").fill(newname)
        self.dialog_confirm.click()
        logger.info(f"操作完成云服务器{name}: 编辑修改为{newname}")

    @submenu("弹性云服务器")
    def ecs_vnc(self, name: str, vncpwd: str = "sugon@20"):
        """登录VNC
        Args：
            name: 云服务器名称
            password: VNC登录密码
        """
        logger.info(f"云服务器{name}：登录VNC")

        # 使用 trigger_action 参数，确保 expect_page 在点击前开始监听
        with self.new_tab_context(trigger_action=lambda: self.click_action(name, "登录")) as new_page:
            # 输入VNC密码并登录
            try:
                new_page.locator("#app iframe").content_frame.get_by_label("Password:").fill(vncpwd)
            except:
                new_page.locator("#app iframe").content_frame.get_by_label("密码：").fill(vncpwd)
            new_page.locator("#app iframe").content_frame.get_by_role("button", name="确认").click()
            loc = new_page.locator("#app iframe").content_frame.locator("canvas")
            expect(loc).to_be_visible(timeout=30000)
            # 保存截图到文件
            sleep(5)
            screenshot_dir = Path(__file__).resolve().parents[2] / "screenshots"
            screenshot_dir.mkdir(exist_ok=True)
            screenshot_vnc = screenshot_dir / f"{name}_{time.strftime('%Y%m%d%H%M%S')}.png"
            # 保存截图到文件
            loc.screenshot(path=str(screenshot_vnc))
            logger.info(f"截图保存成功: {screenshot_vnc}")

            # 将截图添加到 Allure 报告
            with open(screenshot_vnc, "rb") as f:
                allure.attach(
                    body=f.read(),
                    name=f"vnc截图_{name}",
                    attachment_type=allure.attachment_type.PNG
                )
            logger.info(f"云服务器{name}：VNC登录成功")

    @submenu("弹性云服务器")
    def ecs_rebuild(self, name: str, version: str, bit: str, image: str):
        """重建云主机
        Args：
            name: 云服务器名称
            version: 重建云主机的操作系统版本
            bit: 重建云主机的操作系统位数
            image: 重建云主机的镜像源
        """
        self.click_action(name, "重建云主机")
        # 选择操作系统版本
        self.get_by_role("textbox", name="请选择操作系统版本").click()
        self.get_by_role("listitem").filter(has_text=version).click()
        # self._select_image(image)
        # 选择操作系统版本
        self.get_by_role("textbox", name="请选择操作系统位数").click()
        self.get_by_role("listitem").filter(has_text=bit).click()
        # 选择镜像源
        self.get_by_role("textbox", name="请选择镜像").click()
        self.get_by_title(image, exact=True).click()
        self.dialog_confirm.click()
        logger.info(f"重建云主机操作完成：{name}，操作系统版本：{version}，操作系统位数：{bit}，镜像：{image}")

    @submenu("弹性云服务器")
    def ecs_clone(self, name: str, clonename: str, net: str, subnet: str, encryption: dict, ipv6=False):
        """克隆云服务器
        Args：
            name: 云服务器名称
            clonename: 克隆名称
            net: 网络
            subnet: 子网
            ipv6: ipv6地址
            encryption: 加密盘：加密密钥

        """
        self.click_action(name, "克隆")
        # 输入克隆名称
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").click()
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(clonename)

        # 选择网络
        self.locator("//label[text()='网络']/following-sibling::div//input").click()
        self.get_by_text(net, exact=True).click()

        # 选择子网
        self.locator("form div").filter(has_text=f"子网").get_by_placeholder("请选择").click()
        self.get_by_text(f"{subnet}(10").click()

        # 分配ipv6地址
        try:
            self.get_by_role("textbox", name="请选择IPv6 地址").click()
            if ipv6:
                self.get_by_text("自动分配IPv6地址").click()
            else:
                self.get_by_text("暂不分配IPv6地址").click()
        except:
            pass

        # 选择密钥
        try:
            self.locator("label").filter(has_text="密钥").locator("span")
            if encryption and len(encryption) != 0:
                for key, value in encryption.items():
                    self.click_action(key, "选择密钥")
                    # 需补充选择密钥步骤
                    self.get_by_text(value).click()
                    self.dialog_confirm.click()
        except:
            pass
        # 点击确定 克隆
        self.dialog_confirm.click()
        logger.info(f"操作完成: 克隆云服务器{name}: 克隆名称{clonename}")

    @submenu("弹性云服务器")
    def ecs_operations(self, name: str, operation: str):
        """操作
        Args:
            name: 云服务器名称
            operation: 操作选项
        """
        try:
            self.click_action(name, operation)
        except  Exception as e:
            logger.error(f"云服务器{name}：{operation}失败")
            raise e
        if operation == "重启":
            self.get_by_text("重启 取消", exact=True).get_by_text("重启", exact=True).click()
        elif operation == "强制重启":
            self.get_by_text("强制重启 取消", exact=True).get_by_text("强制重启", exact=True).click()
        elif operation in ["恢复运行", "取消暂停"]:
            self.get_by_label(operation).get_by_text("确定", exact=True).click()
        else:
            self.dialog_confirm.click()
        logger.info(f"操作完成: {name}云服务器点击: {operation}")

    @submenu("弹性云服务器")
    def ecs_reset_state(self, name: str):
        """重置状态
        Args:
            name: 云服务器名称
        """
        try:
            self.click_action(name, "重置状态")
            self.dialog_confirm.click()
            logger.info(f"操作完成: 云服务器{name}点击重置状态")
        except Exception as e:
            logger.error(f"云服务器{name}：重置状态失败:{e}")
            raise e

    @submenu("弹性云服务器")
    def ecs_load_network(
        self,
        name: str,
        net: str,
        subnet: str,
        mode="标准",
        ipv4: dict = None
    ):
        """加载网卡
        Args:
            name: 云服务器名称
            net: 网络
            subnet: 子网
            mode: 网络加速模式
            ipv4: IPV4分配方式，{"method": "自动分配"}，{"method": "选择端口", "端口":"xxxx"},{"method": "选择端口",“加密网卡”:True}
        """
        checked_subnet = ""
        try:
            self.click_action(name, "加载网卡")
            # 选择网络
            logger.info(f"云服务器{name}：选择网络{net}")
            self.get_by_role("textbox", name="请选择网络").click()
            self.get_by_text(net, exact=True).click()
            # 选择子网
            self.get_by_role("textbox", name="请选择子网").click()
            self.get_by_role("listitem").filter(has_text=f"{subnet}(").click()
            checked_subnet = self.get_by_role("textbox", name="请选择子网").input_value().split("(")[1].split(".0/")[0]
            logger.info(f"云服务器{name}：选择子网{subnet}, 实际子网{checked_subnet}")
            # 选择网络加速模式
            if mode:
                logger.info(f"云服务器{name}：选择网络加速模式{mode}")
                self.get_by_role("radio").filter(has_text=mode).click()
            if ipv4:
                for key, value in ipv4.items():
                    logger.info(f"云服务器{name}：IPV4分配方式{key}：{value}")
                    self.get_by_role("radio").filter(has_text=key).click()
                    self.get_by_text(value).click()
            self.get_by_label("加载网卡").get_by_text("确定").click()
            logger.info(f"操作完成: 云服务器{name}: 加载网卡")
            return checked_subnet
        except Exception as e:
            logger.error(f"云服务器{name}：加载网卡失败:{e}")
            raise e

    @submenu("弹性云服务器")
    def ecs_uninstall_network(self, name: str, net: str):
        """卸载网卡
        Args:
            name: 云服务器名称
            net: 需卸载的网卡
        """
        self.click_action(name, "卸载网卡")
        # 选择网络
        self.get_by_role("textbox", name="请选择网络").click()
        self.get_by_role("listitem").filter(has_text=net).click()
        self.dialog_confirm.click()
        logger.info(f"操作完成: 云服务器{name}卸载网: {net}")

    @submenu("弹性云服务器")
    def ecs_bind_pub_ip(self, name: str, subnet: str = "Autotest", pub_net: str = "public_net"):
        """绑定公网IP
        Args:
            name: 云服务器名称
            subnet: 子网
            pub_net: 公网资源池
        """
        self.click_action(name, "绑定公网IP")
        # 选择端口
        self.get_by_role("row").filter(has_text=subnet).get_by_role("radio").click()
        self.get_by_text("下一步", exact=True).click()
        # 选择资源池
        bind_dialog = self.get_by_role("dialog", name="绑定公网IP")
        bind_dialog.get_by_placeholder("请选择").click()
        self.get_by_text(pub_net).click()
        # 选择公网ip
        # 获取所有可用IP行，随机选择一个
        available_rows = bind_dialog.get_by_role("row").filter(has_text="关闭").all()
        if not available_rows:
            raise Exception("没有可用的公网IP")
        # 随机选择一个IP，降低多线程冲突概率
        selected_row = random.choice(available_rows)
        selected_row.get_by_role("radio").click()
        ip_info = selected_row.get_by_role("cell")
        ip = ip_info.nth(1).text_content()
        self.dialog_confirm.click()
        logger.info(f"操作完成: 云服务器{name}: 绑定公网IP: {subnet}, 公网ip: {ip}")
        return str(ip)

    @submenu("弹性云服务器")
    def ecs_unbind_pub_ip(self, name: str, IP_addr: str):
        """解绑公网IP
        Args:
            name: 云服务器名称
            IP_addr: 公网ip地址
        """
        self.click_action(name, "解绑公网IP")
        self.get_by_role("dialog", name="解除绑定公网IP").get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(has_text=IP_addr).click()
        self.get_by_label("解除绑定公网IP", exact=True).get_by_text("确定").click()
        logger.info(f"操作完成: 云服务器{name}: 解绑公网IP: {IP_addr}")

    @submenu("弹性云服务器")
    def ecs_modify_spec(self, name: str, spec: dict):
        """修改规格
        Args:
            name: 云服务器名称
            spec: {
                "type": "基础规格" | "自定义规格",  # 规格类型
                "classify": "计算型" | "通用型" | "内存型",  # 规格分类（仅基础规格需要）
                "CPU": "2",  # CPU核数
                "Mem": "4",  # 内存大小
                "flavor_name": "ecs.c6.xlarge"  # 规格名称（可选，用于精确匹配）
                "shutdown": False | True
            }
        """
        cpu = spec.get("CPU", "2")
        mem = spec.get("Mem", "4")
        spec_type = spec.get("spec_type")
        power_off = spec.get("shutdown", False)
        need_start = False

        try:
            if power_off:
                self.ecs_operations(name, "关机")
                self.assert_status(name, "关机")
                need_start = True  # 标记需要恢复开机

            self.click_action(name, "修改规格")
            if spec_type:
                classify = spec.get("classify", "计算型")
                flavor_name = spec.get("flavor_name")

                # 选择规格分类
                if classify:
                    self.get_by_text(classify).click()

                # 选择具体规格
                if flavor_name:
                    # 通过规格名称精确匹配
                    self.get_by_role("row").filter(has_text=flavor_name).get_by_role("radio").click()
                else:
                    # 通过CPU和内存模糊匹配
                    (self.get_by_role("row").filter(has_text=f"{cpu} 核")
                     .and_(self.get_by_role("row").filter(has_text=f"{mem}.00 GiB"))
                     .and_(self.get_by_role("row").filter(has_text=f"{classify[:-1]}标准"))
                     .get_by_role("radio").first.click())

                self.dialog_confirm.click()
                self.assert_popup_success("调整实例资源配置成功")
                logger.info(f"操作完成: 云服务器{name}修改规格为{classify} {cpu}核{mem}GiB")

            else:  # 自定义规格
                self.get_by_role("radio").filter(has_text="自定义规格").click()

                # 填写CPU和内存
                self.get_by_role("dialog", name="修改规格").get_by_role("textbox").nth(1).fill(cpu)
                self.get_by_role("dialog", name="修改规格").get_by_role("textbox").nth(2).fill(mem)

                # 点击确定按钮
                self.get_by_label("修改规格").get_by_text("确定").click()
                self.assert_popup_success("调整实例资源配置成功")
                logger.info(f"操作完成: 云服务器{name}修改自定义规格为{cpu}核{mem}GiB")

        except Exception as e:
            logger.error(f"云服务器{name}修改规格失败: {e}")
            raise e
        finally:
            if need_start:
                try:
                    self.ecs_operations(name, "启动")
                    self.assert_status(name)
                    logger.info(f"云服务器{name}已恢复开机")
                except Exception as e:
                    logger.error(f"云服务器{name}恢复开机失败: {e}")

    @submenu("弹性云服务器")
    def ecs_modify_pwd(self, name: str, pwd: str, confirm: str):
        """修改密码
        Args:
            name: 云服务器名称
            pwd: 密码
            confirm: 确认密码
        """
        self.click_action(name, "修改密码")
        try:
            self.locator("div").filter(has_text=re.compile(r"^密码$")).get_by_role("textbox").fill(pwd)
            self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(confirm)
            self.get_by_label("修改密码").get_by_text("确定").click()
            logger.info(f"操作完成: 云服务器{name}修改密码为{pwd}")
        except Exception as e:
            logger.info(f"云服务器{name}修改密码失败:{e}")
            raise e

    @submenu("弹性云服务器")
    def ecs_modify_vnc_pwd(self, name: str, vncpwd: str, confirmpwd: str):
        """修改vnc密码
        Args:
            name: 云服务器名称
            vncpwd: vnc密码
            confirmpwd: 确认vnc密码
        """
        self.click_action(name, "修改VNC密码")
        if not self.get_by_role("switch").locator("span").is_enabled():
            self.get_by_role("switch").locator("span").click()
        try:
            self.get_by_role("textbox", name="VNC密码最长为8位").fill(vncpwd)
            self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(confirmpwd)
            self.get_by_label("修改VNC密码").get_by_text("确定").click()
            logger.info(f"操作完成: 云服务器{name}修改VNC密码为{vncpwd}")
        except Exception as e:
            logger.info(f"云服务器{name}修改VNC密码失败:{e}")
            raise e

    @submenu("弹性云服务器")
    def ecs_modify_hostname(self, name: str, hostname: str):
        """修改主机名
        Args:
            name: 云服务器名称
            hostname: 主机名
        """
        self.click_action(name, "修改主机名")
        self.get_by_placeholder("请输入主机名称").fill(hostname)
        self.get_by_label("修改主机名").get_by_text("确定").click()
        logger.info(f"操作完成: 云服务器{name}修改主机名为{hostname}")

    @submenu("弹性云服务器")
    def ecs_time_synchronize(self, name: str, time_server: str, interval: str):
        """时钟同步
        Args:
            name: 云服务器名称
            time_server: 时间服务器
            interval: 同步间隔
        """
        self.click_action(name, "时间同步服务器")
        server_loc = self.get_by_role("textbox", name="例：10.0.13.24或*sugoncloud.")
        server_loc.clear()
        server_loc.fill(time_server)
        logger.info(f"弹性云服务器{name}时钟同步，同步间隔为{interval}秒")
        loc = self.get_by_label("时间同步服务器").locator("form div").filter(has_text="时间同步间隔(秒)").get_by_role(
            "textbox")
        loc.clear()  # 清空输入框默认数据
        loc.fill(interval)
        self.dialog_confirm.click()
        logger.info(f"操作完成: 云服务器{name}时钟同步，同步间隔为{interval}秒")

    @submenu("弹性云服务器")
    def ecss_create(self, name, snapshot_name, desc="", data_disk=False):
        self.click_action(name, "新建快照")
        dialog = self.get_by_role("dialog")
        dialog.locator("div").filter(has_text=re.compile(r"^快照名称$")).get_by_role("textbox").fill(snapshot_name)
        dialog.locator("textarea").fill(desc)
        if data_disk:
            self.page.locator("form span").nth(3).click()
        self.dialog_confirm.click()
        logger.info(f"云服务器快照创建请求已提交: {name}, {snapshot_name}")

    @submenu("弹性云服务器")
    def ecs_batch_operations(self, names: list, operation: str):
        """批量操作云服务器

        Args:
            names: 云服务器名称列表
            operation: 操作类型，支持"批量重启"、"批量关机"、"批量启动"、"批量强制重启"等
        """
        logger.info(f"开始批量操作云服务器: {names}, 操作类型: {operation}")

        try:
            # 选择指定的云服务器
            self.select_rows_by_names(names)

            # 点击更多操作按钮
            self.get_by_role("button", name="更多操作").click()

            # 根据操作类型点击相应的选项
            self._click_batch_operation_option(operation)

            # 确认操作
            self._confirm_batch_operation(operation)

            logger.info(f"批量操作完成: {operation}, 云服务器: {names}")

        except Exception as e:
            logger.error(f"批量操作失败: {operation}, 云服务器: {names}, 错误: {e}")
            raise

    def _click_batch_operation_option(self, operation: str):
        """点击批量操作选项

        Args:
            operation: 操作类型
        """
        # 方法1: 通过aria-controls属性精确定位下拉菜单，然后查找选项
        try:
            operation_btn = self.get_by_role("button", name="更多操作")
            dropdown_id = operation_btn.evaluate("element => element.getAttribute('aria-controls')")
            if dropdown_id:
                specific_dropdown = self.page.locator(f"#{dropdown_id}")
                batch_option = specific_dropdown.get_by_text(operation, exact=True)
                if batch_option.is_visible() and batch_option.is_enabled():
                    batch_option.click()
                    return
                else:
                    raise Exception(f"{operation}选项不可见或不可用")
            else:
                raise Exception("未找到aria-controls属性")
        except Exception as e:
            # 方法2: 备用方案 - 找到最后一个可见的下拉菜单
            logger.warning(f"主要方法失败，使用备用方案: {e}")
            dropdown_menus = self.page.locator('[id^="dropdown-menu-"]')

            # 从后往前遍历，找到最后一个可见的下拉菜单
            for i in range(dropdown_menus.count() - 1, -1, -1):
                menu = dropdown_menus.nth(i)
                if menu.is_visible():
                    option = menu.get_by_text(operation, exact=True)
                    if option.count() > 0 and option.is_visible() and option.is_enabled():
                        option.click()
                        return
            raise Exception(f"所有方法都失败，未找到可用的{operation}选项")

    def _confirm_batch_operation(self, operation: str):
        """确认批量操作

        Args:
            operation: 操作类型
        """
        # 根据不同的操作类型，使用不同的确认方式
        if operation == "批量重启":
            self.get_by_label("批量重启").get_by_text("确定").click()
        elif operation in ["批量关机", "批量启动"]:
            self.locator("div:nth-child(2) > div > .cloud-button-btn > span").click()
        elif operation == "批量强制重启":
            self.get_by_label("批量强制重启").get_by_text("确定").click()
        else:
            # 默认使用通用确认按钮
            self.dialog_confirm.click()

    @submenu("弹性云服务器")
    def ecs_batch_migration(self, names, migration_type="热迁移", scheduling=None, node="master01", cluster="Autotest",
                            bandwidth=None, cpu_auto=False):
        """批量迁移云服务器

        Args:
            names: 云服务器名称列表
            migration_type: 迁移方式，默认为"热迁移"，可选"冷迁移"
            scheduling: 调度方式
            node: 目标节点
            bandwidth: 带宽设置，默认为"全速"
            cpu_auto: CPU自动收敛
        """
        # 选择指定的云服务器
        self.select_rows_by_names(names)

        # 点击更多操作按钮
        self.get_by_role("button", name="更多操作").click()

        # 选择指定的云服务器并点击批量迁移
        self._click_batch_operation_option(f"批量{migration_type}")

        if scheduling == "手动指定":
            self.get_by_role("radio", name="手动指定 󦕟").click()
            if migration_type == "热迁移":
                # 选择目标集群cluster
                self.get_by_text("目标集群").locator("xpath=./following-sibling::div//input").click()
                locs = [
                    self.locator("li").filter(has_text=cluster).nth(1),  # 同名集群内迁移
                    self.locator("li").filter(has_text=cluster)
                ]
                self._find_element(locs, f"集群{cluster}").click()

                # 等待物理机选择区域加载完成
                # 尝试选择指定的目标物理机
                available_hosts = self._get_available_migration_hosts()
                if node in available_hosts:
                    # 点击该节点
                    self.get_by_role("radio", name=node).click()
                    checked_host = node
                    logger.info(f"已选择指定的目标物理机: {checked_host}")

        # 选择带宽
        if migration_type == "热迁移" and bandwidth:
            self.get_by_placeholder("请选择带宽").click()
            # self.locator("li").filter(has_text=bandwidth).click()
            self.locator("//*[text()='半速']/../preceding-sibling::*[1]/span").click()
            self.locator("li").filter(has_text=bandwidth).click()
        if cpu_auto and migration_type == "热迁移":
            # 设置开关
            loc = self.get_by_role("switch").locator("span")
            if not loc.is_enabled():
                loc.click()

        # 确认迁移
        self.dialog_confirm.click()

        logger.info(f"批量迁移云服务器下发成功: {names}, 迁移方式: {migration_type}, 带宽: {bandwidth}")

    @submenu("弹性云服务器")
    def ecs_hot_migration(self, name, target_host=None, m_type="系统分配", storage=False, bandwidth="全速",
                          cpu_auto=False):
        """云服务器热迁移

        Args:
            name: 云服务器名称
            target_host: 目标物理机，如"master03.cloud.local"
            m_type: 调度方式，"系统分配"或"手动指定"
            storage: 是否迁移存储，默认为False
            bandwidth: 迁移速率，默认为"全速"
            cpu_auto: 是否启用CPU自动收敛，默认为False
        """
        checked_host = None
        # 点击云服务器操作按钮，选择热迁移
        self.click_action(name, "热迁移")

        # 选择调度方式
        if m_type == "手动指定":

            self.get_by_role("radio", name="手动指定 󦕟").click()

            # 点击"选择物理机"按钮，打开物理机选择区域
            self.get_by_text("目标物理机").locator("xpath=./following-sibling::div/span").click()

            # 等待物理机选择区域加载完成

            # 取所有可用的物理机节点，排除包含is-disabled属性的节点
            available_hosts = self._get_available_migration_hosts()

            # 如果没有可用物理机，抛出异常
            if not available_hosts:
                error_msg = "没有可用的物理机可供选择"
                logger.error(error_msg)
                locs = [
                    self.get_by_label("close 选择物理机"),
                    self.get_by_text("取消"),
                ]
                self._find_element(locs, "取消").click()
                time.sleep(0.5)  # 等待选择物理机的section关闭
                self.get_by_label("热迁移", exact=True).get_by_text("取消").click()  # 取消热迁移
                pytest.skip(error_msg)

            # 选择目标物理机
            if target_host:
                # 尝试选择指定的目标物理机
                target_host = f"{target_host}.cloud.local" if ".cloud.local" not in target_host else target_host
                if target_host in available_hosts:
                    # 点击该节点
                    self.get_by_role("radio", name=target_host).click()
                    checked_host = target_host
                    self.dialog_confirm.click()
                    logger.info(f"已选择指定的目标物理机: {checked_host}")
                else:
                    # 如果指定的目标物理机不可用，选择第一个可用的
                    logger.warning(f"指定的目标物理机 {target_host} 不可用，选择第一个可用物理机")
                    self.get_by_role("radio", name=available_hosts[0]).click()
                    checked_host = available_hosts[0]
                    self.dialog_confirm.click()
                    logger.info(f"已选择第一个可用的物理机: {checked_host}")

        # 选择是否迁移存储
        if storage:
            self.get_by_role("checkbox").click()

        # 选择迁移速率
        self.get_by_placeholder("请选择迁移速率").click()
        self.locator("li").filter(has_text=bandwidth).click()

        # 设置CPU自动收敛选项
        if cpu_auto:
            switch_locator = self.get_by_role("switch").locator("span")
            if not switch_locator.is_enabled():
                switch_locator.click()

        # 确认热迁移
        self.dialog_confirm.click()

        logger.info(
            f"开始热迁移云服务器: {name}, 调度方式: {m_type}, 目标主机: {checked_host}, 存储迁移: {storage}, 迁移速率: {bandwidth}")
        return checked_host

    @submenu("弹性云服务器")
    def ecs_cold_migration(self, name, m_type="系统分配", cluster=None, target_host="master01"):
        """云服务器冷迁移

        Args:
            name: 云服务器名称
            m_type: 调度方式，"系统分配"或"手动指定"
            cluster: 目标集群，如"Autotest"
            target_host: 目标物理机，如"master01","controller01"
        """
        checked_host = None

        # 点击云服务器操作按钮，选择冷迁移
        self.click_action(name, "冷迁移")
        # 选择调度方式
        if m_type == "手动指定":

            self.get_by_role("radio", name="手动指定 󦕟").click()

            # 选择目标集群cluster
            self.get_by_text("目标集群").locator("xpath=./following-sibling::div//input").click()
            locs = [
                self.locator("li").filter(has_text=cluster).nth(1),  # 同名集群内迁移
                self.locator("li").filter(has_text=cluster)
            ]
            self._find_element(locs, f"集群{cluster}").click()

            # 等待物理机选择区域加载完成

            # 选择目标物理机
            if target_host:
                try:
                    # 尝试选择指定的目标物理机
                    target_host = f"{target_host}.cloud.local" if ".cloud.local" not in target_host else target_host
                    self.locator("section").get_by_placeholder("搜索（名称）").fill(target_host)
                    self.get_by_role("dialog").get_by_text("搜索").click()

                    # 尝试选择指定的目标物理机
                    self.get_by_role("radio", name=target_host).click()
                    checked_host = target_host
                    logger.info(f"已选择指定的目标物理机: {checked_host}")

                except Exception as e:
                    # 如果未指定的目标物理机，选择第一个可用的
                    logger.warning(f"指定的目标物理机 {target_host} 不可用 ，选择第一个可用物理机")
                    self.locator("section").get_by_text("重置").click()
                    available_hosts = self._get_available_migration_hosts()
                    # 如果没有可用物理机，抛出异常
                    if not available_hosts:
                        error_msg = "没有可用的物理机可供选择"
                        logger.error(error_msg)
                        self.dialog_cancel.click()
                        pytest.skip(error_msg)
                    self.get_by_role("radio", name=available_hosts[0]).click()
                    checked_host = available_hosts[0]
                    logger.info(f"已选择第一个可用的物理机: {checked_host}")

        # 确认冷迁移
        self.dialog_confirm.click()

        logger.info(f"云服务器冷迁移请求已提交: {name}，迁移方式: {m_type}, 集群{cluster},目标主机: {checked_host}")
        return checked_host

    @submenu("弹性云服务器")
    def ecs_mount_to_server(self, volume_name, vm_name):
        """将云硬盘挂载到指定服务器

        Args:
            volume_name: 云硬盘名称
            vm_name: 服务器名称
        """
        # 点击挂载云硬盘选项
        self.click_action(vm_name, "挂载云硬盘")

        # 搜索云硬盘
        self.get_by_label("挂载云硬盘").get_by_placeholder("搜索（名称）").fill(volume_name)
        self.get_by_label("挂载云硬盘").get_by_text("搜索").click()

        # 选择云硬盘
        self.get_by_role("row").filter(has_text=volume_name).get_by_role("radio").click()

        # 确认挂载
        self.get_by_label("挂载云硬盘").get_by_text("挂载", exact=True).click()
        logger.info(f"操作完成: 云硬盘{volume_name}挂载到服务器{vm_name}")

    @submenu("弹性云服务器")
    def ecs_unmount_from_server(self, volume_name, vm_name):
        """从指定服务器卸载云硬盘

        Args:
            volume_name: 云硬盘名称
            vm_name: 服务器名称
        """

        # 点击卸载云硬盘选项
        self.click_action(vm_name, "卸载云硬盘")

        # 选择云硬盘
        self.get_by_placeholder("请选择云硬盘").click()
        self.locator("span").filter(has_text=re.compile(rf"^{volume_name}$")).click()

        # 确认卸载
        self.dialog_confirm.click()
        logger.info(f"操作完成: 云硬盘{volume_name}从服务器{vm_name}卸载")

    @submenu("弹性云服务器")
    def ecs_expand_system_disk(self, name: str, new_size: str):
        """扩容弹性云服务器系统盘

        Args:
            name: 云服务器名称
            new_size: 新的系统盘大小（GiB）
        """
        logger.info(f"开始扩容云服务器系统盘: {name}，扩容至: {new_size}GiB")

        # 点击下拉菜单中的"系统盘扩容"选项
        self.click_action(name, "系统盘扩容")

        # 设置新的系统盘大小
        self.get_by_label("系统盘扩容").get_by_role("spinbutton").fill(new_size)

        # 确认扩容
        self.dialog_confirm.click()

        logger.info(f"云服务器系统盘扩容成功: {name}")

    @submenu("弹性云服务器")
    def ecs_modify_cpu_qos(self, name: str, priority: str = "低", ceiling: str = "0.2"):
        """修改云服务器CPU QoS

        Args:
            name: 云服务器名称
            priority: CPU QoS级别，默认为"低"
            ceiling: CPU权重值，默认为0.2
        """
        logger.info(f"开始修改云服务器{name}的CPU QoS: 级别={priority}, 权重={ceiling}")

        # 点击指定云服务器的操作按钮
        self.click_action(name, "修改CPU QoS")

        # 选择CPU QoS级别
        self.get_by_label("修改CPU QoS").get_by_placeholder("请选择").click()
        self.get_by_text(priority, exact=True).click()

        # 设置CPU权重
        self.get_by_label("修改CPU QoS").get_by_role("spinbutton").fill(ceiling)

        # 确认修改
        self.dialog_confirm.click()
        logger.info(f"云服务器{name}的CPU QoS修改请求已提交")

    @submenu("弹性云服务器")
    def ecs_batch_set_startup_order(self, names: list, order: int, delay):
        """批量设置云服务器启动顺序

        Args:
            names: 云服务器名称列表
            order: 启动顺序
            delay: 启动延迟时间(秒)
        """
        logger.info(f"云服务器{names}开始批量设置启动顺序: {str(order)}, 启动延迟时间:{delay}")

        # 选择指定的云服务器
        self.select_rows_by_names(names)

        # 点击设置启动顺序按钮
        self.get_by_role("button", name="更多操作").click()
        self._click_batch_operation_option("设置启动顺序")

        # 设置每台服务器的启动顺序
        self.get_by_role("dialog", name="设置启动顺序").get_by_role("textbox").first.fill(str(order))

        # 设置启动延迟时间
        self.locator("form div").filter(has_text="启动延迟时间(秒)").get_by_role("textbox").fill(delay)

        # 确认设置
        self.dialog_confirm.click()

        logger.info(f"批量设置云服务器启动顺序完成: {names}")

    @submenu("弹性云服务器")
    def ecs_to_details(self, name: str):
        """进入云服务器详情页面

        Args:
            name: 云服务器名称
        """
        logger.info(f"进入云服务器详情页面: {name}")

        # 点击指定云服务器的详情链接
        self.get_by_role("cell", name=name).locator("a").click()

        # 等待详情页面加载完成

        logger.info(f"成功进入云服务器{name}详情页")

    @submenu("弹性云服务器")
    def ecs_mount_cdrom(self, name: str, iso_name: str = None):
        """
        为指定弹性云服务器挂载CD-ROM

        Args:
            name: 云服务器名称
            iso_name: CD-ROM名称，如果为None则使用自动生成的名称
        """
        logger.info(f"开始为云服务器{name}挂载CD-ROM: {iso_name}")
        # 点击云服务器操作按钮
        self.click_action(name, "挂载CD-ROM")

        # 等待挂载CD-ROM对话框出现

        # 选择CD-ROM类型（如果需要选择）
        try:
            # 根据类型iso名称选择对应的单选按钮
            self.get_by_label("挂载CD-ROM").get_by_placeholder("搜索（名称）").fill(iso_name)
            self.get_by_label("挂载CD-ROM").get_by_text("搜索").click()
            self.get_by_label("挂载CD-ROM").get_by_role("radio").first.click()
        except:
            logger.warning(f"未找到CD-ROM '{iso_name}' ，默认选择第一个CD-ROM")
            self.get_by_label("挂载CD-ROM").get_by_text("重置").click()
            self.get_by_label("挂载CD-ROM").get_by_role("row").filter(has_text="autotest").get_by_role(
                "radio").first.click()

        # 点击挂载按钮
        self.get_by_label("挂载CD-ROM").get_by_text("挂载", exact=True).click()
        logger.info(f"云服务器{name}挂载CD-ROM请求已提交")

    @submenu("弹性云服务器")
    def ecs_unmount_cdrom(self, name: str, cdrom_name: str = None):
        """
        为指定弹性云服务器挂载CD-ROM

        Args:
            name: 云服务器名称
            cdrom_name: CD-ROM名称
        """
        logger.info(f"开始为云服务器{name}卸载CD-ROM: {cdrom_name}")
        # 点击云服务器操作按钮
        self.click_action(name, "卸载CD-ROM")

        # 等待挂载CD-ROM对话框出现

        # 选择CD-ROM
        self.get_by_placeholder("请选择CD-ROM").click()
        self.locator("li").filter(has_text=cdrom_name).click()

        # 点击挂载按钮
        self.dialog_confirm.click()
        logger.info(f"云服务器{name}卸载CD-ROM请求已提交")

    @submenu("弹性云服务器")
    def ecs_batch_set_shutdown_order(self, names: list, order: int, delay):
        """批量设置云服务器关机顺序

        Args:
            names: 云服务器名称列表
            order: 关机顺序
            delay: 启动延迟时间(秒)
        """
        logger.info(f"云服务器{names}开始批量设置关机顺序: {str(order)}, 关机延迟时间:{delay}")

        # 选择指定的云服务器
        self.select_rows_by_names(names)

        # 点击设置关机顺序按钮
        self.get_by_role("button", name="更多操作").click()
        self._click_batch_operation_option("设置关机顺序")

        # 设置每台服务器的启动顺序
        self.get_by_label("设置关机顺序").get_by_role("textbox").first.fill(str(order))

        # 设置启动延迟时间
        self.locator("form div").filter(has_text="关机延迟时间(秒)").get_by_role("textbox").fill(delay)

        # 确认设置
        self.dialog_confirm.click()

        logger.info(f"批量设置云服务器关机顺序完成: {names}")

    @submenu("弹性云服务器")
    def ecs_set_boot_order(self, name: str, boot_order: list):
        """
        设置云服务器启动顺序

        Args:
            name: 云服务器名称
            boot_order: 启动顺序配置，格式为：
                [  # 启动设备列表，按优先级排序
                        {"磁盘": "hdc:20GB"},
                        {"网络", "10.228.42.59/fa:16:3e:ae:bb:fa"}
                    ]
        """
        logger.info(f"开始设置云服务器 {name} 的启动顺序")

        # 点击云服务器的操作按钮
        self.click_action(name, "设置启动项")

        # 添加启动项
        if len(boot_order) > 1:
            for i in range(len(boot_order) - 1):
                self.get_by_role("button", name=" 添加启动项").click()

        for i, boot_device in enumerate(boot_order):
            # 选择启动类型
            for boot_type, devices in boot_device.items():
                self.get_by_label("设置启动项").get_by_placeholder("请选择").nth(0 if i == 0 else i * 2).click()

                self.locator("li").filter(has_text=re.compile(fr"^{boot_type}$")).nth(
                    1 if len(boot_order) > 1 else 0).click()

                # 选择设备
                self.get_by_label("设置启动项").get_by_placeholder("请选择").nth((i * 2 + 1)).click()
                self.locator("li").filter(has_text=devices).click()

        # 确认设置
        self.dialog_confirm.click()

        logger.info(f"云服务器 {name} 启动顺序设置完成")

    @submenu("弹性云服务器")
    def ecs_install_tools(self, name: str):
        """为云服务器安装工具

        Args:
            name: 云服务器名称
        """
        # 点击操作按钮
        self.click_action(name, "安装工具")

        # 点击安装并进入下一步
        self.get_by_text("安装并进入下一步").click()
        logger.info(f"云服务器 {name} 安装工具请求已提交")

    @submenu("弹性云服务器")
    def ecs_uninstall_tools(self, name: str):
        """云服务器页面卸载工具

        Args:
            name: 云服务器名称
        """
        logger.info(f"开始为云服务器 {name} 卸载工具")

        # 点击操作按钮
        self.click_action(name, "卸载工具")

        # 点击确定
        time.sleep(2)
        self.dialog_confirm.click()

        logger.info(f"云服务器 {name} 卸载工具请求已提交")

    @submenu("弹性云服务器")
    def ecs_modify_vnc_type(self, name: str, vnc_type: str = "VGA"):
        """修改云服务器VNC显卡类型

        Args:
            name: 云服务器名称
            vnc_type: VNC显卡类型，默认为"VGA"
        """
        logger.info(f"开始修改云服务器 {name} 的VNC显卡类型为: {vnc_type}")

        # 点击云服务器操作按钮，选择修改VNC显卡类型
        self.click_action(name, "修改VNC显卡类型")

        # 选择VNC显卡类型
        cur_type = self.get_by_placeholder("请选择VNC显卡类型").input_value()
        if vnc_type == cur_type:
            pytest.skip(f"云服务器 {name} 的VNC显卡类型已是 {cur_type}")
        self.get_by_placeholder("请选择VNC显卡类型").click()
        self.locator("li").filter(has_text=re.compile(fr"^{vnc_type}$")).click()

        # 确认修改
        self.dialog_confirm.click()

        logger.info(f"云服务器{name}的VNC显卡类型修改提交成功")

    @submenu("弹性云服务器")
    def ecs_modify_cpu_mode(self, name: str, cpu_mode: str, custom_value: str = None):
        """修改云服务器CPU模式
        Args:
            name: 云服务器名称
            cpu_mode: CPU模式，默认为"host-passthrough"
        """
        logger.info(f"开始修改云服务器{name}的CPU模式为: {cpu_mode}")

        # 点击云服务器操作按钮，选择修改CPU模式
        self.click_action(name, "修改CPU模式")

        self.get_by_placeholder("请选择CPU模式").first.click()
        # 选择CPU模式
        if cpu_mode == "自定义":
            self.get_by_text("自定义").click()
            # 如果提供了自定义值，则选择它
            if custom_value:
                self.get_by_placeholder("请选择CPU模式").nth(1).click()
                self.locator("li").filter(has_text=custom_value).click()
        else:
            self.get_by_text(cpu_mode).click()

        # 确认修改
        self.dialog_confirm.click()

        logger.info(f"云服务器{name}的CPU模式修改成功{cpu_mode}, {custom_value}")

    @submenu("弹性云服务器")
    def ecs_mount_bare_disk(self, name: str, pool_name: str):
        """为云服务器挂载裸磁盘

        Args:
            name: 云服务器名称
            pool_name: 存储池名称
        """
        logger.info(f"为云服务器{name}挂载裸磁盘: 存储池={pool_name}")

        # 点击挂载裸磁盘选项
        self.click_action(name, "挂载裸磁盘")

        # 选择存储池
        self.get_by_placeholder("请选择存储池").click()
        # 查找包含存储池名称和总量的选项
        self.locator("li").filter(has_text=re.compile(rf"{pool_name}.*总量:")).click()

        # 选择磁盘
        self.get_by_placeholder("请输入名称").fill(pool_name)

        # 选择挂载裸磁盘选项
        self.get_by_label("挂载裸磁盘").get_by_role("radio").first.click()

        # 确认挂载
        self.get_by_label("挂载裸磁盘").get_by_text("挂载", exact=True).click()
        logger.info(f"为云服务器{name}挂载裸磁盘: 存储池={pool_name}")

    @submenu("弹性云服务器")
    def ecs_unmount_bare_disk(self, name: str, pool_name: str = None):
        """为云服务器卸载裸磁盘

        Args:
            name: 云服务器名称
        """
        logger.info(f"为云服务器{name}挂载裸磁盘: 裸磁盘={pool_name}")

        # 点击挂载裸磁盘选项
        self.click_action(name, "卸载裸磁盘")

        # 选择裸磁盘
        self.get_by_label("卸载裸磁盘").get_by_role("radio").click()

        # 确认卸载
        self.dialog_confirm.click()
        logger.info(f"为云服务器{name}卸载裸磁盘: 裸磁盘={pool_name}")

    @submenu("弹性云服务器")
    def ecs_batch_agent_version(self, names: list, agent_conf: list):
        """批量Agent版本设置
        Args:
            names: 云服务器名称
            agent_conf: Agent版本设置
        """
        logger.info(f"云服务器 {names}批量设置Agent版本{agent_conf}")

        self.select_rows_by_names(names)

        self.get_by_role("button", name="更多操作").click()

        self._click_batch_operation_option("批量Agent版本设置")
        for conf in agent_conf:
            for agent_type, agent_version in conf.items():
                self.locator("label").filter(has_text=agent_type).click()
                locator = self.get_by_role("row",
                                           name=f"默认{agent_type} {agent_version} 系统默认，禁止修改").get_by_role(
                    "radio")
                if not locator.is_checked():
                    locator.click()

        self.dialog_confirm.click()
        logger.info(f"云服务器 {names}批量设置Agent版本{agent_conf}成功")

    @submenu("弹性云服务器")
    def ecs_hot_migration_options(self, name) -> list:
        """云服务器热迁移节点选项

        Args:
            name: 云服务器名称
        """
        # 点击云服务器操作按钮，选择热迁移
        self.click_action(name, "热迁移")

        self.get_by_role("radio", name="手动指定 󦕟").click()

        # 点击"选择物理机"按钮，打开物理机选择区域
        self.get_by_text("目标物理机").locator("xpath=./following-sibling::div/span").click()

        # 等待物理机选择区域加载完成

        # 取所有可用的物理机节点，排除包含is-disabled属性的节点
        available_hosts = self._get_available_migration_hosts()
        self.locator("section").get_by_text("取消").click()
        sleep(1)  # 多个弹窗堆叠，需要等待上一层关闭
        self.close_dialog_if_exists()
        return available_hosts

    @submenu("弹性云服务器")
    def ecs_record_screen(self, name: str):
        """云服务器录屏
        Args:
            name: 云服务器名称
        """
        self.click_action(name, "开启录屏")
        self.get_by_label("开启录屏").get_by_text("开启", exact=True).click()
        self.assert_popup_success(f"{name}实例开启录屏成功")
        logger.info(f"实例: {name}开启录屏")

    @submenu("弹性云服务器")
    def ecs_stop_record_screen(self, name: str):
        """云服务器停止录屏
        Args:
            name: 云服务器名称
        """
        self.click_action(name, "关闭录屏")
        self.get_by_label("关闭录屏").get_by_text("关闭", exact=True).click()
        self.assert_popup_success(f"{name}实例禁用录屏成功")
        logger.info(f"实例: {name}实例关闭录屏成功")

    @submenu("弹性云服务器")
    def ecs_agent_version(self, name: str, agent_conf: list):
        """云服务器获取代理版本
        Args:
            name: 云服务器名称
            agent_conf: 代理类型, [{"FsAgent": "manual"}], [{"FsAgent": "manual"},{"DingAgent": "latest"}]
        """
        self.click_action(name, "Agent版本设置")
        for conf in agent_conf:
            for agent_type, agent_version in conf.items():
                self.locator("label").filter(has_text=agent_type).click()
                locator = self.get_by_role("row",name=f"默认{agent_type} {agent_version} 系统默认，禁止修改").get_by_role("radio")
                if not locator.is_checked():
                    locator.click()
                else:
                    pytest.skip(f"当前{agent_type}版本已设置为: {agent_version}")
        self.dialog_confirm.click()
        logger.info(f"{name}实例修改Agent版本设置为: {agent_conf}")

    @submenu("弹性云服务器")
    def ecs_to_sg_tab(self, name, sub_tab="自定义安全组"):
        """进入虚机详情的安全组页签

        Args:
            name: 云服务器名称
            sub_tab: 子页签名称，默认 "自定义安全组"
        """
        self.ecs_to_details(name)
        # 点击安全组页签
        self.get_by_role("tab", name="安全组", exact=False).click()
        if sub_tab:
            # 使用正则匹配精确文本，处理首尾空格和换行
            self.locator(".security-group-item").filter(has_text=re.compile(rf"^\s*{re.escape(sub_tab)}\s*$")).click()
        logger.info(f"进入云服务器 {name} 的安全组页签")

    def ecs_set_security_groups(self, sg_names: list, bind: bool = True):
        """虚机详情页设置安全组

        Args:
            sg_names: 安全组名称列表
            bind: 绑定/解绑
        """
        # 使用更精准的匹配
        self.get_by_text("设置安全组", exact=True).click()

        dialog = self.get_by_role("dialog").filter(has_text="安全组设置").last
        if not dialog.is_visible():
            dialog = self.get_by_role("dialog").filter(has_text="设置安全组").last

        try:
            pagination_trigger = dialog.get_by_placeholder("请选择")
            if pagination_trigger.count() > 0:
                pagination_trigger.click()
                # 寻找 50条/页 选项
                self.locator("li").filter(has_text="50条/页").last.click()
        except Exception as e:
            logger.warning(f"尝试设置分页为50失败: {e}")

        for sg in sg_names:
            # 找到对应行并勾选
            row = dialog.get_by_role("row", name=re.compile(rf"{re.escape(sg)}")).first
            checkbox = row.locator(".el-checkbox")

            # 检查是否已勾选
            is_checked = "is-checked" in (checkbox.get_attribute("class") or "")
            if bind and not is_checked:
                checkbox.click()
            elif not bind and is_checked:
                checkbox.click()

        self.dialog_confirm.click()

        # 等待成功提示
        self.assert_popup_success(re.compile(r"设置安全组成功|操作成功"))
        logger.info(f"设置安全组完成: {sg_names}, bind={bind}")

    def ecs_get_bound_security_groups(self):
        """获取已绑定的安全组列表
        """
        items = self.locator(".security-group-item").all_text_contents()
        # 清洗数据，提取安全组名称（通常在括号前或者开头）
        bound_sgs = []
        for item in items:
            # 过滤掉空的或者包含 "自定义安全组" 的通用项
            name = item.split('(')[0].strip()
            if name and name not in ["自定义安全组", "安全组"]:
                bound_sgs.append(name)

        logger.info(f"当前绑定的安全组: {bound_sgs}")
        return bound_sgs

    def select_if_not_match(self, locator, value, exact=False):
        """
        如果当前选项不匹配，则选择指定值

        Args:
            locator: 定位器
            value: 期望值
            exact: 是否精确匹配，默认 False
        """
        if locator.input_value() != value:
            locator.click()
            # 增加 visible=True 过滤
            target = self.locator("li:visible")
            if exact:
                target.filter(has_text=re.compile(rf"^{value}$")).first.click()
            else:
                target.filter(has_text=value).first.click()

    def ecs_create_custom_sg_rule(self, **kwargs):
        """在详情页创建自定义安全组规则

        支持从 kwargs 中提取所有安全组规则参数。
        """
        # 录制中可能出现多种按钮点击方式
        btn_locs = [
            self.get_by_text("创建规则 批量删除").get_by_text("创建规则"),
            self.get_by_text("创建规则").first,
        ]
        self._find_element(btn_locs, "添加/创建规则按钮").first.click()

        # 指定弹窗
        dialog = self.get_by_role("dialog").filter(has_text=re.compile(r"创建规则")).last

        # 提取参数
        protocol = kwargs.get("protocol", "所有")
        direction = kwargs.get("direction", "入口")
        remote_type = kwargs.get("remote_type", "CIDR")
        ip_version = kwargs.get("ip_version", "IPv4")
        remote_sg = kwargs.get("remote_sg")
        description = kwargs.get("description", "")
        protocol_type = kwargs.get("protocol_type")
        protocol_code = kwargs.get("protocol_code")
        port_type = kwargs.get("port_type")
        port = kwargs.get("port")
        cidr = kwargs.get("cidr")

        # 选择协议
        protocol_input = dialog.locator("form div").filter(has_text="协议").get_by_placeholder("请选择", exact=True)
        self.select_if_not_match(protocol_input, protocol, exact=True)

        # 如果选择常用协议，需要进一步选择协议类型
        if protocol == "选择常用协议" and protocol_type:
            protocol_type_input = dialog.get_by_placeholder("请选择协议")
            self.select_if_not_match(protocol_type_input, protocol_type, exact=False)

            # 处理端口配置（定制TCP/UDP协议时需要）
            if "TCP" in protocol_type or "UDP" in protocol_type:
                port_type_input = dialog.locator("div").filter(has_text=re.compile(r"^打开端口")).get_by_placeholder(
                    "请选择")
                self.select_if_not_match(port_type_input, port_type, exact=True)

                # 填写端口
                if port_type == "端口范围" and port and "-" in port:
                    start_port, end_port = port.split("-")
                    start_loc = dialog.locator("div").filter(has_text=re.compile(r"^起始端口号$")).get_by_role(
                        "textbox")
                    start_loc.clear()
                    start_loc.fill(start_port)
                    end_loc = dialog.locator("div").filter(has_text=re.compile(r"^终止端口号$")).get_by_role("textbox")
                    end_loc.clear()
                    end_loc.fill(end_port)
                elif port:
                    dialog.get_by_placeholder("请输入端口").fill(port)

        # 如果选择手填协议CODE，填写CODE值
        elif protocol == "手填协议CODE" and protocol_code:
            dialog.get_by_placeholder("请输入协议CODE").fill(protocol_code)

        # 选择方向
        direction_input = dialog.locator("div").filter(has_text=re.compile(r"^方向")).get_by_placeholder("请选择")
        self.select_if_not_match(direction_input, direction, exact=False)

        # 选择远程类型
        remote_type_input = dialog.locator("div").filter(has_text=re.compile(r"^远程")).get_by_placeholder("请选择")
        self.select_if_not_match(remote_type_input, remote_type, exact=True)

        # 选择IP版本
        ip_version_input = dialog.get_by_placeholder("请选择IP版本")
        self.select_if_not_match(ip_version_input, ip_version, exact=False)

        # 根据远程类型填写对应值
        if remote_type == "安全组" and remote_sg:
            # 使用更精确的正则匹配，避免匹配到已选择“安全组”的“远程”下拉框
            dialog.locator("div").filter(has_text=re.compile(r"^安全组$")).get_by_placeholder("请选择").click()
            self.locator("li:visible").filter(has_text=remote_sg).first.click()
        elif remote_type == "CIDR" and cidr:
            dialog.get_by_placeholder(re.compile(r"非必填.*如.*0\.0\.0\.0")).fill(cidr)

        # 填写描述
        if description:
            dialog.locator("textarea").fill(description)

        # 确定并断言
        dialog.get_by_text("确定", exact=True).click()
        self.assert_popup_success(re.compile(r"规则操作成功|新建.*成功|操作成功"))
        logger.info(f"自定义安全组规则创建完成: {kwargs}")

    def ecs_delete_custom_sg_rule(self, description=None):
        """在详情页删除指定的自定义安全组规则
        Args:
            description: 规则描述，用于精确定位某条规则
        """
        if description:
            # 使用描述查找对应行并点击删除
            self.click_action(description, "删除")
        else:
            # 如果没提供描述，默认删除第一条规则（兼容原有逻辑）
            active_pane = self.locator(".el-tab-pane:not([aria-hidden='true'])").first
            target_row = active_pane.locator(".el-table__row").first
            target_row.get_by_text("删除").click()

        self.dialog_confirm.click()
        logger.info(f"自定义安全组规则删除完成: description={description}")

    def ecs_get_custom_sg_rules(self, direction="入口"):
        """获取自定义安全组规则列表

        Args:
            direction: 规则方向，"入口" 或 "出口"
        """
        if direction:
            target_direction = self.get_by_text(direction, exact=True).filter(has_not_text="入口出口")
            if target_direction.count() > 0:
                target_direction.first.click()

        # 查找当前激活的tab页中的表格 headers 和 rows
        active_tab = self.locator(".el-tab-pane:not([aria-hidden='true'])", ".active-tab").first
        headers = [h.strip() for h in active_tab.locator(".el-table__header-wrapper th").all_text_contents() if
                   h.strip()]

        # 过滤掉可能存在的方向选择器文字
        headers = [h for h in headers if h not in ["入口", "出口"]]

        row_locators = active_tab.locator(".el-table__body-wrapper tr").all()

        rules = []
        for row_locator in row_locators:
            cell_contents = self._get_cell_contents(row_locator)
            row_data = dict(zip(headers, cell_contents))

            rule_data = {}
            for key, val in row_data.items():
                if "方向" in key:
                    rule_data["方向"] = val
                elif "以太网类型" in key:
                    rule_data["以太网类型"] = val
                elif "协议" in key:
                    rule_data["协议"] = val
                elif "端口范围" in key:
                    rule_data["端口范围"] = val
                elif "远端IP前缀" in key:
                    rule_data["远端IP前缀"] = val
                elif "远端安全组" in key:
                    rule_data["远端安全组"] = val
                elif "描述" in key:
                    rule_data["描述"] = val
            rules.append(rule_data)

        self.logger.info(f"获取到的云服务器自定义规则列表: {rules}")
        return rules

    def ecs_back_to_list(self):
        """返回云服务器列表页
        """
        logger.info(f"返回云服务器列表页面")
        # 点击指定云服务器的详情链接
        self.locator(".el-icon-back").click()
        # 等待详情页面加载完成

    def assert_ecs_details_info(self, names, info_items: dict, tab: str = "详情", sub_tab: str = None):
        """验证云服务器详情页面中的信息

        Args:
            names: 云服务器名称
            tab: 页签名称
            sub_tab: 子页签名称
            info_items: 需要验证的信息项字典，格式为 {"信息项名称": "期望内容"}
                       例如: {"启动顺序": "3", "启动延迟时间(秒)": "20"}
        """
        logger.info(f"验证云服务器 {names} 的 {tab} 页签信息")
        if isinstance(names, str):
            names = [names]
        for name in names:
            self.ecs_to_details(name)

            logger.info(f"点击 {tab} 页签")
            exact = False if tab == "安全组" or tab == "事件列表" else True
            if tab == "详情":
                sleep(2)
            else:
                self.get_by_role("tab", name=tab, exact=exact).click()
                if sub_tab:
                    self.locator("label").filter(has_text=sub_tab).click()
            # 逐个验证信息项
            for item_name, expected_content in info_items.items():
                if tab == "详情":
                    # 定位信息项
                    info_item = self.get_by_label(tab).get_by_text(item_name, exact=True)
                    # 获取信息项的值
                    _list = ["亲和组", "硬件密码加速", "CPU QoS 优先级", "CPU QoS 上限", "NUMA 绑定", "vNUMA拓扑",
                             "CPU独占", "VNC显卡类型", "CPU模式", "声卡类型"]
                    if item_name in _list:
                        info_value = info_item.locator("xpath=./following-sibling::*").first
                    else:
                        info_value = info_item.locator("xpath=../following-sibling::*").first
                    # 验证信息项的值是否包含期望内容
                    assert str(expected_content) in info_value.inner_text(), \
                        f"验证失败: {tab}的{item_name}不包含{str(expected_content)}, 实际内容: {info_value.inner_text()}"
                    logger.info(
                        f"验证成功: {tab}的{item_name}包含{str(expected_content)}, 实际内容: {info_value.inner_text()}")
                else:
                    expect(self.get_by_role("cell", name=item_name).locator("div")).to_be_visible()
                    assert expected_content in self.get_row_data(item_name).values(), \
                        f"验证失败: {tab}的{item_name}不包含{str(expected_content)}, 实际内容: {self.get_row_data(item_name)}"
            logger.info(f"云服务器 {tab} 详情页面信息验证成功")
            self.goto_submenu("弹性云服务器")


    def assert_ecs_tools_installed(self, name: str):
        """验证云服务器安装工具页面第一步操作是否完成"""
        # 等待安装工具第一步完成
        expect(self.get_by_text("进入VNC控制台")).to_be_visible(timeout=30000)

    def _get_available_migration_hosts(self):
        """获取可用的迁移物理机节点，排除包含is-disabled的节点

        Returns:
            可用物理机节点名称列表
        """
        available_hosts = []
        # 获取所有物理机行
        all_rows = self.locator("section").locator(".el-table__body-wrapper").locator("tr")
        row_count = all_rows.count()
        self.logger.info(f"找到 {row_count} 个tr行")

        # 备用选择器
        if row_count == 0:
            all_rows = self.locator("section").locator("tbody tr")
            row_count = all_rows.count()
            logger.info(f"使用备用选择器找到 {row_count} 个tr行")

        for i in range(row_count):
            try:
                row = all_rows.nth(i)
                first_td = row.locator("td").first

                # 获取节点名称
                host_name = first_td.inner_text().strip()

                # 获取第一个span并检查is-disabled
                first_span = first_td.locator("div label span").nth(0)
                class_attr = ""

                if first_span.count() > 0:
                    class_attr = first_span.get_attribute("class") or ""

                is_disabled = "is-disabled" in class_attr

                # 如果可用且名称不为空
                if not is_disabled and host_name:
                    available_hosts.append(host_name)

            except Exception as e:
                import traceback
                logger.error(f"处理第{i + 1}行出错: {e}")
                logger.error(traceback.format_exc())
                continue

        logger.info(f"可用节点: {available_hosts}")
        return available_hosts

    def ecs_batch_migration_names(self, names: list, pre_nodes: list, available_hosts: list):
        """批量云服务器热迁移节点检查

        Args:
            names: 云服务器名称
            available_hosts: 可用节点
        """
        unique_nodes = set(pre_nodes)

        # 场景1: 所有虚机在同一节点
        if len(unique_nodes) == 1:
            self.logger.info(f"虚机在同一节点{unique_nodes}")
            if not available_hosts:
                pytest.skip("没有可用的节点满足亲和组迁移策略")

            final_node = random.choice(available_hosts)
            self.ecs_hot_migration(names[0], final_node, m_type="手动指定")
            self.assert_status(names[0], status="迁移中", refresh=True, refresh_interval=2)
            self.assert_status(names[0])

            return names[1:], final_node

        # 场景2: 虚机分布在不同节点
        if len(unique_nodes) > 1 and len(unique_nodes) <= len(available_hosts) + 1:
            # 统计每个节点的索引
            node_indices = {}
            for idx, node in enumerate(pre_nodes):
                node_indices.setdefault(node, []).append(idx)

            # 找出现次数最少的节点
            min_node = min(node_indices, key=lambda n: len(node_indices[n]))
            min_indices = node_indices[min_node]

            # 如果有唯一节点（出现1次），只移除一个
            if len(min_indices) == 1:
                names.pop(min_indices[0])
                return names, min_node

            # 否则移除该节点的所有虚机
            [names.pop(idx) for idx in sorted(min_indices, reverse=True)]
            return names, min_node
        else:
            pytest.skip("没有可用的节点满足亲和组迁移策略")

    def wait_for_snapshot_start(self, vm_name, snap_time, timeout=3600):
        """等待快照开始创建

        Args:
            vm_name: 虚拟机名称
            snap_time: 目标时间（小时，如16表示16点）
            timeout: 最大超时时间（秒），默认为3600秒（1小时）

        Returns:
            bool: 如果成功检测到快照创建开始，返回True；否则返回False
        """
        logger.info(f"等待快照开始创建，虚拟机: {vm_name}, 目标时间: {snap_time}点")
        start_time = time.time()
        polling_started = False
        polling_duration = 180  # 3分钟
        polling_start_time = None

        # 等待到达目标时间
        while time.time() - start_time < timeout:
            # 获取当前时间
            current_hour = int(time.strftime("%H", time.localtime()))
            current_time_str = time.strftime("%H:%M:%S", time.localtime())

            # 如果当前时间还未到目标时间，继续等待
            if current_hour < snap_time:
                logger.debug(f"当前时间 {current_time_str} 小于目标时间 {snap_time}点，继续等待...")
                self.page.wait_for_timeout(3000)  # 等待3秒
                continue

            # 如果到达目标时间但轮询还未开始，开始轮询计时
            if not polling_started:
                logger.info(f"已到达目标时间 {snap_time}点，开始轮询检查虚拟机状态")
                polling_started = True
                polling_start_time = time.time()

            # 检查虚拟机状态
            try:
                self.locator(".el-icon-refresh").click()
                status = self.get_row_data(vm_name).get("状态", "")

                if "创建快照中" in status:
                    logger.info(f"检测到虚拟机 {vm_name} 开始创建快照")
                    return True
            except Exception as e:
                logger.warning(f"检查虚拟机状态时出错: {str(e)}")

            # 如果轮询时间超过3分钟，退出
            if polling_started and (time.time() - polling_start_time) > polling_duration:
                logger.warning(f"轮询 {polling_duration} 秒后仍未检测到快照创建")
                break

            # 轮询间隔3秒
            self.page.wait_for_timeout(3000)

        # 只有在真正超时后返回True
        logger.warning(f"等待快照创建状态超时, 检查快照")
        return True

    def assign_ip(self, pool: str = "public_net(基础版)", count: str = "1", method: str = "快速选择", ip: str = None):
        """
        分配公网IP
        Args:
            pool: 资源池
            count: 数量
            method: 模式
            ip: 公网IP
        """
        self.goto_service("虚拟私有云")
        self.goto_submenu("弹性公网IPv4")
        self.get_by_text("分配公网IP").first.click()
        basic_loc = self.get_by_label("分配公网IP")
        # 选择资源池
        basic_loc.get_by_placeholder("请选择").first.click()
        self.locator("li").filter(has_text=pool).click()

        # 选择数量
        basic_loc.get_by_placeholder("请选择").nth(1).click()
        self.locator("li").filter(has_text=re.compile(rf"^{count}$")).last.click()

        if count == "1":
            if method == "快速选择":
                if ip is not None:
                    self.locator("div").filter(has_text=re.compile(r"^IP$")).get_by_placeholder("请选择").click()
                    self.locator("li").filter(has_text=ip).click()
                else:
                    pass
            elif method == "手动输入":
                self.locator("label").filter(has_text="手动输入").click()
                ip_loc = self.locator("div").filter(has_text=re.compile(r"^IP$")).get_by_role("textbox")
                ip_loc.clear()
                ip_loc.fill(ip)

        self.dialog_confirm.click()
        self.assert_popup_success("执行成功")
        logger.info(f"操作完成: 存储池{pool}, 数量:{count} {ip}")

    def assert_ecs_info(self, name: str, row_name: str, exception: str):
        """验证云服务器信息
        Args:
            name: 云服务器名称
            row_name: 验证参数
            exception: 验证内容
        """
        logger.info(f"验证{name}云服务器{row_name}: {exception}")
        assert exception in self.get_row_data(name).get(row_name)

    def assert_ecs_info_not_contains(self, name: str, row_name: str, exception: str):
        """验证云服务器信息
        Args:
            name: 云服务器名称
            row_name: 验证参数
            exception: 验证内容
        """
        logger.info(f"验证{name}云服务器{row_name}: {exception}")
        assert exception not in self.get_row_data(name).get(row_name)

    def assert_image_name(self, name: str, image_name: str):
        logger.info(f"验证{name}服务器镜像名称: {image_name}")
        assert self.get_row_data(name).get("镜像名称").__eq__(image_name), f"{name}服务器镜像名称与{image_name}不一致"

    def bind_mfip(self, ip: str, network="Autotest", project="默认项目"):
        """虚机绑定mfip
        Args:
            project: 项目名称
            network: 网络名称
            ip: 公网ip地址

        """
        self.goto_service("网络设施")
        self.mfip_create(project, network, ip)
        self.assert_popup_success("执行成功")
        self.mfip_search(ip)
        # return self.get_column_data("Mfip 地址")[0]
        return self.get_row_data(ip).get("Mfip 地址")

    def stout_to_dict(self, strs):
        """将gova show字输出的符串转为字典
        Args:
            strs: 字符串
        Returns:
            字典
        """
        result = {}
        strs = strs.replace("+", "")
        strs = strs.strip()
        l = strs.split("|")
        for i, v in enumerate(l):
            if i % 3 == 1:
                result[v.strip()] = l[i + 1].strip()
            else:
                continue
        return result

    def assert_ecs_enable(self, name: str, ssh_vm, timeout=120):
        """验证云服务器可用性
        Args:
            name: 云服务器名称
            ssh_vm: 云服务器ssh对象
            """

        logger.info(f"验证{name}云服务器可用性")
        logger.info(f"验证云服务器{name} fs-agent状态为active (running)")
        self.wait_for_update(ssh_vm, "systemctl status fs-agent", "active (running)", timeout=timeout)
        stdout = ssh_vm.run("systemctl status fs-agent", return_rc=True)
        assert stdout.get("stdout").count("active (running)") \
               and stdout.get("rc") == 0, "fs-agent未启动"

        logger.info(f"验证云服务器{name} ding-agent服务状态为启动")
        self.wait_for_update(ssh_vm, "ps -ef | grep ding", "ding-agent", timeout=timeout)
        stdout = ssh_vm.run("ps -ef | grep ding", return_rc=True)
        assert stdout.get("stdout").count("ding-agent") \
               and stdout.get("rc") == 0, "ding-agent未启动"

        logger.info(f"验证云服务器{name}能ping通 100.126.255.250")
        ssh_vm.ping("100.126.255.250")

        logger.info(f"验证云服务器{name}能 curl通http://169.254.169.254:80/openstack")
        stdout = ssh_vm.run("curl http://169.254.169.254:80/openstack", return_rc=True)
        assert stdout.get("stdout").count("latest") \
               and stdout.get("rc") == 0, "curl失败"

    def wait_for_update(self, ssh_vm, cmd, expection, timeout=30, check_interval=15):
        """等待主机更新完成
        Args:
            ssh_vm: ssh对象及run的命令
            expection: 期望值
            timeout: 超时时间
            check_interval: 检查间隔
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if ssh_vm.run(cmd, return_rc=True).get('stdout').count(expection):
                break  # 已更新，退出轮询
            time.sleep(check_interval)

    def ecs_recover(self, name: str):
        """恢复弹性云服务器
        Args:
            name: 云服务器名称
        """
        self.click_action(name, "恢复")
        self.get_by_label("恢复实例").get_by_text("确定", exact=True).click()
        logger.info(f"恢复弹性云服务器: {name}")

    # @submenu("快照")
    def ecss_el_setting(self, names, enable=True):
        """设置表头列

        Args:
            names: 列名称
            enable: 是否展示，默认为True
        """
        if isinstance(names, str):
            names = [names]
        self.locator(".el-icon-setting").click()
        for name in names:
            locs = [
                self.get_by_label("checkbox-group").get_by_text(name, exact=True),
                self.get_by_label("checkbox-group").locator("div").filter(has_text=re.compile(fr"^{name}$")),
                self.get_by_label("设置表头").get_by_text(name, exact=True),
                self.get_by_text(name, exact=True),
            ]
            loc = self._find_element(locs, f"checkbox{name}")
            if enable and not loc.is_checked():
                loc.click()
            elif not enable and loc.is_checked():
                loc.click()
        try:
            self.dialog_confirm.click()
        except:
            self.locator(".el-icon-setting").click()  # 收起下拉

        self.logger.info(f"表头设置完成 {'显示' if enable else '隐藏'}{names}")

__all__ = ["EcsPageBase"]
