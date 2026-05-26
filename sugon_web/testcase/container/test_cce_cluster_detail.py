import allure
import pytest

from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('集群管理-详情页-节点操作')
class TestCCENodeOperations:

    @allure.title("集群详情页-节点停止调度和开启调度")
    def test_node_schedule_stop_and_start(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 停止节点调度"):
            cce_page.cce_node_schedule_stop(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证节点状态为无法调度"):
            cce_page.assert_status(node_name, "无法调度", timeout=60)

        with allure_step_log("步骤4: 开启节点调度"):
            cce_page.cce_node_schedule_start(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤5: 验证节点状态恢复正常调度"):
            cce_page.assert_status(node_name, "正常调度", timeout=60)

    @allure.title("集群详情页-节点添加和删除自定义标签")
    def test_node_label_add_and_delete(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 添加自定义标签"):
            cce_page.cce_node_label_add(node_name, "test-key", "test-value")
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 删除自定义标签"):
            cce_page.cce_node_label_delete(node_name, "test-key")
            cce_page.assert_popup_success()

    @allure.title("集群详情页-新增计算节点")
    def test_node_create(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 记录当前节点数量"):
            before_count = cce_page.get_node_count()

        with allure_step_log("步骤3: 新增计算节点"):
            cce_page.cce_node_create(num=1, volume_size=50, flavor="4C8G", max_pods=110)
            cce_page.assert_popup_success()

        with allure_step_log("步骤4: 验证节点数量增加"):
            after_count = cce_page.get_node_count()
            assert after_count == before_count + 1, f"节点数量未增加: 期望 {before_count + 1}, 实际 {after_count}"

    @allure.title("集群详情页-节点排水")
    def test_node_drain(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 执行节点排水"):
            cce_page.cce_node_drain(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证节点排水成功"):
            cce_page.assert_status(node_name, "排水成功", timeout=300)

    @allure.title("集群详情页-修改节点规格")
    def test_node_flavor_change(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 记录当前节点规格"):
            before_data = cce_page.get_row_data(node_name)
            before_flavor = before_data.get("规格", "") if before_data else ""

        with allure_step_log("步骤3: 修改节点规格"):
            target_flavor = "8C16G"
            if before_flavor == target_flavor:
                target_flavor = "4C8G"
            cce_page.cce_node_flavor_change(node_name, target_flavor)
            cce_page.assert_popup_success()

        with allure_step_log("步骤4: 验证节点规格已变更"):
            cce_page.assert_status(node_name, "运行中", timeout=600)
            after_data = cce_page.get_row_data(node_name)
            after_flavor = after_data.get("规格", "") if after_data else ""
            assert target_flavor in after_flavor, f"规格未变更: 期望包含 {target_flavor}, 实际 {after_flavor}"

    @allure.title("集群详情页-节点挂载新云硬盘")
    def test_node_volume_mount_new(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 挂载新云硬盘"):
            cce_page.cce_node_volume_mount_new(
                node_name,
                name=f"test-vol-{cluster_name}",
                volume_type="xbd-test",
                volume_mode="thin",
                size=50,
                mount_path="/data/test"
            )
            cce_page.assert_popup_success()


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('集群管理-详情页-网络操作')
class TestCCENetworkOperations:

    @allure.title("集群详情页-绑定和解绑集群公网IP")
    def test_public_ip_bind_unbind(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 绑定公网IP"):
            cce_page.cce_public_ip_bind()
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证绑定按钮变为解绑"):
            expect(cce_page.page.get_by_text("解绑公网IP")).to_be_visible(timeout=10000)

        with allure_step_log("步骤4: 解绑公网IP"):
            cce_page.cce_public_ip_unbind()
            cce_page.assert_popup_success()

        with allure_step_log("步骤5: 验证解绑后按钮恢复为绑定"):
            expect(cce_page.page.get_by_text("绑定公网IP")).to_be_visible(timeout=10000)

    @allure.title("集群详情页-绑定和解绑公网域名")
    def test_public_domain_bind_unbind(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 绑定公网IP（前置条件）"):
            cce_page.cce_public_ip_bind()
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 绑定公网域名"):
            cce_page.cce_public_domain_bind("test")
            cce_page.assert_popup_success()

        with allure_step_log("步骤4: 验证绑定域名按钮变为解绑"):
            expect(cce_page.page.get_by_text("解绑公网域名")).to_be_visible(timeout=10000)

        with allure_step_log("步骤5: 解绑公网域名"):
            cce_page.cce_public_domain_unbind()
            cce_page.assert_popup_success()

        with allure_step_log("步骤6: 验证公网域名已解绑"):
            expect(cce_page.page.get_by_text("绑定公网域名")).to_be_visible(timeout=10000)

        with allure_step_log("步骤7: 解绑公网IP（清理）"):
            expect(cce_page.page.get_by_text("解绑公网IP")).to_be_visible(timeout=10000)
            cce_page.cce_public_ip_unbind()
            cce_page.assert_popup_success()

        with allure_step_log("步骤8: 验证公网IP已解绑"):
            expect(cce_page.page.get_by_text("绑定公网IP")).to_be_visible(timeout=10000)

    @allure.title("集群详情页-未绑定公网IP时绑定域名提示错误")
    def test_public_domain_without_ip_error(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 点击绑定公网域名"):
            cce_page.page.get_by_text("绑定公网域名").click()

        with allure_step_log("步骤3: 验证提示错误信息"):
            message = cce_page.locator(".el-message__content")
            message.wait_for(state="visible", timeout=10000)
            assert "请先绑定公网IP" in message.inner_text()

    @allure.title("集群详情页-绑定和解绑节点公网IP")
    def test_node_public_ip_bind_unbind(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_detail_page(cluster_name)

        with allure_step_log("步骤2: 绑定节点公网IP"):
            cce_page.cce_node_public_ip_bind(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证节点行中公网IP已绑定"):
            ip_text = cce_page.get_node_public_ip_text(node_name)
            assert ip_text, f"节点 {node_name} 公网IP未绑定成功"

        with allure_step_log("步骤4: 解绑节点公网IP"):
            cce_page.cce_node_public_ip_unbind(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤5: 验证节点行中公网IP已解绑"):
            ip_text = cce_page.get_node_public_ip_text(node_name)
            assert not ip_text, f"节点 {node_name} 公网IP未解绑成功，当前值: {ip_text}"
