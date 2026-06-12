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

    def _attempt_login():
        """单次登录尝试，成功返回 True，失败返回 False，异常返回 None。"""
        try:
            _navigate_to_login(page)
        except Exception as e:
            logger.warning(f"verify_login: 导航到登录页异常: {e}")
            return None
        # 登录前关闭可能残留的弹窗（如许可到期弹窗），避免遮挡登录按钮
        _close_any_popup(page)
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
    # 断言组织已出现在组织树中（后端异步写入可能延迟）
    iam.iam_assert_org_in_tree(org_name, timeout=15)

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
    # 断言子组织已出现在组织树中（后端异步写入可能延迟）
    iam.iam_assert_org_in_tree(child_name, timeout=15)

    return {
        "child_name": child_name,
        "parent_name": parent_name,
    }


def modify_and_assert_quota(iam_page, service_name, quotas, assertions):
    """修改指定服务的配额并逐项断言指标值。

    配额不足/服务不存在/值超max降级时标记环境问题并跳过。
    成功时返回实际分配的配额字典（含降级后的值），失败时返回None。

    Args:
        iam_page: IAM 页面对象
        service_name: 服务名称
        quotas: 待修改的配额字典
        assertions: 断言期待值列表 [(指标名, 期望值), ...]

    Returns:
        dict|None: 成功返回实际配额字典，失败/跳过返回None
    """
    try:
        iam_page.iam_modify_service_quota(service_name, quotas)
        iam_page.wait_for_page_ready()
    except EnvironmentError as e:
        logger.warning(f"{service_name} 配额修改跳过(配额不足/平台限制): {e}")
        return None
    except AssertionError as e:
        msg = str(e)
        if "未找到服务" in msg:
            logger.warning(f"{service_name} 跳过(服务不存在): {msg}")
            return None
        raise
    for metric_name, expected in assertions:
        actual_val = _resolve_quota_value(metric_name, quotas, expected)
        iam_page.iam_assert_quota_value(service_name, metric_name, actual_val)
    logger.info(f"{service_name} 配额修改验证通过（{len(assertions)}项）")
    return quotas


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
        for _ in range(5):
            closed = False
            # 检查 el-message-box
            msg_box = page.locator(".el-message-box__wrapper")
            if msg_box.count() > 0 and msg_box.first.is_visible():
                for btn_text in ["确定", "确认", "关闭"]:
                    for btn in msg_box.first.locator("button").filter(has_text=btn_text).all():
                        if btn.is_visible():
                            btn.click()
                            page.wait_for_timeout(800)
                            closed = True
                            break
                    if closed:
                        break
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                continue
            # 检查 el-dialog
            dialog = page.locator(".el-dialog__wrapper")
            if dialog.count() > 0 and dialog.first.is_visible():
                for btn_text in ["确定", "确认", "关闭"]:
                    for btn in dialog.first.locator("button").filter(has_text=btn_text).all():
                        if btn.is_visible():
                            btn.click()
                            page.wait_for_timeout(800)
                            closed = True
                            break
                    if closed:
                        break
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                continue
            break
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
    from sugon_web.utils.logger import logger
    _navigate_to_login(page)
    LoginPage(page).login(username, password)
    page.wait_for_load_state("domcontentloaded")
    # 轮询等待路由跳转离开登录页（Vue 路由切换可能比 DOMContentLoaded 慢）
    for _ in range(20):
        if "login" not in page.url.lower():
            break
        page.wait_for_timeout(500)
    logger.info(f"login_as_user: user={username}, url={page.url}")


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


