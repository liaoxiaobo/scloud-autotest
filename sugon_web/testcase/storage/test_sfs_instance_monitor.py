import allure
import pytest
from sugon_web.utils.logger import allure_step_log


@allure.epic('存储服务')
@allure.feature('文件存储 SFS')
@allure.story('文件存储-实例监控功能验证')
class TestSFSInstanceMonitor:
    """验证文件存储 SFS 实例的监控查看功能。"""

    EXPECTED_METRICS = [
        "CPU使用率",
        "内存使用率",
        "磁盘使用率",
        "网卡上行数据",
        "网卡下行数据",
        "磁盘读速率",
        "磁盘写速率",
        "磁盘读IOPS",
        "磁盘写IOPS",
    ]

    @allure.title("文件存储-查看实例监控")
    @pytest.mark.parametrize("sfs_instance", [{"protocol": "nfs", "volume_size": 10}], indirect=True)
    def test_sfs_instance_view_monitor(self, sfs_page, sfs_instance):
        """验证文件存储 SFS 实例监控页面能正常加载并展示 9 项指标图表。"""
        name = sfs_instance["name"]

        with allure_step_log("步骤1: 等待实例状态收敛到正常"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_wait_for_status(name, status="正常", timeout=300)

        with allure_step_log("步骤2: 点击“查看监控”进入监控详情页"):
            sfs_page.sfs_instance_view_monitor(name)

        with allure_step_log("步骤3: P1 断言-监控图表区域可见且包含 9 项指标"):
            sfs_page.assert_monitor_charts_visible(min_charts=9, timeout=60000)
            metric_texts = sfs_page.sfs_monitor_wait_for_metrics(
                self.EXPECTED_METRICS, timeout=60
            )
            missing = []
            for metric in self.EXPECTED_METRICS:
                if not any(metric in text for text in metric_texts):
                    missing.append(metric)
            assert not missing, (
                f"[FieldAssertion] 监控指标缺失 | 期望包含: {self.EXPECTED_METRICS} | "
                f"缺失: {missing} | 实际指标文本: {metric_texts}"
            )
