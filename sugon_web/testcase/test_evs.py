import pytest
import allure
from sugon_web.utils.util import random_data, load_data


@allure.epic('存储服务')
@allure.feature('云硬盘')
@allure.story('基本功能验证')
class TestEVS:

    @allure.title("云硬盘-创建&删除")
    @pytest.mark.parametrize("params", load_data('test_volume_create'))
    def test_volume_create(self, evs_page, params, ssh_host):

        # 如果是共享盘测试，检查当前存储类型是否支持
        if params.get('shared', False):
            supported_storages = ['xstor', 'xbd', 'ceph', 'ustor', 'zbs']
            current_storage = evs_page.env['stor']

            if current_storage not in supported_storages:
                pytest.skip(f"当前存储类型 {current_storage} 不支持创建共享云硬盘，跳过测试")

        name = random_data()
        with allure.step("步骤1: 创建单个云硬盘"):
            evs_page.evs_create(
                name,
                empty=params['empty'],
                size=params["size"],
                desc=params["desc"],
                shared=params.get('shared', False)  # 默认为False，如果数据中没有shared字段
            )

            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.assert_status(name, status="可用")

            # 验证云硬盘属性
            data = evs_page.get_row_data(name)
            assert data['可启动'] == ('是' if not params['empty'] else '否')
            assert data['容量'] == f"{params['size']}GiB"
            assert data['共享盘'] == ('是' if params.get('shared', False) else '否')
            assert data['加密'] == "未加密"

        with allure.step("步骤2: 删除单个云硬盘"):
            evs_page.evs_remove(name)
            evs_page.evs_delete(name)
            evs_page.assert_deleted(name)
            assert ssh_host.run(f"cinder list| grep {name}") == ""

    @allure.title("云硬盘-批量创建&批量删除")
    def test_volume_batch_delete(self, evs_page, ssh_host):

        volume_names = []
        with allure.step("步骤1: 批量创建云硬盘"):
            base_name = random_data()
            evs_page.evs_create(
                name=base_name,
                count=3,
                size=10,
                desc="批量删除测试云硬盘"
            )
            evs_page.assert_popup_success("创建云硬盘成功")

            # 生成批量创建的云硬盘名称列表
            for i in range(3):
                volume_names.append(f"{base_name}-{i}")

            # 验证所有云硬盘创建成功
            for name in volume_names:
                evs_page.assert_status(name, status="可用")

        with allure.step("步骤2: 批量回收云硬盘"):
            evs_page.evs_remove(volume_names)
            # evs_page.assert_popup_success()

        with allure.step("步骤3: 批量删除回收站中的云硬盘"):
            evs_page.evs_delete(volume_names)
            # evs_page.assert_popup_success()

        # 验证云硬盘已彻底删除
        for name in volume_names:
            evs_page.assert_deleted(name)
        assert ssh_host.run(f"cinder list| grep {base_name}") == ""

    @allure.title("云硬盘-列表页搜索")
    def test_volume_search(self, evs_page, volume):

        with allure.step("步骤1: 输入名称进行搜索"):
            evs_page.goto_submenu("云硬盘")  # TODO: 连跑时会处于回收站页，加跳转解决
            keyword = volume['name'][:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, exact_match=False)

        with allure.step("步骤2: 重置搜索条件"):
            evs_page.btn_reset.click()
            evs_page.wait_for_page_ready()
            assert evs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("云硬盘-修改")
    @pytest.mark.parametrize("params", load_data('test_modify'))
    def test_volume_edit(self, evs_page, volume, params):

        new_name = volume["name"] + params["name_suffix"]
        new_desc = params["new_desc"]
        
        with allure.step("步骤1: 修改云硬盘的名称和描述"):
            evs_page.evs_edit(volume["name"], new_name, new_desc)
            evs_page.assert_popup_success("执行成功")
            evs_page.assert_list_contain(new_name)

    @allure.title("云硬盘-克隆")
    def test_volume_clone(self, evs_page, volume, ssh_host):

        clone_name = "clone_" + volume["name"]
        
        with allure.step("步骤1: 克隆云硬盘"):
            evs_page.evs_clone(volume["name"], clone_name)
            evs_page.assert_popup_success("克隆云硬盘成功")
            evs_page.assert_status(clone_name, status="可用")

        with allure.step("步骤2: 清理克隆的云硬盘"):
            evs_page.evs_remove(clone_name)
            evs_page.evs_delete(clone_name)
            evs_page.assert_deleted(clone_name)
            assert ssh_host.run(f"cinder list| grep {clone_name}") == ""

    @allure.title("云硬盘-扩容")
    @pytest.mark.parametrize("params", load_data('test_volume_expand'))
    def test_volume_expand(self, evs_page, volume, params, ssh_host):

        name = volume["name"]
        new_size = params["new_size"]
        
        with allure.step("步骤1: 扩容云硬盘"):
            evs_page.evs_expand(name, new_size)
            evs_page.assert_popup_success("执行成功")
            evs_page.assert_status(name, status="可用")
            assert ssh_host.run(f"cinder list | grep {name} |awk {{'print $8'}}") == str(new_size)

    @allure.title("云硬盘-启用QoS")
    def test_volume_enable_qos(self, evs_page, volume):

        with allure.step("步骤1: 启用云硬盘QoS限制"):
            evs_page.evs_enable_qos(
                volume_name=volume["name"],
                read_speed=100,
                write_speed=100,
                read_iops=200,
                write_iops=200
            )
            evs_page.assert_popup_success("设置单卷QoS成功")

    @allure.title("云硬盘-关闭QoS")
    def test_volume_disable_qos(self, evs_page, volume):

        with allure.step("步骤1: 关闭云硬盘QoS限制"):
            evs_page.evs_disable_qos(volume_name=volume["name"])
            evs_page.assert_popup_success("设置单卷QoS成功")

    @allure.title("云硬盘-挂载&卸载")
    def test_volume_bind_vm(self, evs_page, vm, volume, ssh_vm):

        evs_page.goto_service('云硬盘')    # TODO: 引入vm fixture导致evs_page定位不到云硬盘菜单，加跳转解决

        with allure.step("步骤1: 挂载云硬盘"):
            evs_page.evs_mount(volume["name"], vm["name"])
            evs_page.assert_popup_success()
            evs_page.assert_status(volume["name"], status="正在使用")
            disk_name = evs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"lsblk | grep {disk_name}") != ""

        with allure.step("步骤2: 卸载云硬盘"):
            evs_page.evs_unmount(volume["name"], vm["name"])
            evs_page.assert_popup_success()
            evs_page.assert_status(volume["name"], status="可用")
            assert evs_page.get_row_data(volume["name"]).get("挂载信息") == "--"
            assert ssh_vm.run(f"lsblk | grep {disk_name}") == ""

    @allure.title("云硬盘-转镜像")
    def test_volume_convert_to_image(self, ecs_page, evs_page, ssh_host):

        name=random_data()
        with allure.step("步骤1: 创建带镜像的云硬盘"):
            evs_page.evs_create(name, empty=False)
            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.assert_status(name, status="可用")

        with allure.step("步骤2: 将云硬盘转换为镜像"):
            image_name = "image_from_volume_" + name
            evs_page.evs_convert_to_image(
                volume_name=name,
                image_name=image_name
            )
            evs_page.assert_popup_success()
            evs_page.assert_status(name, status="上传中")
            evs_page.assert_status(name, status="可用", timeout=1200)

            # 切换到弹性云服务器服务的镜像服务页面
            evs_page.goto_service("弹性云服务器")
            evs_page.goto_submenu("镜像服务")
            evs_page.assert_list_contain(image_name)

        with allure.step("步骤3：清理测试数据"):
            # 删除创建的镜像
            ecs_page.ecs_image_delete(image_name)
            ecs_page.assert_deleted(image_name)
            # 删除创建的云硬盘
            evs_page.goto_service("云硬盘")
            evs_page.evs_remove(name)
            evs_page.evs_delete(name)
            evs_page.assert_deleted(name)
            assert ssh_host.run(f"cinder list| grep {name}") == ""

    @allure.title("云硬盘-重置状态")
    def test_volume_reset_status(self, evs_page, volume, ssh_host):

        with allure.step("步骤1: 构造删除中的云硬盘"):
            ssh_host.run(f'cinder reset-state --state deleting {volume["name"]}')
            evs_page.goto_submenu('云硬盘')
            evs_page.assert_status(volume["name"], status="删除中", refresh=True)

        with allure.step("步骤2: 重置云硬盘状态"):
            evs_page.evs_reset_status(volume["name"])
            evs_page.assert_popup_success("重置状态成功")
            evs_page.assert_status(volume["name"], status="错误")

        with allure.step("步骤3: 恢复云硬盘状态"):
            ssh_host.run(f'cinder reset-state --state available {volume["name"]}')
            evs_page.assert_status(volume["name"], status="可用", refresh=True)

    @allure.title("云硬盘-查看快照")
    def test_volume_view_snapshots(self, evs_page, volume, evss):

        with allure.step("步骤1: 查看快照"):
            evs_page.evs_view_snapshots(volume["name"])
            evs_page.assert_list_contain(evss["name"])
            snapshot_data = evs_page.get_row_data(evss["name"])
            assert snapshot_data["名称"] == evss["name"]
            assert snapshot_data["云硬盘名称"] == volume["name"]

