import re
import time
from pathlib import Path
from time import sleep
import allure
import pytest
from playwright.sync_api import expect

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger

class EcsLifecycleMixin(BasePage):
    """ECS 生命周期与配置修改操作。"""
    @submenu("弹性云服务器")
    def ecs_remove(self, names):
        """回收云服务器资源，支持单个和批量操作

        Args:
            names: 云服务器名称（字符串）或云服务器名称列表（列表）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击更多操作按钮
            self.get_by_role("button", name="更多操作 ").click()

            # 点击批量删除选项
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_action(names, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成



    @submenu("弹性云服务器")
    def ecs_edit(self, name: str, newname: str):
        """修改指定云服务器名称
        Args:
            name: 云服务器名称
            newname: 新的云服务器名称
        """
        self.click_action(name, "编辑")
        self.get_by_role("textbox", name="请输入实例名称").fill(newname)
        self.dialog_confirm.click()
        logger.info(f"操作完成云服务器{name}: 编辑修改为{newname}")


    @submenu("弹性云服务器")
    def ecs_vnc(self, name: str, vncpwd: str = "sugon@20"):
        """登录VNC
        Args：
            name: 云服务器名称
            password: VNC登录密码
        """
        logger.info(f"云服务器{name}：登录VNC")

        # 使用 trigger_action 参数，确保 expect_page 在点击前开始监听
        with self.new_tab_context(trigger_action=lambda: self._trigger_instance_login(name, login_type="VNC")) as new_page:
            # 输入VNC密码并登录
            try:
                new_page.locator("#app iframe").content_frame.get_by_label("Password:").fill(vncpwd)
            except:
                new_page.locator("#app iframe").content_frame.get_by_label("密码：").fill(vncpwd)
            new_page.locator("#app iframe").content_frame.get_by_role("button", name="确认").click()
            loc = new_page.locator("#app iframe").content_frame.locator("canvas")
            expect(loc).to_be_visible(timeout=30000)
            # 保存截图到文件
            sleep(5)
            screenshot_dir = Path(__file__).resolve().parents[2] / "screenshots"
            screenshot_dir.mkdir(exist_ok=True)
            screenshot_vnc = screenshot_dir / f"{name}_{time.strftime('%Y%m%d%H%M%S')}.png"
            # 保存截图到文件
            loc.screenshot(path=str(screenshot_vnc))
            logger.info(f"截图保存成功: {screenshot_vnc}")

            # 将截图添加到 Allure 报告
            with open(screenshot_vnc, "rb") as f:
                allure.attach(
                    body=f.read(),
                    name=f"vnc截图_{name}",
                    attachment_type=allure.attachment_type.PNG
                )
            logger.info(f"云服务器{name}：VNC登录成功")


    def _trigger_instance_login(self, name: str, login_type: str = "VNC"):
        """触发实例登录并按需选择登录方式。

        当前登录弹窗可能包含 VNC、SSH 等多种方式。统一在这里处理，
        便于后续扩展其它登录入口，而不影响具体登录流程实现。
        """
        self.click_action(name, "登录")

        login_dialog = self.get_by_role("dialog", name="登录")
        expect(login_dialog).to_be_visible()

        if login_type:
            self.get_by_role("dialog").locator("div").filter(has_text=login_type).nth(3).click()
            logger.info(f"云服务器{name}：已选择登录方式 {login_type}")

        self.get_by_text("立即登录").click()

        # self.get_by_text("立即登录 取消").get_by_text("取消").click() # 手动关闭登录选择方式弹窗


    @submenu("弹性云服务器")
    def ecs_rebuild(self, name: str, image: str, pre_type: str = "精简置备"):
        """重建云主机并选择镜像。
            Args:
                name: 云服务器名称
                image: 镜像名称
                pre_type: 置备方式，默认精简置备
        """
        self.click_action(name, "重建云主机")
        self.page.wait_for_load_state("domcontentloaded")

        rebuild_dialog = self.locator("div[role='dialog'][aria-label='重建云主机']:visible")
        expect(rebuild_dialog).to_be_visible()
        mode_trigger = self._find_element(
            [
                self.locator("div").filter(has_text=re.compile(r"^置备方式精简置备厚置备$")).get_by_placeholder("请选择"),
                self.locator("form div").filter(has_text="置备方式精简置备厚置备 请选择置备方式").get_by_placeholder("请选择")],
            "重建云主机置备方式选择框",
            timeout=3000)
        mode_trigger.click()
        self.get_by_role("listitem").filter(has_text=pre_type).click()
        self._select_from_named_drawer(drawer_title="选择镜像", item_name=image, open_drawer=True)
        self.dialog_confirm.click()
        logger.info(f"重建云主机完成: {name}, 镜像: {image}")


    @submenu("弹性云服务器")
    def ecs_clone(self, name: str, clonename: str, net: str, subnet: str, encryption: dict, ipv6=False):
        """克隆云服务器
        Args：
            name: 云服务器名称
            clonename: 克隆名称
            net: 网络
            subnet: 子网
            ipv6: ipv6地址
            encryption: 加密盘：加密密钥

        """
        self.click_action(name, "克隆")
        # 输入克隆名称
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").click()
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(clonename)

        # 选择网络
        self.locator("//label[text()='网络']/following-sibling::div//input").click()
        self.get_by_text(net, exact=True).click()

        # 选择子网
        self.locator("form div").filter(has_text=f"子网").get_by_placeholder("请选择").click()
        self.get_by_text(f"{subnet}(10").click()

        # 分配ipv6地址
        try:
            self.get_by_role("textbox", name="请选择IPv6 地址").click()
            if ipv6:
                self.get_by_text("自动分配IPv6地址").click()
            else:
                self.get_by_text("暂不分配IPv6地址").click()
        except:
            pass

        # 选择密钥
        try:
            self.locator("label").filter(has_text="密钥").locator("span")
            if encryption and len(encryption) != 0:
                for key, value in encryption.items():
                    self.click_action(key, "选择密钥")
                    # 需补充选择密钥步骤
                    self.get_by_text(value).click()
                    self.dialog_confirm.click()
        except:
            pass
        # 点击确定 克隆
        self.dialog_confirm.click()
        logger.info(f"操作完成: 克隆云服务器{name}: 克隆名称{clonename}")


    @submenu("弹性云服务器")
    def ecs_operations(self, name: str, operation: str):
        """操作
        Args:
            name: 云服务器名称
            operation: 操作选项
        """
        try:
            self.click_action(name, operation)
        except  Exception as e:
            logger.error(f"云服务器{name}：{operation}失败")
            raise e
        if operation == "重启":
            self.get_by_text("重启 取消", exact=True).get_by_text("重启", exact=True).click()
        elif operation == "强制重启":
            self.get_by_text("强制重启 取消", exact=True).get_by_text("强制重启", exact=True).click()
        elif operation in ["恢复运行", "取消暂停"]:
            self.get_by_label(operation).get_by_text("确定", exact=True).click()
        else:
            self.dialog_confirm.click()
        logger.info(f"操作完成: {name}云服务器点击: {operation}")


    @submenu("弹性云服务器")
    def ecs_reset_state(self, name: str):
        """重置状态
        Args:
            name: 云服务器名称
        """
        try:
            self.click_action(name, "重置状态")
            self.dialog_confirm.click()
            logger.info(f"操作完成: 云服务器{name}点击重置状态")
        except Exception as e:
            logger.error(f"云服务器{name}：重置状态失败:{e}")
            raise e


    def ecs_recover(self, name: str):
        """恢复弹性云服务器
        Args:
            name: 云服务器名称
        """
        self.click_action(name, "恢复")
        self.get_by_label("恢复实例").get_by_text("确定", exact=True).click()
        logger.info(f"恢复弹性云服务器: {name}")

    @submenu("弹性云服务器")
    def ecs_modify_spec(self, name: str, spec: dict):
        """修改规格
        Args:
            name: 云服务器名称
            spec: {
                "type": "基础规格" | "自定义规格",  # 规格类型
                "classify": "计算型" | "通用型" | "内存型",  # 规格分类（仅基础规格需要）
                "CPU": "2",  # CPU核数
                "Mem": "4",  # 内存大小
                "flavor_name": "ecs.c6.xlarge"  # 规格名称（可选，用于精确匹配）
                "shutdown": False | True
            }
        """
        cpu = spec.get("CPU", "2")
        mem = spec.get("Mem", "4")
        spec_type = spec.get("spec_type")
        power_off = spec.get("shutdown", False)
        need_start = False

        try:
            if power_off:
                self.ecs_operations(name, "关机")
                self.assert_status(name, "关机")
                need_start = True  # 标记需要恢复开机

            self.click_action(name, "修改规格")
            if spec_type:
                classify = spec.get("classify", "计算型")
                flavor_name = spec.get("flavor_name")

                # 选择规格分类
                if classify:
                    self.get_by_text(classify).click()

                # 选择具体规格
                if flavor_name:
                    # 通过规格名称精确匹配
                    self.get_by_role("row").filter(has_text=flavor_name).get_by_role("radio").click()
                else:
                    # 通过CPU和内存模糊匹配
                    (self.get_by_role("row").filter(has_text=f"{cpu} 核")
                     .and_(self.get_by_role("row").filter(has_text=f"{mem}.00 GiB"))
                     .and_(self.get_by_role("row").filter(has_text=f"{classify[:-1]}标准"))
                     .get_by_role("radio").first.click())

                self.dialog_confirm.click()
                self.assert_popup_success("调整实例资源配置成功")
                logger.info(f"操作完成: 云服务器{name}修改规格为{classify} {cpu}核{mem}GiB")

            else:  # 自定义规格
                self.get_by_role("radio").filter(has_text="自定义规格").click()

                # 填写CPU和内存
                self.get_by_role("dialog", name="修改规格").get_by_role("textbox").nth(1).fill(cpu)
                self.get_by_role("dialog", name="修改规格").get_by_role("textbox").nth(2).fill(mem)

                # 点击确定按钮
                self.get_by_label("修改规格").get_by_text("确定").click()
                self.assert_popup_success("调整实例资源配置成功")
                logger.info(f"操作完成: 云服务器{name}修改自定义规格为{cpu}核{mem}GiB")

        except Exception as e:
            logger.error(f"云服务器{name}修改规格失败: {e}")
            raise e
        finally:
            if need_start:
                try:
                    self.ecs_operations(name, "启动")
                    self.assert_status(name)
                    logger.info(f"云服务器{name}已恢复开机")
                except Exception as e:
                    logger.error(f"云服务器{name}恢复开机失败: {e}")


    @submenu("弹性云服务器")
    def ecs_modify_pwd(self, name: str, pwd: str, confirm: str):
        """修改密码
        Args:
            name: 云服务器名称
            pwd: 密码
            confirm: 确认密码
        """
        self.click_action(name, "修改密码")
        try:
            self.locator("div").filter(has_text=re.compile(r"^密码$")).get_by_role("textbox").fill(pwd)
            self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(confirm)
            self.get_by_label("修改密码").get_by_text("确定").click()
            logger.info(f"操作完成: 云服务器{name}修改密码为{pwd}")
        except Exception as e:
            logger.info(f"云服务器{name}修改密码失败:{e}")
            raise e


    @submenu("弹性云服务器")
    def ecs_modify_vnc_pwd(self, name: str, vncpwd: str, confirmpwd: str):
        """修改vnc密码
        Args:
            name: 云服务器名称
            vncpwd: vnc密码
            confirmpwd: 确认vnc密码
        """
        self.click_action(name, "修改VNC密码")
        if not self.get_by_role("switch").locator("span").is_enabled():
            self.get_by_role("switch").locator("span").click()
        try:
            self.get_by_role("textbox", name="VNC密码最长为8位").fill(vncpwd)
            self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(confirmpwd)
            self.get_by_label("修改VNC密码").get_by_text("确定").click()
            logger.info(f"操作完成: 云服务器{name}修改VNC密码为{vncpwd}")
        except Exception as e:
            logger.info(f"云服务器{name}修改VNC密码失败:{e}")
            raise e


    @submenu("弹性云服务器")
    def ecs_modify_hostname(self, name: str, hostname: str):
        """修改主机名
        Args:
            name: 云服务器名称
            hostname: 主机名
        """
        self.click_action(name, "修改主机名")
        self.get_by_placeholder("请输入主机名称").fill(hostname)
        self.get_by_label("修改主机名").get_by_text("确定").click()
        logger.info(f"操作完成: 云服务器{name}修改主机名为{hostname}")


    @submenu("弹性云服务器")
    def ecs_time_synchronize(self, name: str, time_server: str, interval: str):
        """时钟同步
        Args:
            name: 云服务器名称
            time_server: 时间服务器
            interval: 同步间隔
        """
        self.click_action(name, "时间同步服务器")
        server_loc = self.get_by_role("textbox", name="例：10.0.13.24或*sugoncloud.")
        server_loc.clear()
        server_loc.fill(time_server)
        logger.info(f"弹性云服务器{name}时钟同步，同步间隔为{interval}秒")
        loc = self.get_by_label("时间同步服务器").locator("form div").filter(has_text="时间同步间隔(秒)").get_by_role(
            "textbox")
        loc.clear()  # 清空输入框默认数据
        loc.fill(interval)
        self.dialog_confirm.click()
        logger.info(f"操作完成: 云服务器{name}时钟同步，同步间隔为{interval}秒")


    @submenu("弹性云服务器")
    def ecs_modify_cpu_qos(self, name: str, priority: str = "低", ceiling: str = "0.2"):
        """修改云服务器CPU QoS

        Args:
            name: 云服务器名称
            priority: CPU QoS级别，默认为"低"
            ceiling: CPU权重值，默认为0.2
        """
        logger.info(f"开始修改云服务器{name}的CPU QoS: 级别={priority}, 权重={ceiling}")

        # 点击指定云服务器的操作按钮
        self.click_action(name, "修改CPU QoS")

        # 选择CPU QoS级别
        self.get_by_label("修改CPU QoS").get_by_placeholder("请选择").click()
        self.get_by_text(priority, exact=True).click()

        # 设置CPU权重
        self.get_by_label("修改CPU QoS").get_by_role("spinbutton").fill(ceiling)

        # 确认修改
        self.dialog_confirm.click()
        logger.info(f"云服务器{name}的CPU QoS修改请求已提交")


    @submenu("弹性云服务器")
    def ecs_modify_vnc_type(self, name: str, vnc_type: str = "VGA"):
        """修改云服务器VNC显卡类型

        Args:
            name: 云服务器名称
            vnc_type: VNC显卡类型，默认为"VGA"
        """
        logger.info(f"开始修改云服务器 {name} 的VNC显卡类型为: {vnc_type}")

        # 点击云服务器操作按钮，选择修改VNC显卡类型
        self.click_action(name, "修改VNC显卡类型")

        # 选择VNC显卡类型
        cur_type = self.get_by_placeholder("请选择VNC显卡类型").input_value()
        if vnc_type == cur_type:
            pytest.skip(f"云服务器 {name} 的VNC显卡类型已是 {cur_type}")
        self.get_by_placeholder("请选择VNC显卡类型").click()
        self.locator("li").filter(has_text=re.compile(fr"^{vnc_type}$")).click()

        # 确认修改
        self.dialog_confirm.click()

        logger.info(f"云服务器{name}的VNC显卡类型修改提交成功")


    @submenu("弹性云服务器")
    def ecs_modify_cpu_mode(self, name: str, cpu_mode: str, custom_value: str = None):
        """修改云服务器CPU模式
        Args:
            name: 云服务器名称
            cpu_mode: CPU模式，默认为"host-passthrough"
        """
        logger.info(f"开始修改云服务器{name}的CPU模式为: {cpu_mode}")

        # 点击云服务器操作按钮，选择修改CPU模式
        self.click_action(name, "修改CPU模式")

        self.get_by_placeholder("请选择CPU模式").first.click()
        # 选择CPU模式
        if cpu_mode == "自定义":
            self.get_by_text("自定义").click()
            # 如果提供了自定义值，则选择它
            if custom_value:
                self.get_by_placeholder("请选择CPU模式").nth(1).click()
                self.locator("li").filter(has_text=custom_value).click()
        else:
            self.get_by_text(cpu_mode).click()

        # 确认修改
        self.dialog_confirm.click()

        logger.info(f"云服务器{name}的CPU模式修改成功{cpu_mode}, {custom_value}")
