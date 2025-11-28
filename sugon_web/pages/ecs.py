import re
import time
from time import sleep
from playwright.sync_api import expect
from sugon_web.pages.ops import OpsPage
from sugon_web.common.base import submenu
from sugon_web.utils.logger import logger


class EcsPage(OpsPage):
    def __init__(self, page, env):
        super().__init__(page, env)

    @submenu("弹性云服务器")
    def ecs_create(
            self,
            name,
            count=1,
            network="Autotest",
            subnet="Autotest(10",
            cluster="Autotest",
            flavor="ecs.c6.large",
            image_name="",
            os_version="centos7.9",
            login_password="admin1234@sugon",
            vnc_password="sugon@20",
            sys_size=100,
            **kwargs
    ):
        """创建云服务器

        Args:
            name: 云服务器名称
            count: 创建数量，默认为1
            network: 网络，默认为"Autotest"
            subnet: 子网，默认为"Autotest(10"
            cluster: 集群，默认为"Autotest"
            flavor: 规格，默认为"ecs.c6.large"
            image_name: 镜像名称，默认为空（使用storage_pool）
            os_version: 操作系统版本，默认为"centos7.9"
            login_password: 登录密码，默认为"admin1234@sugon"
            vnc_password: VNC密码，默认为"sugon@20"
            sys_size: 系统盘大小，默认为100
        """
        logger.info(f"开始创建云服务器: {name}，数量: {count}")

        # 点击新建按钮
        self.btn_create.click()

        # 填写基本信息
        self.get_by_role("textbox", name="请输入名称").first.fill(name)

        # 设置创建数量（如果大于1）
        if count > 1:
            self.get_by_role("spinbutton").first.fill(str(count))

        # 选择集群
        self._select_cluster(cluster)

        # 选择规格
        self._select_flavor(flavor)

        # 选择镜像
        self._select_image(image_name, os_version)

        # 配置系统盘
        self._set_sys_volume(sys_size)

        # 选择网络
        self._select_network(network, subnet)

        # 设置密码
        self._set_passwords(login_password, vnc_password)

        # 提交创建
        self.get_by_text("立即创建").click()
        self.wait_for_operation_complete()
        logger.info(f"云服务器创建请求已提交: {name}，数量: {count}")

    def _select_cluster(self, cluster):
        """选择集群"""
        self.get_by_role("textbox", name="请选择集群").click()
        self.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(cluster)}$")).click()

    def _select_flavor(self, flavor):
        """选择规格"""
        self.locator(".el-icon-circle-plus-outline").first.click()
        self.search(flavor)
        self.get_by_role("row").filter(has_text=re.compile(rf"{re.escape(flavor)}")).get_by_role("radio").click()
        self.get_by_role("dialog").get_by_text("确定").click()

    def _select_image(self, image_name, os_version):
        """选择镜像"""
        image_name = image_name or self.storage_pool

        # 选择存储池
        self.get_by_role("textbox", name="请选择", exact=True).nth(2).click()
        self.get_by_text(self.storage_pool).click()
        
        # 选择操作系统版本
        self.get_by_role("textbox", name="请选择操作系统版本").click()
        self.get_by_text(os_version).click()
        
        # 选择64位
        self.get_by_role("textbox", name="请选择操作系统位数").click()
        self.get_by_role("listitem").filter(has_text=re.compile(r"^64位$")).click()
        
        # 选择具体镜像
        self.get_by_role("textbox", name="请选择镜像").click()
        self.get_by_title(image_name, exact=True).click()

    def _set_sys_volume(self, size, mode="厚置备"):
        """系统盘配置"""
        if "xbd" in self.storage_pool:
            self.get_by_role("textbox", name="请选择", exact=True).nth(4).click()
            self.get_by_text(mode).click()
        self.get_by_role("spinbutton").nth(1).fill(str(size))


    def _select_network(self, network, subnet):
        """选择网络"""
        # 选择网络
        self.get_by_role("textbox", name="请选择网络").click()
        self.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(network)}$")).click()
        
        # 选择子网
        self.get_by_role("textbox", name="请选择子网").click()
        self.get_by_role("listitem").filter(has_text=re.compile(rf"{re.escape(subnet)}")).locator("span").click()   # 去掉^和$，进行模糊匹配

    def _set_passwords(self, login_password, vnc_password):
        """设置密码"""
        # 设置登录密码
        self.get_by_role("textbox", name="请输入密码").fill(login_password)
        self.locator("div").filter(has_text=re.compile(r"^确认登录密码$")).get_by_role("textbox").fill(login_password)
        
        # 设置VNC密码
        self.get_by_role("textbox", name="VNC密码最长为8位").fill(vnc_password)
        self.locator("div").filter(has_text=re.compile(r"^确认VNC密码$")).get_by_role("textbox").fill(vnc_password)

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
            self.click_dropdown_option(names, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("回收站")
    def ecs_delete(self, names, secure=False):
        """删除回收站中的云服务器资源，支持单个和批量操作

        Args:
            names: 云服务器名称（字符串）或云服务器名称列表（列表）
            secure: 是否安全删除（彻底删除），默认为False（普通删除）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击批量删除按钮
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            # 根据参数选择删除类型
            delete_option = "安全删除" if secure else "删除"

            # 使用BasePage中的通用下拉菜单选项点击方法
            self.click_dropdown_option(names, delete_option)

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()
        sleep(6)    # 临时方案: 等待删除弹窗自动关闭，规避元素未消失导致的定位异常

    def assert_ecs_info(self, name: str, row_name: str, exception: str):
        """验证云服务器信息
        Args:
            name: 云服务器名称
            row_name: 验证参数
            exception: 验证内容
        """
        logger.info(f"验证{name}云服务器{row_name}: {exception}")
        assert self.get_row_data(name).get(row_name).__contains__(exception)

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

    @submenu("弹性云服务器")
    def ecs_edit(self, name: str, newname: str):
        """修改指定云服务器名称
        Args:
            name: 云服务器名称
            newname: 新的云服务器名称
        """
        logger.info(f"云服务器{name}：编辑修改为{newname}")
        self.click_dropdown_option(name, "编辑")
        self.get_by_role("textbox", name="请输入实例名称").fill(newname)
        self.dialog_confirm.click()

    @submenu("弹性云服务器")
    def ecs_vnc(self, name: str, vncpwd: str, pwd: str=None):
        """修改VNC密码
        Args：
            name: 云服务器名称
            password: VNC登录密码
            pwd: 登录密码（预留）
        """
        logger.info(f"云服务器{name}：登录VNC")
        self.click_dropdown_option(name, "登录VNC")
        self.switch_to_new_tab()
        self.locator("#app iframe").content_frame.get_by_role("textbox", name="密码：").fill(vncpwd)
        self.locator("#app iframe").content_frame.get_by_role("button", name="确认").click()

    @submenu("弹性云服务器")
    def ecs_rebuild(self, name: str, version: str, bit: str, image: str):
        """重建云主机
        Args：
            name: 云服务器名称
            version: 重建云主机的操作系统版本
            bit: 重建云主机的操作系统位数
            image: 重建云主机的镜像源
        """
        logger.info(f"重建云主机：{name}，操作系统版本：{version}，操作系统位数：{bit}，镜像：{image}")
        self.click_dropdown_option(name, "重建云主机")
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
        logger.info(f"克隆云服务器{name}：-->{clonename}")
        self.click_dropdown_option(name, "克隆")
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
                    self.click_dropdown_option(key, "选择密钥")
                    # 需补充选择密钥步骤
                    self.get_by_text(value).click()
                    self.dialog_confirm.click()
        except:
            pass
        # 点击确定 克隆
        self.dialog_confirm.click()

    @submenu("弹性云服务器")
    def ecs_operations(self, name: str, operation: str):
        """操作
        Args:
            name: 云服务器名称
            operation: 操作选项
        """
        logger.info(f"{name}云服务器：{operation}")
        try:
            self.click_dropdown_option(name, operation)
        except  Exception as e:
            logger.error(f"云服务器{name}：{operation}失败")
            raise e
        if operation == "重启":
            self.get_by_text("重启 取消", exact=True).get_by_text("重启", exact=True).click()
        elif operation == "强制重启":
            self.get_by_text("强制重启 取消", exact=True).get_by_text("强制重启", exact=True).click()
        elif operation in ["恢复运行", "暂停", "取消暂停"]:
            self.get_by_label(operation, exact=True).get_by_text("确定", exact=True).click()
        else:
            self.dialog_confirm.click()

    @submenu("弹性云服务器")
    def ecs_reset_state(self, name: str):
        """重置状态
        Args:
            name: 云服务器名称
        """
        logger.info(f"云服务器{name}：重置状态")
        try:
            self.click_dropdown_option(name, "重置状态")
            self.dialog_confirm.click()
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
            TODO: 加速模式、分配方式不同场景加载网卡的用例
        """
        logger.info(f"云服务器{name}：加载网卡")
        try:
            self.click_dropdown_option(name, "加载网卡")
            # 选择网络
            logger.info(f"云服务器{name}：选择网络{net}")
            self.get_by_role("textbox", name="请选择网络").click()
            self.get_by_text(net, exact=True).click()
            # 选择子网
            logger.info(f"云服务器{name}：选择子网{subnet}")
            self.get_by_role("textbox", name="请选择子网").click()
            self.get_by_role("listitem").filter(has_text=f"{subnet}(").click()
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
        logger.info(f"云服务器{name}卸载网卡：{net}")
        self.click_dropdown_option(name, "卸载网卡")
        # 选择网络
        self.get_by_role("textbox", name="请选择网络").click()
        self.get_by_role("listitem").filter(has_text=net).click()
        self.dialog_confirm.click()

    @submenu("弹性云服务器")
    def ecs_bind_pub_ip(self, name: str, subnet: str = "Autotest", pub_net: str = "public"):
        """绑定公网IP
        Args:
            name: 云服务器名称
            subnet: 子网
            pub_net: 公网资源池
        """
        logger.info(f"云服务器{name}：绑定公网IP：{subnet}")
        self.click_dropdown_option(name, "绑定公网IP")
        # 选择端口
        self.get_by_role("row").filter(has_text=subnet).get_by_role("radio").click()
        self.get_by_text("下一步", exact=True).click()
        # 选择资源池
        self.get_by_role("dialog", name="绑定公网IP").get_by_placeholder("请选择").click()
        self.get_by_text(pub_net).click()
        # 选择公网ip
        ip_info = self.get_by_role("row").filter(has_text="关闭").first.get_by_role("cell")
        ip_info.first.click()
        ip = ip_info.nth(1).text_content()
        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()
        return str(ip)

    @submenu("弹性云服务器")
    def ecs_unbind_pub_ip(self, name: str, IP_addr: str):
        """解绑公网IP
        Args:
            name: 云服务器名称
            IP_addr: 公网ip地址
        """
        logger.info(f"云服务器{name}：解绑公网IP：{IP_addr}")
        self.click_dropdown_option(name, "解绑公网IP")
        self.get_by_role("dialog", name="解除绑定公网IP").get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(has_text=IP_addr).click()
        self.get_by_label("解除绑定公网IP", exact=True).get_by_text("确定").click()

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

        self.click_dropdown_option(name, "修改规格")
        try:
            if spec_type:
                classify = spec.get("classify", "计算型")
                flavor_name = spec.get("flavor_name")
                logger.info(f"云服务器{name}修改规格为{classify} {cpu}核{mem}GiB")
                
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
                     .and_(self.get_by_role("row").filter(has_text="标准"))
                     .get_by_role("radio").click())
                
                self.dialog_confirm.click()
                
            else:  # 自定义规格
                logger.info(f"云服务器{name}修改自定义规格为{cpu}核{mem}GiB")
                self.get_by_role("radio").filter(has_text="自定义规格").click()
                
                # 填写CPU和内存
                self.get_by_role("dialog", name="修改规格").get_by_role("textbox").nth(1).fill(cpu)
                self.get_by_role("dialog", name="修改规格").get_by_role("textbox").nth(2).fill(mem)
                
                # 点击确定按钮
                self.get_by_label("修改规格").get_by_text("确定").click()
                
        except Exception as e:
            logger.error(f"云服务器{name}修改规格失败: {e}")
            raise e

    @submenu("弹性云服务器")
    def ecs_modify_pwd(self, name: str, pwd: str, confirm: str):
        """修改密码
        Args:
            name: 云服务器名称
            pwd: 密码
            confirm: 确认密码
        """
        logger.info(f"云服务器{name}修改密码为{pwd}")
        self.click_dropdown_option(name, "修改密码")
        try:
            self.locator("div").filter(has_text=re.compile(r"^密码$")).get_by_role("textbox").fill(pwd)
            self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(confirm)
            self.get_by_label("修改密码").get_by_text("确定").click()
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
        logger.info(f"云服务器{name}修改密码为{vncpwd}")
        self.click_dropdown_option(name, "修改VNC密码")
        if not self.get_by_role("switch").locator("span").is_enabled():
            self.get_by_role("switch").locator("span").click()
        try:
            self.get_by_role("textbox", name="VNC密码最长为8位").fill(vncpwd)
            self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(confirmpwd)
            self.get_by_label("修改VNC密码").get_by_text("确定").click()
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
        logger.info(f"云服务器{name}修改主机名称为{hostname}")
        self.click_dropdown_option(name, "修改主机名")
        self.get_by_placeholder("请输入主机名称").fill(hostname)
        self.get_by_label("修改主机名").get_by_text("确定").click()

    @submenu("弹性云服务器")
    def ecs_time_synchronize(self, name: str, time_server: str, interval: str):
        """时钟同步
        Args:
            name: 云服务器名称
            time_server: 时间服务器
            interval: 同步间隔
        """
        logger.info(f"弹性云服务器{name}时钟同步")
        self.click_dropdown_option(name, "时间同步服务器")
        self.get_by_role("textbox", name="例：10.0.13.24或*sugoncloud.").fill(time_server)
        logger.info(f"弹性云服务器{name}时钟同步，同步间隔为{interval}秒")
        self.get_by_label("时间同步服务器").locator("form div").filter(has_text="时间同步间隔(秒)").get_by_role("textbox").fill(interval)
        self.get_by_label("时间同步服务器").locator("div").filter(has_text="确定").nth(3).click()

    @submenu("弹性云服务器")
    def ecs_bind_unbind_group(self, name: str, operation: str, group_name: str):
        """解绑/解绑亲和组
        Args:
            name: 云服务器名称
            group_name: 亲和组名称
        """
        logger.info(f"云服务器{name}绑定亲和组{group_name}")
        self.click_dropdown_option(name, operation)
        self.get_by_role("dialog", name=operation).get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(has_text=group_name).click()
        # self.dialog_confirm()
        self.get_by_label(operation).get_by_text("确定").click()

    @submenu("镜像服务")
    def ecs_image_delete(self, image_name):
        """删除指定名称的镜像

        Args:
            image_name: 镜像名称
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(image_name, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    def bind_mfip(self, ip: str, project="默认项目"):
        """虚机绑定mfip
        Args:
            project: 项目名称
            ip: 公网ip地址

        """
        self.goto_service("网络设施")
        self.mfip_create(project, "Autotest", ip)
        self.assert_popup_success("执行成功")
        self.mfip_search(ip)
        return self.get_column_data("Mfip 地址")[0]

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

    def assert_ecs_enable(self, name: str, ssh_vm, timeout=60):
        """验证云服务器可用性
        Args:
            name: 云服务器名称
            ssh_vm: 云服务器ssh对象
            """

        logger.info(f"验证{name}云服务器可用性")
        logger.info(f"验证云服务器{name} fs-agent状态为active (running)")
        self.wait_for_update(ssh_vm.run("systemctl status fs-agent", return_rc=True), "active (running)", timeout=timeout)
        stdout = ssh_vm.run("systemctl status fs-agent", return_rc=True)
        assert stdout.get("stdout").count("active (running)")\
               and stdout.get("rc") == 0, "fs-agent未启动"

        logger.info(f"验证云服务器{name} ding-agent服务状态为启动")
        self.wait_for_update(ssh_vm.run("ps -ef | grep ding", return_rc=True), "ding-agent")
        stdout = ssh_vm.run("ps -ef | grep ding", return_rc=True)
        assert stdout.get("stdout").count("ding-agent") \
               and stdout.get("rc") == 0, "ding-agent未启动"

        logger.info(f"验证云服务器{name}能ping通 100.126.255.250")
        stdout = ssh_vm.run("ping -c 3 100.126.255.250", return_rc=True)
        assert stdout.get("stdout").count("3 received, 0% packet loss") \
               and stdout.get("rc") == 0, "ping 100.126.255.250失败"

        logger.info(f"验证云服务器{name}能curl通http://169.254.169.254:80/openstack")
        stdout = ssh_vm.run("curl http://169.254.169.254:80/openstack", return_rc=True)
        assert stdout.get("stdout").count("latest") \
               and stdout.get("rc") == 0, "curl失败"

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
            self.page.wait_for_timeout(1000)

            # 根据操作类型点击相应的选项
            self._click_batch_operation_option(operation)

            # 确认操作
            self._confirm_batch_operation(operation)

            # 等待操作完成
            self.wait_for_operation_complete()
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
            self.get_by_label("批量重启").locator("div").filter(has_text="确定").nth(3).click()
        elif operation == "批量关机":
            self.locator("div:nth-child(2) > div > .cloud-button-btn > span").click()
        elif operation == "批量启动":
            self.locator("div:nth-child(2) > div > .cloud-button-btn > span").click()
        elif operation == "批量强制重启":
            self.get_by_label("批量强制重启").get_by_text("确定").click()
        else:
            # 默认使用通用确认按钮
            self.dialog_confirm.click()

    def wait_for_update(self, ssh_vm, expection, timeout=30, check_interval=15):
        """等待主机更新完成
        Args:
            ssh_vm: ssh对象及run的命令
            expection: 期望值
            timeout: 超时时间
            check_interval: 检查间隔
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if ssh_vm.get("stdout").count(expection):
                break  # 主机名已更新，退出轮询
            time.sleep(check_interval)

    def ecs_recover(self, name: str):
        """恢复弹性云服务器
        Args:
            name: 云服务器名称
        """
        logger.info(f"恢复弹性云服务器: {name}")
        self.click_dropdown_option(name, "恢复")
        self.get_by_label("恢复实例").get_by_text("确定", exact=True).click()

    @submenu("回收站")
    def ecs_recover_delete(self, name: str, delete_volume: bool = False, release_ip: bool = False):
        """安全删除云服务器，可选择是否删除数据盘和释放公网IP

        Args:
            name: 云服务器名称
            delete_volume: 是否删除云服务器挂载的数据盘，默认为True
            release_ip: 是否释放云服务器绑定的公网IP，默认为True
        """
        logger.info(f"开始安全删除云服务器: {name}")

        # 点击指定云服务器的操作按钮
        self.click_dropdown_option(name, "删除")

        # 根据参数选择删除选项
        if delete_volume:
            # 选择删除云服务器挂载的数据盘
            self.locator("label").filter(has_text="删除云服务器挂载的数据盘").locator("span").nth(1).click()
            logger.info(f"已选择删除云服务器{name}挂载的数据盘")

        if release_ip:
            # 选择释放云服务器绑定的公网IP
            self.locator("label").filter(has_text="释放云服务器绑定的公网IP").locator("span").nth(1).click()
            logger.info(f"已选择释放云服务器{name}绑定的公网IP")

        # 确认删除
        self.get_by_label("删除", exact=True).get_by_text("确定").click()

        # 等待操作完成
        self.wait_for_operation_complete()
        logger.info(f"云服务器安全删除请求已提交: {name}")

    @submenu("回收站")
    def ecs_recover_batch_delete(self, names, secure=False):
        """删除回收站中的弹性云服务器资源，支持单个和批量操作

        Args:
            names: 弹性云服务器名称（字符串）或弹性云服务器名称列表（列表）
            secure: 是否安全删除（彻底删除），默认为False（普通删除）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击批量删除按钮
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            # 根据参数选择删除类型
            delete_option = "安全删除" if secure else "删除"

            # 使用BasePage中的通用下拉菜单选项点击方法
            self.click_dropdown_option(names, delete_option)

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("弹性云服务器")
    def ecss_create(self, name, snapshot_name, desc="", data_disk=False):
        """为指定弹性云服务器创建快照

        Args:
            name: 云服务器名称
            snapshot_name: 快照名称
            desc: 快照描述，默认为空
            data_disk: 是否快照数据盘
        """
        # 点击云服务器操作按钮
        self.click_dropdown_option(name, "新建快照")

        # 定位快照创建对话框
        dialog = self.get_by_role("dialog")

        # 填写快照名称
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^快照名称$")).get_by_role("textbox")
        name_input.fill(snapshot_name)

        # 填写描述
        desc_input = dialog.locator("textarea")
        desc_input.fill(desc)

        if data_disk:
            # 选择快照数据盘
            self.page.locator("form span").nth(3).click()

        # 点击确定按钮创建快照
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("快照")
    def ecss_delete(self, snapshot_names):
        """删除弹性云服务器快照，支持单个和批量操作

        Args:
            snapshot_names: 快照名称（字符串）或快照名称列表（列表）
        """
        if isinstance(snapshot_names, list):
            # 批量操作模式
            self.select_rows_by_names(snapshot_names)

            # 点击批量删除按钮
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_dropdown_option(snapshot_names, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

        self.logger.info(f"云服务器快照删除请求已提交: {snapshot_names}")

    @submenu("快照")
    def ecss_edit(self, name, new_name, new_desc):
        """修改指定云服务器快照的名称和描述

        Args:
            name: 原快照名称
            new_name: 新的快照名称
            new_desc: 新的描述信息
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(name, "修改")

        # 定位对话框中的输入框
        dialog = self.get_by_role("dialog")
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^快照名称$")).get_by_role("textbox")
        desc_input = dialog.locator("textarea")

        # 填写新的名称和描述
        name_input.fill(new_name)
        desc_input.fill(new_desc)

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("快照")
    def ecss_restore(self, snapshot_name):
        """使用指定快照还原云服务器

        Args:
            snapshot_name: 快照名称
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(snapshot_name, "还原快照")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

