import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageStat
from playwright._impl._errors import TargetClosedError

from sugon_web.utils.logger import allure_step_log, logger
import allure


DEFAULT_VNC_PASSWORD = "sugon@20"
DEFAULT_ISO_LOGIN_USER = "root"
DEFAULT_ISO_LOGIN_PASSWORD = "admin1234@sugon"
VNC_FINAL_LOGIN_SUCCESS = "login_success"
VNC_FINAL_CONSOLE_LOGIN_PROMPT = "console_login_prompt"


def _attach_vnc_screenshot(canvas, name: str, suffix: str):
    screenshot_dir = Path(__file__).resolve().parents[3] / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)
    screenshot_path = screenshot_dir / f"{name}_{suffix}_{time.strftime('%Y%m%d%H%M%S')}.png"
    canvas.screenshot(path=str(screenshot_path))
    with open(screenshot_path, "rb") as f:
        allure.attach(
            body=f.read(),
            name=f"vnc_{name}_{suffix}",
            attachment_type=allure.attachment_type.PNG,
        )
    logger.info(f"VNC截图已保存: {screenshot_path}")


def _vnc_screenshot_diff(previous: bytes, current: bytes) -> float:
    """计算两张 VNC canvas 截图的归一化平均差异。"""
    previous_img = Image.open(BytesIO(previous)).convert("L").resize((160, 90))
    current_img = Image.open(BytesIO(current)).convert("L").resize((160, 90))
    diff = ImageChops.difference(previous_img, current_img)
    return ImageStat.Stat(diff).mean[0] / 255


def _wait_vnc_install_screen_stable(
    page,
    canvas,
    vm_name: str,
    timeout: int,
    screenshot_interval: int = 300,
    poll_interval: int = 30,
    min_install_seconds: int = 900,
    stable_seconds: int = 300,
    stable_threshold: float = 0.003,
):
    """等待安装画面连续稳定，作为 ISO 安装完成的 UI 信号。"""
    started_at = time.time()
    deadline = started_at + timeout
    stable_since = None
    next_screenshot = started_at + screenshot_interval
    previous = canvas.screenshot()

    while time.time() < deadline:
        page.wait_for_timeout(poll_interval * 1000)
        current = canvas.screenshot()
        diff = _vnc_screenshot_diff(previous, current)
        elapsed = time.time() - started_at
        logger.info(
            f"云服务器 {vm_name}: ISO安装等待中 elapsed={elapsed:.0f}s, "
            f"screen_diff={diff:.5f}, stable_since={stable_since}"
        )

        if elapsed >= min_install_seconds and diff <= stable_threshold:
            stable_since = stable_since or time.time()
            if time.time() - stable_since >= stable_seconds:
                _attach_vnc_screenshot(canvas, vm_name, "install-stable")
                logger.info(f"云服务器 {vm_name}: VNC画面连续稳定，判定ISO安装完成")
                return
        else:
            stable_since = None

        if time.time() >= next_screenshot:
            _attach_vnc_screenshot(canvas, vm_name, "installing")
            next_screenshot = time.time() + screenshot_interval
        previous = current

    _attach_vnc_screenshot(canvas, vm_name, "install-timeout")
    raise AssertionError(
        f"[VNCAssertion] 等待ISO安装完成超时 | 云服务器: {vm_name} | 超时: {timeout}s"
    )


