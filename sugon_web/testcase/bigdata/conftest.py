import pytest

from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.bigdata import EMRPage
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log, logger


@pytest.fixture(scope="function")
def emr_page(page):
    page_obj = EMRPage(page)
    page_obj.goto_service("E-MapReduce")
    return page_obj


@pytest.fixture(scope="class")
def emr(browser_context, config):
    page = _create_logged_in_page(browser_context, config)
    emr_page = EMRPage(page)
    emr_page.goto_service("E-MapReduce")
    name = f"emr-{random_data()}"
    data = {"name": name, "password": "Admin1234@sugon"}
    logger.info(f"为测试类创建共享 E-MapReduce 集群: {name}")

    with allure_step_log(f"前置操作：创建共享 E-MapReduce 集群 {name}"):
        emr_page.create_cluster(name=name)
        emr_page.assert_popup_success("创建E-MapReduce集群成功")
        emr_page.assert_status(name, status="服务运行中", timeout=3600, refresh=True)

    yield data

    with allure_step_log(f"后置操作：删除共享 E-MapReduce 集群 {name}"):
        emr_page.delete_cluster(name)

    page.close()
