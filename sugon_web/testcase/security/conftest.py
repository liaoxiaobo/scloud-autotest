import ipaddress
import re
import time

import pytest
from playwright.sync_api import expect
from sugon_web.pages.network import VpcPage
from sugon_web.pages.security.apt import AptPage
from sugon_web.pages.security.ras import RasPage
from sugon_web.pages.security.usm import UsmPage
from sugon_web.pages.security.ver import VerPage
from sugon_web.pages.security.vdb import VdbPage
from sugon_web.pages.security.waf import WafPage
from sugon_web.pages.security.wpt import WptPage
from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


class SecurityVpcPage(VpcPage):
    """安全合规模块专用的 VPC 页面封装。

    继承 ``VpcPage`` 全部能力，仅补充 ``security_vpc`` fixture 在直接定位到
    VPC 网络列表页（hash）后创建 VPC 所需的表单入口，避免改动公共 ``VpcPage``。
    """

    def _vpc_create_form(self, name, subnet_name, cidr, desc="", subnet_desc="",
                         network_type="Geneve", cluster="Autotest"):
        """填写并提交 VPC 创建表单（不做服务导航/子菜单切换）。"""
        self.btn_create.click()

        self._input_name.fill(name)
        self._select_cluster(cluster)
        if desc:
            self._input_desc.fill(desc)
        self.get_by_role("radio", name=network_type).click()
        self._input_subnet_name.fill(subnet_name)
        if subnet_desc:
            self._input_subnet_desc.fill(subnet_desc)
        self._input_cidr.fill(cidr)

        ip = str(next(ipaddress.ip_network(cidr, strict=False).hosts()))
        self._input_gateway.fill(ip)

        # 默认不关联 ACL 策略；若页面已自动带出，先清空避免提交失败
        acl_item = self.locator(".el-form-item").filter(has_text="关联ACL策略")
        try:
            acl_item.hover()
            clear_icon = acl_item.locator(".el-icon-circle-close")
            if clear_icon.is_visible():
                clear_icon.click()
        except Exception:
            pass

        self.btn_submit.click()

    def select_top_nav_project(self, org_name="默认组织", project_name="默认项目",
                               optional=False):
        """通过顶部导航栏选择项目（不存在时可选跳过）。"""
        self.logger.info(f"选择项目: {org_name} -> {project_name}")
        org_names = [org_name] if isinstance(org_name, str) else org_name

        # optional 模式下，顶部项目选择器未出现则直接返回
        if optional:
            top_btn = self.page.locator(".project_btn")
            found = False
            for _ in range(5):
                if top_btn.count() > 0:
                    try:
                        expect(top_btn.first).to_be_visible(timeout=2000)
                        found = True
                        break
                    except Exception:
                        pass
                self.page.wait_for_timeout(1000)
            if not found:
                self.logger.info("顶部项目选择器未出现，optional 模式跳过项目选择")
                return

        def _try_select_project():
            items = self.page.locator(".project_item")
            for i in range(items.count()):
                item = items.nth(i)
                if project_name in item.inner_text():
                    item.locator(".el-radio").click()
                    return True
            return False

        def _attempt_select():
            top_btn_ready = False
            top_project_btn = None
            for _ in range(30):
                top_project_btn = self.page.locator(".project_btn").filter(
                    has_text=re.compile(r"请选择项目|" + re.escape(project_name))
                )
                if top_project_btn.count() == 0:
                    top_project_btn = self.page.locator(".project_btn")
                if top_project_btn.count() > 0:
                    try:
                        expect(top_project_btn.first).to_be_visible(timeout=2000)
                        top_btn_ready = True
                        break
                    except Exception:
                        pass
                self.page.wait_for_timeout(1000)

            if not top_btn_ready or top_project_btn is None:
                if optional:
                    return False, None
                raise AssertionError("顶部项目选择按钮未在预期时间内出现")

            # 已选中目标项目则无需操作
            current_text = top_project_btn.first.inner_text()
            if project_name in current_text and "请选择项目" not in current_text:
                self.logger.info(f"当前已选中项目 '{project_name}'，无需选择")
                return True, None

            top_project_btn.first.click()
            self.page.wait_for_timeout(1000)

            panel = self.page.locator(".project_dialog").first
            expect(panel).to_be_visible(timeout=15000)
            self.page.wait_for_timeout(2000)

            # 在左侧组织树中选择组织路径
            for i, target in enumerate(org_names):
                is_leaf = (i == len(org_names) - 1)
                self.page.evaluate("""
                    (args) => {
                        const [target, isLeaf] = args;
                        const tree = document.querySelector('.department_tree');
                        if (!tree) return;
                        const items = tree.querySelectorAll('.one-tree-msg-text-content');
                        for (let item of items) {
                            if (item.innerText.trim() === target) {
                                const parent = item.closest('.one-tree-msg');
                                if (!parent) return;
                                const icon = parent.querySelector('.one-tree-jiantou');
                                if (!isLeaf && icon) icon.click();
                                else parent.click();
                                break;
                            }
                        }
                    }
                """, [target, is_leaf])
                self.page.wait_for_timeout(3000)

            # 等待项目列表并选择目标项目
            deadline = time.time() + 12
            while time.time() < deadline:
                if _try_select_project():
                    return True, panel
                time.sleep(1)

            # 未找到则尝试按项目名称搜索
            try:
                key_select = panel.locator(".el-select").first
                if key_select.count() > 0:
                    key_select.click()
                    self.page.wait_for_timeout(500)
                    project_option = self.page.locator(
                        ".el-select-dropdown__item").filter(has_text="项目名称")
                    if project_option.count() > 0:
                        project_option.first.click()
                        self.page.wait_for_timeout(500)
            except Exception as e:
                self.logger.warning(f"切换项目搜索类型失败: {e}")

            search_input = panel.locator('input[type="text"]').filter(
                has=self.page.get_by_placeholder(re.compile(r"搜索|请输入"))
            )
            if search_input.count() > 0:
                self.logger.info(
                    f"项目列表中未直接找到 '{project_name}'，尝试按项目名称搜索")
                search_input.first.fill("")
                search_input.first.fill(project_name)
                self.page.wait_for_timeout(500)
                self.page.keyboard.press("Enter")
                self.page.wait_for_timeout(2000)
                deadline = time.time() + 10
                while time.time() < deadline:
                    if _try_select_project():
                        return True, panel
                    time.sleep(1)

            return False, panel

        selected, panel = _attempt_select()

        if not selected:
            if optional:
                self.logger.warning(f"项目 '{project_name}' 选择失败，optional 模式忽略")
                if panel is not None:
                    try:
                        cancel_btn = panel.locator(".dialog_footer").get_by_text(
                            "取消", exact=True)
                        if cancel_btn.count() > 0:
                            cancel_btn.click()
                            self.page.wait_for_timeout(500)
                    except Exception:
                        pass
                return
            raise AssertionError(
                f"项目选择失败：组织路径'{org_names}'下未找到项目'{project_name}'")

        # 已选中且无需打开弹窗时 panel 为 None，直接返回
        if panel is None:
            return

        # 点击确定并等待页面刷新
        panel.locator(".dialog_footer").get_by_text("确定", exact=True).click()
        self.page.wait_for_timeout(800)
        self.wait_for_page_ready()