@allure.epic('存储服务')
@allure.feature('云硬盘')
@allure.story('回收站功能验证')
class TestGarbage:

    @allure.title("回收站-移入&移出云硬盘")
    def test_volume_restore(self, evs_page, volume):

        with allure.step("步骤1: 云硬盘移入回收站"):
            evs_page.evs_remove(volume["name"])

        with allure.step("步骤2: 从回收站恢复云硬盘"):
            evs_page.evs_restore(volume["name"])
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_status(volume["name"], status="可用")

    @allure.title("回收站-列表页搜索")
    def test_garbage_search(self, evs_page, volume):

        with allure.step("步骤1: 云硬盘移入回收站"):
            evs_page.evs_remove(volume["name"])

        with allure.step("步骤2: 输入名称进行搜索"):
            evs_page.goto_submenu("回收站")
            keyword = volume['name'][:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, exact_match=False)

        with allure.step("步骤3: 重置搜索条件"):
            evs_page.btn_reset.click()
            evs_page.wait_for_page_ready()
            assert evs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure.step("步骤4: 从回收站恢复云硬盘"):
            evs_page.evs_restore(volume["name"])
            evs_page.assert_popup_success(f"云硬盘{volume['name']}移出回收站成功")

    @allure.title("回收站-安全删除")
    def test_volume_secure_delete(self, evs_page, ssh_host):

        name=random_data()
        with allure.step("步骤1: 创建云硬盘"):
            evs_page.evs_create(name)
            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.assert_status(name, status="可用")

        with allure.step("步骤2: 云硬盘移入回收站"):
            evs_page.evs_remove(name)

        with allure.step("步骤3: 安全删除云硬盘"):
            evs_page.evs_delete(name, secure=True)
            evs_page.assert_deleted(name)
            assert ssh_host.run(f"cinder list| grep {name}") == ""

