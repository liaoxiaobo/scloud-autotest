"""
数据库相关工具函数模块

提供数据库操作相关的工具函数，包括：
- Playwright页面元素定位器
- 网络和子网选择
- 后端资源验证
- SSH命令执行和结果解析
"""
import re
import random
import string
from time import sleep

from faker import Faker


fake = Faker(locale="zh_CN")


def input_name(self):
    """
    获取实例名称输入框定位器
    :param self: 页面对象实例
    :return: Locator 名称输入框定位器
    """
    return self.locator("form").filter(has_text="基本设置").get_by_role("textbox").first


def input_password(self):
    """
    获取管理员密码输入框定位器
    :param self: 页面对象实例
    :return: Locator 密码输入框定位器
    """
    return self.get_by_placeholder("请输入管理员用户密码")


def input_confirm_password(self):
    """
    获取确认密码输入框定位器
    :param self: 页面对象实例
    :return: Locator 确认密码输入框定位器
    """
    return self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox")


def project_dropdown(self):
    """
    获取项目下拉框定位器
    :param self: 页面对象实例
    :return: Locator 项目下拉框定位器
    """
    return self.locator("form").filter(has_text="基本设置").get_by_placeholder("请选择").nth(1)


def disk_type_dropdown(self):
    """
    获取数据盘类型下拉框定位器
    :param self: 页面对象实例
    :return: Locator 数据盘类型下拉框定位器
    """
    return self.locator("div").filter(has_text=re.compile(r"^数据盘类型")).get_by_placeholder("请选择")


def select_labeled_dropdown(self, label_texts, dropdown_index: int = 0):
    """
    按字段标签文本定位下拉框。
    适用于页面结构一致、仅字段名称文案不同的场景。
    :param self: 页面对象实例
    :param label_texts: 标签文案或文案列表
    :param dropdown_index: 同一表单项下第几个“请选择”
    :return: Locator 下拉框定位器
    """
    if isinstance(label_texts, str):
        label_texts = [label_texts]

    for label_text in label_texts:
        patterns = [
            ("div", re.compile(rf"^{re.escape(label_text)}$")),
            (".el-form-item", re.compile(re.escape(label_text))),
        ]
        for selector, pattern in patterns:
            containers = self.locator(selector).filter(has_text=pattern)
            count = containers.count()
            for i in range(count):
                container = containers.nth(i)
                fields = container.get_by_placeholder("请选择", exact=True)
                if fields.count() == 0:
                    fields = container.locator("input[placeholder='请选择']")
                if fields.count() <= dropdown_index:
                    continue
                return fields.nth(dropdown_index)

    raise RuntimeError(f"未找到标签为 {label_texts} 的下拉框")


def select_disk_type_like_doris(self, disk_type: str, label_texts=None):
    """
    参考 Doris 当前适配方式选择数据盘类型：
    优先按字段标签定位；仅在标签定位失败时，回退到页面最后一个“请选择”。
    :param self: 页面对象实例
    :param disk_type: 磁盘类型名称
    :param label_texts: 数据盘类型字段标签，可传字符串或列表
    """
    dropdown = None
    label_texts = label_texts or ["数据盘类型", "云硬盘类型"]

    try:
        dropdown = select_labeled_dropdown(self, label_texts)
        dropdown.scroll_into_view_if_needed()
        dropdown.click(timeout=3000)
    except Exception:
        dropdown = None

    if dropdown is None:
        dropdowns = self.locator("#cloud-container-content").get_by_placeholder("请选择", exact=True)
        count = dropdowns.count()
        if count > 0:
            dropdown = dropdowns.nth(count - 1)
            try:
                dropdown.scroll_into_view_if_needed()
                dropdown.click(timeout=3000)
            except Exception:
                dropdown = None

    if dropdown is None:
        raise RuntimeError("当前页面未找到可点击的数据盘类型下拉框")

    self.page.wait_for_timeout(1000)
    self.get_by_text(disk_type).last.click()


