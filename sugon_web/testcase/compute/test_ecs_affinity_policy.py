import allure
import pytest

from sugon_web.testcase.compute._ecs_fixtures import affinity
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.utils.decorators import skip_if_nodes_less_than


@allure.epic("计算服务")
@allure.feature("亲和组")
@allure.story("亲和组策略验证")
class TestEcsAffinityPolicy:
    """验证亲和策略：3台虚机运行在同一计算节点上。"""

    @pytest.mark.parametrize("affinity", [{"policy": "亲和"}], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 3}, "bind_mfip": False}], indirect=True)
    @allure.title("ECS-创建亲和策略的亲和组")
    def test_ecs_affinity_policy(self, ecs_page, affinity, vm, ssh_host):
        vm_names = [v["name"] for v in vm]
        hosts = [v["host"] for v in vm]

        with allure_step_log("步骤1: 列表页验证计算节点分布"):
            assert len(set(hosts)) == 1, (
                f"[FieldAssertion] 亲和策略验证 | 3台虚机应运行在同一物理机 | "
                f"实际: {hosts}"
            )

        with allure_step_log("步骤2: SSH后端验证计算节点"):
            for v in vm:
                guest_info = ssh_host.guest_show(v["name"])
                actual_node = guest_info.get("node")
                assert actual_node == hosts[0], (
                    f"[BackendAssertion] {v['name']} | 后端节点验证 | "
                    f"期望: {hosts[0]} | 实际: {actual_node}"
                )

        with allure_step_log("步骤3: 详情页验证亲和组信息"):
            for v in vm:
                ecs_page.assert_ecs_details_info(
                    v["name"], info_items={"亲和组": affinity}
                )


@allure.epic("计算服务")
@allure.feature("亲和组")
@allure.story("亲和组策略验证")
class TestEcsAntiAffinityPolicy:
    """验证反亲和策略：n台虚机分布在n个不同计算节点上；n+1台创建失败。"""

    @pytest.mark.parametrize("affinity", [{"policy": "反亲和"}], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 3}, "bind_mfip": False}], indirect=True)
    @skip_if_nodes_less_than(2)
    @allure.title("ECS-创建反亲和策略的亲和组")
    def test_ecs_anti_affinity_policy(self, ecs_page, affinity, vm, ssh_host, config):
        node_count = int(config.get("_node_count", 2))
        vm_names = [v["name"] for v in vm]
        hosts = [v["host"] for v in vm]

        with allure_step_log("步骤1: 列表页验证计算节点分布"):
            unique_hosts = set(hosts)
            assert len(unique_hosts) == node_count, (
                f"[FieldAssertion] 反亲和策略验证 | {node_count}台虚机应分布在"
                f"{node_count}个不同物理机 | 实际: {hosts}"
            )

        with allure_step_log("步骤2: SSH后端验证计算节点"):
            for v in vm:
                guest_info = ssh_host.guest_show(v["name"])
                actual_node = guest_info.get("node")
                assert actual_node in hosts, (
                    f"[BackendAssertion] {v['name']} | 后端节点验证 | "
                    f"期望在 {hosts} 中 | 实际: {actual_node}"
                )

        with allure_step_log("步骤3: 详情页验证亲和组信息"):
            for v in vm:
                ecs_page.assert_ecs_details_info(
                    v["name"], info_items={"亲和组": affinity}
                )

        with allure_step_log(f"步骤4: 验证反亲和资源耗尽，创建{node_count + 1}台应失败"):
            overflow_name = f"ecs-overflow-{random_data(length=3)}"
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.ecs_create(
                basic={"name": overflow_name, "count": node_count + 1},
                advanced={"affinity": [affinity]},
            )
            ecs_page.assert_popup_error()


@allure.epic("计算服务")
@allure.feature("亲和组")
@allure.story("亲和组策略验证")
class TestEcsWeakAffinityPolicy:
    """验证弱亲和策略：n台虚机绑定弱亲和组后可正常创建，不强求节点分布。"""

    @pytest.mark.parametrize("affinity", [{"policy": "弱亲和"}], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 3}, "bind_mfip": False}], indirect=True)
    @allure.title("ECS-创建弱亲和策略的亲和组")
    def test_ecs_weak_affinity_policy(self, ecs_page, affinity, vm):
        vm_names = [v["name"] for v in vm]

        with allure_step_log("步骤1: 验证虚机创建成功"):
            for v in vm:
                assert v.get("host"), (
                    f"[FieldAssertion] {v['name']} | 虚机应已分配计算节点"
                )

        with allure_step_log("步骤2: 详情页验证亲和组信息"):
            for v in vm:
                ecs_page.assert_ecs_details_info(
                    v["name"], info_items={"亲和组": affinity}
                )


@allure.epic("计算服务")
@allure.feature("亲和组")
@allure.story("亲和组策略验证")
class TestEcsWeakAntiAffinityPolicy:
    """验证弱反亲和策略：n台虚机绑定弱反亲和组后可正常创建，不强求节点分布。"""

    @pytest.mark.parametrize("affinity", [{"policy": "弱反亲和"}], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 3}, "bind_mfip": False}], indirect=True)
    @skip_if_nodes_less_than(2)
    @allure.title("ECS-创建弱反亲和策略的亲和组")
    def test_ecs_weak_anti_affinity_policy(self, ecs_page, affinity, vm):
        vm_names = [v["name"] for v in vm]

        with allure_step_log("步骤1: 验证虚机创建成功"):
            for v in vm:
                assert v.get("host"), (
                    f"[FieldAssertion] {v['name']} | 虚机应已分配计算节点"
                )

        with allure_step_log("步骤2: 详情页验证亲和组信息"):
            for v in vm:
                ecs_page.assert_ecs_details_info(
                    v["name"], info_items={"亲和组": affinity}
                )
