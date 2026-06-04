import calendar
import ipaddress
import os
import random
import string
import time

import pytest
import yaml
import allure
from datetime import datetime
from functools import wraps
from pathlib import Path
from jinja2 import Template
from typing import List, Dict, Any
from pathlib import Path
from functools import wraps
from sugon_web.config.config import Config
from sugon_web.utils.logger import logger

_fake = None

def _get_fake():
    global _fake
    if _fake is None:
        try:
            from faker import Faker
            _fake = Faker(locale="zh_CN")
        except Exception:
            # faker 包损坏时的兜底：用标准库生成假数据
            class _FakeFaker:
                @staticmethod
                def phone_number():
                    return "138" + "".join(str(random.randint(0, 9)) for _ in range(8))
                @staticmethod
                def email():
                    return f"autotest-{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}@example.com"
                @staticmethod
                def ipv4():
                    return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
                @staticmethod
                def ipv6(network=False):
                    base = f"2001:db8::{random.randint(0, 65535):x}"
                    return f"{base}/128" if network else base
            _fake = _FakeFaker()
    return _fake

def get_file_abspath(name):
    """
    默认在根目录下遍历查找文件，并返回文件的abspath
    :param name:
    :return:
    """
    current_dir = os.path.dirname(__file__)
    father_dir = os.path.dirname(current_dir)
    for dirpath, dirname, filenames in os.walk(father_dir):
        if name in filenames:
            return os.path.join(dirpath, name)
    return None


def random_data(data_type='string', length=5, cidr=None, version=4):

    if data_type == 'string':
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
        return f'autotest-{random_suffix}'

    elif data_type == 'phone':
        return _get_fake().phone_number()

    elif data_type == 'email':
        return _get_fake().email()

    elif data_type == 'cidr':
        if version == 4:
            return str(ipaddress.IPv4Network((random.randint(0x0a000000, 0x0affffff), 24), strict=False))
        elif version == 6:
            ipv6 = str(_get_fake().ipv6(network=True)).split('/')
            ipv6[1] = '128'
            return '/'.join(ipv6)
        return None

    elif data_type == 'ip':
        if cidr:
            network = ipaddress.ip_network(cidr, strict=False)
            while True:
                ip_addr = str(random.choice(list(network.hosts())))
                if not ip_addr.split('.')[-1] in {'1', '2', '255'}:
                    return ip_addr
        else:
            while True:
                ipv4 = _get_fake().ipv4()
                if not ipv4.split('.')[-1] in {'1', '2', '255'}:
                    return ipv4
    else:
        return None



def load_data(case_name: str, data_file: str = "test_data.yaml") -> List[Dict[str, Any]]:
    """从YAML文件中根据测试用例名称加载对应的测试数据

    Args:
        case_name: 测试用例键名，如 'test_volume_create', 'test_volume_expand'
        data_file: 数据文件名，默认为 'test_data.yaml'

    Returns:
        List[Dict]: 测试数据列表

    Raises:
        FileNotFoundError: 数据文件不存在
        KeyError: 指定的测试用例键不存在
        yaml.YAMLError: YAML文件格式错误

    Examples:
        # 加载云硬盘创建测试数据
        create_data = load_data('test_volume_create')
    """
    try:
        # 构建数据文件路径
        current_file = Path(__file__)
        data_path = current_file.parent.parent / "testcase" / "test_data" / data_file

        # 检查文件是否存在
        if not data_path.exists():
            raise FileNotFoundError(f"测试数据文件不存在: {data_path}")

        # 读取YAML文件
        with open(data_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 使用 Jinja2 渲染模板（支持 auto_days 等函数）
        template = Template(content)
        rendered = template.render(
            auto_days=auto_days,
            now=datetime.now()
        )

        # 解析渲染后的 YAML
        all_data = yaml.safe_load(rendered)
        # 在所有服务中查找测试用例
        for service, service_data in all_data.items():
            if isinstance(service_data, dict) and case_name in service_data:
                test_data = service_data[case_name]

                # 确保返回的是列表格式
                if not isinstance(test_data, list):
                    raise ValueError(f"测试数据必须是列表格式，当前类型: {type(test_data)}")

                return test_data

        # 如果没找到，抛出异常
        raise KeyError(f"测试用例 '{case_name}' 在数据文件中不存在")

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"YAML文件格式错误: {e}")
    except Exception as e:
        raise Exception(f"加载测试数据失败: {e}")


