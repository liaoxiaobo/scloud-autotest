import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@pytest.mark.parametrize("vpc", [{"cidr": "173.3.3.0/24"}], indirect=True)
@allure.epic('网络服务')
@allure.feature('企业路由器')
@allure.story('连接新建功能验证')
class TestERConnectionCreate:

    @allure.title("企业路由器-添加VPC连接功能验证")
    def test_er_vpc_connection_create(self, er_page, vpc):
        """测试HA企业路由器添加VPC连接：使用fixture预置VPC、创建HA ER、添加VPC连接、验证状态。"""
        vpc_name = vpc['name']
        subnet_name = vpc['subnet_name']
        er_name = f"er-ha-{random_data(length=4)}"
        conn_name = f"er-vpc-conn-{random_data(length=4)}"
        cluster_name = "Autotest"
        main_error = None
        cleanup_errors = []

        try:
            with allure_step_log("步骤1: 创建HA企业路由器"):
                er_page._ensure_list_page()
                er_page.er_create(
                    name=er_name,
                    cluster_name=cluster_name,
                    ha_enable=True,
                )
                er_page.assert_popup_success(timeout=10000)
                logger.info(f"HA ER {er_name} 创建提交成功")

            with allure_step_log("步骤2: 等待ER状态变为运行中"):
                er_page._ensure_list_page()
                er_page.assert_status(
                    er_name,
                    status="运行中",
                    timeout=1200,
                    refresh=True,
                    refresh_interval=30,
                )
                logger.info(f"ER {er_name} 状态变为运行中")

            with allure_step_log("步骤3: 添加VPC连接"):
                er_page.goto_connection_tab(er_name)
                er_page.er_connection_create(
                    name=conn_name,
                    conn_type="VPC",
                    vpc_name=vpc_name,
                    subnet_name=subnet_name,
                )
                er_page.assert_popup_success(timeout=10000)
                logger.info(f"VPC连接 {conn_name} 添加成功")

            with allure_step_log("步骤4: 验证连接列表和状态"):
                er_page.assert_status(
                    conn_name,
                    status="运行中",
                    timeout=60,
                    refresh=True,
                    refresh_interval=20,
                )
                logger.info(f"连接 {conn_name} 状态验证成功: 运行中")

        except Exception as e:
            main_error = e
            raise
        finally:
            with allure_step_log("清理: 删除VPC连接"):
                try:
                    er_page.goto_connection_tab(er_name)
                    er_page.er_connection_delete(conn_name)
                    er_page.assert_deleted(conn_name, timeout=30)
                    logger.info(f"连接 {conn_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除连接失败: {e}")
                    cleanup_errors.append(f"删除连接: {e}")

            with allure_step_log("清理: 删除企业路由器"):
                try:
                    er_page._ensure_list_page()
                    er_page.er_delete(er_name)
                    er_page.assert_deleted(er_name, timeout=60)
                    logger.info(f"ER {er_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除ER失败: {e}")
                    cleanup_errors.append(f"删除ER: {e}")

            if cleanup_errors and main_error is None:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")

    @allure.title("企业路由器-添加ER连接功能验证")
    def test_er_er_connection_create(self, er_page, vpc):
        """测试两个ER之间添加ER连接：创建HA和非HA ER、生成授权码、双向添加ER连接、验证状态。"""
        er1_name = f"er-ha-{random_data(length=4)}"
        er2_name = f"er-noha-{random_data(length=4)}"
        conn1_name = f"er1-er2-conn-{random_data(length=4)}"
        conn2_name = f"er2-er1-conn-{random_data(length=4)}"
        cluster_name = "Autotest"
        main_error = None
        cleanup_errors = []

        try:
            with allure_step_log("步骤1: 创建HA企业路由器"):
                er_page._ensure_list_page()
                er_page.er_create(
                    name=er1_name,
                    cluster_name=cluster_name,
                    ha_enable=True,
                )
                er_page.assert_popup_success(timeout=10000)
                logger.info(f"HA ER {er1_name} 创建提交成功")

            with allure_step_log("步骤2: 创建非HA企业路由器"):
                er_page._ensure_list_page()
                er_page.page.wait_for_timeout(2000)
                er_page.er_create(
                    name=er2_name,
                    cluster_name=cluster_name,
                    ha_enable=False,
                )
                er_page.assert_popup_success(timeout=10000)
                logger.info(f"非HA ER {er2_name} 创建提交成功")

            with allure_step_log("步骤3: 等待两个ER状态变为运行中"):
                er_page._ensure_list_page()
                er_page.assert_status(
                    er1_name,
                    status="运行中",
                    timeout=1200,
                    refresh=True,
                    refresh_interval=30,
                )
                er_page.assert_status(
                    er2_name,
                    status="运行中",
                    timeout=1200,
                    refresh=True,
                    refresh_interval=30,
                )
                logger.info("两个ER状态均为运行中")

            with allure_step_log("步骤4: 生成两个ER的授权码"):
                er1_code = er_page.er_generate_auth_code(er1_name)
                er2_code = er_page.er_generate_auth_code(er2_name)
                logger.info("两个ER授权码生成成功")

            with allure_step_log("步骤5: 在HA ER上添加ER连接"):
                er_page.goto_connection_tab(er1_name)
                er_page.er_connection_create(
                    name=conn1_name,
                    conn_type="ER",
                    auth_code=er2_code,
                )
                er_page.assert_popup_success(timeout=10000)
                logger.info(f"HA ER连接 {conn1_name} 添加成功")

            with allure_step_log("步骤6: 验证HA ER连接状态"):
                er_page.assert_status(
                    conn1_name,
                    status="运行中",
                    timeout=60,
                    refresh=True,
                    refresh_interval=20,
                )
                logger.info(f"连接 {conn1_name} 状态验证成功: 运行中")

            with allure_step_log("步骤7: 在非HA ER上添加ER连接"):
                er_page._ensure_list_page()
                er_page.goto_connection_tab(er2_name)
                er_page.er_connection_create(
                    name=conn2_name,
                    conn_type="ER",
                    auth_code=er1_code,
                )
                er_page.assert_popup_success(timeout=10000)
                logger.info(f"非HA ER连接 {conn2_name} 添加成功")

            with allure_step_log("步骤8: 验证非HA ER连接状态"):
                er_page.assert_status(
                    conn2_name,
                    status="运行中",
                    timeout=60,
                    refresh=True,
                    refresh_interval=20,
                )
                logger.info(f"连接 {conn2_name} 状态验证成功: 运行中")

        except Exception as e:
            main_error = e
            raise
        finally:
            with allure_step_log("清理: 删除HA ER的连接"):
                try:
                    er_page.goto_connection_tab(er1_name)
                    er_page.er_connection_delete(conn1_name)
                    er_page.assert_deleted(conn1_name, timeout=30)
                    logger.info(f"连接 {conn1_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除HA ER连接失败: {e}")
                    cleanup_errors.append(f"删除HA ER连接: {e}")

            with allure_step_log("清理: 删除非HA ER的连接"):
                try:
                    er_page._ensure_list_page()
                    er_page.goto_connection_tab(er2_name)
                    er_page.er_connection_delete(conn2_name)
                    er_page.assert_deleted(conn2_name, timeout=30)
                    logger.info(f"连接 {conn2_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除非HA ER连接失败: {e}")
                    cleanup_errors.append(f"删除非HA ER连接: {e}")

            with allure_step_log("清理: 删除企业路由器"):
                try:
                    er_page._ensure_list_page()
                    er_page.er_delete(er2_name)
                    er_page.assert_deleted(er2_name, timeout=60)
                    logger.info(f"非HA ER {er2_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除非HA ER失败: {e}")
                    cleanup_errors.append(f"删除非HA ER: {e}")

                try:
                    er_page._ensure_list_page()
                    er_page.er_delete(er1_name)
                    er_page.assert_deleted(er1_name, timeout=60)
                    logger.info(f"HA ER {er1_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除HA ER失败: {e}")
                    cleanup_errors.append(f"删除HA ER: {e}")

            if cleanup_errors and main_error is None:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")