@allure.epic('存储服务')
@allure.feature('云硬盘')
@allure.story('云硬盘快照功能验证')
class TestEVSS:

    @allure.title("云硬盘快照-创建&删除")
    @pytest.mark.parametrize("params", load_data('test_volume_add_snapshot'))
    def test_volume_add_snapshot(self, evs_page, volume, params):
        snapshot_name = params["snapshot_name_prefix"] + random_data()

        with allure.step("步骤1: 创建云硬盘快照"):
            evs_page.evss_create(volume["name"], snapshot_name, params["desc"])
            evs_page.assert_popup_success("创建快照成功")
            evs_page.goto_submenu("快照")
            evs_page.assert_status(snapshot_name, status="可用")
            snapshot_data = evs_page.get_row_data(snapshot_name)
            assert snapshot_data["描述"] == params["desc"]

        with allure.step("步骤3: 删除云硬盘快照"):
            evs_page.evss_delete(snapshot_name)
            evs_page.assert_deleted(snapshot_name)

    @allure.title("云硬盘快照-批量删除")
    def test_snapshot_batch_delete(self, evs_page, volume):

        snapshot_names = []
        with allure.step("步骤1: 创建多个云硬盘快照"):
            for i in range(3):
                name = random_data()
                snapshot_names.append(name)
                evs_page.evss_create(
                    volume_name=volume["name"],
                    snapshot_name=name,
                    desc=f"批量删除测试快照{i}"
                )
                evs_page.assert_popup_success("创建快照成功")
                evs_page.goto_submenu("快照")
                evs_page.assert_status(name, status="可用")

        with allure.step("步骤2: 批量删除快照"):
            evs_page.evss_delete(snapshot_names)
            # evs_page.assert_popup_success()
            for name in snapshot_names:
                evs_page.assert_deleted(name)

    @allure.title("云硬盘快照-列表页搜索")
    def test_evss_search(self, evs_page, evss):

        with allure.step("步骤1: 输入名称进行搜索"):
            keyword = evss['name'][:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, exact_match=False)

        with allure.step("步骤2: 重置搜索条件"):
            evs_page.btn_reset.click()
            evs_page.wait_for_page_ready()
            assert evs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("云硬盘快照-修改")
    @pytest.mark.parametrize("params", load_data('test_modify'))
    def test_volume_modify_snapshot(self, evs_page, evss, params):

        new_name = evss["name"] + params["name_suffix"]
        new_desc = params["new_desc"]

        with allure.step("步骤1: 修改云硬盘快照的名称和描述"):
            evs_page.evss_edit(evss["name"], new_name, new_desc)
            evs_page.assert_popup_success("更新快照成功")

            # 验证修改后的快照在列表中
            evs_page.assert_list_contain(new_name)

            # 获取修改后的快照数据并验证
            snapshot_data = evs_page.get_row_data(new_name)
            assert snapshot_data["描述"] == new_desc

    @allure.title("云硬盘快照-创建云硬盘")
    def test_create_volume_from_snapshot(self, evs_page, evss, ssh_host):

        with allure.step("步骤1: 从快照创建云硬盘"):
            name = "volume_from_snapshot_" + evss["volume_name"]
            evs_page.evs_create_from_snapshot(
                snapshot_name=evss["name"],
                volume_name=name,
                desc="从快照创建的云硬盘"
            )

            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_list_contain(name)
            evs_page.assert_status(name, status="可用")

        with allure.step("步骤2：清理测试数据"):
            evs_page.evs_remove(name)
            evs_page.evs_delete(name)
            evs_page.assert_deleted(name)
            assert ssh_host.run(f"cinder list| grep {name}") == ""

    @allure.title("快照策略-创建&删除")
    def test_evss_policy_create(self, evs_page):

        name = random_data()
        with allure.step("步骤1: 创建快照策略"):
            evs_page.evss_policy_create(
                name=name,
                hours=[0, 1, 2],
            )
            evs_page.assert_popup_success("添加策略成功")

        with allure.step("步骤2: 删除快照策略"):
            evs_page.evss_policy_delete(name)
            evs_page.assert_deleted(name)

    @allure.title("快照策略-批量删除")
    def test_evss_policy_batch_delete(self, evs_page):

        policy_names = []
        with allure.step("步骤1: 创建多个快照策略"):
            for i in range(3):
                name = random_data()
                policy_names.append(name)
                evs_page.evss_policy_create(
                    name=name,
                    hours=[0, 1, 2],
                    enabled=True,
                    cycle_days=1,
                    retention_type="按数量",
                    retention_value=5
                )
                evs_page.assert_popup_success("添加策略成功")

        with allure.step("步骤2: 批量删除快照策略"):
            evs_page.evss_policy_delete(policy_names)
            # evs_page.assert_popup_success()

        with allure.step("步骤3: 验证快照策略已删除"):
            for name in policy_names:
                evs_page.assert_deleted(name)

    @allure.title("快照策略-列表页搜索")
    def test_evss_policy_search(self, evs_page, evss_policy):

        with allure.step("步骤1: 输入名称进行搜索"):
            keyword = evss_policy[:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, column_name="名称/ID", exact_match=False)

        with allure.step("步骤2: 重置搜索条件"):
            evs_page.btn_reset.click()
            evs_page.wait_for_page_ready()
            assert evs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("快照策略-修改")
    def test_evss_policy_edit(self, evs_page, evss_policy):

        with allure.step("步骤1: 修改快照策略"):
            evs_page.evss_policy_edit(name=evss_policy, hours=[7,8,9])
            evs_page.assert_popup_success("修改策略成功")

    @allure.title("快照策略-云硬盘绑定&解绑快照策略")
    def test_volume_bind_evss_policy(self, evs_page, volume, evss_policy):

        with allure.step("步骤1: 绑定快照策略"):
            evs_page.evs_bind_snapshot_policy(
                volume_name=volume["name"],
                policy_name=evss_policy,
            )
            evs_page.assert_popup_success()

            # 验证快照任务已创建
            evs_page.goto_submenu("快照任务")
            evs_page.assert_list_contain(volume["name"], column_name="云硬盘名称")

        with allure.step("步骤2: 删除快照任务（解绑）"):
            evs_page.evss_task_delete(volume["name"])
            evs_page.assert_deleted(volume["name"])

    @allure.title("快照任务-批量删除")
    def test_snapshot_task_batch_delete(self, evs_page, evss_policy):

        volume_names = []
        with allure.step("步骤1: 批量创建云硬盘"):
            base_name = random_data()
            evs_page.evs_create(
                name=base_name,
                count=3,
                size=10,
                desc="批量删除测试云硬盘"
            )
            evs_page.assert_popup_success("创建云硬盘成功")

            for i in range(3):
                volume_names.append(f"{base_name}-{i}")

            for name in volume_names:
                evs_page.assert_status(name, status="可用")

        with allure.step("步骤2: 为云硬盘绑定快照策略"):
            for name in volume_names:
                evs_page.evs_bind_snapshot_policy(
                    volume_name=name,
                    policy_name=evss_policy,
                    enable_auto_snapshot=True
                )
                evs_page.assert_popup_success()

            evs_page.goto_submenu("快照任务")
            for name in volume_names:
                evs_page.assert_list_contain(name, column_name="云硬盘名称")

        with allure.step("步骤3: 批量删除快照任务"):
            evs_page.evss_task_delete(volume_names)
            # evs_page.assert_popup_success()

        with allure.step("步骤4: 验证快照任务已删除"):
            for name in volume_names:
                evs_page.assert_deleted(name)

        with allure.step("步骤5: 清理测试数据"):
            evs_page.evs_remove(volume_names)
            evs_page.evs_delete(volume_names)
            for name in volume_names:
                evs_page.assert_deleted(name)

    @allure.title("快照任务-禁用&开启自动快照")
    def test_volume_auto_snapshot(self, evs_page, volume, evss_policy):

        with allure.step("步骤1: 绑定快照策略"):
            evs_page.evs_bind_snapshot_policy(
                volume_name=volume["name"],
                policy_name=evss_policy,
            )
            evs_page.assert_popup_success("执行成功")

        with allure.step("步骤2: 开启自动快照"):
            evs_page.evss_task_set_auto_snapshot(volume["name"])
            evs_page.assert_popup_success("执行成功")

        with allure.step("步骤3: 禁用自动快照"):
            evs_page.evss_task_set_auto_snapshot(volume["name"], enable=False)
            evs_page.assert_popup_success("执行成功")

        with allure.step("步骤4: 删除快照任务（解绑）"):
            evs_page.evss_task_delete(volume["name"])
            evs_page.assert_deleted(volume["name"])