def random_string(k: int) -> str:
    """生成指定长度的随机字符串（小写字母+数字）"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=k))


def skip_stor(*stor_value):
    """
    存储类型跳过装饰器

    当当前配置的存储类型在指定的列表中时，跳过测试用例。

    Args:
        *stor_value: 需要跳过测试的存储类型列表

    Examples:
        @skip_stor('ceph')
        def test_function(self):
            pass

        @skip_stor('ceph', 'usan')
        def test_function(self):
            pass
    """

    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            stor = Config.get("stor")
            if stor in stor_value:
                pytest.skip(f"{stor}存储不支持该测试用例")
            return method(self, *args, **kwargs)

        return wrapper

    return decorator


def only_stor(*stor_value):
    """
    存储类型支持装饰器

    当当前配置的存储类型不在指定的列表中时，跳过测试用例。
    与skip_stor装饰器逻辑相反，此装饰器指定只支持的存储类型。

    Args:
        *stor_value: 支持测试的存储类型列表

    Examples:
        @only_stor('ceph')
        def test_function(self):
            pass

        @only_stor('ceph', 'usan')
        def test_function(self):
            pass
    """

    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            stor = Config.get("stor")
            if stor not in stor_value:
                supported = ", ".join(stor_value)
                pytest.skip(f"此测试用例仅支持 {supported} 存储，当前为 {stor}")
            return method(self, *args, **kwargs)

        return wrapper

    return decorator


def get_output(strs):
    """将openstack命令输出内容转为字典"""
    result = {}
    strs = strs.replace("+", "")
    strs = strs.strip()
    l = strs.split("|")
    for i, v in enumerate(l):
        if i % 3 == 1:
            result[v.strip()] = l[i + 1].strip()
        else:
            continue
    return result

def capture_failure_screenshot(page, item, failure_stage):
    """
    捕获失败截图并添加到Allure报告

    Args:
        page: Playwright页面对象
        item: pytest测试项对象
        failure_stage: 失败阶段 (setup/call/teardown)
    """
    try:
        logger.info(f"开始生成失败截图")
        # 统一将运行产物落在仓库根目录，避免写入包目录
        project_root = Path(__file__).resolve().parents[2]

        # 创建 screenshots 目录
        screenshot_dir = project_root / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)

        # 生成截图路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshot_dir / f"{item.name}_{timestamp}.png"

        # 保存截图到文件
        page.screenshot(path=str(screenshot_path))
        logger.info(f"截图保存成功: {screenshot_path}")

        # 记录失败时的页面信息
        failure_info = (
            f"测试失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"测试用例名称: {item.name}\n"
            f"失败阶段: {failure_stage}\n"
            f"当前页面URL: {page.url}\n"
        )
        logger.error(f"测试失败详情:\n{failure_info}")

        # 将截图添加到 Allure 报告
        with allure.step(f"用例信息收集 -> {failure_stage}阶段"):

            with open(screenshot_path, "rb") as f:
                allure.attach(
                    body=f.read(),
                    name=f"失败截图",
                    attachment_type=allure.attachment_type.PNG
                )

            # 添加失败时的页面信息
            allure.attach(
                body=failure_info,
                name="失败信息",
                attachment_type=allure.attachment_type.TEXT
            )

        logger.info(f"失败截图已保存并添加到 Allure 报告: {screenshot_path}")

    except Exception as e:
        logger.error(f"截图保存失败: {e}")

def get_page_from_item(item):
    """
    从测试用例的fixture中获取page对象

    Args:
        item: pytest测试项对象

    Returns:
        Page对象或None
    """
    # 方法1：直接获取page fixture
    page = item.funcargs.get("page", None)
    if page:
        return page

    # 方法2：遍历所有fixture，查找包含page属性的fixture
    for fixture_name, fixture_obj in item.funcargs.items():
        if hasattr(fixture_obj, 'page'):
            page = getattr(fixture_obj, 'page')
            logger.info(f"从 {fixture_name} 中获取到page对象")
            return page

    logger.warning("无法获取page对象")
    return None


def skip_if_nodes_less_than(min_nodes=2):
    """
    节点数跳过装饰器

    当物理机节点数小于指定值时，跳过测试用例。

    Args:
        min_nodes: 最小节点数，默认为2

    Examples:
        @skip_if_nodes_less_than()
        def test_function(self):
            # 节点数小于2时跳过
            pass

        @skip_if_nodes_less_than(3)
        def test_function(self):
            # 节点数小于3时跳过
            pass
    """

    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            # 直接从 Config 中获取节点信息（由 check_compute_nodes fixture 设置）
            nodes = Config._config.get('_node_count', "")

            if int(nodes) < min_nodes:
                logger.warning(f"节点数不足，准备跳过测试")
                pytest.skip(f"节点数不足，当前节点数: {nodes}，要求最小节点数: {min_nodes}")

            logger.info(f"节点数满足要求，继续执行测试")
            return method(self, *args, **kwargs)

        return wrapper

    return decorator

def skip_arch(*arch_value):
    """
    架构类型跳过装饰器

    当当前配置的架构类型在指定的列表中时，跳过测试用例。

    Args:
        *arch_value: 需要跳过测试的架构类型列表 (如 'aarch64', 'x86_64')

    Examples:
        @skip_arch('aarch64')
        def test_function(self):
            pass

        @skip_arch('aarch64', 'x86_64')
        def test_function(self):
            pass
    """

    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            architecture = Config.get("architecture")
            if architecture in arch_value:
                pytest.skip(f"{architecture}架构不支持该测试用例")
            return method(self, *args, **kwargs)

        return wrapper

    return decorator


def auto_days(count: int = 3, exclude_weekday: int = 6) -> list:
    """随机选择不冲突的日期，支持排除单个或多个星期

    Args:
        count: 需要选择的日期数量
        exclude_weekday: 要排除的星期，可以传：
                        - 单个整数：如 6 表示排除周日
                        - 列表：如 [5, 6] 表示排除周六和周日

    Returns:
        日期字符串列表，如 ['5', '12', '25']
    """
    now = datetime.now()
    year, month = now.year, now.month
    _, last_day = calendar.monthrange(year, month)

    exclude_set = set()
    if isinstance(exclude_weekday, (list, tuple)):
        exclude_set.update(exclude_weekday)
    elif isinstance(exclude_weekday, int):
        exclude_set.add(exclude_weekday)

    # 收集所有可用日期（不冲突的）
    available_days = []
    for day in range(1, last_day + 1):
        date = datetime(year, month, day)
        if date.weekday() not in exclude_set:
            available_days.append(str(day))

    # 随机选择指定数量的日期
    if len(available_days) <= count:
        selected_days = available_days
    else:
        selected_days = random.sample(available_days, count)

    # 按数字大小排序
    selected_days = sorted(selected_days, key=int)

    return selected_days

def retry_check(check_func, expected, max_retries=3, interval=5, error_msg=None):
    """
    重试检查，直到 check_func() 返回值等于 expected

    Args:
        check_func: 检查函数，返回需要比较的值
        expected: 期望值
        max_retries: 最大重试次数
        interval: 重试间隔
        error_msg: 错误消息
    """
    for i in range(max_retries):
        actual = check_func()
        if actual == expected:
            return actual
        if i < max_retries - 1:
            time.sleep(interval)

    final_msg = error_msg or f"断言失败: 期望 '{expected}', 实际 '{actual}'"
    raise AssertionError(final_msg)

def render_data(data: dict, **kwargs) -> dict:
    """
    使用 Jinja2 渲染字典中的模板变量

    Args:
        data: 包含 Jinja2 模板变量的字典
        **kwargs: 要注入的变量

    Returns:
        渲染后的字典
    """
    # 将字典转为 YAML 字符串
    yaml_str = yaml.dump(data, allow_unicode=True)

    # 使用 Jinja2 渲染
    template = Template(yaml_str)
    rendered = template.render(**kwargs)

    # 解析回字典
    return yaml.safe_load(rendered)