def project_autotest(self):
    """
    获取Autotest项目选项定位器
    等待下拉列表出现并定位到包含"Autotest"的选项
    :param self: 页面对象实例
    :return: Locator Autotest项目选项定位器
    """
    # 等待下拉列表出现（与 _select_network 方法保持一致的策略）
    dropdown_locator = self.page.locator("body > div.el-select-dropdown:visible").last
    dropdown_locator.wait_for(state="visible", timeout=5000)
    # 定位到包含 "Autotest" 的 li 元素
    return dropdown_locator.locator("li").filter(has_text="Autotest").first


def select_network(self, placeholder_name, option_name):
    """
    选择网络和子网（使用可靠的等待机制）
    :param self: 页面对象实例
    :param placeholder_name: placeholder名称
    :param option_name: 下拉框选项（支持精确匹配或模糊匹配）
    :param fuzzy_match: 是否使用模糊匹配，默认False为精确匹配
    """
    """
       选择网络和子网（Element UI 稳定版）
       """
    page = self.page
    page.get_by_role("textbox", name=placeholder_name).click()
    sleep(1)
    dropdown = page.locator("body > div.el-select-dropdown:visible").last
    dropdown.wait_for(state="visible")
    items = dropdown.locator("li.el-select-dropdown__item")
    if option_name == "Autotest":
        # 精确匹配
        pattern = re.compile(rf"^{re.escape(option_name)}$")
    else:
        # 前缀匹配（Autotest:10. 开头，后面任意内容）
        pattern = re.compile(rf"^{re.escape(option_name)}.*")

    target = items.filter(has_text=pattern)
    target.first.scroll_into_view_if_needed()
    target.first.click()


def random_string(k: int) -> str:
    """
    生成指定长度的随机字符串（小写字母+数字）
    :param k: 字符串长度
    :return: str 随机字符串
    """
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=k))


def get_ping_code(self, ip: str, ssh_host) -> int:
    """
    获取ping命令返回码
    :param self: 页面对象实例
    :param ip: IP地址
    :param ssh_host: SSH连接对象
    :return: int ping命令返回码（0表示成功，非0表示失败）
    :raises RuntimeError: 命令执行或解析失败时
    """
    try:
        output = ssh_host.run(f"ping -c 4 -W 1 {ip}; echo $?").strip()
        return int(output.split('\n')[-1])
    except Exception as e:
        raise RuntimeError(f"获取ping返回码失败: {e}")


def get_disk_size(self, node_name: str, ssh_host) -> int:
    """
    获取云盘大小
    :param self: 页面对象实例
    :param node_name: 节点名称
    :param ssh_host: SSH连接对象
    :return: int 云盘大小（GB）
    :raises RuntimeError: 命令执行或解析失败时
    """
    try:
        output = ssh_host.run(
            f"scli volume list | grep -F '{node_name}' | head -n 1 | cut -d '|' -f 6 | xargs"
        ).strip()
        return int(output)
    except Exception as e:
        raise RuntimeError(f"获取云盘大小失败 (节点: {node_name}): {e}")


def get_specification(self, node_name: str, ssh_host) -> str:
    """
    获取节点规格
    :param self: 页面对象实例
    :param node_name: 节点名称
    :param ssh_host: SSH连接对象
    :return: str 节点规格名称
    :raises RuntimeError: 命令执行或解析失败时
    """
    try:
        guest_id = ssh_host.run(
            f"scli guest list --name '{node_name}' | grep -F '{node_name}' | head -n 1 | cut -d '|' -f 2 | xargs"
        ).strip()
        if not guest_id and node_name.endswith("-0"):
            instance_name = node_name.rsplit("-0", 1)[0]
            guest_id = ssh_host.run(
                f"scli guest list --name '{instance_name}' | grep -F '{instance_name}' | head -n 1 | cut -d '|' -f 2 | xargs"
            ).strip()
        if not guest_id:
            raise RuntimeError(f"未找到节点对应的 guest id: {node_name}")

        output = ssh_host.run(f"scli guest show {guest_id}").strip()

        for line in output.splitlines():
            if "flavor_name" in line and "│" in line:
                parts = [part.strip() for part in line.split("│") if part.strip()]
                if len(parts) >= 2 and parts[0] == "flavor_name":
                    return parts[1]

        patterns = [
            re.compile(r"flavor_name\s*\|\s*([^\|\n]+)"),
            re.compile(r"flavor_name\s*:\s*([^\n]+)"),
            re.compile(r"flavor\s*\|\s*([^\|\n]+)"),
            re.compile(r"flavor\s*:\s*([^\n]+)"),
        ]
        for pattern in patterns:
            match = pattern.search(output)
            if match:
                return match.group(1).strip()

        raise RuntimeError(f"未能从 scli guest show 输出中解析规格信息: {output}")
    except Exception as e:
        raise RuntimeError(f"获取节点规格失败 (节点: {node_name}): {e}")


