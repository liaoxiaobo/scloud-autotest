import allure
import pytest
from sugon_web.pages.database import DorisPage, KingbasePage, MongoDBPage, MySQLPage, PgSQLPage, XScalePage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data, random_string
from sugon_web.conftest import _create_logged_in_page
from sugon_web.utils import db_util


@pytest.fixture(scope="function")
def mysql_page(page):
    """初始化MySQL实例管理页面"""
    mysql_page = MySQLPage(page)
    mysql_page.goto_service('AnhanDB(for MySQL)')
    return mysql_page


@pytest.fixture(scope="function")
def doris_page(page):
    """初始化Doris实例管理页面"""
    doris_page = DorisPage(page)
    doris_page.goto_service('数据仓库 Doris')
    return doris_page


@pytest.fixture(scope="function")
def pgsql_page(page):
    """初始化PostgreSQL实例管理页面"""
    pgsql_page = PgSQLPage(page)
    pgsql_page.goto_service('AnhanDB(for PostgreSQL)')
    return pgsql_page


@pytest.fixture(scope="function")
def kingbase_page(page):
    """初始化KingbaseES实例管理页面"""
    kingbase_page = KingbasePage(page)
    kingbase_page.goto_service('人大金仓 KingbaseES')
    return kingbase_page


@pytest.fixture(scope="function")
def mongodb_page(page):
    """初始化MongoDB实例管理页面"""
    mongodb_page = MongoDBPage(page)
    mongodb_page.goto_service('AnhanDB(for MongoDB)')
    return mongodb_page


@pytest.fixture(scope="function")
def xscale_page(page):
    """初始化XScale实例管理页面"""
    return XScalePage(page)


@pytest.fixture(scope="class")
def doris(browser_context, config):
    """创建一个供整个测试类使用的Doris实例对象"""
    page = _create_logged_in_page(browser_context, config)
    doris_page = DorisPage(page)
    doris_page.goto_service('数据仓库 Doris')
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

    page.close()


@pytest.fixture(scope="class")
def mysql(browser_context, config):
    """创建一个供整个测试类使用的MySQL实例对象"""
    page = _create_logged_in_page(browser_context, config)
    mysql_page = MySQLPage(page)
    mysql_page.goto_service('AnhanDB(for MySQL)')
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

    page.close()


