"""数据生成与加载工具。

纯基础设施函数，无业务语义，可在任意层使用：
- random_data / random_string：资源名称生成
- load_data：YAML 测试数据加载（支持 Jinja2 模板渲染）
- render_data：Jinja2 字典模板渲染
- auto_days：随机日期选择
- get_file_abspath：项目内文件路径查找
"""

import calendar
import ipaddress
import os
import random
import string
from datetime import datetime
from pathlib import Path
from typing import Any, List, Dict

import yaml
from faker import Faker
from jinja2 import Template

fake = Faker(locale="zh_CN")


def get_file_abspath(name):
    """
    默认在根目录下遍历查找文件，并返回文件的 abspath。
    """
    current_dir = os.path.dirname(__file__)
    father_dir = os.path.dirname(current_dir)
    for dirpath, dirname, filenames in os.walk(father_dir):
        if name in filenames:
            return os.path.join(dirpath, name)
    return None


def random_data(data_type='string', length=5, cidr=None, version=4):
    """生成随机测试数据。

    Args:
        data_type: 数据类型，支持 string / phone / email / cidr / ip
        length: 字符串长度
        cidr: IP 生成时使用的 CIDR 网段
        version: IP 版本，4 或 6
    """
    if data_type == 'string':
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
        return f'autotest-{random_suffix}'

    elif data_type == 'phone':
        return fake.phone_number()

    elif data_type == 'email':
        return fake.email()

    elif data_type == 'cidr':
        if version == 4:
            return str(ipaddress.IPv4Network((random.randint(0x0a000000, 0x0affffff), 24), strict=False))
        elif version == 6:
            ipv6 = str(fake.ipv6(network=True)).split('/')
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
                ipv4 = fake.ipv4()
                if not ipv4.split('.')[-1] in {'1', '2', '255'}:
                    return ipv4
    else:
        return None


def random_string(k: int) -> str:
    """生成指定长度的随机字符串（小写字母 + 数字）。"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=k))


def load_data(case_name: str, data_file: str = "test_data.yaml") -> List[Dict[str, Any]]:
    """从 YAML 文件中根据测试用例名称加载对应的测试数据。

    Args:
        case_name: 测试用例键名，如 'test_volume_create'
        data_file: 数据文件名，默认为 'test_data.yaml'

    Returns:
        List[Dict]: 测试数据列表

    Raises:
        FileNotFoundError: 数据文件不存在
        KeyError: 指定的测试用例键不存在
    """
    current_file = Path(__file__)
    data_path = current_file.parent.parent / "testcase" / "test_data" / data_file

    if not data_path.exists():
        raise FileNotFoundError(f"测试数据文件不存在: {data_path}")

    with open(data_path, 'r', encoding='utf-8') as f:
        content = f.read()

    template = Template(content)
    rendered = template.render(
        auto_days=auto_days,
        now=datetime.now()
    )

    all_data = yaml.safe_load(rendered)
    for service, service_data in all_data.items():
        if isinstance(service_data, dict) and case_name in service_data:
            test_data = service_data[case_name]
            if not isinstance(test_data, list):
                raise ValueError(f"测试数据必须是列表格式，当前类型: {type(test_data)}")
            return test_data

    raise KeyError(f"测试用例 '{case_name}' 在数据文件中不存在")


def auto_days(count: int = 3, exclude_weekday: int = 6) -> list:
    """随机选择不冲突的日期，支持排除单个或多个星期。

    Args:
        count: 需要选择的日期数量
        exclude_weekday: 要排除的星期，可以传单个整数或列表

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

    available_days = []
    for day in range(1, last_day + 1):
        date = datetime(year, month, day)
        if date.weekday() not in exclude_set:
            available_days.append(str(day))

    if len(available_days) <= count:
        selected_days = available_days
    else:
        selected_days = random.sample(available_days, count)

    return sorted(selected_days, key=int)


def render_data(data: dict, **kwargs) -> dict:
    """使用 Jinja2 渲染字典中的模板变量。

    Args:
        data: 包含 Jinja2 模板变量的字典
        **kwargs: 要注入的变量

    Returns:
        渲染后的字典
    """
    yaml_str = yaml.dump(data, allow_unicode=True)
    template = Template(yaml_str)
    rendered = template.render(**kwargs)
    return yaml.safe_load(rendered)


def retry_check(check_func, expected, max_retries=3, interval=5, error_msg=None):
    """重试检查，直到 check_func() 返回值等于 expected。

    Args:
        check_func: 检查函数，返回需要比较的值
        expected: 期望值
        max_retries: 最大重试次数
        interval: 重试间隔（秒）
        error_msg: 错误消息

    Raises:
        AssertionError: 重试耗尽后仍未匹配期望值
    """
    import time
    for i in range(max_retries):
        actual = check_func()
        if actual == expected:
            return actual
        if i < max_retries - 1:
            time.sleep(interval)

    final_msg = error_msg or f"断言失败: 期望 '{expected}', 实际 '{actual}'"
    raise AssertionError(final_msg)
