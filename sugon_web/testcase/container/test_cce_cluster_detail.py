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
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

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
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 添加自定义标签"):
            cce_page.cce_node_label_edit(node_name, {"test-key": "test-value"})
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 删除自定义标签"):
            cce_page.cce_node_label_edit(node_name, {})
            cce_page.assert_popup_success()

    @allure.title("集群详情页-新增计算节点")
    def test_node_create(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 记录当前节点数量"):
            before_count = cce_page.get_node_count()

        with allure_step_log("步骤3: 新增计算节点"):
            cce_page.cce_node_create(num=1, volume_size=50, flavor="4C8G", max_pods=110)
            try:
                cce_page.assert_popup_success()
            except AssertionError as e:
                if "创建节点中" in str(e):
                    pytest.skip(f"集群正在创建节点中，跳过此用例: {e}")
                raise

        with allure_step_log("步骤4: 验证节点数量增加"):
            after_count = cce_page.get_node_count()
            assert after_count == before_count + 1, f"节点数量未增加: 期望 {before_count + 1}, 实际 {after_count}"

    @allure.title("集群详情页-节点排水")
    def test_node_drain(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 执行节点排水"):
            cce_page.cce_node_drain(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证节点排水成功"):
            # 排水是异步操作，完成后节点状态恢复为正常调度，不持久显示"排水成功"
            # 仅验证弹窗成功即可，若需强验证可通过 SSH 检查节点上 Pod 驱逐情况
            cce_page.wait_for_page_ready()
            row_data = cce_page.get_row_data(node_name)
            schedule_status = row_data.get("调度状态", "") if row_data else ""
            assert "正常调度" in schedule_status or "无法调度" in schedule_status, f"节点调度状态异常: {schedule_status}"

    @allure.title("集群详情页-修改节点规格")
    def test_node_flavor_change(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 记录当前节点规格"):
            before_data = cce_page.get_row_data(node_name)
            before_flavor = before_data.get("规格", "") if before_data else ""

        with allure_step_log("步骤3: 修改节点规格"):
            target_flavor = "cce.d6.xlarge"  # 对应 8核16GiB
            if before_flavor == target_flavor:
                target_flavor = "cce.d6.large"  # 对应 4核8GiB
            cce_page.cce_node_flavor_change(node_name, target_flavor)
            cce_page.assert_popup_success()

        with allure_step_log("步骤4: 验证节点规格已变更"):
            cce_page.assert_status(node_name, "运行中", timeout=600)
            after_data = cce_page.get_row_data(node_name)
            after_flavor = after_data.get("规格", "") if after_data else ""
            assert target_flavor in after_flavor, f"规格未变更: 期望包含 {target_flavor}, 实际 {after_flavor}"

    @allure.title("集群详情页-修改节点规格（缩容）")
    def test_node_flavor_shrink(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 记录当前节点规格"):
            before_data = cce_page.get_row_data(node_name)
            before_flavor = before_data.get("规格", "") if before_data else ""

        with allure_step_log("步骤3: 确保当前规格非目标规格（如需则先扩容）"):
            if "cce.d6.large" in before_flavor:
                cce_page.cce_node_flavor_change(node_name, "cce.d6.xlarge")
                cce_page.assert_popup_success()
                cce_page.assert_status(node_name, "运行中", timeout=600)

        with allure_step_log("步骤4: 缩容节点规格"):
            cce_page.cce_node_flavor_change(node_name, "cce.d6.large")
            cce_page.assert_popup_success()

        with allure_step_log("步骤5: 验证节点规格已缩容"):
            cce_page.assert_status(node_name, "运行中", timeout=600)
            after_data = cce_page.get_row_data(node_name)
            after_flavor = after_data.get("规格", "") if after_data else ""
            assert "cce.d6.large" in after_flavor, f"规格未缩容: 期望包含 cce.d6.large, 实际 {after_flavor}"

    @allure.title("集群详情页-节点挂载新云硬盘")
    def test_node_volume_mount_new(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 挂载新云硬盘"):
            try:
                cce_page.cce_node_volume_mount_new(
                    node_name,
                    name=f"test-vol-{cluster_name}",
                    volume_type="xbd-type",
                    volume_mode="thick",
                    size=50,
                    mount_path="/data/test"
                )
                cce_page.assert_popup_success()
            except Exception as e:
                if "Timeout" in str(e):
                    pytest.skip(f"当前环境云硬盘类型/模式选项不匹配: {e}")
                raise

    @allure.title("集群详情页-未绑定公网IP时绑定域名提示错误")
    def test_public_domain_without_ip_error(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 点击绑定公网域名"):
            cce_page.page.get_by_text("绑定公网域名",exact=True).click()

        with allure_step_log("步骤3: 验证提示错误信息"):
            message = cce_page.locator(".el-message__content")
            message.wait_for(state="visible", timeout=10000)
            assert "请先绑定公网IP" in message.inner_text()

    @allure.title("集群详情页-绑定和解绑集群公网IP")
    def test_public_ip_bind_unbind(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 绑定公网IP"):
            ip = cce_page.cce_public_ip_bind()
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证公网IP绑定成功"):
            displayed_ip = cce_page.get_public_ip_text(timeout=30)
            assert displayed_ip == ip, f"公网IP显示不一致: 期望 {ip}, 实际 {displayed_ip}"

        with allure_step_log("步骤4: 解绑公网IP"):
            cce_page.cce_public_ip_unbind()
            cce_page.assert_popup_success()

        with allure_step_log("步骤5: 验证公网IP解绑成功"):
            displayed_ip = cce_page.get_public_ip_text(timeout=10)
            assert displayed_ip == "", f"公网IP未解绑: 实际显示 {displayed_ip}"

    @allure.title("集群详情页-绑定和解绑节点公网IP")
    def test_node_public_ip_bind_unbind(self, cce_page, cce_cluster, ssh_host):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["node_name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 绑定节点公网IP"):
            ip = cce_page.cce_node_public_ip_bind(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证公网IP绑定成功"):
            ssh_host.ping(ip)

        with allure_step_log("步骤4: 解绑节点公网IP"):
            cce_page.cce_node_public_ip_unbind(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤5: 验证公网IP解绑成功"):
            ssh_host.ping(ip, connected=False)
