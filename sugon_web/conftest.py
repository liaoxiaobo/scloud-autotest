import datetime
import pytest
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from sugon_web.utils.logger import logger
from sugon_web.utils.util import get_file_abspath, capture_failure_screenshot
from sugon_web.common.ssh import SSH
from sugon_web.common.base import BasePage
from sugon_web.config.config import Config

def pytest_addoption(parser):
    """添加命令行参数支持"""
    parser.addoption("--host", action="store", help="指定测试环境的主机地址")
    parser.addoption("--browser-type", action="store", help="指定浏览器类型 (chromium/firefox/webkit)")
    parser.addoption("--headless", action="store", help="是否无头模式 (true/false)")
    parser.addoption("--stor", action="store", help="指定存储类型")
    parser.addoption("--username", action="store", help="登录用户名")
    parser.addoption("--password", action="store", help="登录密码")

def pytest_configure(config):
    """pytest 配置钩子，用于设置日志文件路径和 allure-result 目录"""

    # 获取项目根目录
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent

    # 创建 logs 目录
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    # 设置日志文件路径（添加日期）
    today = datetime.now().strftime("%Y-%m-%d")
    log_file_path = log_dir / f"pytest-{today}.log"
    config.option.log_file = str(log_file_path)

    # 创建 allure-result 目录
    allure_dir = project_root / "allure-result"
    allure_dir.mkdir(exist_ok=True)

    # 设置 allure-result 目录路径
    config.option.allure_report_dir = str(allure_dir)


@pytest.fixture(scope="session")
def config(pytestconfig):
    """配置fixture，初始化Config类并返回Config对象"""
    # 获取命令行参数
    host = pytestconfig.getoption("--host")
    browser_type = pytestconfig.getoption("--browser-type")
    headless = pytestconfig.getoption("--headless")
    stor = pytestconfig.getoption("--stor")
    username = pytestconfig.getoption("--username")
    password = pytestconfig.getoption("--password")

    # 加载配置
    Config.load(host=host)

    # 覆盖配置（使用命令行参数）
    Config.override(
        browser=browser_type,
        headless=headless,
        stor=stor,
        username=username,
        password=password
    )
    logger.info(f"测试配置加载完成: {Config.get()}")
    return Config

@pytest.fixture(scope="session")
def browser(config):
    """
    Session级别的browser fixture
    所有测试用例共享同一个浏览器实例，提高性能
    """
    # 从Config对象获取配置
    browser_type = config.get("browser")
    headless = config.get("headless")
    slow_mo = config.get("slow_mo")

    logger.info(f"开始初始化浏览器: type={browser_type}, headless={headless}")

    try:
        with sync_playwright() as p:
            logger.info("启动浏览器...")
            # 动态选择浏览器类型
            browser = getattr(p, browser_type).launch(
                headless=headless,
                slow_mo=slow_mo
            )
            logger.info(f"浏览器 {browser_type} 启动成功")

            yield browser

            logger.info("浏览器关闭中...")
            browser.close()
            logger.info("浏览器已关闭")

    except Exception as e:
        logger.error(f"浏览器初始化失败: {e}")
        raise


@pytest.fixture(scope="class")
def browser_context(browser):
    """
    浏览器上下文fixture

    Context是浏览器上下文，类似于浏览器的隐身模式窗口。
    每个context有独立的cookies、localStorage等数据。
    """
    context = browser.new_context(
        ignore_https_errors=True,  # 忽略 SSL 错误
        permissions=["clipboard-read", "clipboard-write"],  # 剪贴板权限
    )

    logger.info("浏览器上下文创建成功")

    yield context

    context.close()
    logger.info("浏览器上下文已关闭")


@pytest.fixture(scope="class")
def page(browser_context, config):
    """
    每个测试用例获得独立的页面实例，保证测试隔离性
    受限于用例设计及被依赖fixture，此fixture暂时只能在class级别使用
    """
    base_url = config.get("base_url")
    username = config.get("username")
    password = config.get("password")

    try:
        logger.info("创建新页面...")
        page = browser_context.new_page()
        logger.info("页面创建成功")

        logger.info(f"导航到目标URL: {base_url}")
        page.goto(base_url)
        logger.info(f"页面导航完成，当前URL: {page.url}")

        # 检查是否已登录，如果未登录则执行登录
        if not _is_logged_in(page):
            _login(page, {"username": username, "password": password})
            logger.info("登录成功")

            # 关闭弹窗
            base_page_obj = BasePage(page)
            base_page_obj.close_dialog_if_exists()

        yield page

    except Exception as e:
        logger.error(f"页面初始化失败: {e}")
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
    """处理测试报告，在失败时截图并添加到Allure报告"""
    outcome = yield
    rep = outcome.get_result()

    # 获取页面对象
    page = item.funcargs.get("page", None)

    # 处理call阶段（测试执行阶段）
    if rep.when == "call":
        if rep.passed:
            logger.info(f"测试通过: {item.name}")
        elif rep.failed:
            logger.error(f"测试失败: {item.name}")
            if page:
                capture_failure_screenshot(page, item, "call")
        elif rep.skipped:
            logger.warning(f"测试跳过: {item.name}")

    # 处理setup阶段（测试前置准备阶段）
    elif rep.when == "setup":
        if rep.failed:
            logger.error(f"测试设置失败: {item.name}")
            if page:
                capture_failure_screenshot(page, item, "setup")

    # 处理teardown阶段（测试清理阶段）
    elif rep.when == "teardown":
        if rep.failed:
            logger.error(f"测试清理失败: {item.name}")
            if page:
                capture_failure_screenshot(page, item, "teardown")


@pytest.fixture(scope="session")
def ssh_host(config):
    """创建直接连接到目标主机的SSH会话，不使用跳板机"""
    host = config.get("host")
    pkey = config.get("pkey")

    ssh = SSH()
    ssh.connect(host=host, username="scloudadmin", pkey=get_file_abspath(pkey), use_jumphost=False)
    yield ssh
    ssh.close()


@pytest.fixture(scope="session")
def jump_host(config):
    """创建并配置跳板机连接"""
    host = config.get("host")
    pkey = config.get("pkey")

    ssh = SSH()
    ssh._set_jumphost(host=host, username="scloudadmin", pkey=get_file_abspath(pkey))
    yield ssh
    ssh.close()

@pytest.fixture(scope="class")
def ssh_vm(jump_host):
    """创建通过跳板机连接的SSH会话"""
    ssh = SSH()
    try:
        ssh.jumphost_client = jump_host.jumphost_client
        yield ssh
    finally:
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


def _login(page, config):
    """执行登录操作"""
    username = config.get("username")
    password = config.get("password")

    if not username or not password:
        raise ValueError("环境配置中缺少用户名或密码")

    # 填写登录信息
    page.get_by_placeholder("请输入登录账号").fill(username)
    page.get_by_placeholder("请输入登录密码").fill(password)
    page.get_by_text("登 录").click()

    # 等待页面加载完成
    page.wait_for_load_state("networkidle")
    page.wait_for_load_state("domcontentloaded")