def _login_installed_iso_from_vnc(
    page,
    canvas,
    vm_name: str,
    username: str = DEFAULT_ISO_LOGIN_USER,
    password: str = DEFAULT_ISO_LOGIN_PASSWORD,
    login_timeout: int = 120,
    success_diff_threshold: float = 0.035,
    stable_seconds: int = 15,
    stable_threshold: float = 0.004,
):
    """在安装完成后的 VNC 登录页输入账号密码，并通过画面变化和稳定性校验登录成功。"""
    before_login = canvas.screenshot()
    _attach_vnc_screenshot(canvas, vm_name, "before-login")

    box = canvas.bounding_box() or {"width": 1000, "height": 700}
    canvas.click(position={"x": int(box["width"] * 0.5), "y": int(box["height"] * 0.56)})
    page.keyboard.type(username, delay=50)
    page.keyboard.press("Enter")
    page.wait_for_timeout(2000)
    page.keyboard.type(password, delay=50)
    page.keyboard.press("Enter")

    deadline = time.time() + login_timeout
    last_diff = 0.0
    stable_since = None
    previous_after_login = None
    changed_snapshot_attached = False
    while time.time() < deadline:
        page.wait_for_timeout(5000)
        after_login = canvas.screenshot()
        last_diff = _vnc_screenshot_diff(before_login, after_login)
        frame_diff = (
            _vnc_screenshot_diff(previous_after_login, after_login)
            if previous_after_login
            else 1.0
        )
        logger.info(
            f"云服务器 {vm_name}: ISO系统登录校验中 screen_diff={last_diff:.5f}, "
            f"frame_diff={frame_diff:.5f}, threshold={success_diff_threshold}, "
            f"stable_since={stable_since}"
        )
        if last_diff >= success_diff_threshold and frame_diff <= stable_threshold:
            stable_since = stable_since or time.time()
            if time.time() - stable_since >= stable_seconds:
                _attach_vnc_screenshot(canvas, vm_name, "login-success")
                logger.info(f"云服务器 {vm_name}: VNC使用 {username} 登录成功")
                return
        else:
            stable_since = None

        if last_diff >= success_diff_threshold and not changed_snapshot_attached:
            _attach_vnc_screenshot(canvas, vm_name, "login-changed")
            changed_snapshot_attached = True
        previous_after_login = after_login

    _attach_vnc_screenshot(canvas, vm_name, "login-failed")
    raise AssertionError(
        f"[VNCAssertion] ISO安装后VNC登录失败或画面未进入登录后系统界面 | 云服务器: {vm_name} | "
        f"用户: {username} | 最后screen_diff: {last_diff:.5f}"
    )


def _assert_iso_console_login_prompt_from_vnc(
    page,
    canvas,
    vm_name: str,
    ready_timeout: int = 120,
    stable_seconds: int = 20,
    stable_threshold: float = 0.004,
):
    """校验 ISO 安装完成后停在文本控制台登录提示页。"""
    deadline = time.time() + ready_timeout
    stable_since = None
    previous = canvas.screenshot()

    while time.time() < deadline:
        page.wait_for_timeout(5000)
        current = canvas.screenshot()
        frame_diff = _vnc_screenshot_diff(previous, current)
        logger.info(
            f"云服务器 {vm_name}: 等待文本控制台登录提示稳定中 "
            f"frame_diff={frame_diff:.5f}, threshold={stable_threshold}, stable_since={stable_since}"
        )
        if frame_diff <= stable_threshold:
            stable_since = stable_since or time.time()
            if time.time() - stable_since >= stable_seconds:
                _attach_vnc_screenshot(canvas, vm_name, "console-login-prompt")
                logger.info(f"云服务器 {vm_name}: VNC已停在文本控制台登录提示页")
                return
        else:
            stable_since = None
        previous = current

    _attach_vnc_screenshot(canvas, vm_name, "console-login-prompt-timeout")
    raise AssertionError(
        f"[VNCAssertion] ISO安装后未稳定停在文本控制台登录提示页 | 云服务器: {vm_name} | "
        f"超时: {ready_timeout}s"
    )


