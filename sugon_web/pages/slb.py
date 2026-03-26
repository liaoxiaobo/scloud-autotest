import re
from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.util import random_data


class SlbPage(BasePage):
    """
    负载均衡页面
    """

    @submenu("负载均衡（基础版）")
    def slb_create(self, name=None, version="V2", cluster=None, vpc=None,
                   ip_type="自动分配", ip_address=None, spec=None, desc=None, 
                   ha_enable=False):
        """创建负载均衡
        
        Args:
            name: 负载均衡名称，可以为None，将会自动生成随机名称
            version: 版本类型，"V1" 或 "V2"，默认"V2"
            cluster: 集群名称，V2版本适用
            vpc: 虚拟私有云(VPC)名称
            ip_type: IP分配方式，"自动分配"、"快速选择" 或 "手动输入"
            ip_address: 当ip_type为"快速选择"或"手动输入"时的IP地址，此时为必填项
            spec: 规格设置，V2版本适用 (例如: "slb.d6.large 2核 4GiB 内网带宽")
            desc: 描述信息
            ha_enable: 是否启用HA开关 (True=开启, False=不开启)
        """
        self.btn_create.click()

        # 填写名称
        if not name:
            name = f"slb-{random_data()}"
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").click()
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(name)

        # 选择版本类型
        self.get_by_role("radio", name=version).click()

        # HA开关设置（对V1和V2通用）
        ha_switch = self.get_by_role("switch")
        if ha_switch.is_visible():
            is_checked = ha_switch.get_attribute("aria-checked") == "true"
            if is_checked != ha_enable:
                ha_switch.locator("span").click()

        # 只有在V2时才需要选择集群和规格
        if version == "V2":
            # 集群选择
            if cluster:
                self.locator("form div").filter(has_text="基础设置 名称 版本类型 V1 V2 HA 集群").get_by_placeholder("请选择").click()
                self.locator("li").filter(has_text=re.compile(rf"^{re.escape(cluster)}$")).click()

        # 网络配置 - VPC
        if vpc:
            if version == "V1":
                self.locator("#cloud-container-content").get_by_placeholder("请选择").click()
            else:
                self.locator("form div").filter(has_text="网络配置 子网网络 子网 IPv4 IPv6").get_by_placeholder("请选择").click()
            # 使用包含名称的项
            self.get_by_text(vpc).first.click()

        # 网络配置 - IP分配方式
        if ip_type == "自动分配":
            self.locator("label").filter(has_text="自动分配").click()
        elif ip_type in ["快速选择", "手动输入"]:
            # 当IP分配方式为手动分配的时候才能快速选择或手动输入ip，且ip是必填
            if not ip_address:
                raise ValueError("在IPv4分配方式为手动分配且选择快速选择或手动输入时，IP是必填项")
                
            # 先点击“手动分配”
            self.locator("label").filter(has_text="手动分配").click()
            # 在 IPv4 分配方式为手动分配的时候，选择具体的子选项并填入 IP
            self.locator("label").filter(has_text=ip_type).click()
            
            # 锚定包含 “快速选择/手动输入” 单选按钮的表单项容器
            container = self.locator("div.el-form-item__content").filter(has=self.get_by_role("radio", name="快速选择"))
            
            if ip_type == "快速选择":
                # 点击该容器内的下拉框。
                container.get_by_placeholder("请选择").click()
                self.get_by_text(ip_address, exact=True).click()
            elif ip_type == "手动输入":
                # 同理填入手动输入框
                container.get_by_placeholder("请输入", exact=True).click()
                container.get_by_placeholder("请输入", exact=True).fill(ip_address)

        # 规格设置 - 只有在V2才需要选择
        if version == "V2" and spec:
            self.get_by_role("row", name=spec).get_by_role("radio").click()

        # 描述
        if desc:
            self.locator("textarea").click()
            self.locator("textarea").fill(desc)

        # 提交
        self.btn_submit.click()
        
        self.logger.info(f"负载均衡创建完成: {name} ({version})")
        return name

    def _slb_lb_set_basic_config(self, lb_name, protocol, port=None, desc=None, 
                                  acl_enable=False, access_policy=None, ip_group=None):
        """步骤1: 基础配置"""
        # 监听器名称
        self.locator("div").filter(has_text=re.compile(r"^监听器名称$")).get_by_role("textbox").fill(lb_name)
        
        # 描述
        if desc:
            self.locator("textarea").fill(desc)
            
        # 协议
        self.get_by_label("新建监听器").get_by_role("textbox", name="请选择").click()
        self.get_by_text(protocol, exact=True).last.click() # 使用last以应对可能重复项
        
        # 端口
        if port:
            self.get_by_role("spinbutton").fill(str(port))
        
        # 访问控制
        acl_switch = self.locator("div.el-form-item").filter(has_text="启用访问控制").get_by_role("switch")
        is_checked = acl_switch.get_attribute("aria-checked") == "true"
        if is_checked != acl_enable:
            acl_switch.locator("span").click()
        
        if acl_enable and access_policy:
            # 选择策略类型 (针对黑白名单)
            self.locator("div").filter(has_text=re.compile(r"^访问控制$")).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=access_policy).click()
            
            # 选择IP地址组
            if ip_group:
                self.get_by_label("新建监听器").locator("div").filter(has_text=re.compile(r"^IP地址组$")).get_by_placeholder("请选择").click()
                self.get_by_text(ip_group, exact=True).click()
        
        self.get_by_text("下一步").click()

    def _slb_lb_set_listener_config(self, pool_name, balance_method, health_check):
        """步骤2: 监听器配置 (资源池)"""
        if not pool_name:
            pool_name = f"pool-{random_data()}"
        
        # 资源池名称
        self.locator("div").filter(has_text=re.compile(r"^资源池名称$")).get_by_role("textbox").fill(pool_name)
        
        # 均衡算法
        self.get_by_label("新建监听器").get_by_role("textbox", name="请选择").click()
        self.locator("li").filter(has_text=re.compile(fr"^{balance_method}$")).click()
        
        # 健康检查激活状态
        self.get_by_role("radio", name="激活" if health_check else "不激活").click()
        
        self.get_by_text("下一步").click()

    def _slb_lb_set_confirm_info(self):
        """步骤3: 确认信息"""
        # 点击最后一步的“新建”按钮（在 footer 中的容器定位更精准）
        self.locator(".dialog-box-footer").get_by_text("新建", exact=True).click()

    @submenu("负载均衡（基础版）")
    def slb_lb_create(self, slb_name, lb_name, protocol="TCP", port=80, 
                            desc=None, acl_enable=False, access_policy=None, ip_group=None,
                            pool_name=None, balance_method="轮询", health_check=True):
        """为负载均衡创建监听器 (3步流程)
        
        Args:
            slb_name: 负载均衡名称
            lb_name: 监听器名称
            protocol: 监听协议，默认"TCP"
            port: 监听端口号，默认80
            desc: 描述
            acl_enable: 是否启用访问控制，默认False
            access_policy: 访问策略，可选"黑名单"、"白名单"，默认None
            ip_group: IP地址组名称，在使用访问策略时必填
            pool_name: 资源池名称，如果为None则自动生成
            balance_method: 负载均衡算法，可选"源IP"、"加权轮询"、"轮询"，默认"轮询"
            health_check: 是否开启健康检查，默认True (激活)
        """
        # 进入SLB详情页
        self.get_by_role("row", name=slb_name).locator("a").click()
        
        # 切换到监听器Tab
        self.get_by_role("tab", name="监听器").click()
        
        # 点击创建。针对空页面和有列表的情况做兼容
        btn_create = self.get_by_text("立即创建")
        if not btn_create.is_visible():
            btn_create = self.get_by_text("新建", exact=True)
        btn_create.click()
        
        # 1. 基础配置
        self._slb_lb_set_basic_config(lb_name, protocol, port, desc, acl_enable, access_policy, ip_group)
            
        # 2. 监听器配置 (资源池)
        self._slb_lb_set_listener_config(pool_name, balance_method, health_check)
            
        # 3. 确认信息
        self._slb_lb_set_confirm_info()
        
        self.logger.info(f"SLB监听器创建成功: {lb_name} ({protocol}:{port})")
        return lb_name


    @submenu("负载均衡（基础版）")
    def slb_delete(self, names):
        """删除负载均衡
        
        Args:
            names: 负载均衡名称或名称列表
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