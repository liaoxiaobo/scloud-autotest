import random
from sugon_web.pages.login import LoginPage
from sugon_web.pages.iam.iam import IamPage
from sugon_web.config.config import Config
from sugon_web.utils.util import random_data
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

    # 清除 cookie 和存储后直接前往登录页（比点击下拉菜单更稳定）
    page.context.clear_cookies()
    page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
    page.goto(f"{base_url}/#/login")
    page.wait_for_timeout(3000)

    # 关闭可能残留的弹窗
    try:
        for btn in page.locator(".el-message-box__wrapper button").filter(has_text="确定").all():
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
                break
    except Exception:
        pass

    login.login(username, password)

    # 轮询等待：要么跳转离开登录页（成功），要么出现错误弹窗（失败）
    success = False
    for i in range(20):
        page.wait_for_timeout(500)
        current_url = page.url.lower()
        if "login" not in current_url:
            success = True
            break
        # 出现错误弹窗即判定失败
        if page.locator(".el-message-box__wrapper").is_visible():
            break

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

    # 如果期望成功但实际失败，关闭弹窗后重试一次（应对后端状态同步延迟）
    if expect_success and not success:
        logger.warning(f"verify_login: user={username} 首次登录失败，关闭弹窗后重试...")
        _close_any_popup(page)
        page.wait_for_timeout(1500)
        # 确保仍在登录页，若已跳转则重新导航
        if "login" not in page.url.lower():
            page.goto(f"{base_url}/#/login")
            page.wait_for_timeout(2000)
        try:
            login.login(username, password)
        except Exception as e:
            logger.warning(f"verify_login: 重试登录时异常: {e}")
            success = False
        else:
            for _ in range(20):
                page.wait_for_timeout(500)
                if "login" not in page.url.lower():
                    success = True
                    break
                if page.locator(".el-message-box__wrapper").is_visible():
                    break

    result = success == expect_success
    logger.info(f"verify_login: user={username}, expect={expect_success}, actual_success={success}, result={result}")

    # 关闭可能存在的登录失败提示弹窗（使用多重策略）
    _close_any_popup(page)

    # 恢复 admin 登录状态
    page.context.clear_cookies()
    page.goto(f"{base_url}/#/login")
    page.wait_for_timeout(3000)
    try:
        login.login("admin", "keystone_sugon")
    except Exception as e:
        logger.warning(f"verify_login: 恢复 admin 登录异常: {e}")
    page.wait_for_timeout(3000)

    # 回到 IAM 页面以便后续操作
    try:
        page.goto(f"{base_url}/iam/#/departmentManage")
        page.wait_for_timeout(3000)
    except Exception:
        pass

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