def allocate_org_all_quotas(iam_page, org_name):
    """给指定一级组织分配项目配额测试所需的全部服务配额。

    环境缺失的服务自动跳过，不阻塞流程。

    Args:
        iam_page: IamPage 页面对象
        org_name: 一级组织名称
    """
    org_quota_config = {
        "计算": {
            "云服务器ECS": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "系统盘总量(GiB)": 1000},
            "机密云服务器SECS": {"机密云服务器总量(个)": 100},
            "镜像服务IMS": {"镜像总量(个)": 100, "镜像容量总量(GiB)": 1000},
            "裸金属BMS": {"软装版服务器总量(台)": 10},
        },
        "存储": {
            "云硬盘EVS": {"容量总量(GiB)": 1000, "快照总量(GiB)": 1000},
            "文件存储SFS": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "虚拟机总量(个)": 100, "云硬盘总量(GiB)": 1000},
            "对象存储OSS": {"桶容量(GiB)": 1000},
            "对象存储(专业版) OBS": {"桶容量(GiB)": 1000},
        },
        "网络": {
            "弹性公网IP": {"弹性公网IP总量(个)": 100},
            "云防火墙CFW": {"cpu总量(个)": 100, "内存总量(GiB)": 1000},
            "虚拟私有云": {"总量(个)": 100},
            "负载均衡（基础版）": {"总量(个)": 100},
        },
        "灾备管理": {
            "实例备份ECBS": {"实例备份总量(GiB)": 1000},
        },
        "数据库": {
            "AnhanDB(for MySQL)": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "AnhanDB(for PostgreSQL)": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "AnhanDB(for MongoDB)": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "AnhanDB-XScale": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "数据仓库Doris": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "金仓数据库": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
        },
        "大数据计算": {
            "E-MapReduce": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "EMR总量(个)": 100, "云硬盘总量(GiB)": 1000},
        },
        "安全合规": {
            "云漏洞扫描RAS": {"cpu总量(个)": 100, "内存总量(GiB)": 100},
            "日志审计VER": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "网页防篡改WPT": {"cpu总量(个)": 100, "内存总量(GiB)": 100},
            "数据库审计VDB": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "攻击预警APT": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "WEB应用防火墙WAF": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "堡垒机高级版USM": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
        },
        "中间件": {
            "AnhanDB(for Redis)": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "云搜索服务CSS": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "分布式消息服务Kafka": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "分布式消息服务 RabbitMQ": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "监控服务Prometheus": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
        },
        "容器服务": {
            "云容器引擎CCE": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
            "容器镜像服务SCR": {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
        },
    }

    iam_page.goto_service("统一身份认证IAM")
    # 组织树异步加载，额外等待确保新创建的组织可见
    iam_page.page.wait_for_timeout(5000)
    iam_page.iam_open_org_quota(org_name)

    for service_type, services in org_quota_config.items():
        try:
            iam_page.iam_filter_quota_service_type(service_type)
        except Exception as e:
            logger.warning(f"组织配额页面无 {service_type} 服务类型，跳过: {e}")
            continue

        for service_name, quotas in services.items():
            try:
                iam_page.iam_modify_service_quota(service_name, quotas)
                iam_page.wait_for_page_ready()
                logger.info(f"组织 {org_name} 分配 {service_name} 配额成功")
            except Exception as e:
                logger.warning(f"组织 {org_name} 分配 {service_name} 配额失败: {e}")


