import allure
import pytest
from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.middleware import KafkaPage, RedisPage, ESPage, RabbitMQPage, PrometheusPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data


@pytest.fixture(scope="function")
def redis_page(page):
    """初始化Redis实例管理页面"""
    redis_page = RedisPage(page)
    redis_page.goto_service('AnhanDB(for Redis)')
    return redis_page


@pytest.fixture(scope="function")
def kafka_page(page):
    """初始化Kafka实例管理页面"""
    kafka_page = KafkaPage(page)
    kafka_page.goto_service('分布式消息服务 Kafka')
    return kafka_page


@pytest.fixture(scope="function")
def es_page(page):
    """初始化云搜索服务 CSS 实例管理页面"""
    es_page = ESPage(page)
    es_page.goto_service('云搜索服务')
    return es_page


@pytest.fixture(scope="function")
def rabbitmq_page(page):
    """初始化 RabbitMQ 实例管理页面"""
    rabbitmq_page = RabbitMQPage(page)
    rabbitmq_page.goto_service('分布式消息服务 RabbitMQ')
    return rabbitmq_page


@pytest.fixture(scope="function")
def prometheus_page(page):
    """初始化 Prometheus 集群管理页面"""
    prometheus_page = PrometheusPage(page)
    prometheus_page.goto_service('监控服务')
    return prometheus_page


@pytest.fixture(scope="class")
def redis(browser_context, config):
    """创建一个供整个测试类使用的Redis实例对象（包含一个单机用于升级测试，一个集群用于基础功能测试）"""
    page = _create_logged_in_page(browser_context, config)
    redis_page = RedisPage(page)
    redis_page.goto_service('AnhanDB(for Redis)')
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

    page.close()


@pytest.fixture(scope="class")
def kafka(browser_context, config):
    """创建一个供整个测试类使用的Kafka实例对象"""
    page = _create_logged_in_page(browser_context, config)
    kafka_page = KafkaPage(page)
    kafka_page.goto_service('分布式消息服务 Kafka')
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

    page.close()


@pytest.fixture(scope="class")
def css(browser_context, config):
    """创建一个供整个测试类使用的云搜索服务 CSS 集群实例对象"""
    page = _create_logged_in_page(browser_context, config)
    es_page = ESPage(page)
    es_page.goto_service('云搜索服务')
    name = f"css-{random_data()}"
    data = {"name": name, "password": "Aa123456"}
    logger.info(f"为测试类创建共享云搜索服务 CSS 实例: {name}")

    with allure_step_log(f"前置操作：创建共享实例 {name}"):
        es_page.create_instance(name=name, security_mode=True)
        es_page.assert_popup_success("创建ElasticSearch资源成功")
        es_page.assert_status(name, status="运行中", timeout=2400, refresh=True)

    yield data

    with allure_step_log(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享云搜索服务 CSS 实例: {name}")
        es_page.delete_instance(name)

    page.close()


@pytest.fixture(scope="class")
def rabbitmq(browser_context, config):
    """创建一个供整个测试类使用的 RabbitMQ 集群实例对象"""
    page = _create_logged_in_page(browser_context, config)
    rabbitmq_page = RabbitMQPage(page)
    rabbitmq_page.goto_service('分布式消息服务 RabbitMQ')
    name = f"rabbitmq-{random_data()}"
    data = {"name": name, "password": "Admin1234@sugon"}
    logger.info(f"为测试类创建共享 RabbitMQ 集群实例: {name}")

    with allure_step_log(f"前置操作：创建共享实例 {name}"):
        rabbitmq_page.create_instance(name=name)
        rabbitmq_page.assert_popup_success("创建Rabbitmq资源成功")
        rabbitmq_page.assert_status(name, status="运行中", timeout=2400, refresh=True)

    yield data

    with allure_step_log(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享 RabbitMQ 实例: {name}")
        rabbitmq_page.delete_instance(name)

    page.close()


@pytest.fixture(scope="class")
def prometheus(browser_context, config):
    """创建一个供整个测试类使用的 Prometheus 集群对象"""
    page = _create_logged_in_page(browser_context, config)
    prometheus_page = PrometheusPage(page)
    prometheus_page.goto_service('监控服务')
    name = f"prometheus-{random_data()}"
    data = {"name": name}
    logger.info(f"为测试类创建共享 Prometheus 集群: {name}")

    with allure_step_log(f"前置操作：创建共享集群 {name}"):
        prometheus_page.create_instance(name=name)
        prometheus_page.assert_popup_success("创建Prometheus资源成功")
        prometheus_page.assert_status(name, status="运行中", timeout=2400, refresh=True)

    yield data

    with allure_step_log(f"后置操作：删除共享集群 {name}"):
        logger.info(f"清理共享 Prometheus 集群: {name}")
        prometheus_page.delete_instance(name)

    page.close()
