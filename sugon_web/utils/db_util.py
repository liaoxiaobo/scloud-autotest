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


def select_network(self, network, subnet):
    """
    选择网络和子网（使用可靠的等待机制）
    :param self: 页面对象实例
    :param network: 网络名称
    :param subnet: 子网名称
    """
    # --- 选择网络 ---
    self.get_by_role("textbox", name="请选择网络").click()
    # 等待下拉列表出现
    network_list_locator = self.page.locator("body > div.el-select-dropdown:visible").last
    network_list_locator.wait_for(state="visible", timeout=5000)
    # 点击选项
    network_list_locator.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(network)}$")).click()

    # --- 选择子网 ---
    self.get_by_role("textbox", name="请选择子网").click()
    # 等待下拉列表出现
    subnet_list_locator = self.page.locator("body > div.el-select-dropdown:visible").last
    subnet_list_locator.wait_for(state="visible", timeout=5000)
    # 点击选项
    subnet_list_locator.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(subnet)}$")).locator(
        "span").click()


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
            f"cinder list | grep {node_name} | awk -F'|' '{{print $5}}' | tr -d ' '"
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
        output = ssh_host.run(
            f"gova show $(gova list | grep {node_name} | awk '{{print $2}}') | awk -F'|' '/flavor_name/ {{gsub(/^ +| +$/, \"\", $3); print $3}}'"
        ).strip()
        return output
    except Exception as e:
        raise RuntimeError(f"获取节点规格失败 (节点: {node_name}): {e}")


def get_node_mfip_from_db(self, ssh_host, db_name: str, node_name: str) -> str:
    """
    通过在master节点执行anhan命令，从数据库中查询节点的mfip
    :param self: 页面对象实例
    :param ssh_host: master节点的SSH连接对象
    :param db_name: 数据库名称
    :param node_name: 节点名称
    :return: str 节点的mfip地址
    """
    sql_query = f"use {db_name};select mfip from node where name='{node_name}'"
    command = f"echo 'admin1234@sugon' | su - root -c \"anhan -e \\\"{sql_query}\\\"\""
    result = ssh_host.run(command)
    # 假设结果的最后一行是IP地址
    ip_from_db = result.strip().splitlines()[-1].strip()
    self.logger.info(f"从数据库查询到节点 '{node_name}' 的IP地址为: {ip_from_db}")
    return ip_from_db


def assert_backend_deleted(self, ssh_host, name: str, command: str = "gova list", timeout: int = 600,
                           interval: int = 10):
    """
    断言资源已从后端删除，支持轮询检查
    :param self: 页面对象实例
    :param ssh_host: SSH连接对象
    :param name: 要检查的资源名称
    :param command: 用于检查的命令模板，默认为 "gova list"
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