import allure

from sugon_web.utils.logger import allure_step_log


@allure.epic('云备份')
@allure.feature('实例备份')
@allure.story('备份任务-回收')
class TestBackupTaskRecycle:

    @allure.title("恢复备份任务")
    def test_backup_recovery(self, backup_task, backup_page):
        """测试回收站恢复备份任务功能"""
        task_name = backup_task.get("task_name")

        with allure_step_log("步骤1: 删除备份任务"):
            backup_page.backup_remove(task_name)

        with allure_step_log("步骤2: 恢复备份任务"):
            backup_page.backup_recovery(task_name)

    @allure.title("验证列表页搜索&重置")
    def test_backup_recycle_search(self, backup_page, backup_task):
        task_name = backup_task.get('task_name')

        with allure_step_log("步骤1: 删除备份任务"):
            backup_page.backup_remove(task_name)

        with allure_step_log("步骤2: 输入名称进行搜索"):
            keyword = task_name.split("-")[-1]
            backup_page.goto_submenu("回收")
            backup_page.backup_search(keyword)
            backup_page.assert_list_contain(keyword, column_name="任务名", exact_match=False)

        with allure_step_log("步骤3: 重置搜索条件"):
            backup_page.btn_reset.click()
            # 断言重置后搜索输入框已清空
            assert backup_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("验证删除单个备份任务")
    def test_backup_recycle_delete(self, backup_page, backup_task):
        task_name = backup_task.get('task_name')

        with allure_step_log("步骤1: 删除备份任务"):
            # 重置搜索条件
            backup_page.btn_reset.click()
            backup_page.backup_delete(task_name)
            backup_page.assert_deleted(task_name)
