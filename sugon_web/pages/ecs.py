import re
from time import sleep
from playwright.sync_api import expect
from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger


class EcsPage(BasePage):
    def __init__(self, page, env):
        super().__init__(page, env)

    @submenu("弹性云服务器")
    def ecs_create(
            self,
            name,
            network= "Autotest",
            subnet= "Autotest(10",
            cluster="Autotest",
            flavor="ecs.c6.large",
            image_name="",
            os_version="centos7.9",
            login_password="sugon@20",
            vnc_password="sugon@20",
            sys_size = 100,
            **kwargs
    ):
        """创建云服务器"""
        logger.info(f"开始创建云服务器: {name}")

        # 点击新建按钮
        self.btn_create.click()
        
        # 填写基本信息
        self.get_by_role("textbox", name="请输入名称").first.fill(name)
        
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
        logger.info(f"云服务器创建请求已提交: {name}")

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
    def ecs_remove(self, name):
        """回收云服务器"""
        self.click_dropdown_option(name, "删除")
        self.dialog_confirm.click()

    @submenu("回收站")
    def ecs_delete(self, name):
        """删除云服务器"""
        logger.info(f"开始删除云服务器: {name}")
        self.click_dropdown_option(name, "删除")
        self.dialog_confirm.click()
        logger.info(f"云服务器删除请求已提交: {name}")
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
        image = image or self.storage_pool
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
            self.get_by_role("listitem").filter(has_text=f"{net}({subnet}").click()
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
    def ecs_bind_pub_ip(self, name: str, subnet: str = "Autotest", pub_net: str = "public_net(基础版)"):
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
        self.get_by_role("textbox", name="请输入主机名称",exact=True).fill(hostname)
        # self.locator("//*[text()='新主机名']/following-sibling::div//input").fill(hostname)
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