def assert_org_quota_usage(iam_page, service_name, metric_name, expected_usage):
    """反向验证：断言一级组织配额页面中指定服务的使用量等于预期值。

    配额显示格式为"使用量/总量"，本函数验证使用量部分。
    组织配额页面DOM结构可能与项目配额页面不同，使用JS策略为主、Playwright降级为辅。

    Args:
        iam_page: IamPage 页面对象
        service_name: 服务名称
        metric_name: 指标名称（如"cpu使用量(个)"）
        expected_usage: 预期使用量数值（如100）

    Returns:
        bool: 验证通过返回True，失败返回False（已记录warning）
    """
    tab_container = iam_page.page.locator("#tabContainer")
    # 轮询等待 #tabContainer 出现且可见（组织配额内容是异步加载的）
    for _ in range(60):
        if tab_container.count() > 0:
            try:
                if tab_container.first.is_visible():
                    break
            except Exception:
                pass
        iam_page.page.wait_for_timeout(500)
    else:
        logger.warning(f"反向验证跳过：组织配额页面未加载（#tabContainer未渲染或不可见）")
        return False
    iam_page.page.wait_for_timeout(1500)

    # 策略1：JS直接遍历DOM文本节点，不受类名变化影响
    result = iam_page.page.evaluate(
        """(args) => {
            const [svc, metric] = args;
            const cards = document.querySelectorAll('#tabContainer .tab-item');
            for (const card of cards) {
                const title = card.querySelector('.sub-title');
                if (!title) continue;
                const titleText = title.textContent.trim();
                if (titleText === svc || titleText.includes(svc) || svc.includes(titleText)) {
                    // 获取卡片内所有文本节点
                    const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT, null, false);
                    const texts = [];
                    let node;
                    while (node = walker.nextNode()) {
                        const t = node.textContent.trim();
                        if (t) texts.push(t);
                    }
                    for (let i = 0; i < texts.length; i++) {
                        if (texts[i].includes(metric)) {
                            for (let j = i + 1; j < texts.length; j++) {
                                if (/[\\d\\/]/.test(texts[j])) {
                                    return texts[j];
                                }
                            }
                        }
                    }
                    // fallback：遍历所有元素
                    const allEls = card.querySelectorAll('*');
                    for (let i = 0; i < allEls.length; i++) {
                        if (allEls[i].textContent.includes(svc)) continue;
                        if (allEls[i].textContent.includes(metric)) {
                            for (let j = i + 1; j < allEls.length; j++) {
                                const t = allEls[j].textContent.trim();
                                if (/^\\d+/.test(t) || t.includes('/')) {
                                    return t;
                                }
                            }
                        }
                    }
                }
            }
            return null;
        }""",
        [service_name, metric_name]
    )

    # 策略2：Playwright降级（项目配额页面结构）
    if result is None:
        service_card = None
        for _ in range(10):
            tab_items = tab_container.locator(".tab-item").all()
            for item in tab_items:
                title_el = item.locator(".sub-title")
                if title_el.count() > 0:
                    title_text = title_el.first.inner_text().strip()
                    if service_name == title_text or service_name in title_text or title_text in service_name:
                        service_card = item
                        break
            if service_card is not None:
                break
            iam_page.page.wait_for_timeout(1500)

        if service_card is None:
            logger.warning(f"反向验证跳过：配额页面中未找到服务 {service_name}")
            return False

        metric_item = service_card.locator(".item-name").filter(has_text=metric_name)
        if metric_item.count() > 0:
            value_el = metric_item.first.locator("xpath=../..").locator(".item-value")
            if value_el.count() > 0:
                result = value_el.first.inner_text().strip()

        if result is None:
            # 策略3：相邻元素查找
            all_els = service_card.locator("p, span, div").all()
            for i, el in enumerate(all_els):
                try:
                    text = el.inner_text().strip()
                    if metric_name in text:
                        if i + 1 < len(all_els):
                            next_text = all_els[i + 1].inner_text().strip()
                            if "/" in next_text or next_text.replace("/", "").replace(".", "").isdigit():
                                result = next_text
                                break
                except Exception:
                    continue

    if result is None:
        logger.warning(f"反向验证跳过：{service_name} 中未找到指标 {metric_name}")
        return False

    usage_part = result.split("/")[0] if "/" in result else result
    if usage_part == str(expected_usage):
        logger.info(f"反向验证通过：{service_name}-{metric_name} 组织使用量为 {result}")
        return True
    else:
        logger.warning(
            f"反向验证失败：{service_name}-{metric_name} 组织使用量不匹配，"
            f"预期 {expected_usage}，实际 {usage_part}（完整值 {result}）"
        )
        return False
