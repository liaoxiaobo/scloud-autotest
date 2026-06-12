"""
全局 Pytest 配置与 Session/Class/Function 级 Fixture 定义。

职责范围:
- 命令行参数注册 (pytest_addoption)
- 运行产物目录隔离与 Allure 配置 (pytest_configure)
- 浏览器/上下文/页面生命周期管理
- 登录态维护与自动重试登录
- SSH 连接、节点信息探测、部署模式与补丁版本初始化
- 测试失败自动截图并附加到 Allure

============================================================
⚠️ 重要提示：该文件禁止修改已有方法 ⚠️
如需新增功能，请仅通过新增函数/fixture 实现。
严禁直接改动现有代码。
============================================================
"""

import datetime
import os
import re

import allure
import pytest
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from sugon_web.utils.logger import logger
from sugon_web.utils.data import get_file_abspath
from sugon_web.utils.hooks import capture_failure_screenshot, get_page_from_item
from sugon_web.common.remote.ssh import SSH
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
    parser.addoption("--tracing", action="store_true", default=False, help="开启 Playwright tracing")

def _get_run_id_from_args(config):
    """从 pytest 命令行参数提取运行标识，保留与 sugon_web/testcase 一致的目录层级"""
    candidates = []
    for arg in list(config.args):
        if not arg.startswith('-'):
            candidates.append(arg)

    if not candidates:
        for arg in list(config.invocation_params.args):
            if not arg.startswith('-'):
                candidates.append(arg)

    project_root = Path(__file__).resolve().parent.parent

    for candidate in candidates:
        parts = candidate.split('::')
        first_part = parts[0]
        path = Path(first_part).resolve()

        # 转为相对于项目根目录的路径
        try:
            rel_path = path.relative_to(project_root)
        except ValueError:
            rel_path = path

        rel_str = rel_path.as_posix()

        # 去掉 sugon_web/ 前缀（包名前缀，不是测试组织层级语义）
        if rel_str.startswith('sugon_web/'):
            rel_str = rel_str[len('sugon_web/'):]

        # 去掉 testcase/ 前缀，产物直接落在 logs/network/... 层级
        if rel_str.startswith('testcase/'):
            rel_str = rel_str[len('testcase/'):]
        elif rel_str == 'testcase':
            rel_str = ''

        if path.suffix == '.py':
            # 去掉 .py 后缀
            run_id = rel_str[:-3] if rel_str.endswith('.py') else rel_str
            # 如果指定了类名，追加为子路径
            if len(parts) > 1 and parts[1].startswith('Test'):
                run_id = f"{run_id}/{parts[1]}"
            return run_id

        if path.is_dir():
            return rel_str

    testpaths = config.getini('testpaths')
    if testpaths:
        rel = Path(testpaths[0]).as_posix()
        if rel.startswith('sugon_web/'):
            rel = rel[len('sugon_web/'):]
        if rel.startswith('testcase/'):
            rel = rel[len('testcase/'):]
        return rel
    return "default"


def pytest_configure(config):
    """pytest 配置钩子，用于设置日志文件路径和 allure-result 目录"""

    # 获取项目根目录
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent

    # 从命令行参数提取运行标识（测试文件名或类名）
    run_id = _get_run_id_from_args(config)
    os.environ['_PYTEST_RUN_ID'] = run_id

    # 创建 logs 子目录（按 run_id 隔离）
    log_dir = project_root / "logs" / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    # 设置日志文件路径（添加日期）
    today = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_path = log_dir / f"pytest-{today}.log"
    config.option.log_file = str(log_file_path)

    # 创建 allure-result 子目录（按 run_id 隔离），仅清理本子目录历史数据
    allure_dir = project_root / "allure-result" / run_id
    if allure_dir.exists():
        import shutil
        shutil.rmtree(allure_dir)
    allure_dir.mkdir(parents=True, exist_ok=True)

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
                slow_mo=slow_mo,
                args=["--ignore-certificate-errors", "--ignore-certificate-errors-spki-list"],
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
def browser_context(browser, request):
    """
    浏览器上下文fixture

    Context是浏览器上下文，类似于浏览器的隐身模式窗口。
    每个context有独立的cookies、localStorage等数据。
    """
    context = browser.new_context(
        ignore_https_errors=True,  # 忽略 SSL 错误
        permissions=["clipboard-read", "clipboard-write"],  # 剪贴板权限
    )

    # 根据 --tracing 参数决定是否开启 Playwright tracing
    trace_enabled = request.config.getoption("--tracing")
    trace_path = None
    if trace_enabled:
        trace_dir = Path(__file__).resolve().parent.parent / "traces"
        trace_dir.mkdir(exist_ok=True)
        trace_path = trace_dir / f"trace_{request.node.name}.zip"
        # screenshots=False + sources=False 大幅减小 trace 体积（约90%），
        # 保留 snapshots=True 以获取 DOM 结构用于失败分析（弹窗内容、数据量等）
        context.tracing.start(screenshots=False, snapshots=True, sources=False)
        logger.info(f"tracing 已开启，trace 文件将保存至: {trace_path}")

    logger.info("浏览器上下文创建成功")
    request.node._browser_context = context

    yield context

    if trace_enabled and trace_path:
        context.tracing.stop(path=str(trace_path))
        logger.info(f"tracing 已停止，trace 文件: {trace_path}")
    context.close()
    logger.info("浏览器上下文已关闭")


