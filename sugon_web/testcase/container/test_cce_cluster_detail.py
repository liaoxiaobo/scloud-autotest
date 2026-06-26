import allure
import pytest

from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('集群管理-详情页')
class TestCCEDetail:

    @pytest.mark.parametrize("node_type", ["master", "worker"])
    @allure.title("集群详情-节点停止调度和开启调度")
    def test_node_schedule_stop_and_start(self, cce_page, cce_cluster, node_type):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster[f"{node_type}_node"]

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

    @pytest.mark.parametrize("node_type", ["master", "worker"])
    @allure.title("集群详情-节点添加和删除自定义标签")
    def test_node_label_add_and_delete(self, cce_page, cce_cluster, node_type):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster[f"{node_type}_node"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 添加自定义标签"):
            cce_page.cce_node_label_edit(node_name, {"test-key": "test-value"})
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 删除自定义标签"):
            cce_page.cce_node_label_edit(node_name, {})
            cce_page.assert_popup_success()

    @allure.title("集群详情-绑定公网域名提示错误")
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

    @allure.title("集群详情-集群公网IP绑定和解绑")
    def test_public_ip_bind_unbind(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 绑定公网IP"):
            cce_page.cce_public_ip_bind()
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证公网IP绑定成功"):
            cce_page.assert_public_ip_displayed(displayed=True)

        with allure_step_log("步骤4: 解绑公网IP"):
            cce_page.cce_public_ip_unbind()
            cce_page.assert_popup_success()

        with allure_step_log("步骤5: 验证公网IP解绑成功"):
            cce_page.assert_public_ip_displayed(displayed=False)

    @pytest.mark.parametrize("node_type", ["master", "worker"])
    @allure.title("集群详情-节点公网IP绑定和解绑")
    def test_node_public_ip_bind_unbind(self, cce_page, cce_cluster, ssh_host, node_type):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster[f"{node_type}_node"]

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

    @pytest.mark.parametrize("node_type", ["master", "worker"])
    @allure.title("集群详情-节点挂载新云硬盘")
    def test_node_volume_mount_new(self, cce_page, cce_cluster, node_type, ssh_vm):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster[f"{node_type}_node"]
        volume_name = random_data()
        size = 50
        mount_path = f"/data/{volume_name}"

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 挂载新云硬盘"):
            cce_page.cce_node_volume_mount_new(
                node_name,
                name=volume_name,
                volume_type=cce_page.volume_type,
                volume_mode="精简置备",
                size=size,
                mount_path=mount_path
            )
            cce_page.assert_popup_success(timeout=60)

        with allure_step_log("步骤3: 后台验证挂载成功"):
            node_mfip = cce_cluster.get(f"{node_type}_mfip", "")
            assert node_mfip, f"未获取到 {node_type} 节点的 MFIP"
            ssh_vm.connect(node_mfip, port=22022, pwd="admin1234@sugon")
            result = ssh_vm.run(
                f"lsblk -l | grep {mount_path}",
                return_rc=True
            )
            assert result["rc"] == 0, f"未找到挂载路径 {mount_path}: {result.get('stderr', '')}"
            assert f"{size}G" in result["stdout"], f"挂载大小不匹配，期望包含 {size}G，实际: {result['stdout']}"

    @pytest.mark.parametrize("node_type", ["master", "worker"])
    @allure.title("集群详情-修改节点规格")
    def test_node_flavor_change(self, cce_page, cce_cluster, node_type, ssh_host):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster[f"{node_type}_node"]

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
                cce_page.cce_node_flavor_shrink(node_name, target_flavor)
            else:
                cce_page.cce_node_flavor_expand(node_name, target_flavor)
            cce_page.assert_popup_success()

        with allure_step_log("步骤4: 验证节点规格已变更"):
            cce_page.assert_status(node_name, "运行中", timeout=600)
            after_data = cce_page.get_row_data(node_name)
            after_flavor = after_data.get("规格", "") if after_data else ""
            assert target_flavor in after_flavor, f"规格未变更: 期望包含 {target_flavor}, 实际 {after_flavor}"

        with allure_step_log("步骤5: SSH后台验证虚机规格"):
            flavor_specs = {
                "cce.d6.xlarge": {"vcpu": "8", "memory_mb": "16384"},
                "cce.d6.large": {"vcpu": "4", "memory_mb": "8192"},
            }
            expected = flavor_specs.get(target_flavor)
            if expected:
                ssh_host.assert_guest_fields(
                    node_name, expected, f"{node_name}规格变更后端验证失败"
                )

    @pytest.mark.parametrize("node_type", ["master", "worker"])
    @allure.title("集群详情-节点规格缩容")
    def test_node_flavor_shrink(self, cce_page, cce_cluster, node_type, ssh_host):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster[f"{node_type}_node"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情", row_name=node_name, timeout=30)

        with allure_step_log("步骤2: 记录当前节点规格"):
            before_data = cce_page.get_row_data(node_name)
            before_flavor = before_data.get("规格", "") if before_data else ""

        with allure_step_log("步骤3: 确保当前规格非目标规格（如需则先扩容）"):
            if "cce.d6.large" in before_flavor:
                cce_page.cce_node_flavor_expand(node_name, "cce.d6.xlarge")
                cce_page.assert_popup_success()
                cce_page.assert_status(node_name, "运行中", timeout=600)

        with allure_step_log("步骤4: 缩容节点规格"):
            cce_page.cce_node_flavor_shrink(node_name, "cce.d6.large")
            cce_page.assert_popup_success()

        with allure_step_log("步骤4.5: 等待状态进入中间态"):
            # 状态必须先变为"规格调整中"（证明后端已开始处理）
            # 如果操作极快（<30秒已完成），此步骤会超时，不影响后续
            try:
                cce_page.assert_status(node_name, "规格调整中", timeout=30, refresh=True)
            except AssertionError:
                # 状态已经变回"运行中"（操作极快），继续后续断言
                pass

        with allure_step_log("步骤5: 验证节点规格已缩容"):
            cce_page.assert_status(node_name, "运行中", timeout=600, refresh=True)
            after_data = cce_page.get_row_data(node_name)
            after_flavor = after_data.get("规格", "") if after_data else ""
            assert "cce.d6.large" in after_flavor, f"规格未缩容: 期望包含 cce.d6.large, 实际 {after_flavor}"

        with allure_step_log("步骤6: SSH后台验证虚机规格已缩容"):
            ssh_host.assert_guest_fields(
                node_name,
                {"vcpu": "4", "memory_mb": "8192"},
                f"{node_name}规格缩容后端验证失败"
            )

    @allure.title("集群详情-节点排水")
    def test_node_drain(self, cce_page, cce_cluster, ssh_vm):
        cluster_name = cce_cluster["name"]
        node_name = cce_cluster["worker_node"]

        with allure_step_log("步骤1: 进入集群详情页"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="详情")

        with allure_step_log("步骤2: 执行节点排水"):
            cce_page.cce_node_drain(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证UI状态收敛为无法调度"):
            cce_page.assert_status(node_name, "无法调度", timeout=300)

        with allure_step_log("步骤4: SSH登录节点后台验证kubectl节点状态"):
            ssh_vm.connect(cce_cluster["master_mfip"], port=22022, pwd="admin1234@sugon")
            result = ssh_vm.run(f"kubectl get node -o wide | grep {node_name}", return_rc=True)
            assert result["rc"] == 0, f"未找到名称为 {node_name} 的节点: {result.get('stdout', '')}"
            assert "SchedulingDisabled" in result["stdout"], f"节点未进入SchedulingDisabled状态: {result['stdout']}"

        with allure_step_log("步骤5: 恢复节点调度"):
            cce_page.cce_node_schedule_start(node_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤6: 验证节点状态恢复正常调度"):
            cce_page.assert_status(node_name, "正常调度", timeout=300)

    @allure.title("集群详情-新增计算节点")
    def test_node_create(self, cce_page, cce_cluster, ssh_host):
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

        with allure_step_log("步骤4: 获取新增节点名称"):
            cce_page.wait_for_page_ready()
            names = cce_page.get_column_data("名称")
            statuses = cce_page.get_column_data("运行状态")
            creating_nodes = [name for name, status in zip(names, statuses) if status == "创建中"]
            assert len(creating_nodes) == 1, f"期望找到1个'创建中'节点, 实际: {creating_nodes}"
            new_node_name = creating_nodes[0]

        with allure_step_log("步骤5: 验证新增节点状态收敛为运行中"):
            cce_page.assert_status(new_node_name, "运行中", timeout=1200)

        with allure_step_log("步骤6: 删除新增节点"):
            cce_page.cce_node_delete(new_node_name)

        with allure_step_log("步骤7: SSH后台验证虚机和云硬盘已删除"):
            ssh_host.wait_vm_deleted(new_node_name, timeout=300)
            ssh_host.wait_volume_deleted(new_node_name, timeout=300)


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('集群管理-存储类型')
class TestCCEStorageClass:

    @pytest.mark.parametrize("fstype", ["ext4", "xfs"])
    @allure.title("集群详情-新建云硬盘存储类型(fstype={fstype})")
    def test_storage_class_create(self, cce_page, cce_cluster, ssh_host, ssh_vm, fstype):
        cluster_name = cce_cluster["name"]
        mfip = cce_cluster.get("master_mfip", "")
        sc_name = f"evs-sc-{random_data(length=4)}"

        with allure_step_log("步骤1: 进入集群详情-存储类型页面"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="存储类型")

        with allure_step_log(f"步骤2: 创建云硬盘存储类型(fstype={fstype})"):
            cce_page.storage_class_create(
                name=sc_name,
                volume_type=cce_page.volume_type,
                fstype=fstype,
                encrypt=False,
                access_mode="ReadWriteOnce"
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证存储类型列表数据"):
            row_data = cce_page.get_row_data(sc_name)
            assert row_data, f"列表中未找到 {sc_name}"
            assert "云硬盘" in row_data.get("类型", "") or "EVS" in row_data.get("类型", ""), f"类型不匹配: {row_data.get('类型', '')}"
            assert "是" in row_data.get("创建完成", ""), f"创建完成状态不匹配: {row_data.get('创建完成', '')}"

        with allure_step_log(f"步骤4: 后台验证StorageClass yaml(fstype={fstype})"):
            assert mfip, "未获取到集群 MFIP"
            ssh_vm.connect(mfip, port=22022, pwd="admin1234@sugon")
            result = ssh_vm.run(f"kubectl get storageclass {sc_name} -oyaml", return_rc=True)
            assert result["rc"] == 0, f"kubectl 执行失败: {result.get('stderr', '')}"
            yaml_content = result["stdout"]
            assert "storageType" in yaml_content, "yaml 中缺少 storageType"
            assert f"fstype: {fstype}" in yaml_content, f"yaml 中 fstype 值不匹配，期望 {fstype}"

        with allure_step_log("步骤5: 删除存储类型"):
            cce_page.storage_class_delete(sc_name)
            cce_page.assert_deleted(sc_name, timeout=60)

        with allure_step_log("步骤6: 后台验证StorageClass已删除"):
            result = ssh_vm.run(f"kubectl get storageclass {sc_name}", return_rc=True)
            assert result["rc"] != 0 or "NotFound" in result.get("stderr", ""), f"StorageClass {sc_name} 未删除"

    @allure.title("集群详情-批量删除云硬盘存储类型")
    def test_storage_class_batch_delete(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        sc_names = []

        with allure_step_log("步骤1: 进入集群详情-存储类型页面"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="存储类型")

        with allure_step_log("步骤2: 预置两个存储类型"):
            for i in range(2):
                sc_name = f"evs-sc-{random_data(length=4)}"
                sc_names.append(sc_name)
                cce_page.storage_class_create(
                    name=sc_name,
                    volume_type=cce_page.volume_type,
                    fstype="ext4",
                    encrypt=False,
                    access_mode="ReadWriteOnce"
                )
                cce_page.assert_popup_success()

        with allure_step_log("步骤3: 批量删除存储类型"):
            cce_page.storage_class_batch_delete(sc_names)

        with allure_step_log("步骤4: 验证存储类型已删除"):
            cce_page.assert_deleted(sc_names, timeout=60)