@allure.epic('存储服务')
@allure.feature('云硬盘')
@allure.story('业务特性场景验证')
class TestEVSScenario:

    @allure.title("云硬盘快照-数据一致性验证")
    def test_volume_snapshot_data_consistency(self, evs_page, vm, volume, ssh_vm, ssh_host):
        """测试云硬盘快照数据一致性

        测试场景：
        1. 虚机内挂载一块云硬盘A，并且往云硬盘分区写测试文件
        2. 基于该云硬盘创建快照，接着使用快照创建一块新的云硬盘B
        3. 虚机内继续挂载云硬盘B
        4. MD5验证云硬盘B存在该测试文件，两块云硬盘的数据一致
        """

        with allure.step("步骤1: 虚机内挂载云硬盘A并写入测试文件"):
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

        with allure.step("步骤2: 创建云硬盘A的快照并基于快照创建云硬盘B"):

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

        with allure.step("步骤3: 挂载云硬盘B到虚机"):
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

        with allure.step("步骤4: MD5验证云硬盘B存在该测试文件，两块云硬盘的数据一致"):
            # 验证测试文件存在
            assert "test_file.txt" in ssh_vm.run(f"ls -la {mount_point_b}"), "测试文件不存在于云硬盘B中"
            # 验证两个MD5值相同
            assert md5_value_a == ssh_vm.run(f"md5sum {mount_point_b}/test_file.txt | awk '{{print $1}}'"), f"云硬盘A和B的测试文件MD5值不一致"

        with allure.step("步骤5：清理测试数据"):
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

        with allure.step("步骤1: 虚机内挂载云硬盘A并写入测试文件"):
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

        with allure.step("步骤2: 基于云硬盘A克隆创建一块云硬盘B"):
            # 克隆云硬盘A创建云硬盘B
            volume_b_name = "clone_" + volume["name"]
            evs_page.evs_clone(volume["name"], volume_b_name)
            evs_page.assert_popup_success("克隆云硬盘成功")
            evs_page.assert_status(volume_b_name, status="可用")

        with allure.step("步骤3: 挂载云硬盘B到虚机"):
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

        with allure.step("步骤4: MD5验证云硬盘B存在该测试文件，两块云硬盘的数据一致"):
            # 验证测试文件存在
            assert "test_file.txt" in ssh_vm.run(f"ls -la {mount_point_b}"), "测试文件不存在于云硬盘B中"
            # 验证两个MD5值相同
            assert md5_value_a == ssh_vm.run(f"md5sum {mount_point_b}/test_file.txt | awk '{{print $1}}'"), f"云硬盘A和B的测试文件MD5值不一致"

        with allure.step("步骤5：清理测试数据"):
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
        """
        测试共享云硬盘数据一致性：
        1. 通过fixture预置两台云服务器和一块共享云盘
        2. 将该云硬盘挂载到一台云服务器A上，并对盘进行格式化挂载写入测试文件
        3. 将该云硬盘挂载到一台云服务器实例B上，进行挂载后可以看到步骤2的测试文件
        4. 云服务器B上写一个新文件，验证云服务器A上也能查看到该文件，md5值一致
        """

        # 获取两台云服务器信息
        vm_a = vm[0]
        vm_b = vm[1]

        with allure.step("步骤1: 将共享云硬盘挂载到云服务器A并写入测试文件"):
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

        with allure.step("步骤2: 将共享云硬盘挂载到云服务器B"):
            # 挂载共享云硬盘到云服务器B
            evs_page.evs_mount(volume["name"], vm_b["name"])
            evs_page.assert_popup_success()

            # 获取云硬盘在云服务器B中的设备名
            disk_name_b = evs_page.get_row_data(volume["name"]).get("挂载信息").split(f"{vm_b['name']}上的")[-1]

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

        # with allure.step("步骤3: 在云服务器B上创建新文件并验证云服务器A也能访问"):
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

        with allure.step("步骤4: 清理测试数据"):
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


