import allure
import pytest

from sugon_web.utils.data import load_data, random_data, random_string
from sugon_web.utils.logger import allure_step_log


@allure.epic("大数据计算")
@allure.feature("E-MapReduce")
class TestEMRCreate:

    @allure.title("E-MapReduce-创建并删除集群-{params[deploy_mode]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_emr", data_file="test_cdb.yaml"))
    def test_create_and_delete_cluster(self, emr_page, params):
        cluster_name = f"emr-{random_data()}"

        with allure_step_log(f"步骤一：创建 E-MapReduce 集群 {cluster_name}，部署模式 {params['deploy_mode']}"):
            emr_page.create_cluster(name=cluster_name, deploy_mode=params["deploy_mode"])

        with allure_step_log("步骤二：验证创建结果"):
            emr_page.assert_popup_success("创建E-MapReduce集群成功")
            emr_page.assert_cluster_visible(cluster_name)
            emr_page.assert_status(cluster_name, status="服务运行中", timeout=3600, refresh=True)

        with allure_step_log("步骤三：删除集群"):
            emr_page.delete_cluster(cluster_name)

        with allure_step_log("步骤四：验证删除结果"):
            emr_page.assert_deleted(cluster_name, timeout=1800, refresh=True)

    @allure.title("E-MapReduce-批量删除集群")
    def test_batch_delete_clusters(self, emr_page):
        cluster_names = [f"emr-batch-{random_string(5)}", f"emr-batch-{random_string(5)}"]

        for cluster_name in cluster_names:
            with allure_step_log(f"步骤一：创建 E-MapReduce 集群 {cluster_name}"):
                emr_page.create_cluster(name=cluster_name)
                emr_page.assert_popup_success("创建E-MapReduce集群成功")
                emr_page.assert_status(cluster_name, status="服务运行中", timeout=3600, refresh=True)

        with allure_step_log("步骤二：批量删除集群"):
            emr_page.batch_delete_clusters(cluster_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            for cluster_name in cluster_names:
                emr_page.assert_deleted(cluster_name, timeout=1800, refresh=True)
