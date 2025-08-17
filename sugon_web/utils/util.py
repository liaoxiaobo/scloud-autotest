import ipaddress
import random
import string
from faker import Faker

fake = Faker(locale="zh_CN")


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
