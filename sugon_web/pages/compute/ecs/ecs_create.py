import re
from typing import Any, NotRequired, TypedDict
from playwright.sync_api import expect


from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


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

# 单张网卡配置，描述要绑定的网络与子网，支持 IPv4 手动分配和机密互联开关。
EcsNetworkItemConfig = TypedDict(
    "EcsNetworkItemConfig",
    {
        "network": str,
        "subnet": str,
        "ip_allocation": str,  # "自动分配" 或 "手动分配"
        "ip_index": int,  # 手动分配时选择第几个可用 IP，从 0 开始
        "enable_confidential_interconnect": bool,  # 是否开启加密网卡（机密互联）
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


class EcsCreateMixin(BasePage):
    """ECS 创建向导相关操作。"""
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
        self.get_by_text("立即创建").click(timeout=120000)
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

        # 选择集群
        cluster_name = _config_get(basic, "cluster", default="Autotest")
        self._select_cluster(cluster_name)

        # 选择规格
        flavor_info = _config_get(basic, "flavor", default={"base": "ecs.c6.Autotest"})
        self._select_flavor(flavor_info)

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
        image_info = _config_get(storage, "image", default={"source": "镜像", "name": f"{storage_pool}"})
        self._select_image(
            image_source=_config_get(image_info, "source", default="镜像"),
            image_name=_config_get(image_info, "name", default=storage_pool)
        )

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
        disable_default_sg = _config_get(network, "disable_default_sg", default=False)
        if security_groups:
            self._select_security_group(security_groups)
        elif disable_default_sg:
            self._select_security_group([], deselect_default=True)
            logger.info("已取消默认安全组 default")

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
        self.logger.info(f"已选择标签: {labels}")


    def _select_storage_pool(self, storage_pool_name):
        """选择存储池"""
        storage_pool_name = storage_pool_name or self.storage_pool

        # 选择存储池
        self.get_by_role("textbox", name="请选择", exact=True).nth(2).click()
        # self.page.wait_for_load_state("networkidle")
        self.get_by_text(storage_pool_name, exact=True).click()
        self.storage_pool = storage_pool_name
        logger.info(f"已选择存储池: {storage_pool_name}")


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


    def _select_image(self, image_source="镜像", image_name="", **kwargs):
        """选择镜像，支持多种来源方式
        Args:
            image_name: 镜像名称或特定镜像源所需的标识
            image_source: 镜像来源方式，可选值：
                - "镜像": 使用存储池中的镜像（默认）
                - "空启动": 使用空启动模式
                - "快照": 使用快照作为镜像源
                - "ISO": 使用ISO镜像
            **kwargs: 其他参数，如快照ID、ISO大小等
        """
        image_name = image_name or self.storage_pool
        logger.info(f"开始选择镜像: image_source={image_source}, image_name={image_name}")

        try:
            # 选择镜像来源
            self.get_by_role("textbox", name="请选择", exact=True).nth(3).click()
            self.locator("li").filter(has_text=re.compile(rf"^{image_source}$")).click()
            logger.info(f"已选择镜像来源: {image_source}")

            supported_sources = ["镜像", "快照", "ISO", "云硬盘"]
            if image_source in supported_sources and image_name:
                try:
                    self._select_from_named_drawer(
                        drawer_title=f"选择{image_source}",
                        item_name=image_name,
                        reset_first=(image_source == "ISO"),
                    )
                except AssertionError as e:
                    error_msg = str(e)
                    if "抽屉未关闭" in error_msg or "未找到" in error_msg:
                        logger.warning(f"_select_from_named_drawer 失败，尝试备用选择方式: {error_msg}")
                        self._select_image_from_drawer_fallback(image_source, image_name)
                    else:
                        raise
            elif image_source == "空启动":
                pass
            else:
                logger.warning(f"不支持的镜像来源: {image_source}，使用默认镜像方式")

        except Exception as e:
            logger.error(f"选择镜像失败: {str(e)}")
            raise e

    def _select_image_from_drawer_fallback(self, image_source, image_name):
        """备用方式：从抽屉中选择镜像（处理 cl-table + el-radio 组合）

        针对 _select_from_named_drawer 在 cl-table 自定义渲染的 el-radio 上
        force=True 点击无法触发 Vue input 事件的问题，使用非 force 点击。
        """
        drawer_title = f"选择{image_source}"
        logger.info(f"使用备用方式选择镜像: {drawer_title}, {image_name}")

        # 打开抽屉
        self.get_by_text(drawer_title).first.click()
        self.wait_for_page_ready()

        drawer = self.locator(f"div[role='dialog'][aria-label='{drawer_title}']:visible")
        expect(drawer).to_be_visible()

        # 搜索镜像
        search_input = drawer.locator(".cloud-table-header-right input[placeholder='搜索（名称）']")
        if search_input.count() > 0:
            search_input.fill(image_name)
            drawer.locator(".cloud-table-header-right").get_by_text("搜索", exact=True).click()
            self.wait_for_page_ready()

        # 找到目标行
        row = drawer.locator(
            "xpath=.//div[contains(@class,'el-table__body-wrapper')]//tr[.//td[2]//*[normalize-space(text())="
            f"'{image_name}'] or .//td[2][normalize-space(.)='{image_name}']]"
        ).first
        expect(row).to_be_visible(timeout=5000)

        # 尝试多种选择方式（不使用 force=True，让 Vue 事件正常触发）
        select_locators = [
            row.locator(".el-radio__inner"),
            row.locator("label[role='radio']"),
            row.get_by_role("radio"),
            row.locator("td").first,
            row.locator("td").nth(1),
            row,
        ]

        confirm_btn = drawer.get_by_text("确定", exact=True)
        last_error = None

        for select_locator in select_locators:
            if select_locator.count() == 0:
                continue
            try:
                # 不使用 force=True，确保 Vue 事件正常触发
                select_locator.click()
                self.page.wait_for_timeout(800)
                confirm_btn.click()
                try:
                    expect(drawer).not_to_be_visible(timeout=10000)
                    logger.info(f"备用方式选择镜像成功: {image_name}")
                    return
                except AssertionError:
                    last_error = AssertionError(f"{drawer_title} 抽屉未关闭")
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise AssertionError(f"备用方式未找到 {drawer_title} 中的 {image_name} 可选节点")


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
            self.page.wait_for_timeout(2000)

            # 等待下拉列表出现并定位选项
            # 限定到刚打开的那个下拉面板（最后一个可见面板），避免匹配到其他/残留下拉导致误判
            logger.info(f"查找数据盘类型: {vol_type}")
            dropdown = self.page.locator(".el-select-dropdown:visible").last
            option = dropdown.locator(".el-select-dropdown__item", has_text=vol_type).first
            try:
                option.wait_for(state="visible", timeout=5000)
            except Exception:
                raise AssertionError(f"未找到匹配的数据盘类型: {vol_type}")
            logger.info(f"找到并点击数据盘类型: {vol_type}")
            option.click()

            # 设置数据盘大小 - 使用多种定位方式
            self.get_by_role("spinbutton").nth(idx*2).fill(vol_size)
            self.get_by_role("spinbutton").nth(idx*2+1).fill(vol_count)

            logger.info(f"设置数据盘: 类型={vol_type}, 大小={vol_size}GiB, 数量={vol_count}")


    def _select_single_network(self, net_config):
        """选择单个网卡配置

        Args:
            net_config: 网卡配置字典
                - network: 网络名称
                - subnet: 子网名称（支持前缀匹配，如 "sci_vpc1(" 匹配 "sci_vpc1(176.176.20.0/24)"）
                - ip_allocation: IPv4 分配方式，可选 "自动分配"（默认）或 "手动分配"
                - ip_index: 手动分配时选择第几个可用 IP，从 0 开始，默认 0
                - enable_confidential_interconnect: 是否开启加密网卡（机密互联），
                  默认 False。注意：必须先选择手动分配才能开启此开关
        """
        network_name = net_config.get("network")
        subnet_name = net_config.get("subnet")
        ip_allocation = net_config.get("ip_allocation", "自动分配")
        ip_index = net_config.get("ip_index", 0)
        enable_sci = net_config.get("enable_confidential_interconnect", False)

        # 选择网络
        self.get_by_role("textbox", name="请选择网络").click()
        self.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(network_name)}$")).click()
        logger.info(f"选择网络: {network_name}")

        # 选择子网 - 子网选项可能包含额外文本（如IP段），用部分匹配
        self.get_by_role("textbox", name="请选择子网").click()
        # 等待下拉选项出现
        self.page.wait_for_timeout(800)
        # 使用更宽松的匹配：子网名称是选项的一部分
        # 子网选项在 el-select-dropdown 中，可能不在 listitem role 下
        dropdown = self.page.locator(".el-select-dropdown:visible").last
        # 先检查下拉是否已打开
        if dropdown.count() == 0:
            self.logger.warning("子网下拉未打开，重试点击")
            self.get_by_role("textbox", name="请选择子网").click()
            self.page.wait_for_timeout(800)
            dropdown = self.page.locator(".el-select-dropdown:visible").last

        # 获取所有选项文本用于调试
        all_items = dropdown.locator(".el-select-dropdown__item").all()
        item_texts = []
        for item in all_items:
            try:
                item_texts.append(item.inner_text().strip())
            except Exception:
                pass
        self.logger.info(f"子网下拉选项: {item_texts}")

        # 尝试匹配
        option = dropdown.locator(".el-select-dropdown__item").filter(
            has_text=re.compile(rf"{re.escape(subnet_name)}")
        ).first

        # 如果找不到匹配的选项，尝试第一个选项（兜底）
        if option.count() == 0 and len(all_items) > 0:
            self.logger.warning(f"未找到匹配 '{subnet_name}' 的子网选项，尝试第一个选项")
            option = all_items[0]

        option.click()
        logger.info(f"选择子网: {subnet_name}")

        # 处理 IPv4 分配方式
        if ip_allocation == "手动分配":
            # 1. 先选择 "手动分配" 下拉选项
            # 找到 IPv4 分配方式列的下拉框（placeholder="请选择方式"）
            allocation_select = self.page.locator(".el-select").filter(
                has=self.page.locator("input[placeholder='请选择方式']")
            ).first
            allocation_select.click()
            self.page.wait_for_timeout(500)

            # 选择 "手动分配" 选项（teleport 到 body 级）
            alloc_dropdown = self.page.locator(".el-select-dropdown:visible").last
            alloc_dropdown.locator(".el-select-dropdown__item").filter(
                has_text=re.compile(r"^手动分配$")
            ).first.click()
            logger.info("选择 IPv4 分配方式: 手动分配")

            # 等待手动分配弹窗出现
            self.page.wait_for_timeout(800)

            # 2. 在手动分配弹窗中选择 IP
            # 使用包含特定 MAC 输入框 placeholder 的 .el-dialog 来精确定位弹窗
            dialog = self.page.locator(".el-dialog").filter(
                has=self.page.locator("input[placeholder='请按照6c:88:14:dd:25:59的格式输入']")
            ).last
            expect(dialog).to_be_visible(timeout=10000)

            # 选择 IP 分配方式：保持默认"快速选择"（dialog 打开时默认已选中），无需切换
            # 弹窗内 el-form-item 顺序固定：子网(0) → IP(1) → MAC(2)
            # IP 的 form-item 内有 el-select（非 disabled），子网的 select 是 disabled
            ip_select = dialog.locator(".el-form-item").nth(1).locator(".el-select").first
            expect(ip_select).to_be_visible(timeout=8000)
            ip_select.click()
            # 等待下拉面板出现：用 :visible 找当前可见的 dropdown
            ip_dropdown = self.page.locator(".el-select-dropdown:visible").last
            ip_dropdown.locator(".el-select-dropdown__item").first.wait_for(state="visible", timeout=10000)
            ip_options = ip_dropdown.locator(".el-select-dropdown__item").all()
            if len(ip_options) == 0:
                raise AssertionError("手动分配弹窗内未加载到任何可用 IP 选项")
            selected_ip = ip_options[0].inner_text().strip()
            ip_options[0].click()
            logger.info(f"选择第 0 个可用 IP: {selected_ip}")

            # 点击确定关闭弹窗（cl-button 渲染为 div，用 get_by_text 兼容 button/div）
            confirm_btn = dialog.get_by_text("确定", exact=True).last
            confirm_btn.click()

            # 校验弹窗确实因 dialogOK 成功而关闭。
            # 关键：绝不能用 close_dialog_if_exists 强关——若 IP/MAC 校验未过弹窗仍在，
            # 强关会触发 handleNetworkDialogClose 把 allocationMode 重置回"自动分配('1')"，
            # 使机密互联开关变灰、后续点击 30s 超时（这正是之前误判为"环境/DPDK"的根因）。
            try:
                expect(
                    self.page.locator(
                        "input[placeholder='请按照6c:88:14:dd:25:59的格式输入']"
                    )
                ).to_be_hidden(timeout=8000)
            except Exception:
                raise AssertionError(
                    "手动分配弹窗点击确定后未关闭，通常是 IP/MAC 校验未通过；"
                    "弹窗未正常关闭会导致 allocationMode 被重置、机密互联开关无法启用"
                )
            logger.info("手动分配弹窗已关闭（IP 选择已生效，分配方式保持手动分配）")
            self.page.wait_for_timeout(1500)

            # 3. 开启加密网卡（机密互联）开关
            # 前端规则：开关在 allocationMode=='1'(自动) / 架构 aarch64 / DPDK 开启 时被 disabled。
            # 走到这里 allocationMode 已是手动分配('2')，若开关仍 disabled 多半是 DPDK/架构限制，
            # 此时显式报错给出明确原因，而不是盲点 30s 超时。
            if enable_sci:
                # 等待表格重新渲染完成
                self.page.wait_for_selector(".el-table .el-switch", timeout=10000, state="visible")

                sci_switch = self.page.locator(".el-table .el-switch").first
                if sci_switch.count() == 0:
                    sci_switch = self.page.locator(".el-switch").first
                expect(sci_switch).to_be_visible(timeout=8000)

                is_disabled = sci_switch.evaluate(
                    "el => el.classList.contains('is-disabled')"
                )
                if is_disabled:
                    raise AssertionError(
                        "机密互联开关处于禁用状态：IPv4 已为手动分配，"
                        "故禁用原因应为所选集群/主机 DPDK 已开启或架构为 aarch64，"
                        "需改用 DPDK 关闭且非 aarch64 的集群"
                    )

                is_checked = sci_switch.evaluate(
                    "el => el.classList.contains('is-checked')"
                )
                if not is_checked:
                    # 绕过 .el-table__fixed-right 遮罩层：使用 dispatchEvent 模拟完整点击事件链。
                    # 点击根节点 .el-switch 会被遮罩层拦截；dispatchEvent 可触发原生事件并冒泡到 Vue 监听器。
                    sci_switch.evaluate(
                        """el => {
                            const clickEvent = new MouseEvent('click', {
                                bubbles: true,
                                cancelable: true,
                                view: window
                            });
                            el.dispatchEvent(clickEvent);
                        }"""
                    )
                    # 等待 Vue 状态更新并验证开关确实已开启
                    self.page.wait_for_timeout(1000)
                    is_checked_after = sci_switch.evaluate(
                        "el => el.classList.contains('is-checked')"
                    )
                    if not is_checked_after:
                        raise AssertionError(
                            "机密互联开关点击后未开启：dispatchEvent 未触发 Vue 状态更新，"
                            "可能需要检查遮罩层或前端事件绑定"
                        )
                    logger.info("已开启加密网卡（机密互联）开关")
                else:
                    logger.info("加密网卡开关已处于开启状态")

                # 4. 关键：重新打开并关闭手动分配弹窗，强制前端重新同步 network_msg。
                # 背景：第一次 dialogOK 中 form_msg.expandNetwork = $clone(network_msg) 会断开
                # network_msg 与 expandNetwork 的引用。随后开关点击只更新 expandNetwork，
                # 导致提交时用的 network_msg 仍为 encrypted=false。重新打开弹窗点确定会再次
                # 执行 network_msg = form_msg.expandNetwork，使 network_msg 同步到最新状态。
                allocation_select.click()
                self.page.wait_for_timeout(500)
                alloc_dropdown = self.page.locator(".el-select-dropdown:visible").last
                manual_option = alloc_dropdown.locator(".el-select-dropdown__item").filter(
                    has_text=re.compile(r"^手动分配$")
                ).first
                manual_option.click()
                self.page.wait_for_timeout(800)
                dialog = self.page.locator(".el-dialog").filter(
                    has=self.page.locator("input[placeholder='请按照6c:88:14:dd:25:59的格式输入']")
                ).last
                # 若点击已选中选项未打开弹窗，先切到自动分配再切回手动分配
                if dialog.count() == 0 or not dialog.is_visible():
                    logger.warning("二次点击手动分配未打开弹窗，尝试先切自动分配再切回手动分配")
                    alloc_dropdown.locator(".el-select-dropdown__item").filter(
                        has_text=re.compile(r"^自动分配$")
                    ).first.click()
                    self.page.wait_for_timeout(500)
                    allocation_select.click()
                    self.page.wait_for_timeout(500)
                    alloc_dropdown = self.page.locator(".el-select-dropdown:visible").last
                    alloc_dropdown.locator(".el-select-dropdown__item").filter(
                        has_text=re.compile(r"^手动分配$")
                    ).first.click()
                    self.page.wait_for_timeout(800)
                    dialog = self.page.locator(".el-dialog").filter(
                        has=self.page.locator("input[placeholder='请按照6c:88:14:dd:25:59的格式输入']")
                    ).last

                expect(dialog).to_be_visible(timeout=10000)
                # 二次弹窗打开后，必须重新选择 IP，否则表单校验不通过、弹窗无法关闭
                # 弹窗内 el-form-item 顺序固定：子网(0) → IP(1) → MAC(2)
                ip_select = dialog.locator(".el-form-item").nth(1).locator(".el-select").first
                expect(ip_select).to_be_visible(timeout=8000)
                ip_select.click()
                ip_dropdown = self.page.locator(".el-select-dropdown:visible").last
                ip_dropdown.locator(".el-select-dropdown__item").first.wait_for(state="visible", timeout=10000)
                ip_options = ip_dropdown.locator(".el-select-dropdown__item").all()
                if len(ip_options) == 0:
                    raise AssertionError("二次弹窗内未加载到任何可用 IP 选项")
                selected_ip = ip_options[0].inner_text().strip()
                ip_options[0].click()
                logger.info(f"二次弹窗重新选择第 0 个可用 IP: {selected_ip}")
                self.page.wait_for_timeout(500)

                confirm_btn = dialog.get_by_text("确定", exact=True).last
                confirm_btn.click()
                try:
                    expect(
                        self.page.locator(
                            "input[placeholder='请按照6c:88:14:dd:25:59的格式输入']"
                        )
                    ).to_be_hidden(timeout=8000)
                except Exception:
                    raise AssertionError(
                        "二次确认手动分配弹窗点击确定后未关闭，network_msg 可能未同步"
                    )
                logger.info("已重新同步手动分配状态，确保 network_msg 包含机密互联配置")
                self.page.wait_for_timeout(800)
        else:
            logger.info("IPv4 分配方式保持默认: 自动分配")
            # 自动分配模式下不能开启机密互联（前端会 disabled）
            if enable_sci:
                logger.warning("自动分配模式下无法开启机密互联，已忽略 enable_confidential_interconnect=True")


    def _select_security_group(self, security_group, deselect_default=True):
        """选择安全组，默认先取消 default 安全组。

        Args:
            security_group: 要绑定的安全组名称列表。
            deselect_default: 是否先取消默认安全组 default 的勾选。
        """
        if deselect_default:
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
        """设置密钥对。

        按"密钥对"表单项标签锚定下拉框，避免依赖随表单条件渲染而漂移的 nth(4) 占位符位置。
        用 label.el-form-item__label 含"密钥对"定位，排除"密钥对登录"等单选标签。
        """
        self.locator(".el-form-item").filter(
            has=self.locator("label.el-form-item__label").filter(has_text="密钥对")
        ).get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(
            has_text=re.compile(rf"^{re.escape(login_key)}$")
        ).click()


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


    def _set_sound_type(self, sound_type):
        """设置声卡类型

        Args:
            sound_type: 声卡类型，如 "none"、"AC97"、"HDA(ICH6)"、"HDA(ICH9)"
        """
        self.get_by_placeholder("请选择声卡类型").click()
        self.locator("li").filter(has_text=re.compile(rf"^{re.escape(sound_type)}$")).click()
        logger.info(f"已设置声卡类型为: {sound_type}")
