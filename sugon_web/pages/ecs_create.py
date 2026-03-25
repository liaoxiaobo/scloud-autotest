import re
from playwright.sync_api import expect

from sugon_web.config.config import Config
from sugon_web.pages.ecs import EcsPage
from sugon_web.common.base import submenu
from sugon_web.utils.logger import logger
from sugon_web.utils.util import random_data


class EcsCreatePage(EcsPage):

    @submenu("弹性云服务器")
    def ecs_create(self, basic=None, storage=None, network=None, manage=None, advanced=None, **kwargs):
        """创建云服务器

        支持两种调用方式：
        1. v2 式 (字典传参): ecs_create(basic={}, storage={}, network={}, manage={}, advanced={})
        2. v1 式 (扁平传参): ecs_create(name, image_source="镜像", count=1, ...)
        """
        # 1. 检测并转换参数格式 (如果是 v1 扁平化传参)
        if isinstance(basic, str) or "name" in kwargs:
            # 提取 v1 参数
            v1_name = basic if isinstance(basic, str) else kwargs.get("name")
            v1_image_source = storage if isinstance(storage, str) else kwargs.get("image_source", "镜像")
            v1_count = network if isinstance(network, int) else kwargs.get("count", 1)

            # 其余可能的 v1 参数从 args 偏移或 kwargs 获取 (模仿 EcsPage.ecs_create)
            v1_network = kwargs.get("network", "Autotest")
            v1_subnet = kwargs.get("subnet", "Autotest(10")
            v1_cluster = kwargs.get("cluster", "Autotest")
            v1_flavor = kwargs.get("flavor", "ecs.c6.large")
            v1_image_name = kwargs.get("image_name", "")
            v1_os_version = kwargs.get("os_version", "centos7.9")
            v1_login_pwd = kwargs.get("login_password", "admin1234@sugon")
            v1_vnc_pwd = kwargs.get("vnc_password", "sugon@20")
            v1_sys_size = kwargs.get("sys_size", 25)
            v1_enable_ipv6 = kwargs.get("enable_ipv6", False)

            # 构造成 v2 的字典结构
            basic = {"name": v1_name, "数量": v1_count, "集群": v1_cluster, "规格": {"基础规格": v1_flavor}}
            storage = {
                "镜像": {"来源": v1_image_source, "镜像名称": v1_image_name, "ISO": v1_os_version},
                "系统盘": v1_sys_size
            }
            network = {
                "networks": [{"network": v1_network, "subnet": v1_subnet}],
                "enable_ipv6": v1_enable_ipv6
            }
            manage = {"login_type": "密码登录", "login_pwd": v1_login_pwd, "vnc_pwd": v1_vnc_pwd}
            advanced = {}

        # 点击创建按钮
        self.btn_create.click()
        # 填写基本信息
        basic_info = self._basic_info(basic)
        # 填写存储信息
        self._storage_info(storage)
        # 填写网络信息
        self._network_info(network)
        # 填写管理信息
        self._manage_info(manage)
        # 填写高级配置
        self._advanced_info(advanced)

        # 点击创建按钮
        self.get_by_text("立即创建").click()
        logger.info(f"云服务器创建请求已提交: {basic_info.get('name')}，数量: {basic_info.get('count')}")
        return basic_info

    # 保持别名兼容
    ecs_create_v2 = ecs_create

    def _basic_info(self, basic):
        """填写弹性云服务器基本信息
        Args:
            basic: 基本配置信息
                {
                "数量": 1,
                "集群": "Autotest",
                "物理机": "master02",
                "规格": {"基础规格": "ecs.m6.xlarge"}
                "规格": {"自定义规格": {"cpu": "2", "mem": "4"}}
                }
        """
        if basic:
            logger.info(f"basic信息: {basic}")
            name = basic.get("name") if basic.get("name") else random_data('string', 4)
            count = basic.get("数量") if basic.get("数量") else 1
        else:
            name = random_data('string', 4)
            count = 1
        # 填写名称
        self.get_by_role("textbox", name="请输入名称").first.fill(name)

        # 设置创建数量（如果大于1）
        if count > 1:
            self.get_by_role("spinbutton").first.fill(str(count))

        # 选择规格
        flavor_info = basic.get("规格") if basic and basic.get("规格") else {"基础规格": "ecs.c6.large"}
        self._select_flavor(flavor_info)

        # 选择集群
        cluster_name = basic.get("集群") if basic and basic.get("集群") else "Autotest"
        self._select_cluster(cluster_name)

        # 选择物理机
        host = basic.get("物理机") if basic and basic.get("物理机") else ""
        if host:
            self._select_physical_host(host)

        # 选择标签
        labels = basic.get("标签") if basic and basic.get("标签") else []
        if labels:
            self._select_label(labels)
        return {"name": name, "count": count}

    def _storage_info(self, storage):
        """填写弹性云服务器存储配置
        Args:
            storage: 基本配置信息
                {
                "存储池": xstor/usan,
                "密钥": "UUID",
                "镜像":{
                    image_source: "镜像" / "空启动" / "快照" / "ISO"
                    image_name: "镜像名称" / "快照名称" / "ISO名称"
                    os_version: 操作系统版本，默认为"centos7.9"
                    },
                "系统盘": 25,
                "数据盘": [
                    {"vol_type": "ceph-type", "size": "20", "count": "1"},
                    {"vol_type": "usan-type", "size": "20", "count": "1"},
                    ]
                }
        """
        if storage:
            logger.info(f"storage信息: {storage}")
        # 选择存储池
        storage_pool = storage.get("存储池") if storage and storage.get("存储池") else self.storage_pool
        self._select_storage_pool(storage_pool)

        # 选择密钥
        encryption_key = storage.get("密钥") if storage and storage.get("密钥") else ""
        if encryption_key and self.storage_pool in ["xstor-test", "usan-test"]:
            self._enable_encryption(encryption_key)

        # 选择镜像
        image_info = storage.get("镜像") if storage and storage.get("镜像") else {"来源": "镜像", "镜像名称": "", "ISO": "centos7.9"}
        self._select_image(image_info)

        # 设置系统盘大小（云硬盘来源时不需要设置）
        image_source = image_info.get("来源", "镜像")
        if image_source != "云硬盘":
            size = storage.get("系统盘", 25) if storage and storage.get("系统盘") else 25
            self._set_sys_volume(size)

        # 设置数据盘
        data_disks = storage.get("数据盘") if storage and storage.get("数据盘") else []
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
        if network and network.get("安全组"):
            self._select_security_group(network.get("安全组"))

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

    def _select_flavor(self, flavor_info: dict):
        """选择规格
        Args:
            flavor_info: 规格信息
            {"基础规格": {"flavor": "ecs.c6.Autotest}}
            {"自定义规格": {"cpu": "2", "mem": "4"}}
        """
        # 根据规格类型选择不同的处理方式
        flavor_type = flavor_info.keys()
        logger.info(f"规格: {list(flavor_type)[0]}")
        if "自定义规格" in flavor_type:
            # 选择自定义规格
            self.get_by_role("radio", name="自定义规格").click()
            flavor = flavor_info.get("自定义规格")
            # 填写CPU和内存
            logger.info(f"CPU: {flavor.get('CPU')}, 内存: {flavor.get('Mem')}")
            self.locator("div:nth-child(4) > .el-form-item__content > .el-input > .el-input__inner").fill(flavor.get("CPU"))
            # self.get_by_text("CPU", exact=True).locator("xpath=./../../following-sibling::div[1]/div[1]").fill(flavor.get("CPU"))
            # self.locator("label").filter(has_text="CPU").first.locator("xpath=./../following-sibling::div[1]/div[1]").fill(flavor.get("CPU"))
            self.locator("div:nth-child(5) > .el-form-item__content > .el-input > .el-input__inner").fill(flavor.get("Mem"))
            # self.get_by_text("内存", exact=True).locator("xpath=../../following-sibling::div/div").fill(flavor.get("Mem"))
        else:
            # 选择基础规格
            self.get_by_role("radio", name="基础规格").click()
            # 点击选择计算规格按钮
            self.get_by_text("选择计算规格").first.click()

            # 搜索选择规格
            flavor = flavor_info.get("基础规格")
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
        # self.locator("#cloud-container-content span").filter(has_text="标签设置").locator("i").click()
        # self.get_by_role("dialog").locator("span").filter(has_text="条/页20条/页50条/页100条/页").locator("i").click()
        # self.get_by_text("50条/页").click()
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
                image_source: "镜像" / "空启动" / "快照" / "ISO" / "云硬盘"
                image_name: "镜像名称" / "快照名称" / "ISO名称"
                os_version: 操作系统版本，默认为"centos7.9"
            }
        """
        image_name = image_info.get("镜像名称", "") or self.storage_pool
        image_source = image_info.get("来源", "镜像")
        os_version = image_info.get("ISO")
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

    def _select_iso_image(self, iso_name):
        """来源选择 ISO"""
        logger.info(f"使用ISO镜像: {iso_name}")

        # 选择ISO
        self.get_by_role("textbox", name="请选择", exact=True).nth(3).click()
        self.locator("li").filter(has_text="ISO").click()

        if iso_name:
            # 定位并选择ISO行
            self.get_by_role("row", name=iso_name).get_by_role("radio").click()
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
        root_file = "IMAGE_CDB_20220910.qcow2"
        root_dir = "/cbr_test_root"

        data_vols = sorted([vol for vol in vols.keys() if vol != sys_disk])
        for vol_name, size in sorted(vols.items()):
            if vol_name == sys_disk:
                # 系统盘: 直接写数据到预定目录，不用分区/格式化/挂载
                curr_file = root_file
                curr_dir = root_dir
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
