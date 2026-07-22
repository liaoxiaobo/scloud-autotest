import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('企业路由器')
@allure.story('修改基本信息')
class TestEREditBasicInfo:

    @allure.title("企业路由器-修改基本信息-无连接")
    def test_er_edit_basic_info_no_conn(self, er_page):
        """测试非HA企业路由器无连接时的基本信息修改功能。"""
        er_name = f"er-edit-noha-{random_data(length=4)}"
        new_name = f"{er_name}-modify"
        description = "这是autotest修改的描述信息"
        cluster_name = "Autotest"
        main_error = None
        cleanup_errors = []

        try:
            with allure_step_log("步骤1: 创建非HA企业路由器"):
                er_page._ensure_list_page()
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                er_page.er_create(
                    name=er_name,
                    cluster_name=cluster_name,
                    ha_enable=False,
                )
                er_page.assert_popup_success(timeout=10000)
                er_page.assert_status(er_name, status="运行中", timeout=1200, refresh=True, refresh_interval=30)
                logger.info(f"非HA ER {er_name} 创建成功")

            with allure_step_log("步骤2: 修改基本信息"):
                er_page.er_edit(
                    name=er_name,
                    new_name=new_name,
                    description=description,
                )
                er_page.assert_popup_success("修改企业路由器成功")
                logger.info(f"ER基本信息修改成功: {new_name}")

            with allure_step_log("步骤3: 列表页验证修改结果"):
                er_page._ensure_list_page()
                er_page.assert_list_contain(new_name, column_name="名称")
                logger.info("列表页验证通过")

            with allure_step_log("步骤4: 详情页验证修改结果"):
                er_page.goto_er_detail(new_name)
                detail_name = er_page.get_detail_field_value("名称")
                detail_desc = er_page.get_detail_field_value("描述")
                assert detail_name == new_name, f"详情页名称不匹配: 期望 {new_name}, 实际 {detail_name}"
                assert detail_desc == description, f"详情页描述不匹配: 期望 {description}, 实际 {detail_desc}"
                logger.info("详情页验证通过")

        except Exception as e:
            main_error = e
            raise
        finally:
            with allure_step_log("清理: 删除ER实例"):
                try:
                    er_page._ensure_list_page()
                    er_page.close_dialog_if_exists()
                    er_page.wait_for_page_ready()
                    er_page.er_delete(new_name)
                    er_page.assert_deleted(new_name, timeout=60)
                    logger.info(f"ER {new_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除ER失败: {e}")
                    cleanup_errors.append(f"删除ER: {e}")

            if cleanup_errors and main_error is None:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")

    @allure.title("企业路由器-修改基本信息-有连接")
    def test_er_edit_basic_info_with_conn(self, er_page, vpc_page):
        """测试HA企业路由器有连接时的基本信息修改功能。"""
        vpc_name = f"er-edit-vpc-{random_data(length=4)}"
        subnet_name = f"subnet-{random_data(length=4)}"
        er_name = f"er-edit-ha-{random_data(length=4)}"
        new_name = f"{er_name}-modify"
        description = "这是autotest修改的描述信息"
        conn_name = f"conn-{random_data(length=4)}"
        cluster_name = "Autotest"
        main_error = None
        cleanup_errors = []

        try:
            with allure_step_log("步骤1: 创建VPC"):
                vpc_page.goto_service("虚拟私有云")
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                vpc_page.vpc_create(
                    name=vpc_name,
                    subnet_name=subnet_name,
                    cidr="173.3.3.0/24",
                    cluster=cluster_name,
                )
                vpc_page.assert_popup_success("创建虚拟私有云成功")
                vpc_page.assert_status(vpc_name)
                logger.info(f"VPC {vpc_name} 创建成功")

            with allure_step_log("步骤2: 创建HA企业路由器"):
                er_page._ensure_list_page()
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                er_page.er_create(
                    name=er_name,
                    cluster_name=cluster_name,
                    ha_enable=True,
                )
                er_page.assert_popup_success(timeout=10000)
                er_page.assert_status(er_name, status="运行中", timeout=1200, refresh=True, refresh_interval=30)
                logger.info(f"HA ER {er_name} 创建成功")

            with allure_step_log("步骤3: 添加VPC连接到ER"):
                er_page._ensure_list_page()
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                er_page.goto_connection_tab(er_name)
                er_page.er_connection_create(
                    name=conn_name,
                    conn_type="VPC",
                    vpc_name=vpc_name,
                    subnet_name=subnet_name,
                )
                er_page.assert_popup_success(timeout=10000)
                er_page.assert_status(conn_name, status="运行中", timeout=60, refresh=True, refresh_interval=20)
                logger.info(f"VPC连接 {conn_name} 添加成功")

            with allure_step_log("步骤4: 修改基本信息"):
                er_page._ensure_list_page()
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                er_page.er_edit(
                    name=er_name,
                    new_name=new_name,
                    description=description,
                )
                er_page.assert_popup_success("修改企业路由器成功")
                logger.info(f"ER基本信息修改成功: {new_name}")

            with allure_step_log("步骤5: 列表页验证修改结果"):
                er_page._ensure_list_page()
                er_page.assert_list_contain(new_name, column_name="名称")
                logger.info("列表页验证通过")

            with allure_step_log("步骤6: 详情页验证修改结果"):
                er_page.goto_er_detail(new_name)
                detail_name = er_page.get_detail_field_value("名称")
                detail_desc = er_page.get_detail_field_value("描述")
                assert detail_name == new_name, f"详情页名称不匹配: 期望 {new_name}, 实际 {detail_name}"
                assert detail_desc == description, f"详情页描述不匹配: 期望 {description}, 实际 {detail_desc}"
                logger.info("详情页验证通过")

        except Exception as e:
            main_error = e
            raise
        finally:
            with allure_step_log("清理: 删除ER连接"):
                try:
                    er_page._ensure_list_page()
                    er_page.close_dialog_if_exists()
                    er_page.wait_for_page_ready()
                    er_page.goto_connection_tab(new_name)
                    er_page.er_connection_delete(conn_name)
                    er_page.assert_deleted(conn_name, timeout=30)
                    logger.info("ER连接删除成功")
                except Exception as e:
                    logger.warning(f"删除ER连接失败: {e}")
                    cleanup_errors.append(f"删除ER连接: {e}")

            with allure_step_log("清理: 删除ER实例"):
                try:
                    er_page._ensure_list_page()
                    er_page.close_dialog_if_exists()
                    er_page.wait_for_page_ready()
                    er_page.er_delete(new_name)
                    er_page.assert_deleted(new_name, timeout=60)
                    logger.info(f"ER {new_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除ER失败: {e}")
                    cleanup_errors.append(f"删除ER: {e}")

            with allure_step_log("清理: 删除VPC"):
                try:
                    vpc_page.goto_service("虚拟私有云")
                    vpc_page.goto_submenu("虚拟私有云")
                    vpc_page.wait_for_page_ready()
                    vpc_page.vpc_delete(vpc_name)
                    vpc_page.assert_deleted(vpc_name, timeout=120)
                    logger.info(f"VPC {vpc_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除VPC失败: {e}")
                    cleanup_errors.append(f"删除VPC: {e}")

            if cleanup_errors and main_error is None:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")
