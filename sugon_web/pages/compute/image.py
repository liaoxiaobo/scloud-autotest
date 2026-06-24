import re
import time
from sugon_web.common.base import submenu, BasePage
from sugon_web.utils.logger import logger


class ImageServiceMixin(BasePage):

    @submenu("弹性云服务器")
    def ecs_create_image(self, name: str, image_name: str):
        logger.info(f"开始创建云服务器镜像: {image_name}")
        self.click_action(name, "新建镜像")
        self.locator("div").filter(has_text=re.compile(r"^镜像名称$")).get_by_role("textbox").fill(image_name)
        self.dialog_confirm.click()
        logger.info(f"云服务器镜像创建请求已提交: {image_name}")

    @submenu("镜像服务")
    def ecs_image_delete(self, image_name):
        self.click_action(image_name, "删除")
        self.dialog_confirm.click()
        logger.info(f"操作完成: 删除镜像{image_name}成功")

    # ---- 镜像上传相关方法 ----

    def _ims_create_dialog(self):
        """返回可见的新建镜像对话框。"""
        dialog = self.page.locator(".el-dialog:visible, .cv-dialog:visible").filter(
            has=self.page.get_by_text("新建镜像", exact=True)
        ).first
        dialog.wait_for(state="visible", timeout=10000)
        return dialog

    def _select_os_triplet(self, dialog, os_type: str, version: str, arch: str):
        """选择操作系统三联下拉框：类型、版本、位数。"""
        os_row = dialog.locator(".el-form-item").filter(
            has=self.page.get_by_text("操作系统", exact=True).first
        )
        if os_row.count() == 0:
            raise AssertionError("未找到操作系统表单项")

        selects = os_row.locator(".el-select").all()
        if len(selects) < 3:
            raise AssertionError(f"操作系统区域只找到 {len(selects)} 个下拉框，预期3个")

        for dropdown, value in zip(selects[:3], [os_type, version, arch]):
            dropdown.click()
            self.page.wait_for_timeout(300)
            option = self.page.locator(".el-select-dropdown:visible").get_by_text(
                value, exact=True
            ).first
            if option.count() == 0:
                option = self.page.locator(".el-select-dropdown:visible").get_by_text(value).first
            if option.count() == 0:
                self.page.keyboard.press("Escape")
                raise AssertionError(f"未找到操作系统下拉选项: {value}")
            option.click()
            self.page.wait_for_timeout(300)

    def _select_create_upload_method(self, dialog, upload_method: str):
        """选择新建镜像上传方式。"""
        method_item = dialog.locator(".el-form-item").filter(
            has=self.page.get_by_text("镜像上传方式", exact=True)
        )
        if method_item.count() == 0:
            raise AssertionError("未找到镜像上传方式表单项")
        method = method_item.get_by_text(upload_method, exact=True).first
        if method.count() == 0:
            raise AssertionError(f"未找到镜像上传方式: {upload_method}")
        method.click()
        logger.info(f"已选择镜像上传方式: {upload_method}")

    def _set_ims_advanced_checkbox(self, dialog, label_text: str, expected_checked: bool):
        """按创建镜像弹窗中的高级配置复选框文案设置勾选状态。"""
        checkbox = dialog.locator(".el-checkbox").filter(
            has=self.page.get_by_text(label_text, exact=True)
        ).first
        if checkbox.count() == 0:
            raise AssertionError(f"未找到高级配置复选框: {label_text}")

        def current_state():
            input_locator = checkbox.locator('input[type="checkbox"]').first
            if input_locator.count() > 0:
                return input_locator.is_checked(), input_locator.is_disabled()
            classes = checkbox.evaluate(
                """el => {
                    const parts = [el.className || ''];
                    el.querySelectorAll('*').forEach(child => parts.push(child.className || ''));
                    return parts.join(' ');
                }"""
            )
            return "is-checked" in classes, "is-disabled" in classes

        checked, disabled = current_state()
        if checked != expected_checked:
            if disabled:
                raise AssertionError(
                    f"高级配置 {label_text} 当前为 {checked} 且不可编辑，无法设置为 {expected_checked}"
                )
            target = checkbox.locator(".el-checkbox__input").first
            if target.count() > 0:
                target.click()
            else:
                checkbox.click()
            self.page.wait_for_timeout(200)
            checked, _ = current_state()

        assert checked == expected_checked, (
            f"高级配置 {label_text} 勾选状态不符合预期 | 期望: {expected_checked} | 实际: {checked}"
        )
        logger.info(f"高级配置 {label_text} 勾选状态: {checked}")

    def ims_configure_advanced_options(
        self,
        confidential_image: bool = False,
        hygon_feature: bool = False,
        confidential_memory: bool = False,
        protected: bool = False,
        multi_queue: bool = True,
    ):
        """设置并校验新建镜像第一步高级配置。

        默认值对应标准上传截图：仅开启网卡多队列，其余高级项关闭。
        """
        dialog = self._ims_create_dialog()
        self._set_ims_advanced_checkbox(dialog, "机密镜像", confidential_image)
        self._set_ims_advanced_checkbox(dialog, "海光特性", hygon_feature)
        self._set_ims_advanced_checkbox(dialog, "机密内存", confidential_memory)
        self._set_ims_advanced_checkbox(dialog, "是否受保护", protected)
        self._set_ims_advanced_checkbox(dialog, "网卡多队列", multi_queue)

    def ims_create_private_image(
        self,
        name: str,
        image_type: str = "云服务器",
        cpu_arch: str = "x86_64",
        os_type: str = "linux",
        version: str = "centos7.9",
        arch: str = "64位",
        storage_pool: str | None = None,
        boot_type: str = "Legacy",
        upload_method: str = "标准上传",
        advanced_options: dict | None = None,
    ):
        """填写新建镜像第一步基础信息。

        对应页面步骤 1：填写基础信息。默认按截图中的云服务器、x86_64、
        linux/centos7.9/64位、Legacy、高级配置默认项、标准上传填写。
        """
        logger.info(f"填写新建镜像基础信息: {name}")
        dialog = self._ims_create_dialog()
        storage_pool = storage_pool or self.storage_pool

        name_input = dialog.locator(".el-form-item").filter(
            has=self.page.get_by_text("镜像名称", exact=True)
        ).get_by_role("textbox").first
        if name_input.count() > 0:
            name_input.fill(name)
        else:
            dialog.get_by_placeholder("请输入名称").fill(name)

        self._select_dialog_dropdown(dialog, "镜像类型", image_type)
        self._select_dialog_dropdown(dialog, "架构", cpu_arch)
        self._select_os_triplet(dialog, os_type, version, arch)
        self._select_dialog_dropdown(dialog, "存储池", storage_pool)
        self._select_dialog_dropdown(dialog, "启动类型", boot_type)
        self.ims_configure_advanced_options(**(advanced_options or {}))
        self._select_create_upload_method(dialog, upload_method)

        logger.info(
            "新建镜像基础信息填写完成: "
            f"name={name}, type={image_type}, arch={cpu_arch}, os={os_type}/{version}/{arch}, "
            f"storage_pool={storage_pool}, boot_type={boot_type}, upload_method={upload_method}"
        )

    def ims_upload_click_next(self):
        """新建镜像第一步填写完成后点击下一步，进入上传镜像文件页。"""
        dialog = self._ims_create_dialog()
        next_btn = dialog.locator(".cloud-button-btn, .el-button").filter(
            has=self.page.get_by_text("下一步", exact=True)
        ).first
        if next_btn.count() == 0:
            raise AssertionError("未找到新建镜像对话框的下一步按钮")
        next_btn.click()
        self.page.locator(".el-dialog:visible").filter(
            has=self.page.get_by_text("上传镜像文件", exact=True)
        ).first.wait_for(state="visible", timeout=10000)
        # 等待第二步上传区域渲染完成，避免 file input 状态检测不到
        self.page.wait_for_timeout(1000)
        logger.info("已进入新建镜像第二步: 上传镜像文件")

    def ims_upload_image_file(self, local_image_path: str):
        """在新建镜像第二步选择本地镜像文件。"""
        dialog = self._ims_create_dialog()
        # 对话框刚切到第二步时 file input 可能尚未渲染，轮询等待
        deadline = time.time() + 10
        file_input = None
        while time.time() < deadline:
            file_input = dialog.locator('input[type="file"]').first
            if file_input.count() > 0:
                break
            file_input = dialog.locator(".el-upload__input").first
            if file_input.count() > 0:
                break
            self.page.wait_for_timeout(500)
        if not file_input or file_input.count() == 0:
            raise AssertionError("上传镜像文件页未找到 file input")
        file_input.set_input_files(local_image_path)
        self.page.wait_for_timeout(1500)
        logger.info(f"已选择上传镜像文件: {local_image_path}")

    def ims_wait_upload_file_status(self, status: str = "上传成功", timeout: int = 300):
        """等待新建镜像第二步的文件上传状态。

        Args:
            status: 期望状态文本，例如"上传中"、"上传成功"。
            timeout: 超时时间，单位秒。
        """
        logger.info(f"等待镜像文件上传状态: {status}")
        deadline = time.time() + timeout
        last_text = ""
        while time.time() < deadline:
            dialog = self._ims_create_dialog()
            # 只检查上传文件列表区域的状态文本，避免提示信息中的"上传失败"误报
            status_area = dialog.locator(
                ".uploader-list, .uploader-file-info, .el-upload-list"
            ).first
            if status_area.count() > 0:
                last_text = status_area.inner_text()
            else:
                last_text = dialog.inner_text()
            if status in last_text:
                logger.info(f"镜像文件上传状态已变为: {status}")
                return
            if status == "上传中" and "上传成功" in last_text:
                logger.info("镜像文件已直接上传成功，跳过上传中瞬时状态等待")
                return
            # 精确判断上传失败：状态区域出现"上传失败"且不再出现"上传中"
            if "上传失败" in last_text and "上传中" not in last_text:
                raise AssertionError(f"镜像文件上传失败: {last_text}")
            self.page.wait_for_timeout(1000)
        raise AssertionError(f"等待镜像文件上传状态超时 | 期望: {status} | 当前内容: {last_text}")

    def ims_upload_submit(self):
        """提交新建镜像标准上传。"""
        dialog = self._ims_create_dialog()
        confirm_btn = dialog.locator(".cloud-button-btn, .el-button").filter(
            has=self.page.get_by_text("确定", exact=True)
        ).first
        if confirm_btn.count() == 0:
            raise AssertionError("上传镜像文件页未找到确定按钮")
        confirm_btn.wait_for(state="visible", timeout=10000)
        for _ in range(60):
            class_name = confirm_btn.evaluate("el => el.className || ''")
            if "disabled" not in class_name:
                break
            self.page.wait_for_timeout(1000)
        else:
            raise AssertionError("上传镜像文件页确定按钮未在60秒内变为可点击")
        confirm_btn.click()
        # 等待新建镜像对话框关闭，避免遮挡后续页面操作
        dialog.wait_for(state="hidden", timeout=30000)
        logger.info("已提交新建镜像标准上传")

    # ---- 镜像导入相关方法 ----

    def ims_goto_service(self):
        """导航到镜像服务私有镜像页面。

        镜像服务在 190 环境下挂载于弹性云服务器服务内，正确 URL 形态为
        `/ecs/#/ecs-mirror-image`，因此需先进入 ECS 服务再切换左侧"镜像服务"子菜单，
        而不是直接映射到独立的 `/image` 路径。
        """
        self.goto_service("弹性云服务器")
        self.wait_for_page_ready()
        self.goto_submenu("镜像服务")
        self.wait_for_page_ready()
        logger.info(f"已导航到镜像服务私有镜像页: {self.page.url}")

    def ims_open_import_dialog(self):
        """点击导入镜像按钮打开导入对话框。"""
        logger.info("点击导入镜像按钮")
        # cl-button 自定义组件，使用 get_by_text 而非 get_by_role
        # 严格匹配以避免命中对话框标题（也是"导入镜像"）
        # 按钮是 cloud-button-btn 组件，对话框标题是 el-dialog__title
        self.page.locator(".cloud-button-btn, .el-button").filter(
            has=self.page.get_by_text("导入镜像", exact=True)
        ).first.click()
        # 等待对话框出现
        dialog = self.page.locator(".el-dialog:visible, .cv-dialog:visible").filter(has=self.page.get_by_text("导入镜像"))
        dialog.wait_for(state="visible", timeout=10000)
        logger.info("导入镜像对话框已打开")

    def ims_import_image(
        self,
        name,
        url,
        image_type="云服务器",
        os_type="linux",
        version="centos7.9",
        arch="64位",
        cpu_arch="x86_64",
        storage_pool=None,
        boot_type=None,
    ):
        """填写导入镜像表单，兼容两步向导（140环境）和单步（部分190环境）。

        Args:
            name: 镜像名称
            url: 镜像URL
            image_type: 镜像类型（默认"云服务器"）
            os_type: 操作系统类型（默认"linux"）
            version: 操作系统版本（默认"centos7.9"）
            arch: 操作系统位数（默认"64位"）
            cpu_arch: CPU架构（默认"x86_64"）
            storage_pool: 存储池（不传则使用页面默认值）
            boot_type: 启动类型（不传则使用页面默认值）
        """
        logger.info(f"导入镜像: {name}, URL: {url}")
        dialog = self.page.locator(".el-dialog:visible").filter(
            has=self.page.get_by_text("导入镜像", exact=True)
        ).first

        # 检测是否为两步向导（存在准备页）
        prepare_checkbox = dialog.locator(".prepare-checkbox").filter(has=self.page.get_by_text("我已做好以上准备"))
        if prepare_checkbox.count() > 0 and prepare_checkbox.is_visible():
            logger.info("检测到两步向导（准备页），执行Step1")
            # Step 1: 勾选准备复选框并点击下一步
            checkbox = prepare_checkbox.locator(".el-checkbox__input").first
            if checkbox.count() > 0 and not checkbox.locator(".is-checked").count() > 0:
                checkbox.click()
            # 点击下一步
            self.get_by_text("下一步").click()
            # 等待进入Step2
            self.page.wait_for_timeout(500)

        # Step 2: 填写表单
        logger.info("填写导入镜像表单")

        # 镜像URL
        url_input = dialog.locator(".el-form-item").filter(has=self.page.get_by_text("镜像URL", exact=True)).get_by_role("textbox").first
        if url_input.count() > 0:
            url_input.fill(url)
        else:
            # fallback: 直接找 placeholder="请输入镜像URL"
            dialog.get_by_placeholder("请输入镜像URL").fill(url)

        # 镜像名称
        name_input = dialog.locator(".el-form-item").filter(has=self.page.get_by_text("镜像名称", exact=True)).get_by_role("textbox").first
        if name_input.count() > 0:
            name_input.fill(name)
        else:
            dialog.get_by_placeholder("请输入名称").fill(name)

        # 镜像类型 - 下拉选择
        self._select_dialog_dropdown(dialog, "镜像类型", image_type)

        # 架构 - 下拉选择
        self._select_dialog_dropdown(dialog, "架构", cpu_arch)

        # 操作系统（三个字段在同一行，外层标签为"操作系统"）
        os_row = dialog.locator(".el-form-item").filter(has=self.page.get_by_text("操作系统", exact=True).first)
        if os_row.count() > 0:
            os_selects = os_row.locator(".el-select").all()
            if len(os_selects) >= 3:
                # OS类型 - 第1个select
                os_selects[0].click()
                self.page.wait_for_timeout(300)
                option = self.page.locator(".el-select-dropdown:visible").get_by_text(os_type, exact=True).first
                if option.count() == 0:
                    option = self.page.locator(".el-select-dropdown:visible").get_by_text(os_type).first
                if option.count() > 0:
                    option.click()
                    self.page.wait_for_timeout(300)
                else:
                    self.page.keyboard.press("Escape")
                # OS版本 - 第2个select
                os_selects[1].click()
                self.page.wait_for_timeout(300)
                option = self.page.locator(".el-select-dropdown:visible").get_by_text(version, exact=True).first
                if option.count() == 0:
                    option = self.page.locator(".el-select-dropdown:visible").get_by_text(version).first
                if option.count() > 0:
                    option.click()
                    self.page.wait_for_timeout(300)
                else:
                    self.page.keyboard.press("Escape")
                # OS位数 - 第3个select
                os_selects[2].click()
                self.page.wait_for_timeout(300)
                option = self.page.locator(".el-select-dropdown:visible").get_by_text(arch, exact=True).first
                if option.count() == 0:
                    option = self.page.locator(".el-select-dropdown:visible").get_by_text(arch).first
                if option.count() > 0:
                    option.click()
                    self.page.wait_for_timeout(300)
                else:
                    self.page.keyboard.press("Escape")
            else:
                logger.warning(f"操作系统区域只找到 {len(os_selects)} 个下拉框，预期3个")
        else:
            logger.warning("未找到操作系统的表单项")

        if storage_pool:
            self._select_dialog_dropdown(dialog, "存储池", storage_pool)

        if boot_type:
            self._select_dialog_dropdown(dialog, "启动类型", boot_type)

        logger.info(f"导入镜像表单填写完成: {name}")

    def _select_dialog_dropdown(self, dialog, label_text, value):
        """在对话框内选择下拉框选项。

        Args:
            dialog: 对话框 locator
            label_text: 下拉框标签文本
            value: 要选择的值
        """
        try:
            # 找到标签对应的下拉框
            form_item = dialog.locator(".el-form-item").filter(has=self.page.get_by_text(label_text, exact=True).first)
            if form_item.count() == 0:
                form_item = dialog.locator(".el-form-item").filter(has=self.page.get_by_text(label_text).first)

            if form_item.count() > 0:
                # 点击下拉框打开选项
                dropdown = form_item.locator(".el-select").first
                if dropdown.count() > 0:
                    dropdown.click()
                    self.page.wait_for_timeout(300)
                    # 选择选项
                    option = self.page.locator(".el-select-dropdown:visible").get_by_text(value, exact=True).first
                    if option.count() == 0:
                        option = self.page.locator(".el-select-dropdown:visible").get_by_text(value).first
                    if option.count() > 0:
                        option.click()
                        self.page.wait_for_timeout(300)
                    else:
                        # 如果没找到，按Escape关闭下拉框
                        self.page.keyboard.press("Escape")
                else:
                    logger.warning(f"未找到 {label_text} 的下拉框")
            else:
                logger.warning(f"未找到 {label_text} 的表单项")
        except Exception as e:
            logger.warning(f"选择 {label_text}={value} 失败: {e}")
            # 确保下拉框关闭
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass

    def ims_import_submit(self):
        """点击导入提交按钮。兼容"开始导入"和"确定"两种文案。"""
        logger.info("点击导入提交按钮")
        dialog = self.page.locator(".el-dialog:visible").filter(
            has=self.page.get_by_text("导入镜像", exact=True)
        ).first

        # 优先尝试"开始导入"
        submit_btn = dialog.get_by_text("开始导入", exact=True).first
        if submit_btn.count() == 0 or not submit_btn.is_visible():
            # fallback: "确定"
            submit_btn = dialog.get_by_text("确定", exact=True).first

        if submit_btn.count() > 0 and submit_btn.is_visible():
            submit_btn.click()
            logger.info("导入提交按钮已点击")
        else:
            raise AssertionError("未找到导入提交按钮（开始导入/确定）")

    def ims_to_detail(self, image_name):
        """点击镜像名称进入详情页。

        Args:
            image_name: 镜像名称
        """
        logger.info(f"进入镜像详情页: {image_name}")
        # 镜像详情页直接点击名称跳转，无需切换页签
        self.goto_detail_page(image_name, tab_name=None)
        self.wait_for_page_ready()
        logger.info(f"已进入镜像详情页: {image_name}")

    def ims_get_detail_info(self):
        """获取镜像详情页基本信息。

        Returns:
            dict: 包含名称、UUID、类型、OS类型、OS版本、位数、架构、共享模式、状态等字段
        """
        logger.info("获取镜像详情信息")
        self.wait_for_page_ready()

        # 详情页使用 cloud-item-col / cloud-item-label / cloud-item-content 组件
        detail_data = self.page.evaluate("""
            () => {
                const result = {};
                const items = document.querySelectorAll('.cloud-item-col');
                items.forEach(item => {
                    const labelEl = item.querySelector('.cloud-item-label');
                    const valueEl = item.querySelector('.cloud-item-content');
                    if (!labelEl || !valueEl) return;
                    let label = labelEl.textContent.trim();
                    const value = valueEl.textContent.trim();
                    if (label && value) {
                        // 统一 key：页面显示"镜像名称"，测试代码使用"名称"
                        if (label === '镜像名称') label = '名称';
                        result[label] = value;
                    }
                });
                return result;
            }
        """)

        # 兜底：关键字段缺失时用 HTML 正则解析
        if not detail_data or "名称" not in detail_data:
            page_content = self.page.content()
            detail_data = self._parse_detail_page(page_content)

        logger.info(f"镜像详情: {detail_data}")
        return detail_data

    def _parse_detail_page(self, page_content):
        """从页面HTML内容解析详情页字段。"""
        result = {}

        # 名称
        name_match = re.search(r'镜像名称.*?<span[^>]*>(.*?)</span>', page_content, re.DOTALL)
        if name_match:
            result["名称"] = re.sub(r'<[^>]+>', '', name_match.group(1)).strip()

        # UUID
        uuid_match = re.search(r'UUID.*?<span[^>]*>([a-f0-9-]{36})</span>', page_content, re.DOTALL)
        if uuid_match:
            result["UUID"] = uuid_match.group(1)

        # 状态
        status_match = re.search(r'状态.*?(可用|创建中|未知|错误|删除)', page_content, re.DOTALL)
        if status_match:
            result["状态"] = status_match.group(1)

        # 操作系统类型
        os_type_match = re.search(r'操作系统类型.*?<span[^>]*>(.*?)</span>', page_content, re.DOTALL)
        if os_type_match:
            result["操作系统类型"] = re.sub(r'<[^>]+>', '', os_type_match.group(1)).strip()

        # 操作系统版本
        os_ver_match = re.search(r'操作系统版本.*?<span[^>]*>(.*?)</span>', page_content, re.DOTALL)
        if os_ver_match:
            result["操作系统版本"] = re.sub(r'<[^>]+>', '', os_ver_match.group(1)).strip()

        # 操作系统位数
        os_bits_match = re.search(r'操作系统位数.*?<span[^>]*>(\d+位)</span>', page_content, re.DOTALL)
        if os_bits_match:
            result["操作系统位数"] = os_bits_match.group(1)

        # 架构
        arch_match = re.search(r'架构.*?<span[^>]*>(x86_64|aarch64)</span>', page_content, re.DOTALL)
        if arch_match:
            result["架构"] = arch_match.group(1)

        # 镜像类型
        type_match = re.search(r'镜像类型.*?<span[^>]*>(.*?)</span>', page_content, re.DOTALL)
        if type_match:
            result["镜像类型"] = re.sub(r'<[^>]+>', '', type_match.group(1)).strip()

        # 镜像格式
        format_match = re.search(r'镜像格式.*?<span[^>]*>(.*?)</span>', page_content, re.DOTALL)
        if format_match:
            result["镜像格式"] = re.sub(r'<[^>]+>', '', format_match.group(1)).strip()

        # 容量
        capacity_match = re.search(
            r'容量.*?<span[^>]*>(\d+(?:\.\d+)?\s*(?:MiB|GiB|MB|GB))</span>',
            page_content,
            re.DOTALL,
        )
        if capacity_match:
            result["容量"] = capacity_match.group(1).strip()

        # 共享模式
        mode_match = re.search(r'共享模式.*?<span[^>]*>(.*?)</span>', page_content, re.DOTALL)
        if mode_match:
            result["共享模式"] = re.sub(r'<[^>]+>', '', mode_match.group(1)).strip()

        # 启动类型
        boot_match = re.search(r'启动类型.*?<span[^>]*>(.*?)</span>', page_content, re.DOTALL)
        if boot_match:
            result["启动类型"] = re.sub(r'<[^>]+>', '', boot_match.group(1)).strip()

        # 最小磁盘大小
        min_disk_match = re.search(r'最小磁盘大小.*?<span[^>]*>(.*?)</span>', page_content, re.DOTALL)
        if min_disk_match:
            result["最小磁盘大小"] = re.sub(r'<[^>]+>', '', min_disk_match.group(1)).strip()

        # 高级配置
        for field in [
            "机密镜像",
            "加密引擎",
            "密钥类型",
            "密钥UUID",
            "海光特性",
            "机密内存",
            "是否受保护",
            "网卡多队列",
        ]:
            match = re.search(fr'{field}.*?<span[^>]*>(.*?)</span>', page_content, re.DOTALL)
            if match:
                result[field] = re.sub(r'<[^>]+>', '', match.group(1)).strip()

        return result

    # ---- 镜像修改相关方法 ----

    @submenu("镜像服务")
    def ims_open_modify_dialog(self, image_name: str):
        """点击修改按钮打开镜像修改对话框。

        Args:
            image_name: 要修改的镜像名称
        """
        logger.info(f"打开镜像修改对话框: {image_name}")
        self.click_action(image_name, "修改")
        # 等待修改对话框出现（标题为"修改"）
        dialog = self.page.locator(".el-dialog:visible, .cv-dialog:visible").filter(
            has=self.page.get_by_text("修改", exact=True)
        ).first
        dialog.wait_for(state="visible", timeout=10000)
        logger.info("镜像修改对话框已打开")

    def ims_has_action(self, image_name: str, action_text: str) -> bool:
        """判断镜像列表行是否存在指定操作入口。"""
        try:
            row = self.get_row_by_name(image_name)
            interactive_row = self._get_interactive_row(row)
            flat_action = interactive_row.get_by_text(action_text, exact=True)
            for i in range(flat_action.count()):
                action = flat_action.nth(i)
                if action.is_visible():
                    return True

            operation_btn = self._btn_operation(image_name)
            operation_btn.hover()
            self.page.wait_for_timeout(500)
            for selector in ['[id^="dropdown-menu-"]', '[class^="cloud-table-dropdown"]']:
                menus = self.page.locator(selector)
                for i in range(menus.count() - 1, -1, -1):
                    menu = menus.nth(i)
                    if not menu.is_visible():
                        continue
                    if menu.get_by_text(action_text, exact=True).count() > 0:
                        self.page.keyboard.press("Escape")
                        return True
            self.page.keyboard.press("Escape")
            return False
        except Exception as exc:
            logger.warning(f"检查镜像操作入口失败: image={image_name}, action={action_text}, error={exc}")
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
            return False

    def ims_click_action_if_available(self, image_name: str, action_text: str) -> bool:
        """指定镜像操作存在时点击，缺失时返回 False 供用例 skip。"""
        if not self.ims_has_action(image_name, action_text):
            return False
        self.click_action(image_name, action_text)
        self.page.locator(".el-dialog:visible, .cv-dialog:visible").first.wait_for(
            state="visible",
            timeout=10000,
        )
        logger.info(f"已打开镜像操作弹窗: image={image_name}, action={action_text}")
        return True

    def ims_set_share_mode(self, share_mode: str, count: int = 0) -> list[str]:
        """在设置共享模式弹窗中选择共享模式。

        兼容两种UI结构：
        1. el-select 下拉框（常见）
        2. el-radio / el-radio-button（备用）

        Args:
            share_mode: 共享模式文案，如"不共享""全局共享""指定共享"。
            count: 指定共享时需要选择的项目数量；非指定共享忽略。

        Returns:
            已选择的项目名称列表；非指定共享返回空列表。
        """
        dialog = self.page.locator(".el-dialog:visible, .cv-dialog:visible").filter(
            has=self.page.get_by_text("共享模式")
        ).first
        dialog.wait_for(state="visible", timeout=10000)

        # 方案1：尝试 el-select 下拉框结构
        select_row = dialog.locator(".el-form-item").filter(
            has=self.page.get_by_text("共享模式", exact=True)
        )
        if select_row.count() > 0:
            select_trigger = select_row.locator(".el-select").first
            if select_trigger.count() > 0 and select_trigger.is_visible():
                # 点击下拉框触发器
                select_trigger.click()
                self.page.wait_for_timeout(300)
                # 在下拉选项中选择
                option = self.page.locator(".el-select-dropdown:visible").get_by_text(
                    share_mode, exact=True
                ).first
                if option.count() == 0:
                    option = self.page.locator(".el-select-dropdown:visible").get_by_text(
                        share_mode
                    ).first
                if option.count() > 0:
                    option.click()
                    self.page.wait_for_timeout(300)
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(200)
                    logger.info(f"已选择镜像共享模式(下拉框): {share_mode}")
                else:
                    self.page.keyboard.press("Escape")
                    raise AssertionError(f"设置共享模式弹窗下拉选项未找到: {share_mode}")
                # 指定共享需要额外选择项目
                if share_mode == "指定共享" and count > 0:
                    return self._ims_select_share_projects(dialog, count)
                return []

        # 方案2：回退到 radio / el-radio-button 结构
        mode_option = dialog.locator(".el-radio, .el-radio-button, label").filter(
            has=self.page.get_by_text(share_mode, exact=True)
        ).first
        if mode_option.count() == 0:
            mode_option = dialog.get_by_text(share_mode, exact=True).first
        if mode_option.count() == 0:
            raise AssertionError(f"设置共享模式弹窗未找到选项: {share_mode}")

        mode_option.click()
        self.page.wait_for_timeout(300)
        logger.info(f"已选择镜像共享模式(radio): {share_mode}")

        if share_mode != "指定共享" or count <= 0:
            return []
        return self._ims_select_share_projects(dialog, count)

    def _ims_select_share_projects(self, dialog, count: int) -> list[str]:
        """在指定共享模式下选择项目。"""
        selected_projects: list[str] = []
        project_items = dialog.locator(
            ".el-checkbox:not(.is-disabled), .el-transfer-panel__item:not(.is-disabled)"
        )
        for i in range(project_items.count()):
            if len(selected_projects) >= count:
                break
            item = project_items.nth(i)
            text = item.inner_text().strip()
            if not text or text in selected_projects:
                continue
            input_locator = item.locator('input[type="checkbox"]').first
            checked = input_locator.count() > 0 and input_locator.is_checked()
            if not checked:
                item.click()
                self.page.wait_for_timeout(200)
            selected_projects.append(text)
        logger.info(f"已选择指定共享项目: {selected_projects}")
        return selected_projects

    def ims_set_protected(self, protected: bool):
        """在镜像修改弹窗中设置高级配置"是否受保护"。"""
        dialog = self.page.locator(".el-dialog:visible, .cv-dialog:visible").filter(
            has=self.page.get_by_text("修改", exact=True)
        ).first
        dialog.wait_for(state="visible", timeout=10000)
        self._set_ims_advanced_checkbox(dialog, "是否受保护", protected)
        logger.info(f"镜像是否受保护已设置为: {protected}")

    def ims_is_delete_disabled(self, image_name: str) -> bool:
        """判断镜像行"更多"菜单中的删除操作是否置灰。"""
        row = self.get_row_by_name(image_name)
        interactive_row = self._get_interactive_row(row)

        flat_delete = interactive_row.get_by_text("删除", exact=True)
        for i in range(flat_delete.count()):
            option = flat_delete.nth(i)
            if not option.is_visible():
                continue
            disabled = option.evaluate(
                """el => {
                    const disabledAncestor = el.closest(
                        '.is-disabled, .disabled, [disabled], [aria-disabled="true"]'
                    );
                    return Boolean(disabledAncestor)
                        || el.classList.contains('is-disabled')
                        || el.getAttribute('aria-disabled') === 'true'
                        || el.hasAttribute('disabled');
                }"""
            )
            logger.info(f"镜像删除平铺操作置灰状态: image={image_name}, disabled={disabled}")
            return bool(disabled)

        operation_btn = self._btn_operation(image_name)
        operation_btn.hover()
        self.page.wait_for_timeout(500)
        last_found = False
        for selector in ['[id^="dropdown-menu-"]', '[class^="cloud-table-dropdown"]']:
            menus = self.page.locator(selector)
            for i in range(menus.count() - 1, -1, -1):
                menu = menus.nth(i)
                if not menu.is_visible():
                    continue
                delete_option = menu.get_by_text("删除", exact=True).first
                if delete_option.count() == 0:
                    continue
                last_found = True
                disabled = delete_option.evaluate(
                    """el => {
                        const disabledAncestor = el.closest(
                            '.is-disabled, .disabled, [disabled], [aria-disabled="true"]'
                        );
                        return Boolean(disabledAncestor)
                            || el.classList.contains('is-disabled')
                            || el.getAttribute('aria-disabled') === 'true'
                            || el.hasAttribute('disabled');
                    }"""
                )
                self.page.keyboard.press("Escape")
                logger.info(f"镜像删除下拉操作置灰状态: image={image_name}, disabled={disabled}")
                return bool(disabled)

        self.page.keyboard.press("Escape")
        if last_found:
            return False
        raise AssertionError(f"未找到镜像删除操作: {image_name}")

    def ims_modify_image_name(self, new_name: str):
        """在修改对话框中修改镜像名称。

        Args:
            new_name: 新的镜像名称
        """
        logger.info(f"修改镜像名称为: {new_name}")
        dialog = self.page.locator(".el-dialog:visible").filter(
            has=self.page.get_by_text("修改", exact=True)
        ).first
        # 镜像名称输入框
        name_input = dialog.locator(".el-form-item").filter(
            has=self.page.get_by_text("镜像名称", exact=True)
        ).get_by_role("textbox").first
        if name_input.count() > 0:
            name_input.fill(new_name)
        else:
            dialog.get_by_placeholder("请输入名称").fill(new_name)
        logger.info(f"镜像名称已填写: {new_name}")

    def ims_modify_architecture(self, arch: str):
        """在修改对话框中修改镜像架构。

        修改架构为 aarch64 时，启动类型会自动变为 uefi。

        Args:
            arch: 架构值，如 "x86_64" 或 "aarch64"
        """
        logger.info(f"修改镜像架构为: {arch}")
        dialog = self.page.locator(".el-dialog:visible").filter(
            has=self.page.get_by_text("修改", exact=True)
        ).first
        self._select_dialog_dropdown(dialog, "架构", arch)
        logger.info(f"架构已选择: {arch}")

    def ims_modify_os_version(self, os_type: str, version: str, bits: str = None):
        """在修改对话框中修改操作系统信息。

        修改对话框中操作系统类型/版本/位数三个字段在同一行，外层 label 为"操作系统"，
        内层三个 el-select 无独立 label，需按 DOM 顺序依次选择。

        Args:
            os_type: 操作系统类型，如 "linux" 或 "windows"
            version: 操作系统版本，如 "centos7.9" 或 "麒麟v10"
            bits: 操作系统位数，如 "64位"（可选）
        """
        logger.info(f"修改操作系统: type={os_type}, version={version}, bits={bits}")
        dialog = self.page.locator(".el-dialog:visible").filter(
            has=self.page.get_by_text("修改", exact=True)
        ).first

        # 操作系统三个字段在同一行，外层 label 为"操作系统"
        os_row = dialog.locator(".el-form-item").filter(
            has=self.page.get_by_text("操作系统", exact=True).first
        )
        if os_row.count() == 0:
            raise AssertionError("未找到操作系统表单项")

        selects = os_row.locator(".el-select").all()
        if len(selects) < 3:
            raise AssertionError(f"操作系统区域只找到 {len(selects)} 个下拉框，预期3个")

        # 1. 操作系统类型
        selects[0].click()
        self.page.wait_for_timeout(300)
        option = self.page.locator(".el-select-dropdown:visible").get_by_text(os_type, exact=True).first
        if option.count() == 0:
            option = self.page.locator(".el-select-dropdown:visible").get_by_text(os_type).first
        if option.count() > 0:
            option.click()
            self.page.wait_for_timeout(300)
        else:
            self.page.keyboard.press("Escape")

        # 2. 操作系统版本（切换 os_type 后会重新加载版本列表，需多等一下）
        selects[1].click()
        self.page.wait_for_timeout(800)
        option = self.page.locator(".el-select-dropdown:visible").get_by_text(version, exact=True).first
        if option.count() == 0:
            option = self.page.locator(".el-select-dropdown:visible").get_by_text(version).first
        if option.count() > 0:
            option.click()
            self.page.wait_for_timeout(300)
        else:
            self.page.keyboard.press("Escape")

        # 3. 操作系统位数（如果提供）
        if bits:
            selects[2].click()
            self.page.wait_for_timeout(300)
            option = self.page.locator(".el-select-dropdown:visible").get_by_text(bits, exact=True).first
            if option.count() == 0:
                option = self.page.locator(".el-select-dropdown:visible").get_by_text(bits).first
            if option.count() > 0:
                option.click()
                self.page.wait_for_timeout(300)
            else:
                self.page.keyboard.press("Escape")

        logger.info("操作系统信息已修改")

    def ims_modify_submit(self):
        """点击修改对话框的确定按钮提交修改。"""
        logger.info("点击修改提交按钮")
        dialog = self.page.locator(".el-dialog:visible").filter(
            has=self.page.get_by_text("修改", exact=True)
        ).first
        # 确定按钮 - cl-button 自定义组件，使用 get_by_text 而非 get_by_role
        confirm_btn = dialog.get_by_text("确定", exact=True).first
        if confirm_btn.count() > 0 and confirm_btn.is_visible():
            confirm_btn.click()
            logger.info("修改提交按钮已点击")
        else:
            raise AssertionError("未找到修改对话框的确定按钮")

    def ims_get_row_data(self, image_name: str) -> dict:
        """获取镜像列表中指定行的数据。

        Args:
            image_name: 镜像名称

        Returns:
            dict: 行数据字典
        """
        logger.info(f"获取镜像行数据: {image_name}")
        return self.get_row_data(image_name)

    # ---- 镜像详情页存储池页签相关方法 ----

    def _active_tab_root(self):
        """返回当前激活页签容器，没有页签时回退到主内容区。"""
        candidates = [
            self.locator(".el-tab-pane[aria-hidden='false']:visible").first,
            self.locator(".el-tab-pane:not([aria-hidden='true']):visible").first,
            self.locator(".el-tabs__content .el-tab-pane:visible").first,
            self.locator("#cloud-container-content").first,
        ]
        for candidate in candidates:
            try:
                if candidate.count() > 0 and candidate.is_visible():
                    return candidate
            except Exception:
                continue
        return self.locator("#cloud-container-content").first

    def ims_click_storage_pool_tab(self):
        """进入镜像详情页的存储池页签。"""
        logger.info("切换到镜像详情页存储池页签")
        # 先等待页签容器出现
        tabs_container = self.page.locator(".el-tabs__header, .el-tabs__nav").first
        try:
            tabs_container.wait_for(state="visible", timeout=10000)
        except Exception:
            logger.warning("等待页签容器超时，继续尝试查找存储池页签")

        tab = self.get_by_role("tab", name="存储池", exact=True).first
        if tab.count() == 0:
            tab = self.locator(".el-tabs__item").filter(
                has=self.page.get_by_text("存储池", exact=True)
            ).first
        if tab.count() == 0:
            # 回退：尝试非精确匹配
            tab = self.get_by_role("tab", name=re.compile(r"存储池")).first
        if tab.count() == 0:
            raise AssertionError("未找到镜像详情页存储池页签")
        tab.click()
        self.wait_for_page_ready()
        self._active_tab_root().locator(".el-table__body-wrapper:visible").first.wait_for(
            state="visible",
            timeout=10000,
        )
        logger.info("已进入镜像详情页存储池页签")

    def _ims_storage_pool_rows(self) -> list[dict]:
        """读取当前存储池页签的所有行数据。"""
        root = self._active_tab_root()
        rows = root.locator(".el-table__body-wrapper:visible tr").all()
        result = []
        for row in rows:
            try:
                row_data = self.get_row_data_by_locator(row)
                if row_data:
                    result.append(row_data)
            except Exception as exc:
                logger.debug(f"读取存储池行失败: {exc}")
        logger.info(f"镜像详情存储池行数据: {result}")
        return result

    def _ims_pool_name_from_row(self, row: dict) -> str:
        """兼容不同表头名称获取存储池名称。"""
        return (
            row.get("存储池名称")
            or row.get("名称")
            or row.get("存储池")
            or row.get("后端存储")
            or ""
        )

    def ims_get_pool_info(self, pool_name: str) -> dict:
        """获取镜像详情页指定存储池行信息。"""
        for row in self._ims_storage_pool_rows():
            if self._ims_pool_name_from_row(row) == pool_name:
                logger.info(f"找到存储池 {pool_name}: {row}")
                return row
        raise AssertionError(f"未找到存储池行: {pool_name}")

    def _ims_sync_pool_dialog(self):
        """返回同步存储池弹窗。"""
        dialog = self.page.locator(".el-dialog:visible, .cv-dialog:visible").filter(
            has=self.page.get_by_text("同步存储池")
        ).first
        if dialog.count() == 0:
            dialog = self.page.locator(".el-dialog:visible, .cv-dialog:visible").filter(
                has=self.page.get_by_text("存储池", exact=True)
            ).first
        dialog.wait_for(state="visible", timeout=10000)
        return dialog

    def _ims_split_pool_names(self, pool_text) -> set[str]:
        """把列表中的存储池展示文本拆成名称集合。"""
        if isinstance(pool_text, (list, tuple, set)):
            raw_text = " ".join(str(item) for item in pool_text)
        else:
            raw_text = str(pool_text or "")
        names = set()
        for part in re.split(r"[,，、\s]+", raw_text):
            part = part.strip()
            if part and part not in {"-", "--"}:
                names.add(part)
        return names

    def _ims_open_sync_pool_dropdown(self):
        """打开同步存储池弹窗里的存储池下拉框。"""
        dialog = self._ims_sync_pool_dialog()
        form_item = dialog.locator(".el-form-item").filter(
            has=self.page.get_by_text("存储池", exact=True).first
        ).first
        root = form_item if form_item.count() > 0 else dialog
        dropdown = root.locator(".el-select").first
        if dropdown.count() == 0:
            dropdown = root.locator(".el-input, input").first
        if dropdown.count() == 0:
            raise AssertionError("同步存储池弹窗未找到存储池下拉框")
        dropdown.click()
        self.page.wait_for_timeout(300)

    def _ims_sync_pool_options(self) -> list[str]:
        """读取同步存储池下拉框当前可选项。"""
        options = []
        option_locators = self.page.locator(
            ".el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)"
        ).all()
        for option in option_locators:
            text = option.inner_text().strip()
            if text and text not in {"请选择", "无数据"}:
                options.append(text)
        logger.info(f"同步存储池可选项: {options}")
        return options

    def ims_get_another_storage_pool(self, original_pools: str = "") -> str:
        """从同步存储池弹窗中获取一个未在镜像当前存储池列表里的可选存储池。"""
        existed = self._ims_split_pool_names(original_pools)
        self._ims_open_sync_pool_dropdown()
        options = self._ims_sync_pool_options()
        self.page.keyboard.press("Escape")
        for option in options:
            if option not in existed:
                logger.info(f"选择待同步的新存储池: {option}")
                return option
        if options:
            logger.info(f"未找到非当前存储池，使用第一个可选存储池: {options[0]}")
            return options[0]
        raise AssertionError(f"同步存储池弹窗没有可选存储池 | 当前存储池: {original_pools}")

    def ims_select_storage_pool(self, pool_name: str | None = None, exclude_pools=None) -> str:
        """在同步存储池弹窗中选择存储池。

        pool_name 为空时选择列表中第一个不在 exclude_pools 内的可选项。
        """
        excluded = self._ims_split_pool_names(exclude_pools)
        self._ims_open_sync_pool_dropdown()
        options = self._ims_sync_pool_options()
        target_pool = pool_name
        if not target_pool:
            for option in options:
                if option not in excluded:
                    target_pool = option
                    break
            if not target_pool and options:
                target_pool = options[0]
        if not target_pool:
            self.page.keyboard.press("Escape")
            raise AssertionError(f"同步存储池弹窗没有可选存储池 | 排除项: {excluded}")

        option = self.page.locator(
            ".el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)"
        ).get_by_text(target_pool, exact=True).first
        if option.count() == 0:
            option = self.page.locator(
                ".el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)"
            ).get_by_text(target_pool).first
        if option.count() == 0:
            self.page.keyboard.press("Escape")
            raise AssertionError(f"同步存储池弹窗未找到存储池选项: {target_pool} | 可选项: {options}")
        option.click()
        self.page.wait_for_timeout(300)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(200)
        logger.info(f"已选择同步存储池: {target_pool}")
        return target_pool

    def ims_wait_for_pool_sync(self, pool_name: str, timeout: int = 300):
        """等待镜像同步到指定存储池，表现为该存储池状态可用且 Hash 已生成。"""
        self.ims_click_storage_pool_tab()
        self.ims_wait_for_pool_hash_sync(pool_name, timeout=timeout)

    def ims_wait_for_pool_appeared(self, pool_name: str, timeout: int = 60) -> dict:
        """等待目标存储池出现在镜像详情页存储池页签。"""
        logger.info(f"等待目标存储池出现在详情页: {pool_name}")
        deadline = time.time() + timeout
        last_rows = []
        while time.time() < deadline:
            try:
                row = self.ims_get_pool_info(pool_name)
                logger.info(f"目标存储池已出现: {row}")
                return row
            except AssertionError:
                last_rows = self._ims_storage_pool_rows()
                self.page.wait_for_timeout(3000)
                self.ims_page_reload()
                self.ims_click_storage_pool_tab()
        raise AssertionError(f"等待目标存储池出现超时 | 存储池: {pool_name} | 最后行: {last_rows}")

    def ims_wait_for_pool_progress(self, pool_name: str, progress: str = "100%", timeout: int = 300) -> dict:
        """等待目标存储池同步进度达到指定值。

        如果页面刷新时同步已经完成且 Hash 已生成，也返回当前行，避免小镜像同步过快导致误报。
        """
        logger.info(f"等待存储池 {pool_name} 同步进度达到 {progress}")
        deadline = time.time() + timeout
        last_row = {}
        while time.time() < deadline:
            last_row = self.ims_get_pool_info(pool_name)
            current_progress = (last_row.get("进度") or "").strip()
            hash_value = (last_row.get("Hash") or last_row.get("Hash值") or "").strip()
            if current_progress == progress or hash_value not in ["", "-", "--"]:
                logger.info(f"存储池同步进度满足预期: {last_row}")
                return last_row
            self.page.wait_for_timeout(5000)
            self.ims_page_reload()
            self.ims_click_storage_pool_tab()
        raise AssertionError(
            f"等待存储池同步进度超时 | 存储池: {pool_name} | 期望进度: {progress} | 最后一行: {last_row}"
        )

    def ims_get_pool_without_hash(self) -> dict:
        """获取 Hash 为空的存储池行。"""
        for row in self._ims_storage_pool_rows():
            hash_value = (row.get("Hash") or row.get("Hash值") or "").strip()
            if hash_value in ["", "-", "--"]:
                logger.info(f"找到无 Hash 存储池: {row}")
                return row
        return {}

    def ims_get_metadata_pool_info(self) -> dict:
        """获取镜像详情页中元数据存储池为"是"的存储池行。"""
        for row in self._ims_storage_pool_rows():
            metadata_flag = (
                row.get("元数据存储池")
                or row.get("是否元数据存储池")
                or row.get("元数据")
                or ""
            ).strip()
            if metadata_flag == "是":
                logger.info(f"找到元数据存储池: {row}")
                return row
        raise AssertionError(f"未找到元数据存储池为'是'的行: {self._ims_storage_pool_rows()}")

    def ims_get_non_metadata_pool_info(self) -> dict:
        """获取镜像详情页中元数据存储池为"否"的存储池行。"""
        for row in self._ims_storage_pool_rows():
            metadata_flag = (
                row.get("元数据存储池")
                or row.get("是否元数据存储池")
                or row.get("元数据")
                or ""
            ).strip()
            if metadata_flag == "否":
                logger.info(f"找到非元数据存储池: {row}")
                return row
        raise AssertionError(f"未找到元数据存储池为'否'的行: {self._ims_storage_pool_rows()}")

    def ims_get_default_pool(self) -> str:
        """获取当前元数据存储池名称。"""
        return self._ims_pool_name_from_row(self.ims_get_metadata_pool_info())

    def ims_get_storage_pool_rows(self) -> list[dict]:
        """获取镜像详情页存储池页签全部行。"""
        return self._ims_storage_pool_rows()

    def ims_delete_metadata_pool_dialog(self):
        """返回删除元数据存储池时弹出的选择新存储池对话框。"""
        dialog = self.page.locator(".el-dialog:visible, .cv-dialog:visible").filter(
            has=self.page.get_by_text("删除", exact=True)
        ).first
        dialog.wait_for(state="visible", timeout=10000)
        text = dialog.inner_text()
        assert "元数据" in text and "存储池" in text, (
            f"[DialogAssertion] 删除元数据存储池弹窗内容不符合预期 | 实际内容: {text}"
        )
        return dialog

    def ims_select_new_default_pool(self, pool_name: str | None = None) -> str:
        """在删除元数据存储池弹窗中选择新的元数据存储池。"""
        dialog = self.ims_delete_metadata_pool_dialog()
        dropdown = dialog.locator(".el-select").first
        if dropdown.count() == 0:
            dropdown = dialog.locator(".el-input, input").first
        if dropdown.count() == 0:
            raise AssertionError("删除元数据存储池弹窗未找到存储池下拉框")
        dropdown.click()
        self.page.wait_for_timeout(300)

        option_root = self.page.locator(
            ".el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)"
        )
        options = [option.inner_text().strip() for option in option_root.all()]
        options = [option for option in options if option and option not in {"请选择存储池", "无数据"}]
        target_pool = pool_name or (options[0] if options else "")
        if not target_pool:
            self.page.keyboard.press("Escape")
            raise AssertionError(f"删除元数据存储池弹窗没有可选新存储池 | 可选项: {options}")

        option = option_root.get_by_text(target_pool, exact=True).first
        if option.count() == 0:
            option = option_root.get_by_text(target_pool).first
        if option.count() == 0:
            self.page.keyboard.press("Escape")
            raise AssertionError(f"删除元数据存储池弹窗未找到选项: {target_pool} | 可选项: {options}")
        option.click()
        self.page.wait_for_timeout(300)
        logger.info(f"已选择新的元数据存储池: {target_pool}")
        return target_pool

    def ims_wait_for_pool_hash_sync(self, pool_name: str, timeout: int = 300):
        """等待指定存储池 Hash 生成且状态可用。"""
        logger.info(f"等待存储池 {pool_name} Hash 同步完成")
        deadline = time.time() + timeout
        last_row = {}
        while time.time() < deadline:
            last_row = self.ims_get_pool_info(pool_name)
            hash_value = (last_row.get("Hash") or last_row.get("Hash值") or "").strip()
            status = last_row.get("状态", "")
            if hash_value not in ["", "-", "--"] and status == "可用":
                logger.info(f"存储池 {pool_name} Hash 已生成: {hash_value}")
                return
            self.page.wait_for_timeout(5000)
            self.ims_page_reload()
            self.ims_click_storage_pool_tab()
        raise AssertionError(
            f"等待存储池 Hash 生成超时 | 存储池: {pool_name} | 最后一行: {last_row}"
        )

    def ims_page_reload(self):
        """刷新当前镜像详情页。"""
        self.page.reload()
        self.wait_for_page_ready()
        # 等待页面内容渲染（详情页 Vue 渲染需要时间）
        self.page.wait_for_selector(
            ".el-tabs__item, .el-tabs__header, .el-tabs__nav, .el-table__body-wrapper",
            state="visible",
            timeout=15000,
        )

    def click_action_in_table(self, resource_name: str, option_text: str):
        """在当前表格行点击操作项。"""
        self.click_action(resource_name, option_text)
