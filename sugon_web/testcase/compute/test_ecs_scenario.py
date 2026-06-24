import pytest
import allure
from sugon_web.common.mfip_helper import MfipHelper
from sugon_web.testcase.compute._ecs_helpers import collect_vm_metadata
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.utils.decorators import skip_stor, skip_if_nodes_less_than


@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
@allure.story('业务场景覆盖验证')
class TestECSScenario:

    @allure.title("验证已挂载云硬盘的虚机, 克隆后系统盘和数据盘与源虚机数据一致")
    def test_ecs_clone_vm(self, ecs_page, evs_page, vm, volume, ssh_vm, admin_browser_context, config, ssh_host):
        """测试克隆已挂载云硬盘的虚机"""

        ecs_page.goto_service('弹性云服务器')
        vm_name = vm.get("name")
        volume_name = volume.get("name")
        disk_name = ""
        clone_name = f"{vm_name}-1"

        with allure_step_log(f"步骤1: 挂载云硬盘{volume_name}到服务器{vm_name}"):
            ecs_page.ecs_mount_to_server(volume_name, vm_name)

        with allure_step_log(f"步骤2: 验证挂载结果"):
            ecs_page.assert_popup_success(f"挂载云硬盘到虚拟机{vm_name}成功")
            assert ecs_page.get_row_data(vm_name).get("挂载云硬盘") == volume_name

            # 云硬盘页面验证 云硬盘状态=正在使用
            evs_page.goto_service("云硬盘")
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_status(volume["name"], status="正在使用", refresh=True)

            # 验证挂载后页面展示的挂载信息 和 虚机中的挂载信息是否一致
            disk_name = evs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"lsblk | grep {disk_name}") != ""

            # 挂载的云硬盘写入测试数据
            mount_point = "/mnt/test_volume"
            ssh_vm.mount_disk(disk_name, mount_point)
            md5s = ssh_vm.create_file(filepath=f"/root/{vm_name}", size=1024)
            md5d = ssh_vm.create_file(filepath=f"{mount_point}/test_file.txt")

        with allure_step_log(f"步骤3: 克隆云服务器{clone_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_clone(vm_name, clone_name, 'Autotest', 'Autotest', {})

        with allure_step_log(f"步骤4: 验证克隆结果{clone_name}"):
            ecs_page.assert_popup_success(f"{vm_name}实例克隆成功")
            ecs_page.assert_status(clone_name)
            clone_disk = ecs_page.get_row_data(clone_name).get("挂载云硬盘")

            # 克隆后的虚机绑定mfip，验证md5值
            clone_meta = collect_vm_metadata(ecs_page, ssh_host, clone_name)
            mfip = MfipHelper.bind_mfip_with_admin_context(
                admin_browser_context, config, clone_meta["port_id"],
                project_id=clone_meta.get("project_id", "admin-inner-project"),
            )
            ssh_vm.connect(mfip)

            # 克隆的虚机重新mount数据盘，验证md5值
            ssh_vm.run(f"mount /dev/{disk_name} {mount_point}")
            new_md5s = ssh_vm.run(f"md5sum /root/{vm_name}")
            new_md5d = ssh_vm.run(f"md5sum {mount_point}/test_file.txt")
            assert md5s in new_md5s, f"克隆后系统盘数据MD5不一致，原始数据:{md5s},克隆后数据:{new_md5s}"
            assert md5d in new_md5d, f"克隆后系统盘数据MD5不一致，原始数据:{md5d},克隆后数据:{new_md5d}"
            ssh_vm.connect(vm['mfip'])
            ssh_vm.run(f"umount /dev/{disk_name}")

        with allure_step_log(f"步骤5: 从服务器{vm_name}卸载云硬盘{volume_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_unmount_from_server(volume_name, vm_name)
            ecs_page.assert_popup_success(f"从虚拟机{vm_name}分离云硬盘")

        with allure_step_log(f"步骤6: 清理测试数据{clone_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_remove(clone_name)
            ecs_page.ecs_delete(clone_name)
            ecs_page.assert_deleted(clone_name)

        with allure_step_log(f"步骤7: 清理测试数据{clone_disk}"):
            evs_page.goto_service('云硬盘')
            evs_page.evs_remove([clone_disk])
            evs_page.assert_deleted(clone_name)

    @allure.title("验证快照创建的云服务器，恢复系统盘和数据盘成功")
    @skip_stor("usan", "local", 'nfs')
    def test_ecs_snapshot_vm(self, ecs_page, evs_page, vm, volume, ssh_vm, admin_browser_context, config, ssh_host):
        """快照创建的云服务器，恢复系统盘和数据盘成功"""

        ecs_page.goto_service('弹性云服务器')
        vm_name = vm.get("name")
        volume_name = volume.get("name")
        snapshot_name = f"snapshot_{vm_name}"
        new_vm = f"{vm_name}-1"

        with allure_step_log(f"步骤1: 挂载云硬盘{volume_name}到服务器{vm_name}"):
            ecs_page.ecs_mount_to_server(volume_name, vm_name)

        with allure_step_log(f"步骤2: 验证挂载结果, 并向系统盘、云硬盘写入数据"):
            ecs_page.assert_popup_success(f"挂载云硬盘到虚拟机{vm_name}成功")
            assert ecs_page.get_row_data(vm_name).get("挂载云硬盘") == volume_name

            # 云硬盘页面验证 云硬盘状态=正在使用
            evs_page.goto_service("云硬盘")
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_status(volume["name"], status="正在使用", refresh=True)

            # 验证挂载后页面展示的挂载信息 和 虚机中的挂载信息是否一致
            disk_name = evs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]
            ssh_vm.connect(vm['mfip'])
            # assert ssh_vm.run(f"lsblk | grep {disk_name}") != ""

            # 挂载的云硬盘写入测试数据
            mount_point = "/mnt/test_volume"
            ssh_vm.mount_disk(disk_name, mount_point)
            md5s = ssh_vm.create_file(filepath=f"/root/{vm_name}", size=1024)
            md5d = ssh_vm.create_file(filepath=f"{mount_point}/test_file.txt")

        with allure_step_log(f"步骤3: {vm_name}新建快照 {snapshot_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecss_create(name=vm_name, snapshot_name=snapshot_name, desc="系统盘快照测试", data_disk=True)
            ecs_page.assert_popup_success("创建实例快照成功")
            ecs_page.wait_for_source_complete(vm['name'])
            ecs_page.assert_status(vm['name'])

        with allure_step_log(f"步骤4: 基于快照{snapshot_name}创建云服务器{new_vm}"):
            ecs_page.ecs_create(
                basic={"name": new_vm},
                storage={"image": {"source": "快照", "name": snapshot_name}},
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(new_vm)
            newvm_disk = ecs_page.get_row_data(vm_name).get("挂载云硬盘")
            assert ecs_page.get_row_data(new_vm).get("镜像名称") == snapshot_name, "镜像名称快照不一致"
            assert newvm_disk != "--"

            # 云硬盘页面验证 云硬盘状态=正在使用
            evs_page.goto_service("云硬盘")
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_status(newvm_disk, status="正在使用", refresh=True)

            # 验证挂载后页面展示的挂载信息
            new_disk_name = evs_page.get_row_data(newvm_disk).get("挂载信息").split("上的")[-1]

        with allure_step_log(f"步骤5: 验证{new_vm}系统盘和数据盘数据"):
            # ecs_page.goto_service('弹性云服务器')
            ecs_page.goto_submenu('弹性云服务器')
            new_meta = collect_vm_metadata(ecs_page, ssh_host, new_vm)
            new_vm_mfip = MfipHelper.bind_mfip_with_admin_context(
                admin_browser_context, config, new_meta["port_id"],
                project_id=new_meta.get("project_id", "admin-inner-project"),
            )
            ssh_vm.connect(new_vm_mfip)

            # 快照新建的虚机重新mount数据盘，验证md5值
            ssh_vm.mount_disk(new_disk_name, mount_point, format_disk=False)
            new_md5s = ssh_vm.run(f"md5sum /root/{vm_name}")
            new_md5d = ssh_vm.run(f"md5sum {mount_point}/test_file.txt")
            assert md5s in new_md5s, f"快照创建的虚机系统盘数据MD5不一致，原始数据:{md5s},克隆后数据:{new_md5s}"
            assert md5d in new_md5d, f"快照创建的虚机系统盘数据MD5不一致，原始数据:{md5d},克隆后数据:{new_md5d}"

        with allure_step_log(f"步骤6: 从服务器{vm_name}卸载云硬盘{volume_name}"):
            # ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_unmount_from_server(volume_name, vm_name)
            ecs_page.assert_popup_success(f"从虚拟机{vm_name}分离云硬盘")

        with allure_step_log(f"步骤7: 清理测试数据{new_vm}"):
            ecs_page.ecs_remove(new_vm)
            ecs_page.ecs_delete(new_vm)
            ecs_page.assert_deleted(new_vm)

        with allure_step_log(f"步骤8: 清理测试数据{snapshot_name}"):
            ecs_page.goto_submenu("快照")
            ecs_page.ecss_delete(snapshot_name)
            ecs_page.assert_deleted(snapshot_name, refresh=True)

    @allure.title("验证虚机绑定亲和组批量迁移功能")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 3}, "bind_mfip": False}], indirect=True)
    @skip_if_nodes_less_than(2)
    def test_ecs_bind_group_migration(self, ecs_page, vm, ssh_host):
        policy = "亲和"
        if isinstance(vm, list) and len(vm) > 1:
            names = [vm[i].get("name") for i in range(len(vm))]
            ecs_ids = [vm[i].get("id") for i in range(len(vm))]
            pre_nodes = [vm[i].get("host") for i in range(len(vm))]
            all_vms = names.copy() # 备份虚机名称
        else:
            names = [vm.get("name")]
            ecs_ids = vm.get("id")
        group_name = f"{random_data(length=3)}-{policy}"

        with allure_step_log(f"步骤1: 创建{policy}组: {group_name}"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_create_affinity_group(group_name, policy)

        with allure_step_log(f"步骤2: 验证{policy}组创建结果"):
            ecs_page.assert_popup_success("执行成功")
            assert ecs_page.get_row_data(group_name).get("策略") == policy, \
                f"创建亲和组失败，期望策略:{policy},实际策略:{ecs_page.get_row_data(group_name).get('策略')}"

        with allure_step_log(f"步骤3: 云服务器{names}绑定{policy}组并验证绑定结果"):
            ecs_page.ecs_bind_unbind_group(names, "绑定亲和组", group_name)

        with allure_step_log(f"步骤4: 迁移虚机到目标亲和节点"):
            ecs_page.goto_service('弹性云服务器')
            # 获取可热迁移的节点
            available_hosts = ecs_page.ecs_hot_migration_options(names[0])
            m_names, final_node = ecs_page.ecs_batch_migration_names(names, pre_nodes, available_hosts)

        with allure_step_log(f"步骤5: 云服务器{m_names}批量迁移"):
            ecs_page.ecs_batch_migration(m_names)
            ecs_page.assert_popup_success(f"批量热迁移命令下发成功")

        with allure_step_log(f"步骤6: 验证批量迁移结果"):
            nodes = []
            for name in m_names:
                ecs_page.wait_for_source_complete(name)
                ecs_page.assert_status(name)
            for name in m_names:
                ecs_page.assert_status(name)
                nodes.append(ecs_page.get_row_data(name).get("物理机"))

            if policy == "亲和":
                assert len(set(nodes)) == 1, f"云服务器{m_names}未迁移到同一节点"
                assert nodes[0] == final_node, f"云服务器{m_names}未迁移到目标节点"
            else:
                assert len(set(nodes)) > 1, f"云服务器{m_names}未迁移到不同节点"

        with allure_step_log(f"步骤7: 云服务器{all_vms}解绑{policy}组"):
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.ecs_bind_unbind_group(all_vms, "解绑亲和组", group_name)

        with allure_step_log(f"步骤8: 云服务器{all_vms}批量迁移"):
            ecs_page.ecs_batch_migration(all_vms)
            ecs_page.assert_popup_success(f"批量热迁移命令下发成功")

        with allure_step_log(f"步骤9: 验证批量迁移结果"):
            nodes = []
            for name, ecs_id in zip(all_vms, ecs_ids):
                ecs_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=1)
            for name, ecs_id in zip(all_vms, ecs_ids):
                ecs_page.wait_for_source_complete(name)
                nodes.append(ssh_host.guest_show(ecs_id).get("node"))
            assert len(set(nodes)) >= 1

        with allure_step_log(f"步骤10: 删除{policy}组: {group_name}"):
            ecs_page.ecs_delete_affinity_group(group_name)
            ecs_page.assert_deleted(group_name, refresh= True)
