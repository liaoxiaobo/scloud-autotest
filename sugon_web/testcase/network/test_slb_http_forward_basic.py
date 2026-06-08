import time

import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import (
    assert_lb_algorithm,
    collect_lb_http_responses,
    prepare_http_backend,
    stop_http_backend,
)
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log


PORT = 8080


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V2", "ha_enable": True}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("基础版V2-HTTP转发策略验证")
class TestSlbV2HttpForwardPolicy:
    """负载均衡（基础版）V2 HTTP协议转发策略功能验证"""

    @allure.title("SLB-V2-HTTP协议转发策略基本功能验证")
    def test_slbv2_http_forward_policy(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        """用例436748：v2-HTTP协议转发策略基本功能验证"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-http-{random_data()}"
        pool_name = f"pool-{random_data()}"
        forward_pool_name = f"fwd-pool-{random_data()}"
        rule_name = f"rule-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }

        with allure_step_log("步骤1: 创建HTTP监听器（轮询算法，开启健康检查）"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
                port=PORT,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="轮询",
                health_check=True,
                health_type="HTTP",
                http_method="GET",
                url_path="/index.html",
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({
                "slb_name": slb["name"],
                "lb_name": lb_name,
                "pool_name": pool_name,
                "extra_pools": [forward_pool_name],
                "forward_rules": [rule_name],
            })

        with allure_step_log("步骤2: 添加默认资源池成员（ecs1/ecs2/ecs3）"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(backend["name"], port=PORT)

        with allure_step_log("步骤3: 创建转发目标资源池（只包含ecs1）"):
            vpc_page.lb_pool_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                pool_name=forward_pool_name,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success()
            vpc_page.lb_pool_add_vm(
                vm_names=[backends[0]["name"]],
                lb_name=lb_name,
                pool_name=forward_pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")

        with allure_step_log("步骤4: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                # 先停止旧进程，避免端口占用导致新进程无法启动
                stop_http_backend(ssh_vm, backend, port=PORT)
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)
                # 额外创建test1目录，用于转发策略URL路径匹配验证
                ssh_vm.connect(backend["mfip"])
                workdir = f"/root/slb-http-ecs{i + 1}-{PORT}"
                ssh_vm.run(
                    f"mkdir -p {workdir}/test1 && "
                    f"echo 'this is ecs{i + 1} for test1' > {workdir}/test1/index.html",
                    check_rc=True,
                )

        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤5: 内网VIP访问测试（验证轮询）"):
            ssh_vm.connect(requester["mfip"])
            time.sleep(5)
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=12
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "V2 HTTP 内网VIP 轮询验证",
            )

        with allure_step_log("步骤6: 新建HTTP转发策略"):
            # 使用URL路径作为匹配条件（页面对象当前支持单条件）
            # 需求原文为"域名 www.test1.com，URL转发 /test1/index.html"
            # 实际通过URL路径条件即可验证转发策略核心功能
            vpc_page.lb_forward_rule_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                rule_name=rule_name,
                condition_type="URL路径",
                judge_condition="精确匹配相等",
                condition_value="/test1/index.html",
                forward_pool_name=forward_pool_name,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤7: 验证转发策略生效（URL路径匹配）"):
            # 先等待转发规则生效（配置同步到负载均衡器需要时间）
            time.sleep(30)
            ssh_vm.connect(requester["mfip"])
            # 使用直接curl获取响应（避免count_lb_responses的潜在问题）
            responses = []
            for _ in range(6):
                resp = ssh_vm.run(
                    f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/test1/index.html",
                    check_rc=False,
                ).strip()
                responses.append(resp)
            # 转发策略匹配/test1/index.html后，所有请求应被转发到ecs1
            hits = [r for r in responses if r == "this is ecs1 for test1"]
            assert len(hits) == 6, (
                f"转发策略应将所有请求转发到ecs1，"
                f"实际响应: {responses}"
            )

        with allure_step_log("步骤8: 删除转发策略"):
            vpc_page.lb_forward_rule_delete(slb["name"], lb_name, rule_name)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤9: 验证转发策略删除后回到轮询"):
            ssh_vm.connect(requester["mfip"])
            responses = []
            for _ in range(12):
                resp = ssh_vm.run(
                    f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/test1/index.html",
                    check_rc=False,
                ).strip()
                responses.append(resp)
            # 删除转发策略后，应回到默认资源池的轮询调度
            total_hits = len([r for r in responses if r])
            assert total_hits > 0, f"未采集到任何响应: {responses}"
            # 至少有两个后端被命中（允许轻微偏差）
            backend_hits = {r for r in responses if "for test1" in r}
            assert len(backend_hits) >= 2, (
                f"删除转发策略后应回到轮询，至少命中2台后端，实际: {responses}"
            )

        # 步骤10: 删除HTTP监听器 —— 由 clean_lb_listener fixture 的 teardown 自动处理
        # 清理顺序：转发规则 -> 非默认资源池成员 -> 非默认资源池 -> 默认资源池成员 -> 监听器
        # SLB/VM/VPC 由各自 fixture 的 teardown 自动清理
