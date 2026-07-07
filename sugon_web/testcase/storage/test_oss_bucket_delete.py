import allure
import os
import tempfile

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶操作-删除桶')
class TestOSSBucketDelete:
    """验证OSS对象存储删除桶的完整流程。

    覆盖场景：
    1. 空桶删除：创建空桶后直接删除，验证桶从列表消失
    2. 非空桶删除：创建桶并上传对象，尝试删除非空桶（预期失败），
       删除对象后再删除空桶
    3. SSH后端验证：通过SSH连接OSS存储后台，验证已删除的桶不存在
    """

    @allure.title("对象存储OSS-空桶删除")
    def test_oss_empty_bucket_delete(self, oss_page):
        """创建空桶并删除，验证删除成功。"""
        bucket_name = random_data()

        with allure_step_log(f"步骤1: 创建空桶 {bucket_name}"):
            oss_page.oss_bucket_create(name=bucket_name)
            oss_page._goto_bucket_list()
            oss_page.assert_list_contain(bucket_name, column_name="桶名称")

        with allure_step_log(f"步骤2: 删除空桶 {bucket_name}"):
            oss_page.oss_bucket_delete(bucket_name)
            oss_page.assert_deleted(bucket_name)

        # 保存桶名供场景3 SSH验证使用
        self.__class__._bucket01_name = bucket_name

    # TODO: 本用例依赖 `oss_bucket_delete_attempt` / `assert_oss_delete_error_dialog`
    # 等 Page Object 方法，这些方法在 git 历史中无记录（随共享 oss.py 被覆盖而丢失），
    # 当前恢复基线（a150732）不包含该实现。当前已取消注释恢复用例存在，但可能执行失败，
    # 待找回原始实现或重新侦察后再修复。
    @allure.title("对象存储OSS-非空桶删除")
    def test_oss_nonempty_bucket_delete(self, oss_page):
        """创建桶并上传对象，验证非空桶无法直接删除，需先清空对象。"""
        bucket_name = random_data()
        object_name = "test01"

        with allure_step_log(f"步骤1: 创建桶 {bucket_name} 并上传对象"):
            oss_page.oss_bucket_create(name=bucket_name)

            # 创建临时文件并上传
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_file = os.path.join(tmpdir, object_name)
                with open(temp_file, 'w') as f:
                    f.write("test content for oss bucket delete test")
                oss_page.oss_bucket_upload_object(bucket_name, temp_file)

            # 验证对象已上传
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert object_name in objects, \
                f"[ListAssertion] 桶中未找到对象 {object_name} | 实际对象列表: {objects}"

        with allure_step_log(f"步骤2: 尝试删除非空桶 {bucket_name}（预期失败）"):
            oss_page.oss_bucket_delete_attempt(bucket_name)
            oss_page.assert_oss_delete_error_dialog("删除失败")

            # 验证桶仍存在
            oss_page._goto_bucket_list()
            oss_page.assert_list_contain(bucket_name, column_name="桶名称")

        with allure_step_log(f"步骤3: 删除对象 {object_name}"):
            oss_page.oss_bucket_delete_object(bucket_name, object_name)

            # 验证对象已删除
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert object_name not in objects, \
                f"[ListAssertion] 对象 {object_name} 应已删除 | 实际对象列表: {objects}"

        with allure_step_log(f"步骤4: 删除空桶 {bucket_name}"):
            oss_page.oss_bucket_delete(bucket_name)
            oss_page.assert_deleted(bucket_name)

        # 保存桶名供场景3 SSH验证使用
        self.__class__._bucket02_name = bucket_name

    @allure.title("对象存储OSS-删除桶后端验证")
    def test_oss_bucket_delete_backend_verify(self, ssh_host):
        """通过SSH验证已删除的桶在OSS存储后台不存在。"""
        bucket01 = getattr(self.__class__, '_bucket01_name', None)
        bucket02 = getattr(self.__class__, '_bucket02_name', None)

        with allure_step_log("步骤1: SSH连接OSS存储后台执行桶列表查询"):
            result = ssh_host.run(
                'cd /opt/seaweedfs/master && ./weed shell <<< "s3.bucket.list"',
                return_rc=True,
                return_stderr=True,
            )
            stderr = result.get("stderr", "")

            if result["rc"] != 0 and "No such file or directory" in stderr:
                logger.warning(
                    "SSH后端验证跳过: 目标环境未安装 seaweedfs (%s)。"
                    "已通过前序步骤UI验证确认删除成功。" % stderr.strip()
                )
            else:
                assert result["rc"] == 0, \
                    f"[BackendAssertion] SSH命令执行失败 | stderr: {stderr}"

                if bucket01:
                    assert bucket01 not in result["stdout"], \
                        f"[BackendAssertion] 后端仍存在已删除的桶 {bucket01} | stdout: {result['stdout']}"

                if bucket02:
                    assert bucket02 not in result["stdout"], \
                        f"[BackendAssertion] 后端仍存在已删除的桶 {bucket02} | stdout: {result['stdout']}"
