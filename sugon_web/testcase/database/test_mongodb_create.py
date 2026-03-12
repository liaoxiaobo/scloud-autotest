import pytest
import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, random_string, load_data

@allure.epic('数据库服务')
@allure.feature('AnhanDB(for MongoDB)')
class TestMongoDBCreate:

    @allure.title("MongoDB-创建和删除实例-{params[instance_type]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_mongodb", data_file='test_cdb.yaml'))
    def test_create_and_delete_mongodb(self, mongodb_page, params):
        """测试创建和删除MongoDB实例（单机/副本集/分片集群）"""
        instance_type = params["instance_type"]
        version = params["version"]
        disk_size = params["disk_size"]
        
        name = f"mongo-{random_data()}"
        password = f"Admin1234#{random_string(k=5)}"
        
        with allure_step_log(f"创建{instance_type}实例: {name}"):
            # 分片集群创建时间较长，设置更长的超时时间
            create_timeout = 2400 if instance_type == "分片集群" else 1800
            
            mongodb_page.create_instance(
                name, 
                instance_type=instance_type, 
                version=version,
                password=password,
                disk_size=disk_size
            )
            mongodb_page.assert_popup_success("创建实例")
            mongodb_page.assert_status(name, status="运行中", timeout=create_timeout)

        with allure_step_log("清理资源"):
            mongodb_page.delete_instance(name)
            mongodb_page.assert_deleted(name)