@pytest.fixture(scope="session")
def security_vpc(browser, config):
    """创建安全合规测试专用 VPC，session 级共享，所有 session fixture 结束后自动清理。"""
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.common.auth import prepare_page_session

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    vpc_page = SecurityVpcPage(page)

    # 通过服务导航进入 VPC，继承主门户登录态与项目上下文
    base_url = config.get("base_url").rstrip("/")
    vpc_page.goto_service("虚拟私有云")

    # 8.0.6.0 服务根路径 /vpc 会重定向到概览页，需要通过子菜单进入网络列表
    if "vpc-network-list" not in page.url:
        logger.info(f"当前不在 VPC 网络列表页，通过子菜单切换: {page.url}")
        vpc_page.goto_submenu("虚拟私有云")

    vpc_page.wait_for_page_ready()
    page.wait_for_timeout(2000)

    # 若项目选择器未选中默认项目，则被动选择默认项目
    vpc_page.select_top_nav_project(optional=True)

    vpc_name = random_data().replace("autotest-", "autotest-vpc-")
    subnet_name = random_data()
    cidr = random_data("cidr")

    vpc_page._vpc_create_form(name=vpc_name, subnet_name=subnet_name, cidr=cidr)
    vpc_page.assert_popup_success("创建虚拟私有云成功")
    logger.info(f"安全合规专用 VPC 创建成功: {vpc_name}, CIDR={cidr}")

    yield {"name": vpc_name, "subnet_name": subnet_name, "cidr": cidr}

    vpc_page.goto_service("虚拟私有云")
    # teardown 阶段同样可能因 VPC 服务独立登录态过期被重定向，需重新登录
    for _vpc_attempt in range(2):
        if "/login" not in page.url:
            break
        logger.warning(f"VPC 清理导航时被重定向到登录页（第{_vpc_attempt+1}次），当前URL: {page.url}，尝试重新登录")
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        prepare_page_session(page, config)
        vpc_page.goto_service("虚拟私有云")
    else:
        if "/login" in page.url:
            logger.warning("VPC 清理阶段主门户登录仍未解决，尝试从 VPC 登录页直接登录")
            page.get_by_placeholder("请输入登录账号").fill(config.get("username"))
            page.get_by_placeholder("请输入登录密码").fill(config.get("password"))
            page.get_by_text("登 录").click()
            try:
                page.wait_for_url(lambda u: "login" not in u, timeout=30000)
            except Exception:
                pass
            vpc_page.goto_service("虚拟私有云")

    # 清理阶段需确保位于 VPC 网络列表并选中默认项目（150 环境会弹项目选择器）
    if "vpc-network-list" not in page.url:
        logger.info(f"清理阶段当前不在 VPC 网络列表页，通过子菜单切换: {page.url}")
        vpc_page.goto_submenu("虚拟私有云")
    vpc_page.wait_for_page_ready()
    page.wait_for_timeout(2000)
    vpc_page.select_top_nav_project(optional=True)

    vpc_page.vpc_delete(vpc_name)
    vpc_page.assert_deleted(vpc_name)
    logger.info(f"安全合规专用 VPC 已删除: {vpc_name}")
    page.close()
    context.close()


