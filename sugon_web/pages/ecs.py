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
        self.get_by_text(self.storage_pool, exact=True).click()
        
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
    def ecs_vnc(self, name: str, vncpwd: str):
        """修改VNC密码
        Args：
            name: 云服务器名称
            password: VNC登录密码
        """
        logger.info(f"云服务器{name}：登录VNC")
        self.click_dropdown_option(name, "登录VNC")
        self.switch_to_new_tab()
        self.wait_for_page_ready()
        self.locator("#app iframe").content_frame.get_by_role("textbox", name="密码：").fill(vncpwd)
        self.locator("#app iframe").content_frame.get_by_role("button", name="确认").click()
        self.wait_for_page_ready()
        assert self.locator("#app iframe").content_frame.locator("canvas").is_visible()
        self.switch_to_tab(0)

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
        checked_subnet = ""
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
            checked_subnet = self.get_by_role("listitem").filter(has_text=f"{subnet}(").inner_text().split("(")[1].split(".0/")[0]
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
        loc = self.get_by_label("时间同步服务器").locator("form div").filter(has_text="时间同步间隔(秒)").get_by_role("textbox")
        loc.clear() # 清空输入框默认数据
        loc.fill(interval)
        self.get_by_label("时间同步服务器").locator("div").filter(has_text="确定").nth(3).click()

    @submenu("弹性云服务器")
    def ecs_bind_unbind_group(self, names, operation: str, group_name: str):
        """解绑/解绑亲和组
        Args:
            name: 云服务器名称
            group_name: 亲和组名称
        """
        logger.info(f"云服务器{names}{operation}{group_name}")
        for name in names:
            self.ecs_bind_unbind_affinity_group(name, operation, group_name)
            self.assert_popup_success(f"{name}实例{operation}成功")

    def ecs_bind_unbind_affinity_group(self, name, operation: str, group_name: str):
        self.click_dropdown_option(name, operation)
        self.get_by_role("dialog", name=operation).get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(has_text=group_name).click()
        self.dialog_confirm.click()
        # self.get_by_label(operation).get_by_text("确定").click()

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
        assert stdout.get("stdout").count("active (running)")\
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
            self.wait_for_operation_complete()

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
    def ecs_create_image(self, name: str, imnage_name: str):
        """弹性云服务器新建镜像

        Args:
            name: 弹性云服务器
            imnage_name: 镜像名称
        """
        logger.info(f"开始创建云服务器镜像: {imnage_name}")
        # 点击新建镜像
        self.click_dropdown_option(name, "新建镜像")

        # 填写镜像名称
        self.locator("div").filter(has_text=re.compile(r"^镜像名称$")).get_by_role("textbox").fill(imnage_name)

        # 提交创建
        self.dialog_confirm.click()

        logger.info(f"云服务器镜像创建请求已提交: {imnage_name}")

    @submenu("亲和组")
    def ecs_create_affinity_group(
            self,
            name: str,
            policy="亲和"
    ):
        """创建亲和组

        Args:
            name: 亲和组名称
            policy: 亲和策略，默认为"亲和"，可选"反亲和"
        """
        logger.info(f"开始创建亲和组: {name}, 策略: {policy}")

        # 点击新建按钮
        self.btn_create.click()

        # 填写亲和组名称
        self.get_by_placeholder("请输入亲和组名称").fill(name)

        # 选择策略
        self.get_by_placeholder("请选择策略").click()
        self.locator("li").filter(has_text=re.compile(rf"^{re.escape(policy)}$")).click()

        # 提交创建
        self.dialog_confirm.click()

        logger.info(f"亲和组创建请求已提交: {name}, 策略: {policy}")

    @submenu("亲和组")
    def ecs_delete_affinity_group(self, names):
        """删除亲和组，支持单个和批量操作

        Args:
            names: 亲和组名称列表（列表）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击批量删除按钮
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            # self.click_dropdown_option(names, "删除")
            self.get_by_role("row").filter(has_text=names).locator("i").click()

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

    @submenu("快照策略")
    def ecss_policy_create(self, name, hours, enabled=False, cycle_days=1, retention_type="按数量", retention_value=1,
                           snapshot_data_disk=False):
        """创建云服务器快照策略

        Args:
            name: 策略名称
            enabled: 是否启用策略，默认为False
            hours: 执行时间的小时列表，如[1, 2]表示01:00和02:00执行
            cycle_days: 快照周期（天），默认为1
            retention_type: 保留规则类型，"按数量"、"按时间"或"永久保存"，默认为"按数量"
            retention_value: 保留值，数量或天数，默认为1
            snapshot_data_disk: 是否快照数据盘，默认为False
        """
        # 使用BasePage中的通用创建按钮
        self.btn_create.click()

        # 填写策略名称
        self.get_by_label("新建策略").get_by_role("textbox").fill(name)

        # 设置启用状态
        if enabled:
            self.get_by_role("switch").locator("span").click()

        # 设置执行时间
        if hours:
            for hour in hours:
                self.get_by_text(f"{hour:02d}:00", exact=True).click()

        # 设置快照周期（天）
        self.locator("form div").filter(has_text="快照周期 天").get_by_role("spinbutton").fill(str(cycle_days))

        # 设置是否快照数据盘
        if snapshot_data_disk:
            self.locator("form div").filter(has_text="是否快照数据卷").locator("span").nth(2).click()

        # 设置保留规则
        self.get_by_role("radio", name=retention_type).click()

        if retention_type != "永久保存":
            # 设置保留值
            self.locator("form div").filter(has_text="保留规则按数量 按时间 天 永久保存").get_by_role("spinbutton").fill(str(retention_value))

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

        self.logger.info(f"云服务器快照策略创建请求已提交: {name}")

    @submenu("快照策略")
    def ecss_policy_delete(self, names):
        """删除云服务器快照策略，支持单个和批量操作

        Args:
            names: 策略名称（字符串）或策略名称列表（列表）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击批量删除按钮
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            # 使用BasePage中的通用下拉菜单选项点击方法
            self.click_dropdown_option(names, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

        self.logger.info(f"云服务器快照策略删除请求已提交: {names}")



    @submenu("弹性云服务器")
    def ecs_batch_migration(self, names, migration_type="热迁移", bandwidth="全速", cpu_auto=False):
        """批量迁移云服务器

        Args:
            names: 云服务器名称列表
            migration_type: 迁移方式，默认为"热迁移"，可选"冷迁移"
            bandwidth: 带宽设置，默认为"全速"
            cpu_auto: CPU自动收敛
        """
        logger.info(f"开始批量迁移云服务器: {names}, 迁移方式: {migration_type}, 带宽: {bandwidth}")

        # 选择指定的云服务器并点击批量迁移
        self.ecs_batch_operations(names, "批量迁移")

        # 选择迁移方式
        self.get_by_placeholder("请选择迁移方式").click()
        self.locator("li").filter(has_text=re.compile(rf"^{migration_type}$")).click()

        # 选择带宽
        if migration_type == "热迁移":
            self.get_by_placeholder("请选择带宽").click()
            self.locator("li").filter(has_text=bandwidth).click()
        if cpu_auto and migration_type == "热迁移":
            # 设置开关
            loc = self.get_by_role("switch").locator("span")
            if not loc.is_enabled():
                loc.click()

        # 确认迁移
        # self.get_by_label("批量迁移").get_by_text("确定").click()
        self.dialog_confirm.click()
        # 等待操作完成
        self.wait_for_operation_complete()

        # 验证成功提示
        self.assert_popup_success(f"批量{migration_type}命令下发成功")

        logger.info(f"批量迁移操作完成: {names}, 迁移方式: {migration_type}")


    @submenu("弹性云服务器")
    def ecs_hot_migration(self, name, target_host=None, bandwidth="全速", cpu_auto=False):
        """云服务器热迁移

        Args:
            name: 云服务器名称
            target_host: 目标物理机，如"master03.cloud.local"
            bandwidth: 迁移速率，默认为"全速"
            cpu_auto: 是否启用CPU自动收敛，默认为False
        """
        logger.info(f"开始热迁移云服务器: {name}, 目标主机: {target_host}, 带宽: {bandwidth}")
        checked_host = None
        # 点击云服务器操作按钮，选择热迁移
        self.click_dropdown_option(name, "热迁移")

        # 选择目标物理机
        self.get_by_placeholder("请选择目标物理机").click()

        # 等待下拉列表加载完成
        self.wait_for_operation_complete()

        # 获取所有下拉选项
        all_host_options = self.locator("li").filter(has_text="CPU剩余量")
        options_count = all_host_options.count()
        available_hosts = []

        # 遍历所有选项，获取文本并排除包含"当前节点"的选项
        for i in range(options_count):
            option = all_host_options.nth(i)
            option_text = option.inner_text()
            if "当前节点" not in option_text:
                available_hosts.append({"element": option, "text": option_text})
        logger.info(f"可操作下拉选项: {[x.get('text') for x in available_hosts]}")
        # 如果没有可用物理机，抛出异常
        if not available_hosts:
            error_msg = "没有可用的物理机可供选择"
            logger.error(error_msg)
            raise Exception(error_msg)

        # 尝试选择指定的目标物理机
        if target_host:
            for host in available_hosts:
                if target_host in host["text"]:
                    host["element"].click()
                    logger.info(f"已选择指定的目标物理机: {host['text']}")
                    checked_host = host["text"]
                    break

            # 如果指定的目标物理机不可用，选择第一个可用的
            if not checked_host:
                logger.warning(f"指定的目标物理机 {target_host} 不可用，选择第一个可用物理机")
                available_hosts[0]["element"].click()
                logger.info(f"已选择第一个可用的物理机: {available_hosts[0]['text']}")
                checked_host = available_hosts[0]["text"]
        else:
            # 如果没有指定目标物理机，选择第一个可用的
            available_hosts[0]["element"].click()
            logger.info(f"已选择第一个可用的物理机: {available_hosts[0]['text']}")
            checked_host = available_hosts[0]["text"]

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

        # 验证成功提示
        self.assert_popup_success("热迁移命令下发成功")

        logger.info(f"云服务器热迁移请求已提交: {name}，目标主机: {checked_host}")
        return checked_host.split("CPU剩余量")[0].strip()

    @submenu("弹性云服务器")
    def ecs_cold_migration(self, name, target_host=None):
        """云服务器冷迁移

        Args:
            name: 云服务器名称
            target_host: 目标物理机，如"master01.cloud.local"
        """
        logger.info(f"开始热迁移云服务器: {name}, 目标主机: {target_host}")
        checked_host = None
        # 点击云服务器操作按钮，选择热迁移
        self.click_dropdown_option(name, "冷迁移")

        # 选择目标物理机
        self.get_by_placeholder("请选择物理机").click()

        # 等待下拉列表加载完成
        self.wait_for_operation_complete()

        # 获取所有下拉选项
        all_host_options = self.locator("li").filter(has_text="CPU剩余量")
        options_count = all_host_options.count()
        available_hosts = []

        # 遍历所有选项，获取文本并排除包含"当前节点"的选项
        for i in range(options_count):
            option = all_host_options.nth(i)
            option_text = option.inner_text()
            if not option.get_attribute("class").count("is-disabled"):
                logger.info(f"可操作下拉选项class属性: {option.get_attribute('class')}")
                available_hosts.append({"element": option, "text": option_text})
        logger.info(f"可操作下拉选项: {[x.get('text') for x in available_hosts]}")
        # 如果没有可用物理机，抛出异常
        if not available_hosts:
            error_msg = "没有可用的物理机可供选择"
            logger.error(error_msg)
            raise Exception(error_msg)

        # 尝试选择指定的目标物理机
        if target_host:
            for host in available_hosts:
                if target_host in host["text"]:
                    host["element"].click()
                    logger.info(f"已选择指定的目标物理机: {host['text']}")
                    checked_host = host["text"]
                    break

            # 如果指定的目标物理机不可用，选择第一个可用的
            if not checked_host:
                logger.warning(f"指定的目标物理机 {target_host} 不可用，选择第一个可用物理机")
                available_hosts[0]["element"].click()
                logger.info(f"已选择第一个可用的物理机: {available_hosts[0]['text']}")
                checked_host = available_hosts[0]["text"]
        else:
            # 如果没有指定目标物理机，选择第一个可用的
            available_hosts[0]["element"].click()
            logger.info(f"已选择第一个可用的物理机: {available_hosts[0]['text']}")
            checked_host = available_hosts[0]["text"]

        # 确认冷迁移
        self.dialog_confirm.click()

        # 验证成功提示
        self.assert_popup_success("冷迁移命令下发成功")

        logger.info(f"云服务器热迁移请求已提交: {name}，目标主机: {checked_host}")
        return checked_host.split("CPU剩余量")[0].strip()

    @submenu("弹性云服务器")
    def ecs_mount_to_server(self, volume_name, vm_name):
        """将云硬盘挂载到指定服务器

        Args:
            volume_name: 云硬盘名称
            vm_name: 服务器名称
        """
        # 点击挂载云硬盘选项
        self.click_dropdown_option(vm_name, "挂载云硬盘")

        # 搜索云硬盘
        self.get_by_placeholder("搜索(云硬盘名称）").fill(volume_name)
        self.get_by_label("挂载云硬盘").get_by_text("搜索").click()

        # 选择云硬盘
        self.get_by_role("row").filter(has_text=volume_name).get_by_role("radio").click()

        # 确认挂载
        self.get_by_label("挂载云硬盘").get_by_text("挂载", exact=True).click()

        # 等待操作完成
        self.wait_for_operation_complete()

        self.assert_popup_success(f"挂载云硬盘到虚拟机{vm_name}成功")


    @submenu("弹性云服务器")
    def ecs_unmount_from_server(self, volume_name, vm_name):
        """从指定服务器卸载云硬盘

        Args:
            volume_name: 云硬盘名称
            vm_name: 服务器名称
        """

        # 点击卸载云硬盘选项
        self.click_dropdown_option(vm_name, "卸载云硬盘")

        # 选择云硬盘
        self.get_by_placeholder("请选择云硬盘").click()
        self.locator("span").filter(has_text=re.compile(rf"^{volume_name}$")).click()

        # 确认卸载
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_operation_complete()

        self.assert_popup_success(f"从虚拟机{vm_name}分离云硬盘")

    @submenu("弹性云服务器")
    def ecs_expand_system_disk(self, name: str, new_size: str):
        """扩容弹性云服务器系统盘

        Args:
            name: 云服务器名称
            new_size: 新的系统盘大小（GiB）
        """
        logger.info(f"开始扩容云服务器系统盘: {name}，扩容至: {new_size}GiB")

        # 点击下拉菜单中的"系统盘扩容"选项
        self.click_dropdown_option(name, "系统盘扩容")

        # 设置新的系统盘大小
        self.get_by_label("系统盘扩容").get_by_role("spinbutton").fill(new_size)

        # 确认扩容
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_operation_complete()
        self.assert_popup_success(f"{name}实例扩容成功")
        logger.info(f"云服务器系统盘扩容成功: {name}")

    @submenu("弹性云服务器")
    def ecs_modify_cpu_qos(self, name: str, priority: str = "低", ceiling: str = "0.2"):
        """修改云服务器CPU QoS

        Args:
            name: 云服务器名称
            level: CPU QoS级别，默认为"低"
            weight: CPU权重值，默认为0.2
        """
        logger.info(f"开始修改云服务器{name}的CPU QoS: 级别={priority}, 权重={ceiling}")

        # 点击指定云服务器的操作按钮
        self.click_dropdown_option(name, "修改CPU QoS")

        # 选择CPU QoS级别
        self.get_by_label("修改CPU QoS").get_by_placeholder("请选择").click()
        self.get_by_text(priority, exact=True).click()

        # 设置CPU权重
        self.get_by_label("修改CPU QoS").get_by_role("spinbutton").fill(ceiling)

        # 确认修改
        self.dialog_confirm.click()
        logger.info(f"云服务器{name}的CPU QoS修改请求已提交")

        self.wait_for_operation_complete()
        self.assert_popup_success(f"设置cpu-qos成功")

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
        self.locator("div:nth-child(3) > .cloud-button-btn").first.click()

        # 设置每台服务器的启动顺序
        self.get_by_role("dialog", name="设置启动顺序").get_by_role("textbox").first.fill(str(order))

        # 设置启动延迟时间
        self.locator("form div").filter(has_text="启动延迟时间(秒)").get_by_role("textbox").fill(delay)

        # 确认设置
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_operation_complete()
        self.assert_popup_success("执行成功")

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
        self.wait_for_page_ready()

        logger.info(f"成功进入云服务器{name}详情页")
    def ecs_back_to_list(self):
        """返回云服务器列表页
        """
        logger.info(f"返回云服务器列表页面")
        # 点击指定云服务器的详情链接
        self.locator(".el-icon-back").click()
        # 等待详情页面加载完成
        self.wait_for_page_ready()

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
        self.click_dropdown_option(name, "挂载CD-ROM")

        # 等待挂载CD-ROM对话框出现
        self.wait_for_page_ready()

        # 选择CD-ROM类型（如果需要选择）
        try:
            # 根据类型iso名称选择对应的单选按钮
            self.get_by_placeholder("搜索(镜像名称)").fill(iso_name)
            self.get_by_label("挂载CD-ROM").get_by_text("搜索").click()
            self.get_by_label("挂载CD-ROM").get_by_role("radio").first.click()
        except:
            logger.warning(f"未找到CD-ROM '{iso_name}' ，默认选择第一个CD-ROM")
            self.get_by_label("挂载CD-ROM").get_by_text("重置").click()
            self.get_by_label("挂载CD-ROM").get_by_role("row").filter(has_text="autotest").get_by_role("radio").first.click()

        # 点击挂载按钮
        self.get_by_label("挂载CD-ROM").get_by_text("挂载", exact=True).click()

        # 等待操作完成
        self.wait_for_operation_complete()

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
        self.click_dropdown_option(name, "卸载CD-ROM")

        # 等待挂载CD-ROM对话框出现
        self.wait_for_page_ready()

        # 选择CD-ROM
        self.get_by_placeholder("请选择CD-ROM").click()
        self.locator("li").filter(has_text=cdrom_name).click()

        # 点击挂载按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_operation_complete()

    def assert_ecs_details_info(self, names, info_items: dict, tab: str="详情"):
        """验证云服务器详情页面中的信息

        Args:
            name: 云服务器名称
            tab: 页签名称
            info_items: 需要验证的信息项字典，格式为 {"信息项名称": "期望内容"}
                       例如: {"启动顺序": "3", "启动延迟时间(秒)": "20"}
        """
        logger.info(f"验证云服务器 {names} 的 {tab} 页签信息")
        for name in names:
            self.ecs_to_details(name)

            logger.info(f"点击 {tab} 页签")
            self.get_by_role("tab", name=tab).click()
            self.wait_for_page_ready()
            sleep(1)
            # 逐个验证信息项
            for item_name, expected_content in info_items.items():
                logger.info(f"验证 {tab} 页签的 {item_name}: {str(expected_content)}")
                # 定位信息项
                info_item = self.get_by_text(item_name)
                # 获取信息项的值
                info_value = info_item.locator("xpath=./following-sibling::*").first

                # 验证信息项的值是否包含期望内容
                assert info_value.inner_text().__contains__(str(expected_content)), \
                    f"验证失败: {tab} 的 {item_name} 不包含 {str(expected_content)}, 实际内容: {info_value.inner_text()}"

        logger.info(f"云服务器 {tab} 详情页面信息验证成功")

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

        # 点击设置启动顺序按钮
        self.get_by_text("设置关机顺序").first.click()

        # 设置每台服务器的启动顺序
        self.get_by_label("设置关机顺序").get_by_role("textbox").first.fill(str(order))

        # 设置启动延迟时间
        self.locator("form div").filter(has_text="关机延迟时间(秒)").get_by_role("textbox").fill(delay)

        # 确认设置
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_operation_complete()
        self.assert_popup_success("执行成功")

        logger.info(f"批量设置云服务器关机顺序完成: {names}")