import re
import pytest
import allure
from sugon_web.utils.logger import allure_step_log

@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
@allure.story('弹性云服务器-业务场景覆盖验证')
class TestECSScenario:

    @allure.title("弹性云服务器-挂载/卸载云硬盘功能验证")
    def test_ecs_clone_vm(self, ecs_page, vm, volume, ssh_vm):
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
            sys_md5 = ssh_vm.create_file(filepath=f"/root/{vm_name}", size=1024)
            data_md5 = ssh_vm.create_file(filepath=f"{mount_point}/test_file.txt")

        with allure_step_log(f"步骤3: 克隆云服务器{clone_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_clone(vm_name, clone_name, 'Autotest', 'Autotest', {})

        with allure_step_log(f"步骤4: 验证克隆结果{clone_name}"):
            ecs_page.assert_popup_success(f"{vm_name}实例克隆成功")
            ecs_page.assert_status(clone_name)

            # 克隆后的虚机绑定mfip，验证md5值
            clone_ip = ecs_page.get_row_data(clone_name).get("IP地址").split(':')[1]
            mfip = ecs_page.bind_mfip(clone_ip.strip())
            ssh_vm.connect(mfip)

            # 克隆的虚机重新mount数据盘，验证md5值
            ssh_vm.run(f"mount /dev/{disk_name} {mount_point}")
            clone_sys_md5 = ssh_vm.run(f"md5sum /root/{vm_name}")
            clone_data_md5 = ssh_vm.run(f"md5sum {mount_point}/test_file.txt")
            assert sys_md5 in clone_sys_md5, f"克隆后系统盘数据MD5不一致，原始数据:{sys_md5},克隆后数据:{clone_sys_md5}"
            assert data_md5 in clone_data_md5, f"克隆后系统盘数据MD5不一致，原始数据:{data_md5},克隆后数据:{clone_data_md5}"

        with allure_step_log(f"步骤5: 从服务器{vm_name}卸载云硬盘{volume_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_unmount_from_server(volume_name, vm_name)
            ecs_page.assert_popup_success(f"从虚拟机{vm_name}分离云硬盘")

        with allure_step_log(f"步骤6: 清理测试数据{clone_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_remove(clone_name)
            ecs_page.ecs_delete(clone_name)
            ecs_page.assert_deleted(clone_name)