"""
系统常量配置
"""

# 服务入口路径表
# 说明：
# - value 为 base_url 之后的服务根路径
# - 仅配置这里即可支持 URL 直达服务
# - 未配置入口路径的服务，仍可退回到菜单导航
SERVICE_PATH_MAP = {
    '云硬盘': '/evs',
    '对象存储': '/oss',
    '对象存储专业版': '/obs',
    '文件存储': '/sfs',
    '弹性云服务器': '/ecs',
    '裸金属': '/bms',
    '镜像管理': '/image',
    '虚拟私有云': '/vpc',
    '云专线DC': '/vpc',
    '企业路由器': '/vpc',
    '流量镜像': '/vpc',
    '云防火墙': '/cfw',
    '专有网络VPN': '/vpn',
    '备份': '/backup',
    'AnhanDB(for MySQL)': '/mysql',
    'AnhanDB(for PostgreSQL)': '/pg',
    '人大金仓 KingbaseES': '/kingbase',
    'AnhanDB(for MongoDB)': '/mongodb',
    '数据仓库 Doris': '/doris',
    'xscale': '/xscale',
    'AnhanDB(for Redis)': '/redis',
    '分布式消息服务 Kafka': '/kafka',
    '分布式消息服务 RabbitMQ': '/rbs',
    '云搜索服务': '/es',
    '监控服务': '/prom',
    '云容器引擎': '/cce',
    '交换机组': '/ops/#/exchange-unit-list',
    '基础设施': '/ops',
    '统一身份认证IAM': '/iam/#/departmentManage',
    '运维': '/cms',
    '可信密码模块': '/sdf',
    '攻击预警': '/das/#/apt',
    '云堡垒机高级版': '/das/#/usm',
    '日志审计': '/das/#/ver'
}

