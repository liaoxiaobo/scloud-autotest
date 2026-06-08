import random
from sugon_web.pages.login import LoginPage
from sugon_web.pages.iam.iam import IamPage
from sugon_web.config.config import Config
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import logger


def verify_login(page, username: str, password: str, expect_success: bool) -> bool:
    """验证用户登录是否成功/失败，执行后确保恢复 admin 登录状态。

    Args:
        page: Playwright page 对象
        username: 要验证登录的用户名
        password: 用户密码
        expect_success: 期望是否登录成功

    Returns:
        bool: 实际结果是否与期望一致
    """
    base_url = Config.get("base_url")
    login = LoginPage(page)

    def _attempt_login():
        """单次登录尝试，成功返回 True，失败返回 False，异常返回 None。"""
        try:
            _navigate_to_login(page)
        except Exception as e:
            logger.warning(f"verify_login: 导航到登录页异常: {e}")
            return None
        try:
            login.login(username, password)
        except Exception as e:
            logger.warning(f"verify_login: 登录操作异常: {e}")
            return False
        # 轮询等待：要么跳转离开登录页（成功），要么出现错误弹窗（失败）
        for _ in range(20):
            page.wait_for_timeout(500)
            if "login" not in page.url.lower():
                return True
            if page.locator(".el-message-box__wrapper").is_visible():
                return False
        return False

    result = _attempt_login()
    if result is None:
        result = False
    success = result

    def _close_any_popup(p):
        """关闭页面上可能存在的 el-message-box 弹窗。"""
        for _ in range(3):
            try:
                wrapper = p.locator(".el-message-box__wrapper")
                if not wrapper.is_visible():
                    return True
                clicked = False
                for btn_text in ["确定", "确认"]:
                    for btn in wrapper.locator("button").filter(has_text=btn_text).all():
                        if btn.is_visible():
                            btn.click()
                            p.wait_for_timeout(800)
                            clicked = True
                            break
                    if clicked:
                        break
                if not clicked:
                    for btn in wrapper.locator("button").all():
                        if btn.is_visible():
                            btn.click()
                            p.wait_for_timeout(800)
                            break
                p.keyboard.press("Escape")
                p.wait_for_timeout(300)
            except Exception:
                pass
            if not p.locator(".el-message-box__wrapper").is_visible():
                return True
            p.wait_for_timeout(500)
        return not p.locator(".el-message-box__wrapper").is_visible()

    # 如果期望成功但实际失败，等待后端同步后重试一次
    if expect_success and not success:
        logger.warning(f"verify_login: user={username} 首次登录失败，关闭弹窗后重试...")
        _close_any_popup(page)
        page.wait_for_timeout(5000)
        retry = _attempt_login()
        if retry is not None:
            success = retry

    result = success == expect_success
    logger.info(f"verify_login: user={username}, expect={expect_success}, actual_success={success}, result={result}")

    # 关闭可能存在的登录失败提示弹窗
    _close_any_popup(page)

    # 恢复 admin 登录状态
    restore_admin_login(page)

    return result


def create_iam_user(page, name: str = None, password: str = None, email: str = None, phone: str = None, target_org: str = None):
    """创建 IAM 测试用户，返回用户信息的字典。

    执行后页面停留在 IAM 用户管理列表页。

    Args:
        page: Playwright page 对象（需已登录）
        name: 账号，默认自动生成
        password: 密码，默认 Keystone@1234
        email: 邮箱，默认自动生成
        phone: 手机，默认自动生成
        target_org: 目标子组织名称，精准导航到指定组织树节点

    Returns:
        dict: {"name", "alias", "display_name", "email", "phone", "password", "role"}
    """
    if name is None:
        name = random_data().replace("autotest-", "autotest-iam-")
    if password is None:
        password = "Keystone@1234"
    if email is None:
        email = f"{name}@sugon.com"
    if phone is None:
        phone = "138" + "".join(str(random.randint(0, 9)) for _ in range(8))

    iam = IamPage(page)
    iam.goto_service("统一身份认证IAM")
    iam.iam_create_user(name=name, alias=name, email=email, phone=phone, password=password, target_org=target_org)

    return {
        "name": name,
        "alias": name,
        "display_name": name,
        "email": email,
        "phone": phone,
        "password": password,
        "role": "默认角色",
        "target_org": target_org,
    }


def create_iam_org(page, org_name: str = None, username: str = None, password: str = None,
                   email: str = None, phone: str = None):
    """创建 IAM 顶级组织及管理员用户，返回组织信息字典。

    Args:
        page: Playwright page 对象（需已登录 admin）
        org_name: 组织名称，默认自动生成
        username: 组织管理员账号，默认自动生成
        password: 管理员密码，默认 Autotest@123
        email: 邮箱，默认自动生成
        phone: 手机，默认自动生成

    Returns:
        dict: {"org_name", "username", "password", "phone", "email"}
    """
    if org_name is None:
        org_name = random_data().replace("autotest-", "autotest-org-")
    if username is None:
        username = random_data().replace("autotest-", "autotest-org-user-")
    if password is None:
        password = "Autotest@123"
    if email is None:
        email = f"{username}@sugon.com"
    if phone is None:
        phone = "138" + "".join(str(random.randint(0, 9)) for _ in range(8))

    iam = IamPage(page)
    iam.goto_service("统一身份认证IAM")
    iam.iam_create_organization(
        org_name=org_name,
        username=username,
        email=email,
        phone=phone,
        password=password,
    )

    return {
        "org_name": org_name,
        "username": username,
        "password": password,
        "phone": phone,
        "email": email,
    }