def _create_logged_in_page(browser_context, config):
    """基于给定的 context 创建并返回一个已登录页面。"""
    from sugon_web.common.auth import prepare_page_session

    base_url = config.get("base_url")

    logger.info("创建新页面...")
    page = browser_context.new_page()
    logger.info("页面创建成功")

    prepare_page_session(page, config)

    # 安全网：若URL异常（如 no-permission），重新加载以恢复
    if "no-permission" in page.url:
        logger.info(f"页面在 no-permission，尝试重新加载恢复...")
        try:
            page.goto(base_url)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)
            logger.info(f"重新加载后URL: {page.url}")
        except Exception as e:
            logger.warning(f"重新加载失败: {e}")

    base_page_obj = BasePage(page)
    base_page_obj.close_dialog_if_exists()

    # 拦截 page.close()，在 fixture 失败关闭 page 前自动截图
    _orig_close = page.close

    def _close_with_screenshot():
        import sys
        if sys.exc_info()[0] is not None:
            try:
                screenshot_bytes = page.screenshot()
                if not hasattr(browser_context, '_failure_screenshots'):
                    browser_context._failure_screenshots = []
                browser_context._failure_screenshots.append(screenshot_bytes)
                logger.info("fixture page 关闭前自动截图成功")
            except Exception as e:
                logger.warning(f"fixture page 关闭前自动截图失败: {e}")
        _orig_close()

    page.close = _close_with_screenshot
    return page


@pytest.fixture(scope="function")
def page(browser_context, config):
    """
    每个测试用例获得独立的页面实例，减少同类测试之间的页面污染
    浏览器上下文仍按 class 复用，以保留类内共享登录态
    """
    try:
        page = _create_logged_in_page(browser_context, config)

        yield page

        page.close()
        logger.info("页面已关闭")

    except Exception as e:
        logger.error(f"页面初始化失败: {e}")
        raise


def _attach_pre_captured_screenshots(item, stage):
    """将 fixture 在关闭前预截的图保存到 screenshots 目录并附加到 Allure 报告。"""
    browser_context = item.funcargs.get("browser_context")
    if not browser_context:
        parent = getattr(item, 'parent', None)
        if parent:
            browser_context = getattr(parent, '_browser_context', None)

    if not browser_context or not hasattr(browser_context, '_failure_screenshots'):
        return

    screenshots = browser_context._failure_screenshots
    if not screenshots:
        return

    # 统一将运行产物落在仓库根目录，与 capture_failure_screenshot 保持一致
    project_root = Path(__file__).resolve().parent.parent
    screenshot_dir = project_root / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)

    for idx, screenshot_bytes in enumerate(screenshots):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = screenshot_dir / f"{item.name}_{stage}_{timestamp}_{idx + 1}.png"

            with open(screenshot_path, "wb") as f:
                f.write(screenshot_bytes)
            logger.info(f"{stage}截图保存成功: {screenshot_path}")

            with open(screenshot_path, "rb") as f:
                allure.attach(
                    body=f.read(),
                    name=f"失败截图_{stage}_{idx + 1}",
                    attachment_type=allure.attachment_type.PNG
                )
        except Exception as e:
            logger.warning(f"附加{stage}截图到 Allure 失败: {e}")

    # 清空，避免重复附加
    browser_context._failure_screenshots.clear()


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

    # 先处理 fixture 失败时预截图的数据（fixture 在 makereport 前已关闭 page）
    _attach_pre_captured_screenshots(item, rep.when)

    # 获取page对象
    page = get_page_from_item(item)

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


