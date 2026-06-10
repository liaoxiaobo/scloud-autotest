import re
import time
from typing import TYPE_CHECKING

from playwright.sync_api import Locator, expect

from sugon_web.common.types import ColumnData, TableRowData

if TYPE_CHECKING:
    from sugon_web.common.playwright import CustomLocator


class TablesMixin:
    """表格操作 Mixin。

    提供表格数据读取、行定位、列数据提取、表头设置、排序等能力。
    设计为与 Playwright 组合使用，依赖 self.locator / self.logger。
    """

    _HEADER_NOISE_SELECTORS = [
        '.el-table__column-filter-trigger',
        '.el-table-filter',
        '.el-table__filter',
        '.el-table__filter-panel',
        '.el-table-filter-panel',
        '.filter-panel',
        '[class*="filter-panel"]',
        '[class*="table-filter"]',
        '.el-popper',
        '.el-popover',
        '.el-dropdown',
        '.el-dropdown-menu',
        '.el-checkbox',
        '.el-checkbox-group',
        '.el-radio',
        '.el-radio-group',
        '.caret-wrapper',
        '.el-table__column-sorter',
        '.el-icon-arrow-down',
        '.el-icon-arrow-up',
        '.el-icon--right',
        '[class*="filter-trigger"]',
        '[class*="sort-caret"]',
        '[class*="sorter"]',
        'svg',
        'i[class^="el-icon"]',
    ]

    def _extract_header_text(self, th_locator) -> str:
        """从单个 <th> 元素中提取纯列名文本。

        通过浏览器端 JS 执行，剔除筛选按钮、排序图标、下拉箭头等
        交互元素产生的噪声文本，返回用户可见的列标题。

        Args:
            th_locator: 表格表头单元格 (<th>) 的 Playwright Locator 对象。

        Returns:
            清洗后的列名文本；若提取失败则回退到 text_content() 的原始值。
        """
        try:
            return th_locator.evaluate("""
                (el, selectors) => {
                    const cell = el.querySelector('.cell');
                    if (!cell) {
                        return el.textContent.trim();
                    }

                    // 策略1：移除已知噪声元素
                    const clone = cell.cloneNode(true);
                    selectors.forEach(selector => {
                        try {
                            clone.querySelectorAll(selector).forEach(node => node.remove());
                        } catch (e) {}
                    });
                    let text = (clone.textContent || '').replace(/\\s+/g, ' ').trim();

                    // 策略2：兜底——如果仍有"筛选"+"重置"或文本过长，保守取首个文本/元素节点
                    const noiseWords = ['筛选', '重置'];
                    const hasNoise = noiseWords.every(w => text.includes(w));
                    if (hasNoise || text.length > 15) {
                        for (const node of cell.childNodes) {
                            if (node.nodeType === Node.TEXT_NODE) {
                                const t = node.textContent.trim();
                                if (t) return t;
                            }
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                const tag = node.tagName.toLowerCase();
                                if (tag === 'span' || tag === 'div' || tag === 'p') {
                                    const t = node.textContent.trim();
                                    if (t && !noiseWords.every(w => t.includes(w))) return t;
                                }
                            }
                        }
                    }

                    return text;
                }
            """, self._HEADER_NOISE_SELECTORS)
        except Exception as e:
            self.logger.warning(f"精确提取表头文本失败，回退到原始方式: {e}")
            return (th_locator.text_content() or '').strip()

    @property
    def table_headers(self) -> list[str]:
        """获取主内容区第一个可见表格的表头文本列表。

        注意：
        - 优先取 #cloud-container-content 下第一个可见的 .el-table__header-wrapper
        - 多表格场景下只取第一个表格的表头
        - 未找到时返回空列表，不会抛异常
        """
        headers = []
        header_wrapper = self.locator("#cloud-container-content .el-table__header-wrapper:visible").first

        if header_wrapper.count() > 0:
            th_elements = header_wrapper.locator("th").all()
            headers = [self._extract_header_text(th) for th in th_elements]
            self.logger.info(f"页面表头信息: {headers}, 共{len(headers)}个")
        else:
            self.logger.warning(f"未找到表头信息，尝试使用备用定位方式")
            if self.locator("thead").count() > 0:
                th_elements = self.locator("thead:visible th").all()
                headers = [self._extract_header_text(th) for th in th_elements]
                self.logger.info(f"使用备用方式获取表头信息: {headers}, 共{len(headers)}个")
            else:
                self.logger.error(f"未找到任何表头信息")

        return headers

    @property
    def table_rows(self) -> list[Locator]:
        """获取主内容区第一个可见表格的数据行列表。

        注意：
        - 优先取 #cloud-container-content 下第一个可见的 .el-table__body-wrapper 中的 tr
        - 多表格场景下只取第一个表格的行
        - 未找到时返回空列表，不会抛异常
        """
        locator = self.locator("#cloud-container-content .el-table__body-wrapper:visible tr")
        if locator.count() > 0:
            rows = locator.all()
            self.logger.info(f"成功获取表格行，共{len(rows)}行")
        else:
            self.logger.info(f"未找到表格行")
            rows = []
        return rows

    def get_row_by_name(self, name: str) -> Locator:
        """公共方法: 根据名称查找数据行,用于获取单个或第一个匹配的行(前缀匹配优先)"""
        self._expand_page_size()
        self.page.wait_for_timeout(1000)
        t_body = self.locator(".el-table__body-wrapper")
        if t_body.count() == 0:
            t_body = self

        try:
            pattern = re.compile(rf"^{re.escape(name)}\s")
            target_rows = t_body.locator("tr").filter(has_text=pattern)
            if target_rows.count() > 0:
                self.logger.debug(f"找到精确匹配 {name} 的数据行(空白字符)")
                return target_rows.first

            pattern2 = re.compile(rf"^{re.escape(name)}:\w+")
            target_rows = t_body.locator("tr").filter(has_text=pattern2)
            if target_rows.count() > 0:
                self.logger.debug(f"找到带ID的匹配 {name} 的数据行(冒号)")
                return target_rows.first

            pattern3 = re.compile(rf"^{re.escape(name)}/\w+")
            target_rows = t_body.locator("tr").filter(has_text=pattern3)
            if target_rows.count() > 0:
                self.logger.debug(f"找到带ID的匹配 {name} 的数据行(斜杠)")
                return target_rows.first

        except Exception as e:
            self.logger.debug(f"正则匹配失败: {e}")

        try:
            target_rows = t_body.locator("tr")
            for i in range(target_rows.count()):
                current_row = target_rows.nth(i)
                try:
                    cells = current_row.locator("td")
                    for j in range(cells.count()):
                        cell_text = cells.nth(j).text_content()
                        if cell_text and cell_text.strip() == name:
                            self.logger.info(f"通过遍历找到 '{name}' 的精确匹配行")
                            return current_row
                except Exception as e:
                    self.logger.debug(f"检查行 {i} 时出错: {e}")
                    continue

            for i in range(target_rows.count()):
                current_row = target_rows.nth(i)
                try:
                    cells = current_row.locator("td")
                    for j in range(cells.count()):
                        cell_text = cells.nth(j).text_content()
                        if cell_text and cell_text.strip().startswith(name):
                            self.logger.info(f"通过遍历找到 '{name}' 的前缀匹配行(单元格: {cell_text.strip()})")
                            return current_row
                except Exception as e:
                    self.logger.debug(f"检查行 {i} 时出错: {e}")
                    continue
        except Exception as e:
            self.logger.info(f"遍历表格行失败: {e}")

        raise AssertionError(f"未找到名称为 '{name}' 的数据行")

    def get_rows_by_text(self, text: str) -> Locator:
        """公共方法：根据文本查找数据行，用于获取所有匹配的行（包含匹配）"""
        target_rows = self.locator(f"tr:has-text('{text}')")

        if target_rows.count() == 0:
            raise AssertionError(f"未找到包含'{text}' 的数据行")

        self.logger.info(f"找到 {target_rows.count()} 个包含 '{text}' 的数据行")
        return target_rows

    def _get_cell_contents(self, target_row):
        """公共方法：获取单元格内容并进行清洗"""
        cells = target_row.get_by_role("cell").all()
        cell_contents = [cell.text_content() for cell in cells[:-1]]
        cell_contents = [re.sub(r'\s+', ' ', item).strip() for item in cell_contents]
        self.logger.info(f"页面数据行信息: {cell_contents}, 共{len(cell_contents)}个")
        return cell_contents

    def get_row_data(self, name: str) -> TableRowData:
        """
        根据名称获取目标行数据，返回表头与单元格内容的键值对字典

        Args:
            name: 行名称，用于定位特定行

        Returns:
            dict: 表头与单元格内容的键值对字典，已移除空表头和"操作"列

        Raises:
            AssertionError: 当找不到指定名称的行时
        """
        self.logger.info(f"开始获取资源({name})的数据")

        try:
            target_row = self.get_row_by_name(name)
        except AssertionError as e:
            self.logger.error(f"获取数据行失败: {str(e)}")
            raise

        table_index = target_row.evaluate("""
            el => {
                const table = el.closest('.el-table');
                if (!table) return -1;
                return Array.from(document.querySelectorAll('.el-table')).indexOf(table);
            }
        """)

        if table_index != -1:
            header_wrapper = self.locator(".el-table").nth(table_index).locator(".el-table__header-wrapper")
            th_elements = header_wrapper.locator("th").all()
            headers = [self._extract_header_text(th) for th in th_elements]
        else:
            headers = self.table_headers


        # 清理表头文本中的特殊空白字符（如 \xa0、&nbsp;），与 _get_cell_contents 保持一致
        headers = [re.sub(r'\s+', ' ', h).strip() for h in headers]
        cell_contents = self._get_cell_contents(target_row)

        result = dict(zip(headers, cell_contents))
        self.logger.debug(f"原始数据行: {result}")

        exclude_headers = ["", "操作"]
        for key in exclude_headers:
            if key in result:
                del result[key]

        self.logger.info(f"处理后的数据: {result}")
        return result

    def get_column_data(self, header_name: str, deduplicate: bool = True, context: str = "auto") -> ColumnData:
        """根据表头名称获取该列的所有数据
            Args:
                header_name: 表头名称
                deduplicate: 是否处理合并单元格的重复值
                context: "auto" | "dialog" | "main" | "active-tab"
                    - auto: 自动判断
                    - dialog: 优先查找弹窗内的表格
                    - main: 只查找主页面表格
                    - active-tab: 只查找当前激活的tab页内的表格
        """
        if context == "dialog":
            dialog = self.get_by_role("dialog").filter(has=self.page.locator(".el-table"))
            if dialog.count() > 0 and dialog.is_visible():
                search_root = dialog.first
            else:
                search_root = self
        elif context == "active-tab":
            active_tab = self.locator(".el-tab-pane:not([aria-hidden='true'])")
            if active_tab.count() > 0:
                search_root = active_tab.first
            else:
                search_root = self
        elif context == "auto":
            try:
                dialog = self.locator(".el-tab-pane:not([aria-hidden='true'])")
                search_root = dialog.first
            except Exception as e:
                try:
                    active_tab = self.get_by_role("dialog").filter(has=self.page.locator(".el-table"))
                    search_root = active_tab.first
                except Exception as e:
                    search_root = self
        else:
            search_root = self

        table_wrappers = search_root.locator(".el-table").all()
        visible_table = None
        target_header_index = None

        for table in table_wrappers:
            try:
                if not table.is_visible():
                    continue

                header_wrapper = table.locator(".el-table__header-wrapper")
                if header_wrapper.count() == 0:
                    continue

                th_elements = header_wrapper.locator("th").all()
                headers = [self._extract_header_text(th) for th in th_elements]

                if header_name in headers:
                    visible_table = table
                    target_header_index = headers.index(header_name)
                    self.logger.info(f"找到包含 '{header_name}' 的可见表格，表头: {headers}")
                    break

            except Exception as e:
                self.logger.debug(f"检查表格时出错: {e}")
                continue

        if visible_table is None:
            self.logger.info(f"未找到包含 '{header_name}' 的可见表格，使用默认方式")
            headers = self.table_headers
            if header_name not in headers:
                self.logger.warning(f"表头 '{header_name}' 不存在")
                return []
            target_header_index = headers.index(header_name)
            all_rows = self.table_rows
        else:
            body_wrapper = visible_table.locator(".el-table__body-wrapper")
            all_rows = body_wrapper.locator("tr").all()

        self.logger.info(f"表头 '{header_name}' 的索引位置: {target_header_index}")
        self.logger.info(f"获取到的数据行共{len(all_rows)}行")

        column_data = []
        for i, row in enumerate(all_rows):
            try:
                cells = row.get_by_role("cell").all()
                if len(cells) > target_header_index:
                    cell_content = cells[target_header_index].text_content()
                    cleaned_content = re.sub(r'\s+', ' ', cell_content).strip()
                    if deduplicate and cleaned_content:
                        parts = cleaned_content.split()
                        if len(set(parts)) == 1:
                            cleaned_content = parts[0]
                    if cleaned_content:
                        column_data.append(cleaned_content)
                        self.logger.debug(f"第{i + 1}行数据: {cleaned_content}")
            except Exception as e:
                self.logger.warning(f"获取第{i + 1}行数据时出错: {e}")

        self.logger.info(f"获取到的列数据共{len(column_data)}条: {column_data}")
        return column_data

    def _expand_page_size(self, target_size: str = "50") -> bool:
        """尝试将当前可见表格的分页条数扩大。

        按优先级查找分页器：
        1. 主内容区 (#cloud-container-content)
        2. 当前激活 tab 页
        3. 页面全局

        点击分页条数下拉后，优先选择 target_size，没有则依次尝试 100/50 条/页。
        若点开了下拉但未找到匹配选项，会按 ESC 关闭下拉避免遮挡。

        Args:
            target_size: 目标分页条数，默认 "50"

        Returns:
            bool: 是否成功调整分页条数
        """
        try:
            size_triggers = [
                self.locator("#cloud-container-content .el-pagination__sizes .el-input__inner"),
                self.locator(".el-tab-pane:not([aria-hidden='true']) .el-pagination__sizes .el-input__inner"),
                self.locator(".el-pagination__sizes .el-input__inner"),
            ]

            size_trigger = None
            for loc in size_triggers:
                if loc.count() > 0 and loc.first.is_visible():
                    size_trigger = loc.first
                    break

            if size_trigger is None:
                self.logger.debug("未找到可见的分页条数切换器")
                return False

            size_trigger.click()
            self.page.wait_for_timeout(500)

            for size in [f"{target_size}条/页", "100条/页", "50条/页"]:
                option = self.locator("li:visible").filter(has_text=size).last
                if option.count() > 0 and option.is_visible():
                    option.click()
                    if hasattr(self, "wait_for_page_ready"):
                        self.wait_for_page_ready()
                    else:
                        self.page.wait_for_timeout(1000)
                    self.logger.info(f"分页条数已调整为 {size}")
                    return True

            # 点开了下拉但没找到选项，关闭下拉避免遮挡后续操作
            self.page.keyboard.press("Escape")
            return False

        except Exception as e:
            self.logger.debug(f"扩大分页条数失败: {e}")
            return False

    def select_rows_by_names(self, names: list[str]) -> None:
        """公共方法: 根据名称列表勾选表格行

        Args:
            names: 资源名称列表
        """
        # 先尝试扩大分页条数，让尽可能多的目标行在同一页可见
        self._expand_page_size()

        for name in names:
            loc = self.get_by_role("row", name=name).locator("label span").last
            if not loc.is_checked():
                loc.click()
                self.logger.info(f"勾选资源 '{name}'")

    def get_row_data_by_locator(self, loc: Locator) -> TableRowData:
        """获取指定行数据"""
        headers = self.table_headers
        cell_contents = self._get_cell_contents(loc)
        result = dict(zip(headers, cell_contents))
        self.logger.debug(f"原始数据行: {result}")

        exclude_headers = ["", "操作"]
        for key in exclude_headers:
            if key in result:
                del result[key]
        return result

    def assert_row_contains(self, name: str, expected_data: str, timeout: int = 300) -> None:
        """断言指定行包含期望文本（包含匹配）。

        注意：expected_data 使用包含匹配（to_contain_text），
        只要行文本中出现该片段即通过，不需要完全一致。

        Args:
            name: 行名称，用于定位特定行
            expected_data: 期望出现的文本片段
            timeout: 等待行出现的超时时间（秒）

        Raises:
            AssertionError: 当行数据不包含期望文本时
        """
        target_row = self.get_row_by_name(name)
        timeout = timeout * 1000
        expect(target_row).to_contain_text(expected_data, timeout=timeout)
        self.logger.info(f"行 '{name}' 包含期望数据 '{expected_data}'")

    def set_table_header(self, names: str | list[str], enable: bool = True) -> None:
        """设置表头列

        Args:
            names: 列名称（单个或列表）
            enable: 是否展示，默认为True
        """
        if isinstance(names, str):
            names = [names]
        self.locator(".el-icon-setting").click()
        for name in names:
            locs = [
                self.get_by_label("checkbox-group").get_by_text(name, exact=True),
                self.get_by_label("checkbox-group").locator("div").filter(has_text=re.compile(fr"^{name}$")),
                self.get_by_label("设置表头").get_by_text(name, exact=True),
                self.get_by_text(name, exact=True),
            ]
            loc = self._find_element(locs, f"checkbox{name}")
            if enable and not loc.is_checked():
                loc.click()
            elif not enable and loc.is_checked():
                loc.click()
        try:
            self.dialog_confirm.click()
        except:
            self.locator(".el-icon-setting").click()

        self.wait_for_page_ready()
        self.logger.info(f"表头设置完成 {'显示' if enable else '隐藏'}{names}")

    def sort_by_header(self, header_name: str, order: str = "desc") -> None:
        """点击表头进行排序。

        注意：若表头不存在，本方法静默返回，不会抛异常。

        Args:
            header_name: 表头名称，如"创建时间"
            order: 排序方式，"asc"升序或"desc"降序，默认降序

        Raises:
            AssertionError: 当排序箭头定位失败时（表头存在但无法点击排序箭头）
        """
        header_cell = self.get_by_role("cell", name=header_name)
        if header_cell.count() == 0:
            self.logger.warning(f"未找到表头: {header_name}")
            return

        class_attr = header_cell.get_attribute("class") or ""

        is_asc_active = "ascending" in class_attr
        is_desc_active = "descending" in class_attr

        if order == "desc" and is_desc_active:
            self.logger.info(f"已经是 {header_name} 降序排列")
            return
        if order == "asc" and is_asc_active:
            self.logger.info(f"已经是 {header_name} 升序排列")
            return

        caret_wrapper = header_cell.locator(".caret-wrapper")
        if order == "desc":
            caret_wrapper.locator("i.descending").click()
            self.logger.info(f"已按 {header_name} 降序排列")
        else:
            caret_wrapper.locator("i.ascending").click()
            self.logger.info(f"已按 {header_name} 升序排列")

    def _get_interactive_row(self, row: Locator) -> Locator:
        """获取可交互的行（优先返回 fixed-right 层，避免被遮挡）"""
        try:
            # 1. 获取当前行在所属 tbody 中的物理索引
            row_index = row.evaluate("el => Array.from(el.parentNode.children).indexOf(el)")

            # 2. 获取当前所属表格在页面所有 el-table 中的索引，用于解决多表格共存时的定位偏移
            table_index = row.evaluate("""
                el => {
                    const table = el.closest('.el-table');
                    if (!table) return -1;
                    return Array.from(document.querySelectorAll('.el-table')).indexOf(table);
                }
            """)

            if table_index != -1:
                # 3. 在对应的表格内根据索引定位固定列中心对应的行
                fixed_right = self.locator(".el-table").nth(table_index).locator(".el-table__fixed-right .el-table__row").nth(row_index)
                if fixed_right.count() > 0 and fixed_right.is_visible():
                    return fixed_right
        except Exception as e:
            self.logger.debug(f"通过索引获取可交互行时出错: {e}")
        return row
