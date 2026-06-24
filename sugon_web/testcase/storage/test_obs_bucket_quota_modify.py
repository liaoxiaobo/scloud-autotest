import os
from pathlib import Path

import allure
import pytest
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
LARGE_FILE = TEST_DATA_DIR / "large_file.bin"
SMALL_FILES = [TEST_DATA_DIR / f"small_file_{i:02d}.bin" for i in range(1, 14)]


def _ensure_test_data():
    """确保测试数据文件存在，不存在则生成。"""
    TEST_DATA_DIR.mkdir(exist_ok=True)

    # 大文件：1.1GB（稀疏文件，节省磁盘空间）
    if not LARGE_FILE.exists() or LARGE_FILE.stat().st_size < 1024 * 1024 * 1024 + 1:
        with open(LARGE_FILE, "wb") as f:
            f.seek(1024 * 1024 * 1024 + 100)  # 1GB + 100 bytes
            f.write(b"\x00")
        logger.info(f"已生成大文件: {LARGE_FILE} ({LARGE_FILE.stat().st_size} 字节)")

    # 小文件：13个，每个约100KB
    for small_file in SMALL_FILES:
        if not small_file.exists():
            with open(small_file, "wb") as f:
                f.write(os.urandom(100 * 1024))  # 100KB random data
            logger.info(f"已生成小文件: {small_file}")


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('桶列表-桶配额验证')
class TestOBSBucketQuotaModify:

    @allure.title("对象存储-修改桶容量验证配额生效")
    @pytest.mark.parametrize("bucket", [{"capacity": "1"}], indirect=True)
    def test_obs_bucket_capacity_limit_modify(self, obs_page, bucket):
        bucket_name = bucket["name"]
        _ensure_test_data()

        with allure_step_log("步骤1: 创建1GB容量桶并验证"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.assert_list_contain(bucket_name)
            row_data = obs_page.get_row_data(bucket_name)
            assert row_data.get("对象数量") == "0", \
                f"新建桶对象数量应为0，实际为 {row_data.get('对象数量')}"

        with allure_step_log("步骤2: 验证1GB容量限制-上传大对象被阻止"):
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.obs_object_tab_click()

            # 验证上传被阻止
            is_blocked = obs_page.obs_object_upload_check_capacity_blocked(str(LARGE_FILE))
            assert is_blocked, \
                "上传大文件到1GB桶时，应立即上传按钮被禁用或显示容量不足提示"

        with allure_step_log("步骤3: 在桶列表查看对象数量为0"):
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(2000)
            row_data = obs_page.get_row_data(bucket_name)
            assert row_data.get("对象数量") == "0", \
                f"桶对象数量应为0，实际为 {row_data.get('对象数量')}"

        with allure_step_log("步骤4: 修改桶容量为10GB"):
            obs_page.obs_bucket_modify_quota(bucket_name, capacity="10")
            # 修改成功后回到桶列表
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(2000)

        with allure_step_log("步骤5: 验证扩容后大对象可上传（不被阻止）"):
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.page.wait_for_timeout(1500)

            # 验证桶容量显示为10GB
            capacity_text = obs_page.obs_bucket_capacity_get(bucket_name)
            assert capacity_text and "10" in capacity_text, \
                f"桶容量应为10GB，实际显示: {capacity_text}"

            obs_page.obs_object_tab_click()

            # 使用容量检查方法验证大文件不再被阻止（避免1GB文件实际上传耗时过长）
            is_blocked = obs_page.obs_object_upload_check_capacity_blocked(str(LARGE_FILE))
            assert not is_blocked, \
                f"扩容到10GB后，上传大文件不应再被阻止，但上传按钮仍被禁用或显示容量不足"

            # 额外上传一个小文件验证上传功能正常
            obs_page.obs_object_upload(str(SMALL_FILES[0]))
            obs_page.page.wait_for_timeout(10000)
            obs_page._close_task_list_panel_if_exists()
            obs_page.page.wait_for_timeout(2000)

            # 刷新对象列表并验证包含上传的小文件
            object_names = obs_page.get_column_data("名称")
            if SMALL_FILES[0].name not in object_names:
                obs_page.page.wait_for_timeout(5000)
                object_names = obs_page.get_column_data("名称")
            assert SMALL_FILES[0].name in object_names, \
                f"对象列表应包含上传的文件 {SMALL_FILES[0].name}，当前列表: {object_names}"

    @allure.title("对象存储-修改对象数量限制验证生效")
    @pytest.mark.parametrize("bucket", [{"capacity": "10", "object_limit": 10}], indirect=True)
    def test_obs_bucket_object_limit_modify(self, obs_page, bucket):
        bucket_name = bucket["name"]
        _ensure_test_data()

        with allure_step_log("步骤1: 创建10GB容量+10个对象数量限制桶"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.assert_list_contain(bucket_name)

        with allure_step_log("步骤2: 验证对象数量限制显示为10"):
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.page.wait_for_timeout(1500)
            limit_text = obs_page.obs_bucket_object_limit_get(bucket_name)
            assert limit_text and "10" in limit_text, \
                f"对象数量限制应为10，实际显示: {limit_text}"

        with allure_step_log("步骤3: 上传11个小对象验证数量限制"):
            obs_page.obs_object_tab_click()
            # 只上传前11个文件（small_file_01 ~ small_file_11）
            obs_page.obs_object_batch_upload([str(f) for f in SMALL_FILES[:11]])
            obs_page.page.wait_for_timeout(15000)
            obs_page._close_task_list_panel_if_exists()
            obs_page.page.wait_for_timeout(3000)

            # 刷新对象列表并验证对象数量
            object_names = obs_page.get_column_data("名称")
            # 过滤掉表头残留和大小信息列
            valid_objects = [
                n for n in object_names
                if n and n not in ["", "暂无数据", "名称"]
                and not n.endswith(("GB", "MB", "KB", "B"))
            ]
            assert len(valid_objects) == 10, \
                f"对象数量应为10（1个因限制上传失败），实际为 {len(valid_objects)}: {valid_objects}"

        with allure_step_log("步骤4: 在桶列表查看对象数量为10"):
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(2000)
            row_data = obs_page.get_row_data(bucket_name)
            assert row_data.get("对象数量") == "10", \
                f"桶对象数量应为10，实际为 {row_data.get('对象数量')}"

        with allure_step_log("步骤5: 修改对象数量限制为无限制"):
            obs_page.obs_bucket_modify_quota(bucket_name, object_limit="unlimited")
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(2000)

        with allure_step_log("步骤6: 验证取消限制后可继续上传"):
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.page.wait_for_timeout(1500)

            # 验证对象数量限制显示为"不限制"
            limit_text = obs_page.obs_bucket_object_limit_get(bucket_name)
            assert limit_text and ("不限制" in limit_text or "unlimited" in limit_text.lower()), \
                f"对象数量限制应为不限制，实际显示: {limit_text}"

            obs_page.obs_object_tab_click()

            # 上传2个新的小文件（small_file_12、small_file_13，确保不与已有对象重名）
            extra_files = SMALL_FILES[11:13]
            obs_page.obs_object_batch_upload([str(f) for f in extra_files])
            obs_page.page.wait_for_timeout(15000)
            obs_page._close_task_list_panel_if_exists()
            obs_page.page.wait_for_timeout(3000)

            # 对象列表存在分页（每页10条），返回桶列表通过"对象数量"列验证总数
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(3000)
            row_data = obs_page.get_row_data(bucket_name)
            assert row_data.get("对象数量") == "12", \
                f"桶对象数量应为12（10+2），实际为 {row_data.get('对象数量')}"
