import ipaddress
import os
import random
import string
from typing import List, Dict, Any
from faker import Faker
import yaml
from pathlib import Path

fake = Faker(locale="zh_CN")

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
        return fake.phone_number()

    elif data_type == 'email':
        return fake.email()

    elif data_type == 'cidr':
        if version == 4:
            # return fake.ipv4_private(network=True, address_class=None)
            return str(ipaddress.IPv4Network((random.randint(0x0a000000, 0x0affffff), 24), strict=False))   # 生成一个 10.0.0.0 到 10.255.255.255 之间的整数作为网络地址部分
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
            all_data = yaml.safe_load(f)

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