@pytest.fixture(scope="session")
def usm_instance(browser, config, security_vpc):
    """创建 USM 实例并自动清理（scope=session）。

    所有 USM 测试共享同一个实例，session 结束时自动删除。
    测试方法声明 usm_instance 参数即可接入，通过 usm_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._usm_helpers import create_usm_instance, delete_usm_instance
    from sugon_web.utils.data import random_data

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    usm_page_obj = UsmPage(page)
    usm_page_obj.goto_list_page()

    name = random_data().replace("autotest-", "autotest-usm-")
    result = None

    try:
        result = create_usm_instance(page, usm_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        yield result
    finally:
        if result is not None:
            try:
                delete_usm_instance(page, usm_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 USM 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_usm_page = UsmPage(new_page)
                        delete_usm_instance(new_page, new_usm_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 USM 实例也失败: {e2}")
                        raise e2 from e
                else:
                    logger.error(f"清理 USM 实例失败: {e}")
                    raise
        page.close()
        context.close()


@pytest.fixture(scope="function")
def apt_page(page):
    """初始化攻击预警APT页对象"""
    page_object = AptPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="function")
def usm_page(page):
    """初始化云堡垒机高级版USM页对象"""
    page_object = UsmPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="session")
def ver_instance(browser, config, security_vpc):
    """创建 VER 实例并自动清理（scope=session）。

    所有 VER 测试共享同一个实例，session 结束时自动删除。
    测试方法声明 ver_instance 参数即可接入，通过 ver_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._ver_helpers import create_ver_instance, delete_ver_instance
    from sugon_web.utils.data import random_data

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    ver_page_obj = VerPage(page)
    ver_page_obj.goto_list_page()

    name = random_data().replace("autotest-", "autotest-ver-")
    result = None

    try:
        result = create_ver_instance(page, ver_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        yield result
    finally:
        if result is not None:
            try:
                delete_ver_instance(page, ver_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 VER 实例失败（可能 session 过期）: {e}，尝试新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_ver_page = VerPage(new_page)
                        delete_ver_instance(new_page, new_ver_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 VER 实例也失败: {e2}，实例可能遗留")
                else:
                    logger.error(f"清理 VER 实例失败: {e}")
                    raise
        page.close()
        context.close()


@pytest.fixture(scope="session")
def vdb_instance(browser, config, security_vpc):
    """创建 VDB 实例并自动清理（scope=session）。

    所有 VDB 操作类测试共享同一个实例，session 结束时自动删除。
    测试方法声明 vdb_instance 参数即可接入，通过 vdb_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._vdb_helpers import create_vdb_instance, delete_vdb_instance
    from sugon_web.utils.data import random_data

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    vdb_page_obj = VdbPage(page)
    vdb_page_obj.goto_list_page()

    name = random_data().replace("autotest-", "autotest-vdb-")
    result = None

    try:
        result = create_vdb_instance(page, vdb_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        yield result
    finally:
        if result is not None:
            try:
                delete_vdb_instance(page, vdb_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 VDB 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_vdb_page = VdbPage(new_page)
                        delete_vdb_instance(new_page, new_vdb_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 VDB 实例也失败: {e2}")
                        raise e2 from e
                else:
                    logger.error(f"清理 VDB 实例失败: {e}")
                    raise
        page.close()
        context.close()


@pytest.fixture(scope="function")
def ver_page(page):
    """初始化日志审计VER页对象"""
    page_object = VerPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="function")
def vdb_page(page, security_vpc):
    """初始化数据库审计VDB页对象，并确保存在可用的专有网络。"""
    page_object = VdbPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="function")
def waf_page(page):
    """初始化WEB应用防火墙WAF页对象"""
    page_object = WafPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="class")
def waf_instance(browser, config, security_vpc, request):
    """创建 WEB应用防火墙WAF 实例并自动清理（scope=class）。

    所有 WAF 测试共享同一个实例，类内所有测试执行完成后自动清理。
    测试方法声明 waf_instance 参数即可接入，通过 waf_instance["name"] 获取实例名。

    参数:
        request.param: dict, 可选
            - name: str, 自定义名称，默认使用 random_data()

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._waf_helpers import create_waf_instance, delete_waf_instance

    context = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(context, config)
    waf_page_obj = WafPage(page)
    waf_page_obj.goto_list_page()

    params = request.param if hasattr(request, 'param') and request.param else {}
    name = params.get("name") or random_data().replace("autotest-", "autotest-waf-")
    result = None

    try:
        result = create_waf_instance(page, waf_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        yield result
    finally:
        if result is not None:
            try:
                delete_waf_instance(page, waf_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 WAF 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_waf_page = WafPage(new_page)
                        delete_waf_instance(new_page, new_waf_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 WAF 实例也失败: {e2}")
                        raise e2 from e
                else:
                    logger.error(f"清理 WAF 实例失败: {e}")
                    raise
        page.close()
        context.close()


@pytest.fixture(scope="class")
def apt_instance(browser, config, request):
    """创建 APT 实例并自动清理（scope=class）。

    所有 APT 操作类测试共享同一个实例，类内所有测试执行完成后自动清理。
    测试方法声明 apt_instance 参数即可接入，通过 apt_instance["name"] 获取实例名。

    参数:
        request.param: dict, 可选
            - name: str, 自定义名称，默认使用 random_data()

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._apt_helpers import create_apt_instance, delete_apt_instance

    context = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(context, config)
    apt_page_obj = AptPage(page)
    apt_page_obj.goto_list_page()

    params = request.param if hasattr(request, 'param') and request.param else {}
    name = params.get("name") or random_data().replace("autotest-", "autotest-apt-")
    result = None

    try:
        result = create_apt_instance(page, apt_page_obj, name)
        yield result
    finally:
        if result is not None:
            try:
                delete_apt_instance(page, apt_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 APT 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_apt_page = AptPage(new_page)
                        delete_apt_instance(new_page, new_apt_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 APT 实例也失败: {e2}")
                        raise e2 from e
                else:
                    logger.error(f"清理 APT 实例失败: {e}")
                    raise
        page.close()
        context.close()


@pytest.fixture(scope="function")
def ras_page(page):
    """初始化漏洞扫描RAS页对象"""
    page_object = RasPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="class")
def ras_instance(browser_context, config, security_vpc):
    """创建 RAS 实例并自动清理（scope=class）。

    所有 RAS 测试共享同一个实例，类内所有测试执行完成后自动清理。
    测试方法声明 ras_instance 参数即可接入，通过 ras_instance["name"] 获取实例名。

    使用 browser_context（class-scoped）替代独立创建 context，
    确保与函数级 page fixture 共用同一上下文，避免 fixture 解析冲突。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._ras_helpers import create_ras_instance, delete_ras_instance
    from sugon_web.utils.data import random_data

    page = _create_logged_in_page(browser_context, config)
    ras_page_obj = RasPage(page)
    ras_page_obj.goto_list_page()

    name = random_data().replace("autotest-", "autotest-ras-")
    result = None

    try:
        result = create_ras_instance(page, ras_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        yield result
    finally:
        if result is not None:
            try:
                delete_ras_instance(page, ras_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 RAS 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(browser_context, config)
                        new_ras_page = RasPage(new_page)
                        delete_ras_instance(new_page, new_ras_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 RAS 实例也失败: {e2}")
                        raise e2 from e
                else:
                    logger.error(f"清理 RAS 实例失败: {e}")
                    raise
        page.close()


@pytest.fixture(scope="function")
def wpt_page(page):
    """初始化网页防篡改WPT页对象"""
    page_object = WptPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="class")
def wpt_instance(browser, config, security_vpc, request):
    """创建网页防篡改WPT实例并自动清理（scope=class）。

    所有 WPT 测试共享同一个实例，类内所有测试执行完成后自动清理。
    测试方法声明 wpt_instance 参数即可接入，通过 wpt_instance["name"] 获取实例名。

    参数:
        request.param: dict, 可选
            - name: str, 自定义名称，默认使用 random_data()

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._wpt_helpers import create_wpt_instance, delete_wpt_instance

    context = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(context, config)
    wpt_page_obj = WptPage(page)
    wpt_page_obj.goto_list_page()

    params = request.param if hasattr(request, 'param') and request.param else {}
    name = params.get("name") or random_data().replace("autotest-", "autotest-wpt-")
    result = None

    try:
        result = create_wpt_instance(page, wpt_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        yield result
    finally:
        if result is not None:
            try:
                delete_wpt_instance(page, wpt_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 WPT 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_wpt_page = WptPage(new_page)
                        delete_wpt_instance(new_page, new_wpt_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 WPT 实例也失败: {e2}")
                        raise e2 from e
                else:
                    logger.error(f"清理 WPT 实例失败: {e}")
                    raise
        page.close()
        context.close()
