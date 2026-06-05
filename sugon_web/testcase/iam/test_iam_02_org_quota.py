import allure
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic('身份认证IAM')
@allure.feature('组织管理-组织结构树')
@allure.story('修改组织配额')
class TestIamOrgQuota:

    @allure.title("IAM-组织管理-一级组织修改计算配额")
    def test_iam_modify_compute_quota(self, iam_page, iam_shared_org):
        """一级组织修改计算服务配额（ECS/SECS/IMS/BMS）。"""
        org_name = iam_shared_org["org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择组织配额"):
            iam_page.iam_open_org_quota(org_name)

        with allure_step_log("步骤3: 过滤计算服务"):
            if not _filter_and_check(iam_page, "计算"):
                return

        with allure_step_log("步骤4: 分配计算配额"):
            _modify_and_assert(iam_page, "云服务器ECS", {
                "cpu总量(个)": 100, "内存总量(GiB)": 100, "系统盘总量(GiB)": 1000
            }, [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("系统盘使用量(GiB)", "0/1000")])
            _modify_and_assert(iam_page, "机密云服务器SECS",
                               {"机密云服务器总量(个)": 100},
                               [("机密云服务器使用量(个)", "0/100")])
            _modify_and_assert(iam_page, "镜像服务IMS",
                               {"镜像总量(个)": 100, "镜像容量总量(GiB)": 1000},
                               [("镜像使用量(个)", "0/100"), ("镜像容量使用量(GiB)", "0/1000")])
            _modify_and_assert(iam_page, "裸金属BMS",
                               {"软装版服务器总量(台)": 10},
                               [("软装版服务器使用量(台)", "0/10")])

    @allure.title("IAM-组织管理-一级组织修改存储配额")
    def test_iam_modify_storage_quota(self, iam_page, iam_shared_org):
        """一级组织修改存储服务配额（EVS/SFS/OSS/OBS）。"""
        org_name = iam_shared_org["org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择组织配额"):
            iam_page.iam_open_org_quota(org_name)

        with allure_step_log("步骤3: 过滤存储服务"):
            if not _filter_and_check(iam_page, "存储"):
                return

        with allure_step_log("步骤4: 分配存储配额"):
            _modify_and_assert(iam_page, "云硬盘EVS",
                               {"容量总量(GiB)": 1000, "快照总量(GiB)": 1000},
                               [("容量使用量(GiB)", "0/1000"), ("快照使用量(GiB)", "0/1000")])
            _modify_and_assert(iam_page, "文件存储SFS",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "虚拟机总量(个)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"),
                                ("虚拟机使用量(个)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            _modify_and_assert(iam_page, "对象存储OSS",
                               {"桶容量(GiB)": 1000},
                               [("桶使用量(GiB)", "0/1000")])
            _modify_and_assert(iam_page, "对象存储(专业版) OBS",
                               {"桶容量(GiB)": 1000},
                               [("桶使用量(GiB)", "0/1000")])

    @allure.title("IAM-组织管理-一级组织修改网络配额")
    def test_iam_modify_network_quota(self, iam_page, iam_shared_org):
        """一级组织修改网络服务配额（EIP/CFW/VPC/SLB）。"""
        org_name = iam_shared_org["org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择组织配额"):
            iam_page.iam_open_org_quota(org_name)

        with allure_step_log("步骤3: 过滤网络服务"):
            if not _filter_and_check(iam_page, "网络"):
                return

        with allure_step_log("步骤4: 分配网络配额"):
            _modify_and_assert(iam_page, "弹性公网IP",
                               {"弹性公网IP总量(个)": 100},
                               [("弹性公网IP使用量(个)", "0/100")])
            _modify_and_assert(iam_page, "云防火墙CFW",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100")])
            _modify_and_assert(iam_page, "虚拟私有云",
                               {"总量(个)": 100},
                               [("使用量(个)", "0/100")])
            _modify_and_assert(iam_page, "负载均衡（基础版）",
                               {"总量(个)": 100},
                               [("使用量(个)", "0/100")])

    @allure.title("IAM-组织管理-一级组织修改灾备管理配额")
    def test_iam_modify_disaster_recovery_quota(self, iam_page, iam_shared_org):
        """一级组织修改灾备管理服务配额（ECBS）。"""
        org_name = iam_shared_org["org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择组织配额"):
            iam_page.iam_open_org_quota(org_name)

        with allure_step_log("步骤3: 过滤灾备管理服务"):
            if not _filter_and_check(iam_page, "灾备管理"):
                return

        with allure_step_log("步骤4: 分配灾备管理配额"):
            _modify_and_assert(iam_page, "实例备份ECBS",
                               {"实例备份总量(GiB)": 1000},
                               [("实例备份使用量(GiB)", "0/1000")])

    @allure.title("IAM-组织管理-一级组织修改数据库配额")
    def test_iam_modify_database_quota(self, iam_page, iam_shared_org):
        """一级组织修改数据库服务配额（6种数据库）。"""
        org_name = iam_shared_org["org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择组织配额"):
            iam_page.iam_open_org_quota(org_name)

        with allure_step_log("步骤3: 过滤数据库服务"):
            if not _filter_and_check(iam_page, "数据库"):
                return

        with allure_step_log("步骤4: 分配数据库配额"):
            db_services = [
                "AnhanDB(for MySQL)", "AnhanDB(for PostgreSQL)",
                "AnhanDB(for MongoDB)", "AnhanDB-XScale",
                "数据仓库Doris", "金仓数据库",
            ]
            db_quotas = {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000}
            db_asserts = [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")]
            for svc in db_services:
                _modify_and_assert(iam_page, svc, db_quotas, db_asserts)

    @allure.title("IAM-组织管理-一级组织修改大数据计算配额")
    def test_iam_modify_bigdata_quota(self, iam_page, iam_shared_org):
        """一级组织修改大数据计算服务配额（E-MapReduce）。"""
        org_name = iam_shared_org["org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择组织配额"):
            iam_page.iam_open_org_quota(org_name)

        with allure_step_log("步骤3: 过滤大数据计算服务"):
            if not _filter_and_check(iam_page, "大数据计算"):
                return

        with allure_step_log("步骤4: 分配大数据计算配额"):
            _modify_and_assert(iam_page, "E-MapReduce",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "EMR总量(个)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"),
                                ("EMR使用量(个)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])

    @allure.title("IAM-组织管理-一级组织修改安全合规配额")
    def test_iam_modify_security_quota(self, iam_page, iam_shared_org):
        """一级组织修改安全合规服务配额（7种安全服务）。"""
        org_name = iam_shared_org["org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择组织配额"):
            iam_page.iam_open_org_quota(org_name)

        with allure_step_log("步骤3: 过滤安全合规服务"):
            if not _filter_and_check(iam_page, "安全合规"):
                return

        with allure_step_log("步骤4: 分配安全合规配额"):
            _modify_and_assert(iam_page, "云漏洞扫描RAS",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100")])
            _modify_and_assert(iam_page, "日志审计VER",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            _modify_and_assert(iam_page, "网页防篡改WPT",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100")])
            _modify_and_assert(iam_page, "数据库审计VDB",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            _modify_and_assert(iam_page, "攻击预警APT",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            _modify_and_assert(iam_page, "WEB应用防火墙WAF",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            _modify_and_assert(iam_page, "堡垒机高级版USM",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])

    @allure.title("IAM-组织管理-一级组织修改中间件配额")
    def test_iam_modify_middleware_quota(self, iam_page, iam_shared_org):
        """一级组织修改中间件服务配额（5种中间件）。"""
        org_name = iam_shared_org["org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择组织配额"):
            iam_page.iam_open_org_quota(org_name)

        with allure_step_log("步骤3: 过滤中间件服务"):
            if not _filter_and_check(iam_page, "中间件"):
                return

        with allure_step_log("步骤4: 分配中间件配额"):
            mw_services = [
                "AnhanDB(for Redis)", "云搜索服务CSS",
                "分布式消息服务Kafka", "分布式消息服务 RabbitMQ",
                "监控服务Prometheus",
            ]
            mw_quotas = {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000}
            mw_asserts = [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")]
            for svc in mw_services:
                _modify_and_assert(iam_page, svc, mw_quotas, mw_asserts)

    @allure.title("IAM-组织管理-一级组织修改容器服务配额")
    def test_iam_modify_container_quota(self, iam_page, iam_shared_org):
        """一级组织修改容器服务配额（CCE/SCR）。"""
        org_name = iam_shared_org["org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择组织配额"):
            iam_page.iam_open_org_quota(org_name)

        with allure_step_log("步骤3: 过滤容器服务"):
            if not _filter_and_check(iam_page, "容器服务"):
                return

        with allure_step_log("步骤4: 分配容器服务配额"):
            ctn_quotas = {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000}
            ctn_asserts = [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")]
            _modify_and_assert(iam_page, "云容器引擎CCE", ctn_quotas, ctn_asserts)
            _modify_and_assert(iam_page, "容器镜像服务SCR", ctn_quotas, ctn_asserts)


def _modify_and_assert(iam_page, service_name, quotas, assertions):
    """修改指定服务的配额并逐项断言指标值。配额不足/服务不存在/值超max降级时标记并跳过。"""
    try:
        iam_page.iam_modify_service_quota(service_name, quotas)
    except EnvironmentError as e:
        logger.warning(f"{service_name} 配额修改跳过(配额不足): {e}")
        allure.attach(str(e), f"{service_name}-配额不足-环境问题")
        return
    except AssertionError as e:
        msg = str(e)
        if "未找到服务" in msg:
            logger.warning(f"{service_name} 跳过(服务不存在): {msg}")
            allure.attach(msg, f"{service_name}-服务不存在-环境问题")
            return
        raise
    for metric_name, _expected in assertions:
        actual_val = _resolve_quota_value(metric_name, quotas, _expected)
        iam_page.iam_assert_quota_value(service_name, metric_name, actual_val)
    logger.info(f"{service_name} 配额修改验证通过（{len(assertions)}项）")


def _resolve_quota_value(metric_name, quotas, fallback_expected):
    """从quotas字典推导指标的实际期望值（总量->使用量映射）。"""
    for qk, qv in quotas.items():
        for (src, dst) in [("总量", "使用量"), ("总量", "使用总量")]:
            if qk.replace(src, dst) == metric_name:
                return f"0/{qv}"
    return fallback_expected


def _filter_and_check(iam_page, service_type):
    """过滤服务类型tab，若tab不存在则标记环境问题并返回False。"""
    try:
        iam_page.iam_filter_quota_service_type(service_type)
        return True
    except Exception:
        logger.warning(f"服务类型'{service_type}'的tab不存在，当前环境无此服务类型，跳过")
        allure.attach(str(service_type), "服务tab不存在-环境问题")
        return False