@pytest.fixture(scope="class")
def pgsql(browser_context, config):
    """创建一个供整个测试类使用的PostgreSQL实例对象"""
    page = _create_logged_in_page(browser_context, config)
    pgsql_page = PgSQLPage(page)
    pgsql_page.goto_service('AnhanDB(for PostgreSQL)')
    name = f"pgsql-{random_data()}"
    instance_type = "单机"
    user_name = f"user_{random_string(k=5)}"
    user_password = f"sugon1234@{random_string(k=5)}"
    data = {"name": name, "user_name": user_name, "user_password": user_password}
    logger.info(f"为测试类创建共享PostgreSQL实例: {name}")

    with allure_step_log(f"前置操作：创建共享实例 {name}"):
        pgsql_page.create_instance(name, instance_type)
        pgsql_page.assert_popup_success("创建PostgreSQL资源成功")
        pgsql_page.assert_status(name, status="运行中", timeout=1200)

    with allure_step_log(f"前置操作：创建新用户 {user_name}"):
        pgsql_page.create_user(name, user_name, user_password)
        pgsql_page.assert_popup_success("创建用户成功", 10)

    yield data

    with allure_step_log(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享PostgreSQL实例: {name}")
        pgsql_page.delete_instance(data["name"])

    page.close()


@pytest.fixture(scope="class")
def kingbase(browser_context, config):
    """创建一个供整个测试类使用的KingbaseES集群实例对象"""
    page = _create_logged_in_page(browser_context, config)
    kingbase_page = KingbasePage(page)
    kingbase_page.goto_service('人大金仓 KingbaseES')
    name = f"kingbase-{random_data()}"
    instance_type = "集群"
    admin_password = "Admin1234@sugon"
    db_name = f"autodb_{random_string(k=5)}"
    user_name = f"user_{random_string(k=5)}"
    user_password = f"Pwd@1{random_string(k=5)}"
    data = {
        "name": name,
        "admin_password": admin_password,
        "db_name": db_name,
        "user_name": user_name,
        "user_password": user_password,
    }
    logger.info(f"为测试类创建共享KingbaseES实例: {name}")

    with allure_step_log(f"前置操作：创建共享实例 {name}"):
        kingbase_page.create_instance(name, instance_type=instance_type, password=admin_password)
        kingbase_page.assert_popup_success()
        kingbase_page.assert_list_contain(name)
        kingbase_page.assert_status(name, status="运行中", timeout=1800, refresh=True)

    with allure_step_log(f"前置操作：创建数据库 {db_name}"):
        kingbase_page.create_database(name, db_name)
        kingbase_page.assert_popup_success()
        kingbase_page.assert_list_contain(db_name)

    with allure_step_log(f"前置操作：创建用户 {user_name}"):
        kingbase_page.create_user(name, user_name, user_password)
        kingbase_page.assert_popup_success()
        kingbase_page.assert_list_contain(user_name, "用户名")

    yield data

    with allure_step_log(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享KingbaseES实例: {name}")
        kingbase_page.delete_instance(data["name"])

    page.close()


@pytest.fixture(scope="class")
def mongodb(browser_context, config):
    """创建一个供整个测试类使用的MongoDB实例对象（副本集和分片集群）"""
    page = _create_logged_in_page(browser_context, config)
    mongodb_page = MongoDBPage(page)
    mongodb_page.goto_service('AnhanDB(for MongoDB)')
    name = f"mongo-{random_data()}"
    name1 = f"mongo-shard-{random_data()}"
    root_password = "Admin1234#sugon"
    user_name = "root"
    
    data = {"name": name, "name1": name1, "root_password": root_password, "user_name": user_name}
    logger.info(f"为测试类创建共享MongoDB实例: {name}(副本集), {name1}(分片集群)")

    with allure_step_log(f"前置操作：创建共享副本集实例 {name}"):
        mongodb_page.create_instance(name, "副本集", password=root_password)
        mongodb_page.assert_popup_success("创建实例")
        mongodb_page.assert_status(name, status="运行中", timeout=1800, refresh=True)

    with allure_step_log(f"前置操作：创建共享分片集群实例 {name1}"):
        mongodb_page.create_instance(name1, "分片集群", password=root_password)
        mongodb_page.assert_popup_success("创建实例")
        mongodb_page.assert_status(name1, status="运行中", timeout=3600, refresh=True)

    yield data

    with allure_step_log(f"后置操作：删除共享实例"):
        logger.info(f"清理共享MongoDB实例: {name}, {name1}")
        mongodb_page.delete_instance(name1)
        mongodb_page.delete_instance(name)

    page.close()


@pytest.fixture(scope="class")
def xscale(browser_context, config, ssh_host, ssh_vm):
    """创建一个供整个测试类使用的XScale实例对象，并预连接后端计算节点。"""
    page = _create_logged_in_page(browser_context, config)
    xscale_page = XScalePage(page)
    name = f"xscale-{random_data()}"
    admin_password = "admin1234@sugon"
    data = {"name": name, "admin_password": admin_password}
    logger.info(f"为测试类创建共享XScale实例: {name}")

    with allure_step_log(f"前置操作：创建共享实例 {name}"):
        xscale_page.create_instance(name, password=admin_password)
        xscale_page.assert_popup_success()
        xscale_page.assert_list_contain(name)
        xscale_page.assert_status(name, status="就绪", timeout=1500)

    with allure_step_log(f"前置操作：连接实例 {name} 后端计算节点"):
        node_name = f"{name}-cn-0"
        xscale_page.goto_detail_page(name)
        row_data = xscale_page.get_row_data(node_name)
        fixed_ip = row_data.get("内网IP")
        assert fixed_ip, f"未在节点 {node_name} 详情行中获取到内网IP，行数据: {row_data}"
        mfip = ssh_host.find_mfip(fixed_ip)
        ssh_vm.connect(mfip, port=22022, pwd="admin1234@sugon")
        logger.info(f"后端连接成功: {name} -> {mfip}")

    yield data

    with allure_step_log(f"后置操作：删除共享实例 {data['name']}"):
        logger.info(f"清理共享XScale实例: {data['name']}")
        xscale_page.delete_instance(data["name"])
        xscale_page.assert_deleted(name)
        db_util.assert_backend_deleted(xscale_page, ssh_host, name)

    page.close()
