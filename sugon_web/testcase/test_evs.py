import pytest
import allure
from sugon_web.utils.util import random_data, load_data


@allure.epic('存储服务')
@allure.feature('云硬盘 EVS')
class TestEVS:

    @allure.title("云硬盘-创建&删除")
    @pytest.mark.parametrize("params", load_data('test_volume_create'))
    def test_volume_create(self, evs_page, params, ssh_host):

        name=random_data()
        with allure.step("步骤1: 创建单个云硬盘"):
            evs_page.evs_create(
                name,
                empty=params['empty'],
                size=params["size"],
                desc=params["desc"],
            )

            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.assert_status(name, status="可用")

            data = evs_page.get_row_data(name)
            if not params['empty']:
                assert data['可启动'] == '是'
            else:
                assert data['可启动'] == '否'
            assert data['容量'] == str(params["size"]) + "GiB"
            # assert data['描述'] == params["desc"]

        with allure.step("步骤2: 删除单个云硬盘"):
            evs_page.evs_remove(name)
            evs_page.evs_delete(name)
            evs_page.assert_deleted(name)
            assert ssh_host.run(f"cinder list| grep {name}") == ""

    @allure.title("云硬盘-列表页搜索")
    def test_volume_search(self, evs_page, volume):

        with allure.step("步骤1: 输入名称进行搜索"):
            evs_page.goto_submenu("云硬盘")    # TODO: 连跑时会处于回收站页，加跳转解决
            keyword = volume['name'][:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, prefix_mode=True)

    @allure.title("云硬盘-修改")
    @pytest.mark.parametrize("params", load_data('test_volume_modify'))
    def test_volume_edit(self, evs_page, volume, params):

        new_name = volume["name"] + params["name_suffix"]
        new_desc = params["new_desc"]
        
        with allure.step("步骤1: 修改云硬盘的名称和描述"):
            evs_page.evs_edit(volume["name"], new_name, new_desc)
            evs_page.assert_popup_success("执行成功")

            # 更新 name，便于 fixture teardown 阶段正确清理
            volume["name"] = new_name
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
        """测试云硬盘关闭QoS功能"""
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
            ssh_vm.connect(vm['mfip'], pwd="sugon@20")
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

        with allure.step("步骤3: 清理测试数据"):
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
            evs_page.assert_status(volume["name"], status="删除中")

        with allure.step("步骤2: 重置云硬盘状态"):
            evs_page.evs_reset_status(volume["name"])
            evs_page.assert_popup_success("重置状态成功")
            evs_page.assert_status(volume["name"], status="错误")

        with allure.step("步骤3: 恢复云硬盘状态"):
            ssh_host.run(f'cinder reset-state --state available {volume["name"]}')
            evs_page.assert_status(volume["name"], status="可用")

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
            evs_page.assert_list_contain(keyword, prefix_mode=True)

        with allure.step("步骤3: 从回收站恢复云硬盘"):
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
            evs_page.assert_deleted(name, timeout=300)
            assert ssh_host.run(f"cinder list| grep {name}") == ""

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

    @allure.title("云硬盘-查看快照")
    def test_volume_view_snapshots(self, evs_page, volume, evss):

        with allure.step("步骤1: 查看快照"):
            # 从云硬盘页面查看快照
            evs_page.evs_view_snapshots(volume["name"])

            # 验证快照列表中包含指定快照
            evs_page.assert_list_contain(evss["name"])

            # 获取快照数据并验证
            snapshot_data = evs_page.get_row_data(evss["name"])
            assert snapshot_data["名称"] == evss["name"]
            assert snapshot_data["云硬盘名称"] == volume["name"]

    @allure.title("云硬盘快照-列表页搜索")
    def test_evss_search(self, evs_page, evss):

        with allure.step("步骤1: 输入名称进行搜索"):
            keyword = evss['name'][:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, prefix_mode=True)

    @allure.title("云硬盘快照-修改")
    @pytest.mark.parametrize("params", load_data('test_volume_modify_snapshot'))
    def test_volume_modify_snapshot(self, evs_page, evss, params):
        """测试云硬盘快照修改功能"""

        # 生成新的快照名称
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

            # 更新快照名称，便于后续操作
            evss["name"] = new_name

    @allure.title("云硬盘快照-创建云硬盘")
    def test_create_volume_from_snapshot(self, evs_page, evss, ssh_host):
        """测试从快照创建云硬盘功能"""

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

        with allure.step("步骤2: 清理测试数据"):
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

    @allure.title("快照策略-列表页搜索")
    def test_evss_policy_search(self, evs_page, evss_policy):

        with allure.step("步骤1: 输入名称进行搜索"):
            keyword = evss_policy[:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, column_name="名称/ID", prefix_mode=True)

    @allure.title("快照策略-修改")
    def test_evss_policy_edit(self, evs_page, evss_policy):

        with allure.step("步骤1: 修改快照策略"):
            evs_page.evss_policy_edit(name=evss_policy, hours=[7,8,9])
            evs_page.assert_popup_success("修改策略成功")

    @allure.title("云硬盘-绑定&解绑快照策略")
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
            evs_page.evss_task_delete(volume_name=volume["name"])
            evs_page.assert_deleted(volume["name"])

    @allure.title("快照任务-禁用&开启自动快照")
    def test_volume_auto_snapshot(self, evs_page, volume, evss_policy):

        with allure.step("步骤1: 绑定快照策略"):
            evs_page.evs_bind_snapshot_policy(
                volume_name=volume["name"],
                policy_name=evss_policy,
            )
            evs_page.assert_popup_success("执行成功")

        with allure.step("步骤2: 开启自动快照"):
            evs_page.evss_task_set_auto_snapshot(volume_name=volume["name"])
            evs_page.assert_popup_success("执行成功")

        with allure.step("步骤3: 禁用自动快照"):
            evs_page.evss_task_set_auto_snapshot(volume_name=volume["name"], enable=False)
            evs_page.assert_popup_success("执行成功")

        with allure.step("步骤4: 删除快照任务（解绑）"):
            evs_page.evss_task_delete(volume_name=volume["name"])
            evs_page.assert_deleted(volume["name"])