def get_node_mfip_from_db(self, ssh_host, db_name: str, node_name: str, table_name: str = "node") -> str:
    """
    通过在master节点执行anhan命令，从数据库中查询节点的mfip
    :param self: 页面对象实例
    :param ssh_host: master节点的SSH连接对象
    :param db_name: 数据库名称
    :param node_name: 节点名称
    :param table_name: 表名，默认为node
    :return: str 节点的mfip地址
    """
    sql_query = f"use {db_name};select mfip from {table_name} where name='{node_name}'"
    command = f"echo 'admin1234@sugon' | su - root -c \"anhan -e \\\"{sql_query}\\\"\""
    result = ssh_host.run(command)
    # 假设结果的最后一行是IP地址
    ip_from_db = result.strip().splitlines()[-1].strip()
    self.logger.info(f"从数据库查询到节点 '{node_name}' 的IP地址为: {ip_from_db}")
    return ip_from_db


def get_instance_node_ips_from_db(self, ssh_host, db_name: str, instance_name: str) -> list:
    """
    通过数据库查询实例下所有节点名称和 mfip。
    :param self: 页面对象实例
    :param ssh_host: master节点的SSH连接对象
    :param db_name: 数据库名称
    :param instance_name: 实例名称前缀
    :return: list[tuple[str, str]] 节点名称和IP列表
    """
    sql_query = (
        f"use {db_name};"
        f"select name,mfip from node where name like '{instance_name}-%' order by name;"
    )
    command = f"echo 'admin1234@sugon' | su - root -c \"anhan -e \\\"{sql_query}\\\"\""
    result = ssh_host.run(command)
    node_infos = []
    for line in result.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("name") or line.startswith("-"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith(f"{instance_name}-"):
            node_infos.append((parts[0], parts[-1]))
    self.logger.info(f"从数据库查询到实例 '{instance_name}' 节点列表: {node_infos}")
    return node_infos


def get_service_status(self, ssh_host, service_name: str) -> str:
    """
    获取系统服务状态
    :param self: 页面对象实例
    :param ssh_host: SSH连接对象
    :param service_name: 服务名称（如 doris-be, doris-fe, mysql 等）
    :return: str 服务状态（如 running, stopped, failed 等）
    :raises RuntimeError: 命令执行或解析失败时
    """
    try:
        # 执行 systemctl status 命令，获取服务状态
        command = f"systemctl status {service_name}"
        result = ssh_host.run(command)
        self.logger.info(f"systemctl status {service_name} 输出:\n{result}")

        # 解析状态（Active: active (running) 或 Active: inactive (dead) 等）
        if 'active (running)' in result.lower():
            status = 'running'
        elif 'inactive (dead)' in result.lower():
            status = 'stopped'
        elif 'failed' in result.lower():
            status = 'failed'
        else:
            # 如果无法识别状态，返回原始状态行
            for line in result.splitlines():
                if 'Active:' in line:
                    status = line.strip()
                    break
            else:
                status = 'unknown'

        self.logger.info(f"服务 '{service_name}' 的状态为: {status}")
        return status

    except Exception as e:
        raise RuntimeError(f"获取服务状态失败 (服务: {service_name}): {e}")

def assert_backend_created(self, ssh_host, name: str, command: str = "scli guest list", timeout: int = 600,
                           interval: int = 10):
    """
    断言资源已在后端创建成功，支持轮询检查
    :param self: 页面对象实例
    :param ssh_host: SSH连接对象
    :param name: 要检查的资源名称
    :param command: 用于检查的命令模板，默认为 "scli guest list"
    :param timeout: 超时时间（秒），默认为 600 秒（10 分钟）
    :param interval: 轮询间隔时间（秒），默认为 10 秒
    :raises pytest.skip: 当SSH连接未配置时
    :raises pytest.fail: 当资源在超时时间内未被创建时
    """
    import time
    import pytest

    if not ssh_host:
        pytest.skip("SSH host is not configured, skipping backend assertion.")
        return

    end_time = time.time() + timeout
    if command.strip() == "scli guest list":
        check_command = f"scli guest list --name '{name}' | grep -F '{name}'"
    else:
        check_command = f"{command} | grep {name}"
    self.logger.info(f"开始轮询检查后端资源 '{name}' 是否已创建...")

    while time.time() < end_time:
        result = ssh_host.run(check_command)
        if result != "":
            self.logger.info(f"后端资源 '{name}' 已成功创建。")
            self.logger.debug(f"资源详情: {result}")
            return  # 成功，提前退出

        self.logger.debug(f"资源 '{name}' 尚未在后端创建，将在 {interval} 秒后重试...")
        time.sleep(interval)

    # 超时后，最后检查一次并失败
    final_result = ssh_host.run(check_command)
    if final_result != "":
        self.logger.info(f"后端资源 '{name}' 在最后一次检查时已创建。")
        self.logger.debug(f"资源详情: {final_result}")
    else:
        pytest.fail(f"超时错误：资源 '{name}' 在 {timeout} 秒内未能在后端创建。")


def assert_backend_deleted(self, ssh_host, name: str, command: str = "scli guest list", timeout: int = 600,
                           interval: int = 10):
    """
    断言资源已从后端删除，支持轮询检查
    :param self: 页面对象实例
    :param ssh_host: SSH连接对象
    :param name: 要检查的资源名称
    :param command: 用于检查的命令模板，默认为 "scli guest list"
    :param timeout: 超时时间（秒），默认为 600 秒（10 分钟）
    :param interval: 轮询间隔时间（秒），默认为 10 秒
    :raises pytest.skip: 当SSH连接未配置时
    :raises pytest.fail: 当资源在超时时间内未被删除时
    """
    import time
    import pytest

    if not ssh_host:
        pytest.skip("SSH host is not configured, skipping backend assertion.")
        return

    end_time = time.time() + timeout
    if command.strip() == "scli guest list":
        check_command = f"scli guest list --name '{name}' | grep -F '{name}'"
    else:
        check_command = f"{command} | grep {name}"
    self.logger.info(f"开始轮询检查后端资源 '{name}' 是否已删除...")

    while time.time() < end_time:
        result = ssh_host.run(check_command)
        if result == "":
            self.logger.info(f"后端资源 '{name}' 已成功删除。")
            return  # 成功，提前退出

        self.logger.debug(f"资源 '{name}' 仍然存在于后端，将在 {interval} 秒后重试...")
        time.sleep(interval)

    # 超时后，最后检查一次并失败
    final_result = ssh_host.run(check_command)
    if final_result == "":
        self.logger.info(f"后端资源 '{name}' 在最后一次检查时已删除。")
    else:
        pytest.fail(f"超时错误：资源 '{name}' 在 {timeout} 秒内未能从后端删除。")


def get_backend_host(self, ssh_host, name: str) -> str:
    """
    通过 scli guest list 查询后端资源所在的物理机节点
    :param self: 页面对象实例
    :param ssh_host: SSH连接对象 (通常是 master 节点)
    :param name: 资源名称
    :return: str 物理机节点名称
    """
    try:
        command = f"scli guest list --name '{name}' | grep -F '{name}'"
        result = ssh_host.run(command)
        if not result and name.endswith("-0"):
            instance_name = name.rsplit("-0", 1)[0]
            result = ssh_host.run(f"scli guest list --name '{instance_name}' | grep -F '{instance_name}'")
        self.logger.info(f"scli guest list 输出:\n{result}")

        # 解析表格，寻找对应的行并提取 NODE 列
        for line in result.splitlines():
            if name in line and "|" in line:
                # 分割并过滤掉空字符串
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    # parts 为 [UUID, NAME, NODE, ...]
                    host = parts[2]
                    self.logger.info(f"后端查询到资源 '{name}' 当前所在节点为: {host}")
                    return host

        return ""
    except Exception as e:
        self.logger.error(f"获取后端物理机节点失败: {e}")
        return ""
