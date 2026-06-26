import pytest
from sugon_web.pages.security.apt import AptPage
from sugon_web.pages.security.ras import RasPage
from sugon_web.pages.security.usm import UsmPage
from sugon_web.pages.security.ver import VerPage
from sugon_web.pages.security.vdb import VdbPage
from sugon_web.pages.security.waf import WafPage
from sugon_web.pages.security.wpt import WptPage
from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


@pytest.fixture(scope="session")
def security_vpc(browser, config):
    """创建安全合规测试专用 VPC，session 级共享，所有 session fixture 结束后自动清理。"""
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.pages.network import VpcPage

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    vpc_page = VpcPage(page)
    vpc_page.goto_service("虚拟私有云")

    vpc_name = random_data().replace("autotest-", "autotest-vpc-")
    subnet_name = random_data()
    cidr = random_data("cidr")

    vpc_page.vpc_create(name=vpc_name, subnet_name=subnet_name, cidr=cidr)
    vpc_page.assert_popup_success("创建虚拟私有云成功")
    logger.info(f"安全合规专用 VPC 创建成功: {vpc_name}, CIDR={cidr}")

    yield {"name": vpc_name, "subnet_name": subnet_name, "cidr": cidr}

    vpc_page.goto_service("虚拟私有云")
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
def ras_page(page):
    """初始化漏洞扫描RAS页对象"""
    page_object = RasPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="function")
def waf_page(page):
    """初始化WEB应用防火墙WAF页对象"""
    page_object = WafPage(page)
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
                    logger.warning(f"使用原 page 清理 VER 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_ver_page = VerPage(new_page)
                        delete_ver_instance(new_page, new_ver_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 VER 实例也失败: {e2}")
                        raise e2 from e
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
def vdb_page(page):
    """初始化数据库审计VDB页对象"""
    page_object = VdbPage(page)
    page_object.goto_list_page()
    return page_object


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

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
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


@pytest.fixture(scope="class")
def ras_instance(browser, config, security_vpc):
    """创建 漏洞扫描RAS 实例并自动清理（scope=class）。

    所有 RAS 测试共享同一个实例，类内所有测试执行完成后自动清理。
    测试方法声明 ras_instance 参数即可接入，通过 ras_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._ras_helpers import create_ras_instance, delete_ras_instance

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
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
                        new_page = _create_logged_in_page(context, config)
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
        context.close()


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

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
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
    """创建 攻击预警APT 实例并自动清理（scope=class）。

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

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
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