def _probe_boot_started(
    page,
    canvas,
    vm_name: str,
    probe_timeout: int = 120,
    poll_interval: int = 10,
    activity_threshold: float = 0.02,
    big_change_threshold: float = 0.08,
    required_hits: int = 3,
):
    """探测发送引导键后 VNC 画面是否出现活动，判断是否真正进入引导/安装。"""
    started_at = time.time()
    deadline = started_at + probe_timeout
    previous = canvas.screenshot()
    hits = 0
    max_diff = 0.0

    while time.time() < deadline:
        page.wait_for_timeout(poll_interval * 1000)
        current = canvas.screenshot()
        diff = _vnc_screenshot_diff(previous, current)
        max_diff = max(max_diff, diff)
        elapsed = time.time() - started_at
        logger.info(
            f"云服务器 {vm_name}: 引导活动探测 elapsed={elapsed:.0f}s, "
            f"screen_diff={diff:.5f}, hits={hits}, max_diff={max_diff:.5f}"
        )
        if diff >= big_change_threshold:
            logger.info(f"云服务器 {vm_name}: 检测到画面大幅变化，判定已进入引导/安装")
            return True
        if diff >= activity_threshold:
            hits += 1
            if hits >= required_hits:
                logger.info(f"云服务器 {vm_name}: 检测到持续画面活动，判定已进入引导/安装")
                return True
        else:
            hits = 0
        previous = current

    logger.warning(
        f"云服务器 {vm_name}: 引导探测窗口内画面持续静止 (max_diff={max_diff:.5f})，"
        f"判定未进入引导菜单"
    )
    return False


def _wait_vnc_screen_settled(
    page,
    canvas,
    vm_name: str,
    settle_timeout: int = 40,
    poll_interval: int = 2,
    settle_threshold: float = 0.01,
):
    """等待 VNC 画面静止（连续两帧差异低于阈值）。"""
    previous = canvas.screenshot()
    started_at = time.time()
    while time.time() - started_at < settle_timeout:
        page.wait_for_timeout(poll_interval * 1000)
        current = canvas.screenshot()
        diff = _vnc_screenshot_diff(previous, current)
        elapsed = time.time() - started_at
        logger.info(
            f"云服务器 {vm_name}: 等待 boot: 提示符静止 elapsed={elapsed:.0f}s, diff={diff:.5f}"
        )
        if diff < settle_threshold:
            logger.info(f"云服务器 {vm_name}: 画面已静止，判定停在 boot: 提示符")
            return True
        previous = current
    logger.warning(f"云服务器 {vm_name}: 等待 boot: 提示符静止超时，仍按既定流程发送启动按键")
    return False


def _press_keys(page_obj, keys: list[str], delay_ms: int = 500):
    for key in keys:
        page_obj.keyboard.press(key)
        page_obj.wait_for_timeout(delay_ms)


def _open_vnc_and_select_install(
    new_page, vncpwd: str, boot_prompt_mode: bool = False,
    boot_interrupt_keys: list[str] | None = None,
    boot_device_keys: list[str] | None = None,
    boot_keys: list[str] | None = None,
    vm_name: str = "",
):
    """打开 VNC 并选择 ISO 安装项。"""
    from playwright.sync_api import expect
    iframe = new_page.locator("#app iframe").content_frame
    try:
        iframe.get_by_label("Password:").fill(vncpwd)
    except Exception:
        iframe.get_by_label("密码：").fill(vncpwd)
    iframe.get_by_role("button", name="确认").click()

    canvas = iframe.locator("canvas")
    expect(canvas).to_be_visible(timeout=30000)
    canvas.click()

    if boot_prompt_mode:
        # ISO 默认引导菜单是 syslinux vesamenu（方向键导航 + 回车选择），约 60s 后自动
        # 引导默认高亮项 "Boot from local drive" → 空盘卡死。任意按键都会取消自动倒计时。
        # 等画面静止后截图，用 boot_keys 方向键序列把高亮移到目标安装项，再截图确认后回车。
        _wait_vnc_screen_settled(new_page, canvas, vm_name, settle_timeout=60)
        _attach_vnc_screenshot(canvas, vm_name, "iso-boot-menu")
        _press_keys(new_page, boot_keys or ["Enter"], delay_ms=600)
        new_page.wait_for_timeout(500)
        _attach_vnc_screenshot(canvas, vm_name, "iso-boot-menu-highlighted")
        new_page.keyboard.press("Enter")
        logger.info(
            f"云服务器 {vm_name}: 已在 ISO 引导菜单用 {boot_keys} 选中安装项并回车，等待安装完成"
        )
        return canvas

    if boot_interrupt_keys:
        baseline = canvas.screenshot()
        menu_appeared = False
        for idx in range(len(boot_interrupt_keys)):
            new_page.keyboard.press("Escape")
            new_page.wait_for_timeout(300)
            esc_diff = _vnc_screenshot_diff(baseline, canvas.screenshot())
            logger.info(
                f"云服务器 {vm_name}: 抢 ESC 第 {idx + 1} 次, diff_vs_post={esc_diff:.5f}"
            )
            if esc_diff >= 0.015:
                menu_appeared = True
                break
        new_page.wait_for_timeout(500)
        logger.info(f"云服务器 {vm_name}: SeaBIOS 引导菜单检测 menu_appeared={menu_appeared}")
        _attach_vnc_screenshot(canvas, vm_name, "bios-boot-menu")
    else:
        new_page.wait_for_timeout(5000)
        _attach_vnc_screenshot(canvas, vm_name, "boot-menu")

    if boot_device_keys:
        _press_keys(new_page, boot_device_keys, delay_ms=500)
        new_page.wait_for_timeout(3000)
        _attach_vnc_screenshot(canvas, vm_name, "iso-install-menu")

    _press_keys(new_page, boot_keys or ["Enter"], delay_ms=500)
    logger.info(f"云服务器 {vm_name}: 已选择 ISO 安装菜单，等待安装完成")
    return canvas


