import re
import pytest
import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, skip_stor

@allure.epic('存储服务')
@allure.feature('云硬盘')
@allure.story('云硬盘-业务场景覆盖验证')
class TestEVSScenario:

    @allure.title("云硬盘快照-数据一致性验证")
    def test_volume_snapshot_data_consistency(self, evs_page, vm, volume, ssh_vm, ssh_host):

        with allure_step_log("步骤1: 虚机内挂载云硬盘A并写入测试文件"):
            # 挂载云硬盘A到虚机
            evs_page.evs_mount(volume["name"], vm["name"])
            evs_page.assert_popup_success()
            evs_page.assert_status(volume["name"], status="正在使用")

            # 获取云硬盘A在虚机中的设备名
            disk_name = evs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]

            # 连接虚机并操作云硬盘
            ssh_vm.connect(vm['mfip'])

            # 格式化云硬盘并挂载
            mount_point = "/mnt/test_volume_a"
            ssh_vm.mount_disk(disk_name, mount_point)

            # 创建测试文件并计算MD5值
            md5_value_a = ssh_vm.create_file(f"{mount_point}/test_file.txt")

        with allure_step_log("步骤2: 创建云硬盘A的快照并基于快照创建云硬盘B"):

            # 创建云硬盘A的快照
            snapshot_name = "snapshot_" + random_data()
            evs_page.evss_create(volume["name"], snapshot_name, "用于数据一致性验证的快照")
            evs_page.assert_popup_success("创建快照成功")
            evs_page.goto_submenu("快照")
            evs_page.assert_status(snapshot_name, status="可用")

            # 基于快照创建云硬盘B
            volume_b_name = "volume_b_" + random_data()
            evs_page.evs_create_from_snapshot(
                snapshot_name=snapshot_name,
                volume_name=volume_b_name,
                desc="基于快照创建的云硬盘B"
            )
            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_status(volume_b_name, status="可用")

        with allure_step_log("步骤3: 挂载云硬盘B到虚机"):
            # 挂载云硬盘B到虚机
            evs_page.evs_mount(volume_b_name, vm["name"])
            evs_page.assert_popup_success()
            evs_page.assert_status(volume_b_name, status="正在使用")

            # 获取云硬盘B在虚机中的设备名
            disk_name_b = evs_page.get_row_data(volume_b_name).get("挂载信息").split("上的")[-1]

            # 连接虚机并操作云硬盘B
            ssh_vm.connect(vm['mfip'])

            # 挂载云硬盘B
            mount_point_b = "/mnt/test_volume_b"
            ssh_vm.mount_disk(disk_name_b, mount_point_b, format_disk=False)

        with allure_step_log("步骤4: MD5验证云硬盘B存在该测试文件，两块云硬盘的数据一致"):
            # 验证测试文件存在
            assert "test_file.txt" in ssh_vm.run(f"ls -la {mount_point_b}"), "测试文件不存在于云硬盘B中"
            # 验证两个MD5值相同
            assert md5_value_a == ssh_vm.run(f"md5sum {mount_point_b}/test_file.txt | awk '{{print $1}}'"), f"云硬盘A和B的测试文件MD5值不一致"

        with allure_step_log("步骤5：清理测试数据"):
            # 卸载云硬盘B
            ssh_vm.run(f"umount /dev/{disk_name_b}")
            evs_page.evs_unmount(volume_b_name, vm["name"])
            evs_page.assert_popup_success()

            # 删除云硬盘B
            evs_page.evs_remove(volume_b_name)
            evs_page.evs_delete(volume_b_name)
            evs_page.assert_deleted(volume_b_name)
            assert ssh_host.run(f"cinder list| grep {volume_b_name}") == ""

            # 删除快照
            evs_page.goto_submenu("快照")
            evs_page.evss_delete(snapshot_name)
            evs_page.assert_deleted(snapshot_name)

            # 卸载云硬盘A
            ssh_vm.run(f"umount /dev/{disk_name}")
            evs_page.evs_unmount(volume["name"], vm["name"])
            evs_page.assert_popup_success()

    @allure.title("云硬盘克隆-数据一致性验证")
    def test_volume_clone_data_consistency(self, evs_page, vm, volume, ssh_vm, ssh_host):

        with allure_step_log("步骤1: 虚机内挂载云硬盘A并写入测试文件"):
            # 挂载云硬盘A到虚机
            evs_page.evs_mount(volume["name"], vm["name"])
            evs_page.assert_popup_success()
            evs_page.assert_status(volume["name"], status="正在使用")

            # 获取云硬盘A在虚机中的设备名
            disk_name = evs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]

            # 连接虚机并操作云硬盘
            ssh_vm.connect(vm['mfip'])

            # 格式化云硬盘并挂载
            mount_point = "/mnt/test_volume_a"
            ssh_vm.mount_disk(disk_name, mount_point)

            # 创建测试文件并计算MD5值
            md5_value_a = ssh_vm.create_file(f"{mount_point}/test_file.txt")

        with allure_step_log("步骤2: 基于云硬盘A克隆创建一块云硬盘B"):
            # 克隆云硬盘A创建云硬盘B
            volume_b_name = "clone_" + volume["name"]
            evs_page.evs_clone(volume["name"], volume_b_name)
            evs_page.assert_popup_success("克隆云硬盘成功")
            evs_page.assert_status(volume_b_name, status="可用")

        with allure_step_log("步骤3: 挂载云硬盘B到虚机"):
            # 挂载云硬盘B到虚机
            evs_page.evs_mount(volume_b_name, vm["name"])
            evs_page.assert_popup_success()
            evs_page.assert_status(volume_b_name, status="正在使用")

            # 获取云硬盘B在虚机中的设备名
            disk_name_b = evs_page.get_row_data(volume_b_name).get("挂载信息").split("上的")[-1]

            # 连接虚机并操作云硬盘B
            ssh_vm.connect(vm['mfip'])

            # 挂载云硬盘B
            mount_point_b = "/mnt/test_volume_b"
            ssh_vm.mount_disk(disk_name_b, mount_point_b, format_disk=False)

        with allure_step_log("步骤4: MD5验证云硬盘B存在该测试文件，两块云硬盘的数据一致"):
            # 验证测试文件存在
            assert "test_file.txt" in ssh_vm.run(f"ls -la {mount_point_b}"), "测试文件不存在于云硬盘B中"
            # 验证两个MD5值相同
            assert md5_value_a == ssh_vm.run(f"md5sum {mount_point_b}/test_file.txt | awk '{{print $1}}'"), f"云硬盘A和B的测试文件MD5值不一致"

        with allure_step_log("步骤5：清理测试数据"):
            # 卸载云硬盘B
            ssh_vm.run(f"umount /dev/{disk_name_b}")
            evs_page.evs_unmount(volume_b_name, vm["name"])
            evs_page.assert_popup_success()

            # 删除云硬盘B
            evs_page.evs_remove(volume_b_name)
            evs_page.evs_delete(volume_b_name)
            evs_page.assert_deleted(volume_b_name)
            assert ssh_host.run(f"cinder list| grep {volume_b_name}") == ""

            # 卸载云硬盘A
            ssh_vm.run(f"umount /dev/{disk_name}")
            evs_page.evs_unmount(volume["name"], vm["name"])
            evs_page.assert_popup_success()

    @allure.title("共享云硬盘-多实例挂载数据一致性验证")
    @pytest.mark.parametrize("vm", [{"count": 2}], indirect=True)
    @pytest.mark.parametrize("volume", [{"shared": True, "size": 10}], indirect=True)
    def test_shared_volume_data_consistency(self, evs_page, vm, volume, ssh_vm, ssh_host):

        # 获取两台云服务器信息
        vm_a = vm[0]
        vm_b = vm[1]

        with allure_step_log("步骤1: 将共享云硬盘挂载到云服务器A并写入测试文件"):
            # 挂载共享云硬盘到云服务器A
            evs_page.evs_mount(volume["name"], vm_a["name"])
            evs_page.assert_popup_success()
            evs_page.assert_status(volume["name"], status="正在使用")

            # 获取云硬盘在云服务器A中的设备名
            disk_name = evs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]

            # 连接到云服务器A并操作云硬盘
            ssh_vm.connect(vm_a['mfip'])

            # 格式化云硬盘并挂载
            mount_point = "/mnt/shared_volume"
            ssh_vm.mount_disk(disk_name, mount_point)

            # 创建测试文件并计算MD5值
            md5_value_a = ssh_vm.create_file(f"{mount_point}/test_file_a.txt")

        with allure_step_log("步骤2: 将共享云硬盘挂载到云服务器B"):
            # 挂载共享云硬盘到云服务器B
            evs_page.evs_mount(volume["name"], vm_b["name"])
            evs_page.assert_popup_success()

            # 获取云硬盘在云服务器B中的设备名
            mount_info = evs_page.get_row_data(volume["name"]).get("挂载信息")
            pattern = f'{re.escape(vm_b["name"])}上的([^\\s]+)'
            match = re.search(pattern, mount_info)
            if match:
                disk_name_b = match.group(1)
            else:
                raise Exception(f"未找到云服务器B上的设备名: {mount_info}")

            # 连接到云服务器B
            ssh_vm.connect(vm_b['mfip'])

            # 挂载云硬盘（不需要格式化，因为是共享盘）
            mount_point_b = "/mnt/shared_volume_b"
            ssh_vm.run(f"mkdir -p {mount_point_b}")
            ssh_vm.run(f"mount /dev/{disk_name_b} {mount_point_b}")

            # 验证步骤1中创建的测试文件存在
            assert "test_file_a.txt" in ssh_vm.run(f"ls -la {mount_point_b}"), "测试文件不存在于云服务器B的共享云硬盘中"

            # 验证两个MD5值相同
            md5_value_b = ssh_vm.run(f"md5sum {mount_point_b}/test_file_a.txt | awk '{{print $1}}'")
            assert md5_value_a == md5_value_b, f"共享云硬盘中测试文件的MD5值在两台服务器上不一致: {md5_value_a} vs {md5_value_b}"

        # with allure_step_log("步骤3: 在云服务器B上创建新文件并验证云服务器A也能访问"):
        #     # 在云服务器B上创建新文件
        #     md5_value_b_new = ssh_vm.create_file(f"{mount_point_b}/test_file_b.txt")
        #
        #     # 连接到云服务器A并验证新文件存在
        #     ssh_vm.connect(vm_a['mfip'])
        #
        #     # 验证新文件存在且MD5值一致
        #     assert "test_file_b.txt" in ssh_vm.run(f"ls -la {mount_point}"), "云服务器B创建的测试文件不存在于云服务器A的共享云硬盘中"
        #     md5_value_a_new = ssh_vm.run(f"md5sum {mount_point}/test_file_b.txt | awk '{{print $1}}'")
        #     assert md5_value_b_new == md5_value_a_new, f"新创建的测试文件的MD5值在两台服务器上不一致: {md5_value_b_new} vs {md5_value_a_new}"

        with allure_step_log("步骤4: 清理测试数据"):
            # 卸载云服务器A上的共享云硬盘
            ssh_vm.connect(vm_a['mfip'])
            ssh_vm.run(f"umount {mount_point}")
            evs_page.evs_unmount(volume["name"], vm_a["name"])
            evs_page.assert_popup_success()

            # 卸载云服务器B上的共享云硬盘
            ssh_vm.connect(vm_b['mfip'])
            ssh_vm.run(f"umount {mount_point_b}")
            evs_page.evs_unmount(volume["name"], vm_b["name"])
            evs_page.assert_popup_success()

            # 验证云硬盘状态为可用
            evs_page.assert_status(volume["name"], status="可用")