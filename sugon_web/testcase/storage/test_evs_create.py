import pytest
import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data, load_data
from sugon_web.utils.decorators import only_stor


@allure.epic('存储服务')
@allure.feature('云硬盘')
@allure.story('云硬盘-创建功能验证')
class TestEVSCreate:

    @allure.title("云硬盘-创建&删除")
    @pytest.mark.parametrize("params", load_data('test_volume_create'))
    def test_volume_create(self, evs_page, params, ssh_host):

        # 如果是共享盘测试，检查当前存储类型是否支持
        if params.get('shared', False):
            supported_storages = ['xstor', 'xbd', 'ceph', 'ustor', 'zbs']
            current_storage = evs_page.stor

            if current_storage not in supported_storages:
                pytest.skip(f"当前存储类型 {current_storage} 不支持创建共享云硬盘，跳过测试")

        name = random_data()
        with allure_step_log("步骤1: 创建单个云硬盘"):
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
            evs_page.set_table_header("机密存储")
            data = evs_page.get_row_data(name)
            assert data['可启动'] == ('是' if not params['empty'] else '否')
            assert data['容量'] == f"{params['size']}GiB"
            assert data['共享盘'] == ('是' if params.get('shared', False) else '否')
            assert data['机密存储'] == "关闭"

        with allure_step_log("步骤2: 删除单个云硬盘"):
            evs_page.evs_remove(name)
            evs_page.evs_delete(name)
            evs_page.assert_deleted(name)
            ssh_host.wait_volume_deleted(name)

    @only_stor("xstor","usan")
    @allure.title("创建HCT加密类型的云硬盘")
    def test_create_hct_encrypted_volume(self, evs_page, kms_key:dict, ssh_host):
        # 生成随机云硬盘名称
        volume_name = f"encrypted-{random_data()}"

        with allure_step_log("步骤1: 创建加密云硬盘"):
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
            evs_page.set_table_header("机密存储")
            data = evs_page.get_row_data(volume_name)
            assert data['共享盘'] == '否'
            assert data['机密存储'] == "开启"

        with allure_step_log("步骤2: 删除加密云硬盘"):
            # 删除云硬盘
            evs_page.evs_remove(volume_name)
            evs_page.evs_delete(volume_name)
            evs_page.assert_deleted(volume_name)
            ssh_host.wait_volume_deleted(volume_name)

    @only_stor("xstor","usan")
    @allure.title("创建OPENSSL纯软加密类型的云硬盘")
    @pytest.mark.parametrize("kms_key", ["OPENSSL纯软"], indirect=True)
    def test_create_openssl_encrypted_volume(self, evs_page, kms_key:dict, ssh_host):
        # 生成随机云硬盘名称
        volume_name = f"encrypted-{random_data()}"

        with allure_step_log("步骤1: 创建加密云硬盘"):
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
            evs_page.set_table_header("机密存储")
            data = evs_page.get_row_data(volume_name)
            assert data['共享盘'] == '否'
            assert data['机密存储'] == "开启"

        with allure_step_log("步骤2: 删除加密云硬盘"):
            # 删除云硬盘
            evs_page.evs_remove(volume_name)
            evs_page.evs_delete(volume_name)
            evs_page.assert_deleted(volume_name)
            ssh_host.wait_volume_deleted(volume_name)
