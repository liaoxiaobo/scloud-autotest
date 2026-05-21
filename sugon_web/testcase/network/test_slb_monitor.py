import allure
import pytest
import time

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import prepare_http_backend
from sugon_web.utils.logger import allure_step_log


PORT = 8080


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("监控功能验证")
class TestSlbMonitor:
    """负载均衡（基础版）- L4LB - TCP监听器监控功能验证"""

    @allure.title("SLB-TCP监听器监控功能验证")
    def test_slb_monitor_tcp_listener(
        self, page, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        """用例414218：lb基础版 > lb监控 > L4LB > tcp监听器正向功能验证"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = "tcp_8080"
        pool_name = "backend_1"

        # --------------------------------------------------------------
        # 步骤1: 创建TCP监听器并添加资源池成员
        # --------------------------------------------------------------
        with allure_step_log("步骤1: 创建TCP监听器并添加资源池成员"):
            vpc_page.slb_lb_create(
                slb_name=slb,
                lb_name=lb_name,
                protocol="TCP",
                port=PORT,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb, "lb_name": lb_name, "pool_name": pool_name})

            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(backend["name"], port=PORT)

        # --------------------------------------------------------------
        # 步骤2: 后端虚机启动web服务
        # --------------------------------------------------------------
        with allure_step_log("步骤2: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        # 在离开VPC页面前获取所需信息
        slb_uuid = vpc_page.get_slb_uuid(slb)
        lb_vip = vpc_page.get_slb_vip(slb)
        project_id = vpc_page.get_slb_project_id(slb)

        # --------------------------------------------------------------
        # 步骤3: 进入SLB监控详情页（network模块 - 点击"查看监控"）
        # --------------------------------------------------------------
        with allure_step_log("步骤3: 进入SLB监控详情页"):
            vpc_page.goto_submenu("负载均衡（基础版）")
            vpc_page.click_action(slb, "查看监控")
            vpc_page.select_time_range("实时")


        # --------------------------------------------------------------
        # 步骤4: VIP访问测试（生成流量数据）
        # --------------------------------------------------------------
        with allure_step_log("步骤4: VIP访问测试生成流量数据"):
            ssh_vm.connect(requester["mfip"])
            time.sleep(5)
            for _ in range(10):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{PORT}/index.html",
                    check_rc=False,
                )
                time.sleep(1)

        # --------------------------------------------------------------
        # 步骤5: 实例级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤5: 实例级别监控验证"):
            vpc_page.select_object_tab("实例")
            vpc_page.assert_monitor_charts_visible(min_charts=1)

        # --------------------------------------------------------------
        # 步骤6: 监听器级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤6: 监听器级别监控验证"):
            vpc_page.select_object_tab("监听器")
            vpc_page.select_listener(lb_name)
            vpc_page.assert_monitor_charts_visible(min_charts=1)

        # --------------------------------------------------------------
        # 补充流量数据并等待监控数据刷新
        # --------------------------------------------------------------
        with allure_step_log("补充流量数据并等待监控数据刷新"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(20):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{PORT}/index.html",
                    check_rc=False,
                )
                time.sleep(1)
            # 实时模式每10秒刷新一次，等待数据刷新
            time.sleep(15)

        # 验证监控数据不为零
        with allure_step_log("验证实例监控数据不为零"):
            vpc_page.select_object_tab("实例")
            vpc_page.assert_monitor_data_not_zero(wait_sec=5)

        with allure_step_log("验证监听器监控数据不为零"):
            vpc_page.select_object_tab("监听器")
            vpc_page.select_listener(lb_name)
            vpc_page.assert_monitor_data_not_zero(wait_sec=5)

        # --------------------------------------------------------------
        # 步骤7: 进入CMS监控服务的负载均衡详情页（cms模块）
        # 通过 goto_submenu("负载均衡（基础版）") 进入CMS监控服务下
        # 的SLB列表页，再点击slbv1名称进入详情页。
        # --------------------------------------------------------------
        with allure_step_log("步骤7: 进入CMS监控服务的负载均衡详情页"):
            from sugon_web.pages.cms import CmsPage
            cms_page = CmsPage(page)
            cms_page.goto_submenu("负载均衡（基础版）")
            cms_page.click_slb_in_list(slb)
            cms_page.wait_for_page_ready()
            cms_page.page.wait_for_timeout(3000)
            cms_page.select_time_range("实时")

        # --------------------------------------------------------------
        # 步骤8: VIP访问测试（生成流量数据）
        # --------------------------------------------------------------
        with allure_step_log("步骤8: VIP访问测试生成流量数据"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(10):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{PORT}/index.html",
                    check_rc=False,
                )
                time.sleep(1)

        # --------------------------------------------------------------
        # 步骤9: CMS监控-实例级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤9: CMS监控-实例级别监控验证"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # --------------------------------------------------------------
        # 步骤10: CMS监控-监听器级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤10: CMS监控-监听器级别监控验证"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # 补充流量数据并验证CMS监控数据不为零
        with allure_step_log("补充流量数据并等待CMS监控数据刷新"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(20):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{PORT}/index.html",
                    check_rc=False,
                )
                time.sleep(1)
            time.sleep(15)

        with allure_step_log("验证CMS实例监控数据不为零"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_data_not_zero(wait_sec=5)

        with allure_step_log("验证CMS监听器监控数据不为零"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_data_not_zero(wait_sec=5)