@pytest.fixture(scope="session", autouse=True)
def load_deploy_mode(ssh_host):
    """会话初始化时读取部署模式并写入 Config。

    通过 SSH 读取远端 env.yaml 中的 deploy_mode，剥离自 Config 类
    （配置管理器不应包含 SSH 业务逻辑）。
    """
    env_file = "/opt/extra/init-base/env/env.yaml"
    read_cmd = f"cat {env_file} | grep deploy_mode"
    deploy_mode = None

    try:
        current_node = ssh_host.run("hostname", check_rc=True).strip()
        if current_node == "master01":
            output = ssh_host.run(read_cmd, check_rc=True)
        else:
            output = ssh_host.run(
                f'ssh -o StrictHostKeyChecking=no master01 "{read_cmd}"', check_rc=True
            )
        match = re.search(r"^\s*deploy_mode\s*:\s*(\S+)", output, re.MULTILINE)
        deploy_mode = match.group(1).strip() if match else None
    except Exception as exc:
        logger.warning(f"读取 deploy_mode 失败: {exc}")

    Config.set("deploy_mode", deploy_mode)
    return deploy_mode


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

@pytest.fixture(scope="session", autouse=True)
def check_compute_nodes(ssh_host, config):
    """
    检查物理机节点信息并更新到配置中

    Args:
        ssh_host: 直接连接到目标主机的SSH会话对象
        config: Config 对象，用于更新节点数信息

    Returns:
        dict: 包含节点信息的字典
            - nodes: 节点名称列表
            - count: 节点数量
    """
    # 使用 ssh_host 获取节点信息
    try:
        logger.info("开始获取物理机节点信息...")
        # 获取集群的节点
        _output = ssh_host.run("scli aggregate list | grep Autotest | awk '{print $6}'")
        _node_count = _output.split('(')[1].split(')')[0]

        # 将节点信息更新到 config 中
        Config.set('_node_count', _node_count)

        # 返回节点信息
        return {
            'nodes': _node_count
        }

    except Exception as e:
        logger.error(f"获取物理机节点信息失败: {e}")
        _nodes = []

def _write_allure_environment():
    """将 Config 配置信息写入 Allure 的 environment.properties 文件"""
    try:
        # 获取项目根目录和 allure-result 目录
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent
        run_id = os.environ.get('_PYTEST_RUN_ID', 'default')
        allure_dir = project_root / "allure-result" / run_id

        # 确保 allure-result 目录存在
        allure_dir.mkdir(parents=True, exist_ok=True)

        # environment.properties 文件路径
        env_file = allure_dir / "environment.properties"

        # 获取 Config 中的所有配置
        config_data = Config.get()

        env_mappings = [
            ("ENV", "host"),  # 测试环境主机地址
            ("URL", "base_url"),  # 基础URL
            ("STOR", "stor"),  # 存储类型
            ("USER", "username"), # 登录用户名
            ("Arch", "architecture") # 架构类型
        ]

        # 构建环境信息内容
        env_content = []

        # 按照定义的顺序添加环境信息
        for label, config_key in env_mappings:
            if config_key:
                # 从 Config 中获取值
                value = config_data.get(config_key, "Unknown")
            else:
                # 动态生成的值（如测试日期）
                value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            env_content.append(f"{label}={value}")
        patch = config_data.get("patch")
        for key, value in patch.items():
            if key in ["VERSION", "BUILD_TIME", "COMMIT"]:
                env_content.append(f"{key}={value}")
        env_text = '\n'.join(env_content)

        # 写入 run_id 子目录（保留按运行隔离的副本）
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_text)

        # 同时写入 allure-result 根目录，供 allure generate 读取
        root_env_file = project_root / "allure-result" / "environment.properties"
        root_env_file.parent.mkdir(parents=True, exist_ok=True)
        with open(root_env_file, 'w', encoding='utf-8') as f:
            f.write(env_text)

    except Exception as e:
        logger.error(f"写入 Allure 环境信息失败: {e}")

@pytest.fixture(scope="session", autouse=True)
def _get_patch_version(ssh_host, config):
    """
    获取补丁版本信息
    """
    logger.info("开始获取补丁版本信息...")
    env_dic = {}
    # 获取环境节点信息
    hosts = ssh_host._get_host()

    # 获取环境版本信息
    first_host = hosts['master'][0]
    version_info = ssh_host._get_release_version(first_host)
    env_dic.update(version_info)

    Config.set('patch', env_dic)

    try:
        architecture = ssh_host.run(r"arch", check_rc=True)
    except Exception as e:
        architecture = None
        logger.warning(f"无法获取节点架构信息: {e}")
    Config.set('architecture', architecture)

    _write_allure_environment()
