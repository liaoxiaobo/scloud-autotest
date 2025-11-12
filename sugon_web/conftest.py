import datetime
import os
import pytest
import allure
from datetime import datetime
from playwright.sync_api import sync_playwright
from sugon_web.utils.logger import logger
from sugon_web.utils.util import get_file_abspath
from sugon_web.common.ssh import SSH


def pytest_addoption(parser):
    """添加命令行参数"""
    parser.addoption("--host", action="store", default='172.22.3.140', help="测试环境管理VIP")
    parser.addoption("--headless", action="store", default="false", help="是否无头模式运行（true/false）")
    parser.addoption("--browser-type", action="store", default="chromium", help="浏览器类型（chromium/firefox/webkit）")
    parser.addoption("--username", action="store", default="admin", help="登录用户名")
    parser.addoption("--password", action="store", default="keystone_sugon", help="登录密码")
    parser.addoption("--stor", action="store", default='xbd', help="storage backend")


@pytest.fixture(scope="session")
def env(pytestconfig):
    """根据--host参数加载对应环境的配置"""
    host = pytestconfig.getoption("--host")
    username = pytestconfig.getoption("--username")
    password = pytestconfig.getoption("--password")
    stor = pytestconfig.getoption("--stor")
    env = {
        'host': host,
        'url': f"https://{host}:30000",
        "username": username,
        "password": password,
        "stor": stor,
        "pkey": "pkey_scloudadmin"  # 默认使用scloudadmin用户的私钥
    }
    logger.info(f"测试环境配置加载完成")
    yield env


@pytest.fixture(scope="module")
def page(env, pytestconfig):
    """创建新页面，支持动态浏览器类型和 headless 模式"""
    browser_type = pytestconfig.getoption("--browser-type")
    headless = pytestconfig.getoption("--headless").lower() == "true"

    logger.info(f"开始初始化浏览器: type={browser_type}, headless={headless}")

    # 校验浏览器类型是否有效
    valid_browsers = ["chromium", "firefox", "webkit"]
    if browser_type not in valid_browsers:
        error_msg = f"无效的浏览器类型: {browser_type}。支持的选项: {valid_browsers}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    try:
        with sync_playwright() as p:
            logger.info(f"启动 {browser_type} 浏览器...")
            # 动态选择浏览器类型
            browser = getattr(p, browser_type).launch(
                headless=headless,
                slow_mo=0
            )
            logger.info(f"{browser_type} 浏览器启动成功")

            logger.info("创建浏览器上下文...")
            context = browser.new_context(ignore_https_errors=True)  # 显式设置忽略 SSL 错误
            logger.info("浏览器上下文创建成功")

            logger.info("创建新页面...")
            page = context.new_page()
            logger.info("页面创建成功")

            logger.info(f"导航到目标URL: {env['url']}")
            page.goto(env['url'])
            logger.info(f"页面导航完成，当前URL: {page.url}")

            # 检查是否已登录，如果未登录则执行登录
            if not _is_logged_in(page):
                _login(page, env)
                logger.info("登录成功")

            yield page

            logger.info("开始清理浏览器资源...")
            context.close()
            logger.info("浏览器上下文已关闭")
            browser.close()
            logger.info("浏览器已关闭")

    except Exception as e:
        logger.error(f"浏览器初始化失败: {e}")
        raise

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """在setup阶段开始时记录标记"""
    logger.info(f"=== SETUP START: {item.name} ===")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item):
    """在call阶段开始时记录标记"""
    logger.info(f"=== CALL START: {item.name} ===")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item):
    """在teardown阶段开始时记录标记"""
    logger.info(f"=== TEARDOWN START: {item.name} ===")

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()

    # 记录测试开始
    if rep.when == "call":
        if rep.passed:
            logger.info(f"测试通过: {item.name}")
        elif rep.failed:
            logger.error(f"测试失败: {item.name}")
            page = item.funcargs.get("page", None)
            if page:
                try:
                    logger.info(f"开始生成失败截图")
                    # 生成截图
                    screenshot_dir = "screenshots"
                    os.makedirs(screenshot_dir, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_path = os.path.join(
                        screenshot_dir, f"{item.name}_{timestamp}.png"
                    )

                    # 保存截图到文件
                    page.screenshot(path=screenshot_path)
                    logger.info(f"截图保存成功: {screenshot_path}")

                    # 记录失败时的页面信息
                    failure_info = (
                        f"测试失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"测试用例名称: {item.name}\n"
                        f"当前页面URL: {page.url}\n"
                    )
                    logger.error(f"测试失败详情:\n{failure_info}")

                    # 将截图添加到 Allure 报告
                    with open(screenshot_path, "rb") as f:
                        allure.attach(
                            body=f.read(),
                            name=f"失败截图_{item.name}",
                            attachment_type=allure.attachment_type.PNG
                        )

                    # 添加失败时的页面信息
                    allure.attach(
                        body=failure_info,
                        name="失败信息",
                        attachment_type=allure.attachment_type.TEXT
                    )

                    logger.info(f"失败截图已保存并添加到 Allure 报告: {screenshot_path}")

                except Exception as e:
                    logger.error(f"截图保存失败: {e}")
        elif rep.skipped:
            logger.warning(f"测试跳过: {item.name}")
    elif rep.when == "setup":
        if rep.failed:
            logger.error(f"测试设置失败: {item.name}")
    elif rep.when == "teardown":
        if rep.failed:
            logger.error(f"测试清理失败: {item.name}")


@pytest.fixture(scope="session")
def m1(env):
    ssh = SSH()
    ssh.connect(host=env['host'], username="scloudadmin", pkey=get_file_abspath(env['pkey']), use_jumphost=False)
    yield ssh
    ssh.close()


@pytest.fixture(scope="session")
def jump_host(env):
    ssh = SSH()
    ssh._set_jumphost(host=env['host'], username="scloudadmin", pkey=get_file_abspath(env['pkey']))
    yield ssh
    ssh.close()

@pytest.fixture(scope="class")
def ssh(jump_host):
    ssh = SSH()
    ssh.jumphost_client = jump_host.jumphost_client  # 传递跳板机客户端到SSH实例
    yield ssh
    ssh.close()

def _is_logged_in(page):
    """检查是否已登录"""
    try:
        # 检查登录表单是否存在，如果存在说明未登录
        login_form = page.get_by_placeholder("请输入登录账号")
        login_form.wait_for(timeout=2000)
        return False
    except:
        # 找不到登录表单，说明已登录
        return True


def _login(page, env):
    """执行登录操作"""
    username = env.get("username")
    password = env.get("password")

    if not username or not password:
        raise ValueError("环境配置中缺少用户名或密码")

    # 填写登录信息
    page.get_by_placeholder("请输入登录账号").fill(username)
    page.get_by_placeholder("请输入登录密码").fill(password)
    page.get_by_text("登 录").click()

    # 等待页面加载完成
    page.wait_for_load_state("networkidle")
    page.wait_for_load_state("domcontentloaded")