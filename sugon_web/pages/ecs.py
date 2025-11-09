import re
from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger


class EcsPage(BasePage):
    def __init__(self, page, env):
        super().__init__(page, env)

    @submenu("弹性云服务器")
    def ecs_create(
            self,
            name,
            network,
            subnet,
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
        self.get_by_title(image_name).click()

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
        self.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(subnet)}$")).locator("span").click()

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