def create_iam_child_org(page, parent_name: str, child_name: str = None):
    """在指定父组织下创建子组织，返回子组织信息字典。

    Args:
        page: Playwright page 对象（需已登录 admin）
        parent_name: 父组织名称
        child_name: 子组织名称，默认自动生成

    Returns:
        dict: {"child_name", "parent_name"}
    """
    if child_name is None:
        child_name = random_data().replace("autotest-", "autotest-child-")

    iam = IamPage(page)
    iam.goto_service("统一身份认证IAM")
    iam.iam_create_child_organization(parent_name, child_name)

    return {
        "child_name": child_name,
        "parent_name": parent_name,
    }


def modify_and_assert_quota(iam_page, service_name, quotas, assertions):
    """修改指定服务的配额并逐项断言指标值。

    配额不足/服务不存在/值超max降级时标记环境问题并跳过。

    Args:
        iam_page: IAM 页面对象
        service_name: 服务名称
        quotas: 待修改的配额字典
        assertions: 断言期待值列表 [(指标名, 期望值), ...]
    """
    try:
        iam_page.iam_modify_service_quota(service_name, quotas)
        iam_page.wait_for_page_ready()
    except EnvironmentError as e:
        logger.warning(f"{service_name} 配额修改跳过(配额不足): {e}")
        return
    except AssertionError as e:
        msg = str(e)
        if "未找到服务" in msg:
            logger.warning(f"{service_name} 跳过(服务不存在): {msg}")
            return
        raise
    for metric_name, expected in assertions:
        actual_val = _resolve_quota_value(metric_name, quotas, expected)
        iam_page.iam_assert_quota_value(service_name, metric_name, actual_val)
    logger.info(f"{service_name} 配额修改验证通过（{len(assertions)}项）")


def _resolve_quota_value(metric_name, quotas, fallback_expected):
    """从quotas字典推导指标的实际期望值（总量->使用量映射）。"""
    for qk, qv in quotas.items():
        for src, dst in [("总量", "使用量"), ("总量", "使用总量")]:
            if qk.replace(src, dst) == metric_name:
                return f"0/{qv}"
    return fallback_expected


def filter_quota_service_type(iam_page, service_type):
    """过滤服务类型tab，若tab不存在则返回False（环境跳过）。

    Args:
        iam_page: IAM 页面对象
        service_type: 服务类型名称

    Returns:
        bool: tab存在则为True，否则False
    """
    try:
        iam_page.iam_filter_quota_service_type(service_type)
        return True
    except Exception:
        logger.warning(f"服务类型'{service_type}'的tab不存在，当前环境无此服务类型，跳过")
        return False


def _navigate_to_login(page):
    """导航到登录页面并等待登录表单渲染。"""
    from sugon_web.config.config import Config
    base_url = Config.get("base_url")
    # 先关闭可能的弹窗，避免干扰后续导航
    try:
        for _ in range(3):
            dialog = page.locator(".el-message-box__wrapper:visible, .el-dialog__wrapper:visible").first
            if dialog.count() == 0 or not dialog.is_visible():
                break
            for btn in dialog.locator("button").filter(has_text="确定").all():
                if btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(500)
                    break
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
    except Exception:
        pass
    page.context.clear_cookies()
    page.goto(f"{base_url}/#/login", timeout=120000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector("input[placeholder*='登录账号']", timeout=120000)


def login_as_user(page, username: str, password: str):
    """以指定用户身份登录。

    Args:
        page: Playwright page 对象
        username: 用户名
        password: 密码
    """
    from sugon_web.pages.login import LoginPage
    _navigate_to_login(page)
    LoginPage(page).login(username, password)
    page.wait_for_load_state("domcontentloaded")


def restore_admin_login(page):
    """恢复 admin 登录状态。

    导航到登录页并以 admin 身份登录，用于测试中途切换用户后恢复。

    Args:
        page: Playwright page 对象
    """
    login_as_user(page, "admin", "keystone_sugon")
    page.wait_for_load_state("domcontentloaded")


def delete_iam_user(page, name: str, target_org: str = None):
    """删除 IAM 用户并断言已从列表中消失。

    Args:
        page: Playwright page 对象（需已登录 admin）
        name: 用户显示名称（用于列表搜索）
        target_org: 目标子组织名称，用于精准导航到用户所在的组织树节点    """
    iam = IamPage(page)
    iam.goto_service("统一身份认证IAM")
    iam.iam_delete_user(name, target_org=target_org)
    iam.assert_deleted(name, timeout=30, refresh=True)
