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
                self.locator("form div").filter(has_text="网络配置 子网网络 子网 IPv4 IPv6").get_by_placeholder(
                    "请选择").click()
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
                                  acl_enable=False, access_policy=None, ip_group=None,
                                  auth_mode="单向认证", cert_type="国际服务器证书", 
                                  server_cert=None, ca_cert=None, 
                                  http_redirect=False, redirect_port=None):
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
            # 这里的 spinbutton 可能是第一个
            self.get_by_role("spinbutton").first.fill(str(port))
        
        # HTTPS 联动字段
        if protocol == "HTTPS":
            # 认证方式 (单向/双向)
            self.locator("label").filter(has_text=auth_mode).click()
            
            # 服务器证书类型选择
            # 默认两个都勾选。根据 cert_types 调整勾选状态。
            cert_types = [cert_type] if isinstance(cert_type, str) else cert_type
            for ct in ["国际服务器证书", "国密服务器证书"]:
                checkbox_label = self.get_by_label("checkbox-group").locator("label").filter(has_text=ct)
                # 检查当前是否勾选 (el-checkbox 勾选状态在父级 label 的 class 中体现)
                is_checked = "is-checked" in (checkbox_label.get_attribute("class") or "")
                should_be_checked = ct in cert_types
                if is_checked != should_be_checked:
                    checkbox_label.locator("span").nth(1).click()
            
            # 选择证书 (只有勾选了对应类型才进行选择)
            if server_cert:
                # server_cert 可以是一个字符串（默认国际）或者字典 {"国际": "...", "国密": "..."}
                certs_data = {"国际": server_cert} if isinstance(server_cert, str) else server_cert
                for ct_key, cert_name in certs_data.items():
                    full_ct_name = f"{ct_key}服务器证书"
                    if full_ct_name in cert_types:
                        # 使用 label 关联定位下拉框
                        self.locator("div.el-form-item").filter(has_text=full_ct_name).get_by_placeholder("请选择").click()
                        self.locator("li").filter(has_text=cert_name).click()

            # 双向认证下的 CA 证书
            if auth_mode == "双向认证" and ca_cert:
                # 使用 label 关联定位
                self.locator("div.el-form-item").filter(has_text="CA证书").get_by_placeholder("请选择").click()
                self.get_by_text(ca_cert).last.click()

            # HTTP 端口重定向
            if http_redirect:
                self.locator("div").filter(has_text=re.compile(r"^HTTP端口重定向$")).locator("span").click()
                if redirect_port:
                    # 重定向端口通常是第二个 spinbutton，在表单项内定位更准确
                    self.locator("div.el-form-item").filter(has_text="HTTP端口重定向").get_by_role("spinbutton").fill(str(redirect_port))

        # 访问控制
        acl_switch = self.locator("div.el-form-item").filter(has_text="启用访问控制").get_by_role("switch")
        is_checked = acl_switch.get_attribute("aria-checked") == "true"
        if is_checked != acl_enable:
            acl_switch.locator("span").click()
        
        if acl_enable:
            if access_policy:
                # 选择策略类型 (针对黑白名单)
                self.locator("div").filter(has_text=re.compile(r"^访问控制$")).get_by_placeholder("请选择").click()
                self.locator("li").filter(has_text=access_policy).click()
            
            # 选择IP地址组
            if ip_group:
                self.get_by_label("新建监听器").locator("div").filter(has_text=re.compile(r"^IP地址组$")).get_by_placeholder("请选择").click()
                self.get_by_text(ip_group, exact=True).click()
        
        self.get_by_text("下一步").click()

    def _slb_lb_set_listener_config(self, pool_name, balance_method, health_check, 
                                    session_persistence=False, session_type=None,
                                    health_type=None, health_max_retries=None,
                                    health_timeout=None, health_interval=None,
                                    http_method=None, url_path=None):
        """步骤2: 监听器配置 (资源池)"""
        if not pool_name:
            pool_name = f"pool-{random_data()}"
        
        # 资源池名称
        self.locator("div").filter(has_text=re.compile(r"^资源池名称$")).get_by_role("textbox").fill(pool_name)
        
        # 均衡算法
        self.get_by_label("新建监听器").get_by_role("textbox", name="请选择").click()
        self.locator("li").filter(has_text=re.compile(fr"^{balance_method}$")).click()

        # 会话保持激活状态 (源IP算法下不设置)
        if balance_method != "源IP":
            self.locator("div.el-form-item").filter(has_text="会话保持").get_by_role("radio", name="激活" if session_persistence else "禁用").click()
            if session_persistence:
                if not session_type:
                    raise ValueError("会话保持激活时，必须提供 session_type (例如: 'SOURCE IP' 或 'HTTP_COOKIE')")
                # 当激活会话保持时，选择类型 (使用 label[for] 区别)
                self.locator("div.el-form-item").filter(has=self.locator('label[for*="session_persistence_type"]')).get_by_placeholder("请选择").click()
                # 仅在可见的下拉弹窗中进行精确匹配选择
                self.locator("div.el-select-dropdown:visible li").filter(has_text=re.compile(rf"^{re.escape(session_type)}$")).click()

        # 健康检查激活状态 (始终存在)
        self.locator("div.el-form-item").filter(has_text="健康检查").get_by_role("radio", name="激活" if health_check else "禁用").click()
        if health_check:
            if not health_type:
                raise ValueError("健康检查激活时，必须提供 health_type (例如: 'TCP', 'HTTP')")
            # 详细健康检查设置
            if health_type:
                # 使用 label[for] 定位类型下拉框，以区别于会话保持的类型
                self.locator("div.el-form-item").filter(has=self.locator('label[for*="health_monitor.type"]')).get_by_placeholder("请选择").click()
                # 仅在可见的下拉弹窗中进行精确匹配选择
                self.locator("div.el-select-dropdown:visible li").filter(has_text=re.compile(rf"^{re.escape(health_type)}$")).click()
            if health_max_retries:
                self.locator("div.el-form-item").filter(has_text="最大尝试次数").get_by_role("spinbutton").fill(str(health_max_retries))
            if health_timeout:
                self.locator("div.el-form-item").filter(has_text="超时").get_by_role("spinbutton").fill(str(health_timeout))
            if health_interval:
                self.locator("div.el-form-item").filter(has_text="检查间隔").get_by_role("spinbutton").fill(str(health_interval))
            if health_type == "HTTP":
                http_method = http_method or "GET"
                url_path = url_path or "/"

                self.locator("div.el-form-item").filter(has_text="HTTP(S)方法").get_by_placeholder("请选择").click()
                self.locator("div.el-select-dropdown:visible li").filter(
                    has_text=re.compile(rf"^{re.escape(http_method)}$")
                ).click()

                url_input = self.locator("div.el-form-item").filter(has_text="URL地址").get_by_role("textbox")
                url_input.click()
                url_input.fill(url_path)
        
        self.get_by_text("下一步").click()

    def _slb_lb_set_confirm_info(self):
        """步骤3: 确认信息"""
        # 点击最后一步的“新建”按钮（在 footer 中的容器定位更精准）
        self.dialog_confirm.click()
        # self.locator(".dialog-box-footer").get_by_text("新建", exact=True).click()

    @submenu("负载均衡（基础版）")
    def slb_lb_create(self, slb_name, lb_name, protocol="TCP", port=80, 
                            desc=None, acl_enable=False, access_policy=None, ip_group=None,
                            pool_name=None, balance_method="轮询", health_check=True,
                            **kwargs):
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
            **kwargs: 其他 HTTPS 相关参数:
                auth_mode: "单向认证" 或 "双向认证"
                cert_type: "国际服务器证书" 或 "国密服务器证书" (支持字符串或列表)
                server_cert: 证书名称 (支持字符串或字典 {"国际": "...", "国密": "..."})
                ca_cert: CA 证书名称 (双向认证时使用)
                http_redirect: 是否开启 HTTP 端口重定向 (True/False)
                redirect_port: 重定向端口
        """
        # 进入SLB详情页
        self.get_by_role("row", name=slb_name).locator("a").click()
        
        # 切换到监听器Tab。
        self.get_by_role("tab", name="监听器").evaluate("node => node.click()")

        # 点击创建。针对空页面 (立即创建) 和有列表的情况 (新建) 做兼容，最多等待2s
        btn_create = self.get_by_text("立即创建")
        try:
            btn_create.wait_for(state="visible", timeout=1000)
            btn_create.click()
        except:
            # 如果“立即创建”在2s内不可见，尝试点击“新建”
            self.get_by_text("新建", exact=True).click()
        
        # 1. 基础配置
        self._slb_lb_set_basic_config(
            lb_name, protocol, port, desc, acl_enable, access_policy, ip_group,
            auth_mode=kwargs.get("auth_mode", "单向认证"),
            cert_type=kwargs.get("cert_type", "国际服务器证书"),
            server_cert=kwargs.get("server_cert"),
            ca_cert=kwargs.get("ca_cert"),
            http_redirect=kwargs.get("http_redirect", False),
            redirect_port=kwargs.get("redirect_port")
        )
            
        # 2. 监听器配置 (资源池)
        self._slb_lb_set_listener_config(
            pool_name, balance_method, health_check, 
            session_persistence=kwargs.get("session_persistence", False),
            session_type=kwargs.get("session_type"),
            health_type=kwargs.get("health_type"),
            health_max_retries=kwargs.get("health_max_retries"),
            health_timeout=kwargs.get("health_timeout"),
            health_interval=kwargs.get("health_interval"),
            http_method=kwargs.get("http_method"),
            url_path=kwargs.get("url_path")
        )
            
        # 3. 确认信息
        self._slb_lb_set_confirm_info()
        
        self.logger.info(f"SLB监听器创建成功: {lb_name} ({protocol}:{port})")
        return lb_name

    def assert_listener_exists(self, lb_name):
        """验证左侧列表是否存在指定名称的监听器 (针对详情页监听器Tab)"""
        # 使用用户提供的 listener-left-list-item 容器进行精确匹配
        locator = self.locator("div.listener-left-list-item").filter(has_text=lb_name)
        # 确保可见
        locator.wait_for(state="visible", timeout=5000)
        self.logger.info(f"验证监听器 {lb_name} 存在于左侧列表")

    # @submenu("负载均衡（基础版）")
    def slb_lb_delete(self, slb_name, lb_name):
        """删除负载均衡监听器
        
        Args:
            slb_name: 负载均衡名称
            lb_name: 待删除的监听器名称
        """
        # 进入SLB详情页并切换到监听器Tab
        # self.get_by_role("row", name=slb_name).locator("a").click()
        # self.get_by_role("tab", name="监听器").evaluate("node => node.click()")
        
        # 找到目标监听器项并点击删除图标
        target_item = self.locator("div.listener-left-list-item").filter(has_text=lb_name)
        target_item.locator(".el-icon-delete").click()
        
        # 确认删除
        self.dialog_confirm.click()
        
        self.logger.info(f"SLB监听器 {lb_name} 已删除 (SLB: {slb_name})")


    @submenu("负载均衡（基础版）")
    def slb_delete(self, names):
        """负载均衡
        
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