def _restart_vm(ecs_page, vm_name: str):
    ecs_page.goto_service("弹性云服务器")
    ecs_page.wait_for_page_ready()
    ecs_page.search(vm_name)
    ecs_page.ecs_operations(vm_name, "重启")
    ecs_page.wait_for_page_ready()
    logger.info(f"云服务器 {vm_name}: 已下发重启，准备进入 VNC 选择 ISO 安装项")


def install_iso_from_vnc(
    ecs_page,
    vm_name: str,
    vncpwd: str = DEFAULT_VNC_PASSWORD,
    restart_before_vnc: bool = False,
    boot_interrupt_keys: list[str] | None = None,
    boot_device_keys: list[str] | None = None,
    boot_keys: list[str] | None = None,
    boot_prompt_mode: bool = False,
    install_timeout: int = 3600,
    screenshot_interval: int = 300,
    min_install_seconds: int = 900,
    stable_seconds: int = 300,
    login_username: str = DEFAULT_ISO_LOGIN_USER,
    login_password: str = DEFAULT_ISO_LOGIN_PASSWORD,
    expected_final_state: str = VNC_FINAL_LOGIN_SUCCESS,
    max_boot_attempts: int = 3,
    boot_probe_timeout: int = 180,
):
    """进入 VNC，选择 ISO 启动菜单中的安装项并等待安装流程完成。"""
    boot_interrupt_keys = boot_interrupt_keys or []
    boot_device_keys = boot_device_keys or []
    boot_keys = boot_keys or ["Enter"]
    logger.info(
        f"云服务器 {vm_name}: 进入 VNC 执行 ISO 安装，"
        f"restart_before_vnc={restart_before_vnc}, "
        f"boot_interrupt_keys={boot_interrupt_keys}, "
        f"boot_device_keys={boot_device_keys}, boot_keys={boot_keys}, "
        f"boot_prompt_mode={boot_prompt_mode}"
    )

    install_started = False
    vnc_closed = False
    for attempt in range(1, max_boot_attempts + 1):
        if restart_before_vnc or attempt > 1:
            logger.info(
                f"云服务器 {vm_name}: 第 {attempt}/{max_boot_attempts} 次进入引导尝试，先重启虚拟机"
            )
            _restart_vm(ecs_page, vm_name)

        try:
            with ecs_page.new_tab_context(
                trigger_action=lambda: ecs_page._trigger_instance_login(vm_name, login_type="VNC"),
                timeout=30,
            ) as new_page:
                canvas = _open_vnc_and_select_install(
                    new_page, vncpwd, boot_prompt_mode=boot_prompt_mode,
                    boot_interrupt_keys=boot_interrupt_keys,
                    boot_device_keys=boot_device_keys,
                    boot_keys=boot_keys,
                    vm_name=vm_name,
                )

                if (boot_interrupt_keys or boot_prompt_mode) and not _probe_boot_started(
                    new_page, canvas, vm_name, probe_timeout=boot_probe_timeout
                ):
                    _attach_vnc_screenshot(canvas, vm_name, f"boot-miss-attempt-{attempt}")
                    logger.warning(
                        f"云服务器 {vm_name}: 第 {attempt} 次未进入引导菜单，关闭 VNC 后重启重试"
                    )
                    continue

                install_started = True
                _wait_vnc_install_screen_stable(
                    new_page,
                    canvas,
                    vm_name,
                    timeout=install_timeout,
                    screenshot_interval=screenshot_interval,
                    min_install_seconds=min_install_seconds,
                    stable_seconds=stable_seconds,
                )
                if expected_final_state == VNC_FINAL_CONSOLE_LOGIN_PROMPT:
                    _assert_iso_console_login_prompt_from_vnc(new_page, canvas, vm_name)
                    logger.info(f"云服务器 {vm_name}: ISO 安装完成，最终停在文本控制台登录提示页")
                    return

                _login_installed_iso_from_vnc(
                    new_page,
                    canvas,
                    vm_name,
                    username=login_username,
                    password=login_password,
                )
                logger.info(f"云服务器 {vm_name}: ISO 安装并登录校验完成")
                return
        except TargetClosedError:
            vnc_closed = True
            logger.warning(
                f"云服务器 {vm_name}: VNC 页面关闭，返回云服务器页面等待后重试登录"
            )
            break

    if not install_started and not vnc_closed:
        raise AssertionError(
            f"[VNCAssertion] 多次重启后仍未进入 ISO 引导菜单 | 云服务器: {vm_name} | "
            f"尝试次数: {max_boot_attempts}"
        )

    if vnc_closed:
        ecs_page.goto_service("弹性云服务器")
        ecs_page.wait_for_page_ready()
        wait_minutes = 15
        logger.info(f"云服务器 {vm_name}: 返回云服务器页面，等待 {wait_minutes} 分钟后重新打开 VNC")
        ecs_page.page.wait_for_timeout(wait_minutes * 60 * 1000)

        max_login_retries = 3
        login_retry_interval = 10 * 60
        for attempt in range(1, max_login_retries + 1):
            logger.info(f"云服务器 {vm_name}: 第 {attempt} 次尝试重新打开 VNC 校验最终状态")
            try:
                with ecs_page.new_tab_context(
                    trigger_action=lambda: ecs_page._trigger_instance_login(vm_name, login_type="VNC"),
                    timeout=30,
                ) as new_page:
                    from playwright.sync_api import expect
                    iframe = new_page.locator("#app iframe").content_frame
                    try:
                        iframe.get_by_label("Password:").fill(vncpwd)
                    except Exception:
                        iframe.get_by_label("密码：").fill(vncpwd)
                    iframe.get_by_role("button", name="确认").click()

                    canvas = iframe.locator("canvas")
                    expect(canvas).to_be_visible(timeout=30000)
                    _attach_vnc_screenshot(canvas, vm_name, f"retry-{attempt}-before-login")

                    if expected_final_state == VNC_FINAL_CONSOLE_LOGIN_PROMPT:
                        _assert_iso_console_login_prompt_from_vnc(new_page, canvas, vm_name)
                        logger.info(
                            f"云服务器 {vm_name}: 第 {attempt} 次 VNC 已停在文本控制台登录提示页"
                        )
                        return

                    _login_installed_iso_from_vnc(
                        new_page,
                        canvas,
                        vm_name,
                        username=login_username,
                        password=login_password,
                    )
                    logger.info(f"云服务器 {vm_name}: 第 {attempt} 次 VNC 登录成功")
                    return
            except Exception as exc:
                logger.warning(f"云服务器 {vm_name}: 第 {attempt} 次 VNC 登录失败: {exc}")
                if attempt < max_login_retries:
                    ecs_page.page.wait_for_timeout(login_retry_interval * 1000)
                else:
                    raise
