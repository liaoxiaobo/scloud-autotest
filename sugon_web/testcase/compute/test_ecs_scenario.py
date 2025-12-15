import re
import pytest
import allure
from sugon_web.utils.logger import allure_step_log

@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
@allure.story('弹性云服务器-业务场景覆盖验证')
class TestECSScenario:

    @allure.title("弹性云服务器-克隆已挂载云硬盘的虚机")
    def test_ecs_clone_vm(self, ecs_page, evs_page, vm, volume, ssh_vm):
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
            ecs_page.goto_service("云硬盘")
            ecs_page.goto_submenu("云硬盘")
            ecs_page.assert_status(volume["name"], status="正在使用", refresh=True)

            # 验证挂载后页面展示的挂载信息 和 虚机中的挂载信息是否一致
            disk_name = ecs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]
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
            clone_ip = ecs_page.get_row_data(clone_name).get("IP地址").split(':')[1]
            mfip = ecs_page.bind_mfip(clone_ip.strip())
            ssh_vm.connect(mfip)

            # 克隆的虚机重新mount数据盘，验证md5值
            ssh_vm.run(f"mount /dev/{disk_name} {mount_point}")
            new_md5s = ssh_vm.run(f"md5sum /root/{vm_name}")
            new_md5d = ssh_vm.run(f"md5sum {mount_point}/test_file.txt")
            assert md5s in new_md5s, f"克隆后系统盘数据MD5不一致，原始数据:{md5s},克隆后数据:{new_md5s}"
            assert md5d in new_md5d, f"克隆后系统盘数据MD5不一致，原始数据:{md5d},克隆后数据:{new_md5d}"

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
            evs_page.evs_remove(clone_disk)
            evs_page.assert_deleted(clone_name)

    @allure.title("弹性云服务器-快照创建的云服务器，恢复系统盘和数据盘成功")
    def test_ecs_snapshot_vm(self, ecs_page, vm, volume, ssh_vm):
        """快照创建的云服务器，恢复系统盘和数据盘成功"""

        ecs_page.goto_service('弹性云服务器')
        vm_name = vm.get("name")
        volume_name = volume.get("name")
        disk_name = ""
        snapshot_name = f"snapshot_{vm_name}"
        new_vm = f"{vm_name}-1"

        with allure_step_log(f"步骤1: 挂载云硬盘{volume_name}到服务器{vm_name}"):
            ecs_page.ecs_mount_to_server(volume_name, vm_name)

        with allure_step_log(f"步骤2: 验证挂载结果, 并向系统盘、云硬盘写入数据"):
            ecs_page.assert_popup_success(f"挂载云硬盘到虚拟机{vm_name}成功")
            assert ecs_page.get_row_data(vm_name).get("挂载云硬盘") == volume_name

            # 云硬盘页面验证 云硬盘状态=正在使用
            ecs_page.goto_service("云硬盘")
            ecs_page.goto_submenu("云硬盘")
            ecs_page.assert_status(volume["name"], status="正在使用", refresh=True)

            # 验证挂载后页面展示的挂载信息 和 虚机中的挂载信息是否一致
            disk_name = ecs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]
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
            ecs_page.assert_status(vm['name'], status="当前无任务")

        with allure_step_log(f"步骤4: 基于快照{snapshot_name}创建云服务器{new_vm}"):
            ecs_page.ecs_create(new_vm, image_source="快照", image_name=snapshot_name)
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(new_vm)
            newvm_disk = ecs_page.get_row_data(vm_name).get("挂载云硬盘")
            assert ecs_page.get_row_data(new_vm).get("镜像名称") == snapshot_name, "镜像名称快照不一致"
            assert newvm_disk != "--"

            # 云硬盘页面验证 云硬盘状态=正在使用
            ecs_page.goto_service("云硬盘")
            ecs_page.goto_submenu("云硬盘")
            ecs_page.assert_status(newvm_disk, status="正在使用", refresh=True)

            # 验证挂载后页面展示的挂载信息
            new_disk_name = ecs_page.get_row_data(newvm_disk).get("挂载信息").split("上的")[-1]

        with allure_step_log(f"步骤5: 验证{new_vm}系统盘和数据盘数据"):
            ecs_page.goto_service('弹性云服务器')
            new_vm_ip = ecs_page.get_row_data(new_vm).get("IP地址").split(':')[1].strip()
            new_vm_mfip = ecs_page.bind_mfip(new_vm_ip)
            ssh_vm.connect(new_vm_mfip)

            # # 克隆的虚机重新mount数据盘，验证md5值
            ssh_vm.run(f"mount /dev/{new_disk_name} {mount_point}")
            new_md5s = ssh_vm.run(f"md5sum /root/{vm_name}")
            new_md5d = ssh_vm.run(f"md5sum {mount_point}/test_file.txt")
            assert md5s in new_md5s, f"克隆后系统盘数据MD5不一致，原始数据:{md5s},克隆后数据:{new_md5s}"
            assert md5d in new_md5d, f"克隆后系统盘数据MD5不一致，原始数据:{md5d},克隆后数据:{new_md5d}"

        with allure_step_log(f"步骤6: 从服务器{vm_name}卸载云硬盘{volume_name}"):
            ecs_page.goto_service('弹性云服务器')
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