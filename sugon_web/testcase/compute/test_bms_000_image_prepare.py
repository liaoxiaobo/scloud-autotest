import allure

from sugon_web.testcase.compute.conftest import ensure_bms_image
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS镜像前置准备")
class TestBmsImagePrepare:

    @allure.title("裸金属BMS-镜像前置准备")
    def test_bms_image_prepare(self, ssh_host, bms_env):
        """确保创建和重建BMS实例所需的裸金属镜像已存在。"""
        image_name = ensure_bms_image(ssh_host, bms_env)
        with allure_step_log("步骤1: 记录BMS镜像前置结果"):
            logger.info(f"BMS镜像前置准备完成: {image_name}")
            allure.attach(image_name, "BMS镜像名称", allure.attachment_type.TEXT)
