import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data


@allure.epic('网络服务')
@allure.feature('企业路由器')
@allure.story('新建功能验证')
class TestERCreate:

    @allure.title("企业路由器-HA实例-新建功能验证")
    def test_er_create_ha(self, er_page, ssh_host):
        """测试HA企业路由器的新建、列表验证、详情验证和SSH后台验证。"""
        er_name = f"er-ha-{random_data(length=4)}"
        cluster_name = "Autotest"
        main_error = None
        cleanup_errors = []

        try:
            with allure_step_log("步骤1: 进入企业路由器列表页"):
                er_page._ensure_list_page()
                logger.info("已进入企业路由器列表页")

            with allure_step_log("步骤2: 创建HA企业路由器"):
                er_page.er_create(
                    name=er_name,
                    cluster_name=cluster_name,
                    ha_enable=True,
                )
                er_page.assert_popup_success(timeout=10000)
                logger.info(f"企业路由器 {er_name} 创建提交成功")

            with allure_step_log("步骤3: 验证列表页"):
                er_page._ensure_list_page()
                er_page.page.wait_for_timeout(2000)
                er_page.search(er_name)
                er_page.assert_list_contain(er_name, column_name="名称")
                logger.info(f"列表页验证成功: {er_name}")

            with allure_step_log("步骤4: 等待状态变为运行中"):
                er_page.assert_status(
                    er_name,
                    status="运行中",
                    timeout=120,
                    refresh=True,
                    refresh_interval=20,
                )
                logger.info(f"企业路由器 {er_name} 状态变为运行中")

            with allure_step_log("步骤5: 验证详情页"):
                er_page.goto_detail_page(er_name, tab_name="基本信息")
                actual_name = er_page.get_detail_field_value("名称")
                actual_status = er_page.get_detail_field_value("状态")
                assert er_name == actual_name, f"详情页名称不匹配: 期望 {er_name}, 实际 {actual_name}"
                assert "运行中" in actual_status, f"详情页状态不匹配: 期望 运行中, 实际 {actual_status}"
                logger.info(f"详情页验证成功: 名称={actual_name}, 状态={actual_status}")

            with allure_step_log("步骤6: SSH后台验证HA实例"):
                result = ssh_host.run(
                    f"source /root/admin-openrc.sh && scli guest list | grep {er_name}",
                    return_stdout=True,
                )
                logger.info(f"SSH验证结果:\n{result}")
                allure.attach(result, name="SSH后台验证结果", attachment_type=allure.attachment_type.TEXT)

                lines = [line for line in result.strip().split("\n") if line.strip()]
                logger.info(f"SSH输出行数: {len(lines)}")
                assert len(lines) == 2, f"HA实例应运行2台ECS，实际发现 {len(lines)} 台"
                for line in lines:
                    assert "RUNNING" in line, f"ECS状态不为RUNNING: {line}"
                logger.info(f"SSH后台验证成功: {len(lines)} 台ECS均为RUNNING状态")

        except Exception as e:
            main_error = e
            raise
        finally:
            with allure_step_log("清理: 删除企业路由器"):
                try:
                    er_page._ensure_list_page()
                    er_page.page.wait_for_timeout(2000)
                    er_page.er_delete(er_name)
                    er_page.assert_deleted(er_name, timeout=60)
                    logger.info(f"企业路由器 {er_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除企业路由器失败: {e}")
                    cleanup_errors.append(f"删除企业路由器: {e}")

            if cleanup_errors and main_error is None:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")

    @allure.title("企业路由器-非HA实例-新建功能验证")
    def test_er_create_non_ha(self, er_page, ssh_host):
        """测试非HA企业路由器的新建、列表验证、详情验证和SSH后台验证。"""
        er_name = f"er-noha-{random_data(length=4)}"
        cluster_name = "Autotest"
        main_error = None
        cleanup_errors = []

        try:
            with allure_step_log("步骤1: 进入企业路由器列表页"):
                er_page._ensure_list_page()
                logger.info("已进入企业路由器列表页")

            with allure_step_log("步骤2: 创建非HA企业路由器"):
                er_page.er_create(
                    name=er_name,
                    cluster_name=cluster_name,
                    ha_enable=False,
                )
                er_page.assert_popup_success(timeout=10000)
                logger.info(f"企业路由器 {er_name} 创建提交成功")

            with allure_step_log("步骤3: 验证列表页"):
                er_page._ensure_list_page()
                er_page.page.wait_for_timeout(2000)
                er_page.search(er_name)
                er_page.assert_list_contain(er_name, column_name="名称")
                logger.info(f"列表页验证成功: {er_name}")

            with allure_step_log("步骤4: 等待状态变为运行中"):
                er_page.assert_status(
                    er_name,
                    status="运行中",
                    timeout=120,
                    refresh=True,
                    refresh_interval=20,
                )
                logger.info(f"企业路由器 {er_name} 状态变为运行中")

            with allure_step_log("步骤5: 验证详情页"):
                er_page.goto_detail_page(er_name, tab_name="基本信息")
                actual_name = er_page.get_detail_field_value("名称")
                actual_status = er_page.get_detail_field_value("状态")
                assert er_name == actual_name, f"详情页名称不匹配: 期望 {er_name}, 实际 {actual_name}"
                assert "运行中" in actual_status, f"详情页状态不匹配: 期望 运行中, 实际 {actual_status}"
                logger.info(f"详情页验证成功: 名称={actual_name}, 状态={actual_status}")

            with allure_step_log("步骤6: SSH后台验证非HA实例"):
                result = ssh_host.run(
                    f"source /root/admin-openrc.sh && scli guest list | grep {er_name}",
                    return_stdout=True,
                )
                logger.info(f"SSH验证结果:\n{result}")
                allure.attach(result, name="SSH后台验证结果", attachment_type=allure.attachment_type.TEXT)

                lines = [line for line in result.strip().split("\n") if line.strip()]
                logger.info(f"SSH输出行数: {len(lines)}")
                assert len(lines) >= 1, f"后台应至少运行1台ECS，实际发现 {len(lines)} 台"
                assert "RUNNING" in lines[0], f"ECS状态不为RUNNING: {lines[0]}"
                logger.info(f"SSH后台验证成功: {len(lines)} 台ECS为RUNNING状态")

        except Exception as e:
            main_error = e
            raise
        finally:
            with allure_step_log("清理: 删除企业路由器"):
                try:
                    er_page._ensure_list_page()
                    er_page.page.wait_for_timeout(2000)
                    er_page.er_delete(er_name)
                    er_page.assert_deleted(er_name, timeout=60)
                    logger.info(f"企业路由器 {er_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除企业路由器失败: {e}")
                    cleanup_errors.append(f"删除企业路由器: {e}")

            if cleanup_errors and main_error is None:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")
