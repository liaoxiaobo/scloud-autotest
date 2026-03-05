import allure
import pytest

from sugon_web.pages.login import LoginPage
from sugon_web.pages.mysql import MySQLPage
from sugon_web.pages.doris import DorisPage
from sugon_web.pages.pgsql import PgSQLPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data, random_string


@pytest.fixture(scope="function", autouse=True)
def close_dialog_before_test(page):
    """用例执行前关闭可能存在的对话框，避免页面元素定位被遮挡或干扰"""

    try:
        # 直接检查并关闭对话框
        close_button = page.get_by_role("button", name="Close")
        if close_button.is_visible():
            logger.info("发现未关闭的对话框，正在关闭...")
            close_button.click()
    except:
        pass  # 忽略对话框不存在的情况

    yield

@pytest.fixture(scope="module")
def login_page(page):
    """初始化登录页对象"""
    login_page = LoginPage(page)
    login_page.logout()   # 登录测试用例需要先退出登录状态
    return login_page



@pytest.fixture(scope="class")
def mysql_page(page):
    """初始化MySQL实例管理页面"""
    mysql_page = MySQLPage(page)
    mysql_page.goto_service('AnhanDB(for MySQL)')
    return mysql_page


@pytest.fixture(scope="class")
def doris_page(page):
    """初始化Doris实例管理页面"""
    doris_page = DorisPage(page)
    doris_page.goto_service('数据仓库 Doris')
    return doris_page


@pytest.fixture(scope="class")
def pgsql_page(page):
    """初始化PostgreSQL实例管理页面"""
    pgsql_page = PgSQLPage(page)
    pgsql_page.goto_service('AnhanDB(for PostgreSQL)')
    return pgsql_page


@pytest.fixture(scope="class")
def doris(doris_page):
    """创建一个供整个测试类使用的Doris实例对象"""
    name = f"doris-{random_data()}"
    admin_password = "admin1234@sugon"  # Doris默认密码
    db_name = f"autodb_{random_string(k=5)}"
    db_name1 = f"autodb_{random_string(k=5)}"
    user_name = f"user_{random_string(k=5)}"
    user_name1 = f"user_{random_string(k=5)}"
    user_password = f"Pwd@1{random_string(k=5)}"
    data = {"name": name, "admin_password": admin_password, "db_name": db_name, "db_name1": db_name1, "user_name": user_name, "user_password": user_password}
    logger.info(f"为测试类创建共享Doris实例: {name}")

    with allure_step_log(f"前置操作：创建共享实例 {name}"):
        doris_page.create_instance(name, password=admin_password)
        doris_page.assert_popup_success("Doris创建任务提交成功")
        doris_page.assert_status(name, status="就绪", timeout=1800)

    with allure.step(f"前置操作：创建两个数据库 {db_name} 和 {db_name1}"):
        doris_page.create_database(name, db_name)
        doris_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
        doris_page.assert_database_exist(db_name)

        doris_page.create_database(name, db_name1)
        doris_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
        doris_page.assert_database_exist(db_name1)

    with allure.step(f"前置操作：创建两个用户 {user_name} 和 {user_name1}"):
        doris_page.create_user(name, user_name, user_password)
        doris_page.assert_popup_success("操作成功")

        doris_page.create_user(name, user_name1, user_password)
        doris_page.assert_popup_success("操作成功")

    yield data

    with allure_step_log(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享Doris实例: {name}")
        doris_page.delete_instance(data["name"])


@pytest.fixture(scope="class")
def mysql(mysql_page):
    """创建一个供整个测试类使用的MySQL实例对象"""
    name = random_data()
    type = "集群"
    db_name = f"autodb-{random_string(k=5)}"
    user_name = f"user_{random_string(k=5)}"
    user_password = f"sugon1234@{random_string(k=5)}"
    privileges = "读写"
    data = {"name": name, "db_name": db_name, "user_name": user_name, "user_password": user_password}
    logger.info(f"为测试类创建共享MySQL实例: {name}")

    with allure_step_log(f"前置操作：创建共享实例 {name}"):
        mysql_page.create_instance(name, type)
        mysql_page.assert_popup_success("创建MySQL资源成功")
        mysql_page.assert_status(name, status="运行中", timeout=1200)

    with allure_step_log(f"前置操作：创建新数据库 {db_name}"):
        mysql_page.create_database(name, db_name)
        mysql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
        mysql_page.assert_list_contain(db_name)

    with allure_step_log(f"前置操作：创建新用户 {db_name}"):
        mysql_page.create_user(name, user_name, user_password, db_name, privileges)
        mysql_page.assert_popup_success("创建用户成功",10)

    yield data

    with allure_step_log(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享MySQL实例: {name}")
        # 在删除前，确保页面在实例列表页，防止在详情页删除失败
        mysql_page.delete_instance(data["name"])


@pytest.fixture(scope="class")
def pgsql(pgsql_page):
    """创建一个供整个测试类使用的PostgreSQL实例对象"""
    name = f"pgsql-{random_data()}"
    instance_type = "集群"
    db_name = f"autodb_{random_string(k=5)}"
    user_name = f"user_{random_string(k=5)}"
    user_password = f"sugon1234@{random_string(k=5)}"
    privileges = "读写"
    data = {"name": name, "db_name": db_name, "user_name": user_name, "user_password": user_password}
    logger.info(f"为测试类创建共享PostgreSQL实例: {name}")

    with allure_step_log(f"前置操作：创建共享实例 {name}"):
        pgsql_page.create_instance(name, instance_type)
        pgsql_page.assert_popup_success("创建PostgreSQL资源成功")
        pgsql_page.assert_status(name, status="运行中", timeout=1200)

    with allure_step_log(f"前置操作：创建新数据库 {db_name}"):
        pgsql_page.create_database(name, db_name)
        pgsql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
        pgsql_page.assert_list_contain(db_name)

    with allure_step_log(f"前置操作：创建新用户 {user_name}"):
        pgsql_page.create_user(name, user_name, user_password, db_name, privileges)
        pgsql_page.assert_popup_success("创建用户成功", 10)

    yield data

    with allure_step_log(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享PostgreSQL实例: {name}")
        pgsql_page.delete_instance(data["name"])