@allure.epic('存储服务')
@allure.feature('云硬盘')
@allure.story('加密云硬盘功能验证')
class TestEncrypted:

    @allure.title("创建HCT加密类型的云硬盘")
    def test_create_hct_encrypted_volume(self, evs_page, kms_key:dict, ssh_host):

        # 检查当前存储类型是否支持加密功能
        supported_storages = ['usan', 'xstor']
        current_storage = evs_page.env['stor']

        if current_storage not in supported_storages:
            pytest.skip(f"当前存储类型 {current_storage} 不支持创建加密云硬盘，跳过测试")
        # 进入云硬盘页面
        evs_page.goto_service("云硬盘")

        # 生成随机云硬盘名称
        volume_name = f"encrypted-{random_data()}"

        with allure.step("步骤1: 创建加密云硬盘"):
            # 创建加密云硬盘
            evs_page.evs_create(
                name=volume_name,
                encrypted=True,
                encryption_key=kms_key["UUID"]
            )

            # 验证创建成功
            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.assert_status(volume_name, status="可用")

            # 验证云硬盘属性
            data = evs_page.get_row_data(volume_name)
            assert data['共享盘'] == '否'
            assert data['加密'] == "已加密"

        with allure.step("步骤2: 删除加密云硬盘"):
            # 删除云硬盘
            evs_page.evs_remove(volume_name)
            evs_page.evs_delete(volume_name)
            evs_page.assert_deleted(volume_name)
            assert ssh_host.run(f"cinder list| grep {volume_name}") == ""

    @allure.title("创建OPENSSL纯软加密类型的云硬盘")
    @pytest.mark.parametrize("kms_key", ["OPENSSL纯软"], indirect=True)
    def test_create_openssl_encrypted_volume(self, evs_page, kms_key:dict, ssh_host):

        # 检查当前存储类型是否支持加密功能
        supported_storages = ['usan', 'xstor']
        current_storage = evs_page.env['stor']

        if current_storage not in supported_storages:
            pytest.skip(f"当前存储类型 {current_storage} 不支持创建加密云硬盘，跳过测试")
        # 进入云硬盘页面
        evs_page.goto_service("云硬盘")

        # 生成随机云硬盘名称
        volume_name = f"encrypted-{random_data()}"

        with allure.step("步骤1: 创建加密云硬盘"):
            # 创建加密云硬盘
            evs_page.evs_create(
                name=volume_name,
                encrypted=True,
                encryption_key=kms_key["UUID"]
            )

            # 验证创建成功
            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.assert_status(volume_name, status="可用")

            # 验证云硬盘属性
            data = evs_page.get_row_data(volume_name)
            assert data['共享盘'] == '否'
            assert data['加密'] == "已加密"

        with allure.step("步骤2: 删除加密云硬盘"):
            # 删除云硬盘
            evs_page.evs_remove(volume_name)
            evs_page.evs_delete(volume_name)
            evs_page.assert_deleted(volume_name)
            assert ssh_host.run(f"cinder list| grep {volume_name}") == ""