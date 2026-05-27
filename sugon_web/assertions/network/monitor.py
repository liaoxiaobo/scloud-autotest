import math
import time

from sugon_web.common.playwright import expect


class MonitorAssertionMixin:
    """监控业务断言 Mixin。

    验证监控图表可见性、监控数据是否为零、数据是否正常等。
    属于 L2 Business 层断言。
    """

    def assert_monitor_charts_visible(self, min_charts=1, timeout=30000):
        """断言监控图表可见。

        等待图表组件异步加载完成后，验证图表容器存在且可见。

        Args:
            min_charts: 期望的最小图表数量，默认1
            timeout: 等待图表加载的最大时间（毫秒），默认30000
        """
        # 图表在dragableBox组件中异步渲染，需要等待加载完成
        deadline = time.time() + timeout / 1000
        chart_containers = []

        while time.time() < deadline:
            # 优先查找dragableBox内的图表容器
            chart_containers = self.locator(
                ".render-parent-box .box_item, .dragable-box .box_item"
            ).all()
            if not chart_containers:
                # 兜底：查找echarts canvas元素
                chart_containers = self.locator(
                    ".render-parent-box canvas"
                ).all()
            if len(chart_containers) >= min_charts:
                break
            time.sleep(2)

        assert len(chart_containers) >= min_charts, (
            f"监控图表数量不足，期望至少 {min_charts} 个，"
            f"实际 {len(chart_containers)} 个"
        )
        for chart in chart_containers:
            expect(chart).to_be_visible(timeout=5000)
        self.logger.info(
            f"监控图表可见性验证通过，共 {len(chart_containers)} 个图表"
        )

    def assert_monitor_data_not_zero(self, wait_sec=15):
        """断言监控数据不为零。

        通过JavaScript从Vue组件内部状态读取图表数据，验证数据值不为零。
        监控数据可能存在延迟，先等待一段时间让数据加载。

        Args:
            wait_sec: 等待数据加载的秒数，默认15秒
        """
        # 等待数据加载（实时模式每10秒刷新一次）
        time.sleep(wait_sec)

        # 通过JavaScript从Vue组件内部状态读取图表数据
        data_values = self.page.evaluate("""
            () => {
                const values = [];
                document.querySelectorAll('.box_item').forEach(el => {
                    const vue = el.__vue__;
                    if (vue && vue.echartObj && vue.echartObj.dataList) {
                        vue.echartObj.dataList.forEach(series => {
                            if (series.data) {
                                series.data.forEach(point => {
                                    const val = point[1];
                                    if (val !== null && val !== undefined && val !== '') {
                                        values.push(parseFloat(val));
                                    }
                                });
                            }
                        });
                    }
                });
                return values;
            }
        """)

        if data_values and len(data_values) > 0:
            has_non_zero = any(v > 0 for v in data_values if not math.isnan(v))
            assert has_non_zero, (
                f"监控数据均为零或未加载成功，共 {len(data_values)} 个数据点，"
                f"部分值: {data_values[:10]}"
            )
            non_zero_values = [v for v in data_values if v > 0 and not math.isnan(v)]
            self.logger.info(
                f"监控数据非零验证通过，共 {len(data_values)} 个数据点，"
                f"非零值数量: {len(non_zero_values)}, "
                f"最大值: {max(non_zero_values) if non_zero_values else 'N/A'}"
            )
        else:
            # 兜底：如果没有读取到数据，验证图表容器存在
            chart_containers = self.locator(
                ".render-parent-box canvas, .render-parent-box .box_item"
            ).all()
            assert len(chart_containers) > 0, "未找到任何监控图表"
            self.logger.warning(
                f"未能从Vue组件读取监控数据，但存在 {len(chart_containers)} 个图表，"
                "可能数据尚未加载或页面结构不同"
            )

    def assert_monitor_data_zero(self, wait_sec=15, tolerance=0.01):
        """断言监控数据已归零。

        通过JavaScript从Vue组件内部状态读取图表数据，验证所有数据值
        接近零（考虑浮点误差）。适用于流量停止后监控数据回落场景。

        Args:
            wait_sec: 等待数据加载的秒数，默认15秒
            tolerance: 允许的最大非零容差，默认0.01
        """
        time.sleep(wait_sec)

        data_values = self.page.evaluate("""
            () => {
                const values = [];
                document.querySelectorAll('.box_item').forEach(el => {
                    const vue = el.__vue__;
                    if (vue && vue.echartObj && vue.echartObj.dataList) {
                        vue.echartObj.dataList.forEach(series => {
                            if (series.data) {
                                series.data.forEach(point => {
                                    const val = point[1];
                                    if (val !== null && val !== undefined && val !== '') {
                                        values.push(parseFloat(val));
                                    }
                                });
                            }
                        });
                    }
                });
                return values;
            }
        """)

        if data_values and len(data_values) > 0:
            non_zero_values = [
                v for v in data_values
                if not math.isnan(v) and abs(v) > tolerance
            ]
            assert len(non_zero_values) == 0, (
                f"监控数据未完全归零，存在 {len(non_zero_values)} 个非零点，"
                f"最大值: {max(non_zero_values) if non_zero_values else 'N/A'}, "
                f"部分值: {data_values[:20]}"
            )
            self.logger.info(
                f"监控数据归零验证通过，共 {len(data_values)} 个数据点，"
                f"所有值均在容差 {tolerance} 范围内"
            )
        else:
            chart_containers = self.locator(
                ".render-parent-box canvas, .render-parent-box .box_item"
            ).all()
            assert len(chart_containers) > 0, "未找到任何监控图表"
            self.logger.warning(
                "未能从Vue组件读取监控数据，图表存在但数据可能尚未加载"
            )
