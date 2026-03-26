import allure
import pytest

from sugon_web.pages.login import LoginPage
from sugon_web.pages.mysql import MySQLPage
from sugon_web.pages.doris import DorisPage
from sugon_web.pages.pgsql import PgSQLPage
from sugon_web.pages.mongodb import MongoDBPage
from sugon_web.pages.redis import RedisPage
from sugon_web.pages.kafka import KafkaPage
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
def mongodb_page(page):
    """初始化MongoDB实例管理页面"""
    mongodb_page = MongoDBPage(page)
    mongodb_page.goto_service('AnhanDB(for MongoDB)')
    return mongodb_page


@pytest.fixture(scope="class")
def redis_page(page):
    """初始化Redis实例管理页面"""
    redis_page = RedisPage(page)
    redis_page.goto_service('AnhanDB(for Redis)')
    return redis_page


@pytest.fixture(scope="class")
def kafka_page(page):
    """初始化Kafka实例管理页面"""
    kafka_page = KafkaPage(page)
    kafka_page.goto_service('分布式消息服务 Kafka')
    return kafka_page


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

@pytest.fixture(scope="class")
def mongodb(mongodb_page):
    """创建一个供整个测试类使用的MongoDB实例对象（副本集和分片集群）"""
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


@pytest.fixture(scope="class")
def redis(redis_page):
    """创建一个供整个测试类使用的Redis实例对象（包含一个单机用于升级测试，一个集群用于基础功能测试）"""
    name = f"redis-{random_data()}"
    name1 = f"redis-cluster-{random_data()}"
    data = {"name": name, "name1": name1, "password": "admin1234@sugon"}
    logger.info(f"为测试类创建共享Redis实例: {name}(单机), {name1}(集群)")

    with allure_step_log(f"前置操作：创建共享单机实例 {name}"):
        redis_page.create_instance(name, "单机")
        redis_page.assert_popup_success("创建redis资源成功")
        redis_page.assert_status(name, status="运行中", timeout=1200, refresh=True)

    with allure_step_log(f"前置操作：创建共享集群实例 {name1}"):
        redis_page.create_instance(name1, "集群")
        redis_page.assert_popup_success("创建redis资源成功")
        redis_page.assert_status(name1, status="运行中", timeout=3600, refresh=True)

    yield data

    with allure_step_log(f"后置操作：删除共享实例"):
        logger.info(f"清理共享Redis实例: {name}, {name1}")
        redis_page.delete_instance(name1)
        redis_page.delete_instance(name)


@pytest.fixture(scope="class")
def kafka(kafka_page):
    """创建一个供整个测试类使用的Kafka实例对象"""
    name = f"kafka-{random_data()}"
    data = {"name": name}
    logger.info(f"为测试类创建共享Kafka实例: {name}")

    with allure_step_log(f"前置操作：创建共享实例 {name}"):
        kafka_page.create_instance(name=name)
        kafka_page.assert_popup_success("Kafka实例创建成功")
        kafka_page.assert_status(name, status="运行中", timeout=1800, refresh=True)

    yield data

    with allure_step_log(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享Kafka实例: {name}")
        kafka_page.delete_instance(name)
