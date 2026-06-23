import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.testcase.iam._iam_helpers import modify_and_assert_quota, filter_quota_service_type, assert_org_quota_usage


@allure.epic('身份认证IAM')
@allure.feature('组织管理-项目管理')
@allure.story('项目全生命周期及配额管理')
class TestIamProjectManagement:

    @allure.title("IAM-项目管理-创建项目并验证详情")
    def test_iam_create_project(self, iam_page, iam_project):
        """验证项目创建成功，且项目详情页信息正确。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1-2: 进入IAM并选择子组织项目管理"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)

        with allure_step_log("步骤3-4: 验证项目详情"):
            iam_page.iam_open_project_detail(project_name)
            iam_page.wait_for_page_ready()
            # 验证页面已跳转到项目详情
            assert "projectdetail" in iam_page.page.url.lower(), \
                f"未跳转到项目详情页，当前URL: {iam_page.page.url}"
            logger.info(f"已进入项目 {project_name} 详情页: {iam_page.page.url}")

    @allure.title("IAM-项目管理-修改项目描述")
    def test_iam_edit_project(self, iam_page, iam_project):
        """验证项目描述修改成功。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]
        new_desc = "修改后的项目描述"

        with allure_step_log("步骤1-2: 进入IAM并选择子组织项目管理"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)

        with allure_step_log("步骤3: 编辑项目描述"):
            iam_page.iam_edit_project(project_name, new_desc)
            iam_page.assert_popup_success("修改项目成功")
            iam_page.assert_row_contains(project_name, new_desc)

    @allure.title("IAM-项目管理-修改计算配额")
    def test_iam_modify_compute_quota(self, iam_page, iam_project):
        """项目修改计算服务配额（ECS/SECS/IMS/BMS）。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1: 进入项目配额页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)
            iam_page.iam_open_project_quota(project_name)

        with allure_step_log("步骤2: 过滤计算服务"):
            if not filter_quota_service_type(iam_page, "计算"):
                return

        with allure_step_log("步骤3: 分配计算配额"):
            actual_ecs = modify_and_assert_quota(iam_page, "云服务器ECS", {
                "cpu总量(个)": 100, "内存总量(GiB)": 100, "系统盘总量(GiB)": 1000
            }, [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("系统盘使用量(GiB)", "0/1000")])
            actual_secs = modify_and_assert_quota(iam_page, "机密云服务器SECS",
                               {"机密云服务器总量(个)": 100},
                               [("机密云服务器使用量(个)", "0/100")])
            actual_ims = modify_and_assert_quota(iam_page, "镜像服务IMS",
                               {"镜像总量(个)": 100, "镜像容量总量(GiB)": 1000},
                               [("镜像使用量(个)", "0/100"), ("镜像容量使用量(GiB)", "0/1000")])
            actual_bms = modify_and_assert_quota(iam_page, "裸金属BMS",
                               {"软装版服务器总量(台)": 10},
                               [("软装版服务器使用量(台)", "0/10")])

        with allure_step_log("步骤6: 反向验证一级组织使用量"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_open_org_quota(iam_project["parent_org_name"])
            if actual_ecs:
                assert assert_org_quota_usage(iam_page, "云服务器ECS", "cpu使用量(个)", actual_ecs["cpu总量(个)"]), "ECS cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "云服务器ECS", "内存使用量(GiB)", actual_ecs["内存总量(GiB)"]), "ECS 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "云服务器ECS", "系统盘使用量(GiB)", actual_ecs["系统盘总量(GiB)"]), "ECS 系统盘反向验证失败"
            if actual_secs:
                assert assert_org_quota_usage(iam_page, "机密云服务器SECS", "机密云服务器使用量(个)", actual_secs["机密云服务器总量(个)"]), "SECS反向验证失败"
            if actual_ims:
                assert assert_org_quota_usage(iam_page, "镜像服务IMS", "镜像使用量(个)", actual_ims["镜像总量(个)"]), "IMS镜像反向验证失败"
                assert assert_org_quota_usage(iam_page, "镜像服务IMS", "镜像容量使用量(GiB)", actual_ims["镜像容量总量(GiB)"]), "IMS容量反向验证失败"
            if actual_bms:
                assert assert_org_quota_usage(iam_page, "裸金属BMS", "软装版服务器使用量(台)", actual_bms["软装版服务器总量(台)"]), "BMS反向验证失败"

    @allure.title("IAM-项目管理-修改存储配额")
    def test_iam_modify_storage_quota(self, iam_page, iam_project):
        """项目修改存储服务配额（EVS/SFS/OSS/OBS）。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1: 进入项目配额页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)
            iam_page.iam_open_project_quota(project_name)

        with allure_step_log("步骤2: 过滤存储服务"):
            if not filter_quota_service_type(iam_page, "存储"):
                return

        with allure_step_log("步骤3: 分配存储配额"):
            actual_evs = modify_and_assert_quota(iam_page, "云硬盘EVS",
                               {"容量总量(GiB)": 1000, "快照总量(GiB)": 1000},
                               [("容量使用量(GiB)", "0/1000"), ("快照使用量(GiB)", "0/1000")])
            actual_sfs = modify_and_assert_quota(iam_page, "文件存储SFS",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "虚拟机总量(个)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"),
                                ("虚拟机使用量(个)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            actual_oss = modify_and_assert_quota(iam_page, "对象存储OSS",
                               {"桶容量(GiB)": 1000},
                               [("桶使用量(GiB)", "0/1000")])
            actual_obs = modify_and_assert_quota(iam_page, "对象存储(专业版) OBS",
                               {"桶容量(GiB)": 1000},
                               [("桶使用量(GiB)", "0/1000")])

        with allure_step_log("步骤6: 反向验证一级组织使用量"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_open_org_quota(iam_project["parent_org_name"])
            if actual_evs:
                assert assert_org_quota_usage(iam_page, "云硬盘EVS", "容量使用量(GiB)", actual_evs["容量总量(GiB)"]), "EVS容量反向验证失败"
                assert assert_org_quota_usage(iam_page, "云硬盘EVS", "快照使用量(GiB)", actual_evs["快照总量(GiB)"]), "EVS快照反向验证失败"
            if actual_sfs:
                assert assert_org_quota_usage(iam_page, "文件存储SFS", "cpu使用量(个)", actual_sfs["cpu总量(个)"]), "SFS cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "文件存储SFS", "内存使用量(GiB)", actual_sfs["内存总量(GiB)"]), "SFS 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "文件存储SFS", "虚拟机使用量(个)", actual_sfs["虚拟机总量(个)"]), "SFS 虚拟机反向验证失败"
                assert assert_org_quota_usage(iam_page, "文件存储SFS", "云硬盘使用总量(GiB)", actual_sfs["云硬盘总量(GiB)"]), "SFS 云硬盘反向验证失败"
            if actual_oss:
                assert assert_org_quota_usage(iam_page, "对象存储OSS", "桶使用量(GiB)", actual_oss["桶容量(GiB)"]), "OSS反向验证失败"
            if actual_obs:
                assert assert_org_quota_usage(iam_page, "对象存储(专业版) OBS", "桶使用量(GiB)", actual_obs["桶容量(GiB)"]), "OBS反向验证失败"

    @allure.title("IAM-项目管理-修改网络配额")
    def test_iam_modify_network_quota(self, iam_page, iam_project):
        """项目修改网络服务配额（EIP/CFW/VPC/SLB）。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1: 进入项目配额页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)
            iam_page.iam_open_project_quota(project_name)

        with allure_step_log("步骤2: 过滤网络服务"):
            if not filter_quota_service_type(iam_page, "网络"):
                return

        with allure_step_log("步骤3: 分配网络配额"):
            actual_eip = modify_and_assert_quota(iam_page, "弹性公网IP",
                               {"弹性公网IP总量(个)": 100},
                               [("弹性公网IP使用量(个)", "0/100")])
            actual_cfw = modify_and_assert_quota(iam_page, "云防火墙CFW",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/1000")])
            actual_vpc = modify_and_assert_quota(iam_page, "虚拟私有云",
                               {"总量(个)": 100},
                               [("使用量(个)", "0/100")])
            actual_slb = modify_and_assert_quota(iam_page, "负载均衡（基础版）",
                               {"总量(个)": 100},
                               [("使用量(个)", "0/100")])

        with allure_step_log("步骤6: 反向验证一级组织使用量"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_open_org_quota(iam_project["parent_org_name"])
            if actual_eip:
                assert assert_org_quota_usage(iam_page, "弹性公网IP", "弹性公网IP使用量(个)", actual_eip["弹性公网IP总量(个)"]), "EIP反向验证失败"
            if actual_cfw:
                assert assert_org_quota_usage(iam_page, "云防火墙CFW", "cpu使用量(个)", actual_cfw["cpu总量(个)"]), "CFW cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "云防火墙CFW", "内存使用量(GiB)", actual_cfw["内存总量(GiB)"]), "CFW 内存反向验证失败"
            if actual_vpc:
                assert assert_org_quota_usage(iam_page, "虚拟私有云", "使用量(个)", actual_vpc["总量(个)"]), "VPC反向验证失败"
            if actual_slb:
                assert assert_org_quota_usage(iam_page, "负载均衡（基础版）", "使用量(个)", actual_slb["总量(个)"]), "SLB反向验证失败"

    @allure.title("IAM-项目管理-修改灾备管理配额")
    def test_iam_modify_disaster_recovery_quota(self, iam_page, iam_project):
        """项目修改灾备管理服务配额（ECBS）。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1: 进入项目配额页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)
            iam_page.iam_open_project_quota(project_name)

        with allure_step_log("步骤2: 过滤灾备管理服务"):
            if not filter_quota_service_type(iam_page, "灾备管理"):
                return

        with allure_step_log("步骤3: 分配灾备管理配额"):
            actual_ecbs = modify_and_assert_quota(iam_page, "实例备份ECBS",
                               {"实例备份总量(GiB)": 1000},
                               [("实例备份使用量(GiB)", "0/1000")])

        with allure_step_log("步骤6: 反向验证一级组织使用量"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_open_org_quota(iam_project["parent_org_name"])
            if actual_ecbs:
                assert assert_org_quota_usage(iam_page, "实例备份ECBS", "实例备份使用量(GiB)", actual_ecbs["实例备份总量(GiB)"]), "ECBS反向验证失败"

    @allure.title("IAM-项目管理-修改数据库配额")
    def test_iam_modify_database_quota(self, iam_page, iam_project):
        """项目修改数据库服务配额（6种数据库）。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1: 进入项目配额页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)
            iam_page.iam_open_project_quota(project_name)

        with allure_step_log("步骤2: 过滤数据库服务"):
            if not filter_quota_service_type(iam_page, "数据库"):
                return

        with allure_step_log("步骤3: 分配数据库配额"):
            db_services = [
                "AnhanDB(for MySQL)", "AnhanDB(for PostgreSQL)",
                "AnhanDB(for MongoDB)", "AnhanDB-XScale",
                "数据仓库Doris", "金仓数据库",
            ]
            db_quotas = {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000}
            db_asserts = [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")]
            db_actuals = {}
            for svc in db_services:
                actual = modify_and_assert_quota(iam_page, svc, db_quotas.copy(), db_asserts)
                if actual:
                    db_actuals[svc] = actual

        with allure_step_log("步骤6: 反向验证一级组织使用量"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_open_org_quota(iam_project["parent_org_name"])
            for svc, actual in db_actuals.items():
                assert assert_org_quota_usage(iam_page, svc, "cpu使用量(个)", actual["cpu总量(个)"]), f"{svc} cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, svc, "内存使用量(GiB)", actual["内存总量(GiB)"]), f"{svc} 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, svc, "云硬盘使用总量(GiB)", actual["云硬盘总量(GiB)"]), f"{svc} 云硬盘反向验证失败"

    @allure.title("IAM-项目管理-修改大数据计算配额")
    def test_iam_modify_bigdata_quota(self, iam_page, iam_project):
        """项目修改大数据计算服务配额（E-MapReduce）。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1: 进入项目配额页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)
            iam_page.iam_open_project_quota(project_name)

        with allure_step_log("步骤2: 过滤大数据计算服务"):
            if not filter_quota_service_type(iam_page, "大数据计算"):
                return

        with allure_step_log("步骤3: 分配大数据计算配额"):
            actual_emr = modify_and_assert_quota(iam_page, "E-MapReduce",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "EMR总量(个)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"),
                                ("EMR使用量(个)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])

        with allure_step_log("步骤6: 反向验证一级组织使用量"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_open_org_quota(iam_project["parent_org_name"])
            if actual_emr:
                assert assert_org_quota_usage(iam_page, "E-MapReduce", "cpu使用量(个)", actual_emr["cpu总量(个)"]), "EMR cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "E-MapReduce", "内存使用量(GiB)", actual_emr["内存总量(GiB)"]), "EMR 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "E-MapReduce", "EMR使用量(个)", actual_emr["EMR总量(个)"]), "EMR反向验证失败"
                assert assert_org_quota_usage(iam_page, "E-MapReduce", "云硬盘使用总量(GiB)", actual_emr["云硬盘总量(GiB)"]), "EMR 云硬盘反向验证失败"

    @allure.title("IAM-项目管理-修改安全合规配额")
    def test_iam_modify_security_quota(self, iam_page, iam_project):
        """项目修改安全合规服务配额（7种安全服务）。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1: 进入项目配额页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)
            iam_page.iam_open_project_quota(project_name)

        with allure_step_log("步骤2: 过滤安全合规服务"):
            if not filter_quota_service_type(iam_page, "安全合规"):
                return

        with allure_step_log("步骤3: 分配安全合规配额"):
            actual_ras = modify_and_assert_quota(iam_page, "云漏洞扫描RAS",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100")])
            actual_ver = modify_and_assert_quota(iam_page, "日志审计VER",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            actual_wpt = modify_and_assert_quota(iam_page, "网页防篡改WPT",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100")])
            actual_vdb = modify_and_assert_quota(iam_page, "数据库审计VDB",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            actual_apt = modify_and_assert_quota(iam_page, "攻击预警APT",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            actual_waf = modify_and_assert_quota(iam_page, "WEB应用防火墙WAF",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])
            actual_usm = modify_and_assert_quota(iam_page, "堡垒机高级版USM",
                               {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000},
                               [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")])

        with allure_step_log("步骤6: 反向验证一级组织使用量"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_open_org_quota(iam_project["parent_org_name"])
            if actual_ras:
                assert assert_org_quota_usage(iam_page, "云漏洞扫描RAS", "cpu使用量(个)", actual_ras["cpu总量(个)"]), "RAS cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "云漏洞扫描RAS", "内存使用量(GiB)", actual_ras["内存总量(GiB)"]), "RAS 内存反向验证失败"
            if actual_ver:
                assert assert_org_quota_usage(iam_page, "日志审计VER", "cpu使用量(个)", actual_ver["cpu总量(个)"]), "VER cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "日志审计VER", "内存使用量(GiB)", actual_ver["内存总量(GiB)"]), "VER 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "日志审计VER", "云硬盘使用总量(GiB)", actual_ver["云硬盘总量(GiB)"]), "VER 云硬盘反向验证失败"
            if actual_wpt:
                assert assert_org_quota_usage(iam_page, "网页防篡改WPT", "cpu使用量(个)", actual_wpt["cpu总量(个)"]), "WPT cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "网页防篡改WPT", "内存使用量(GiB)", actual_wpt["内存总量(GiB)"]), "WPT 内存反向验证失败"
            if actual_vdb:
                assert assert_org_quota_usage(iam_page, "数据库审计VDB", "cpu使用量(个)", actual_vdb["cpu总量(个)"]), "VDB cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "数据库审计VDB", "内存使用量(GiB)", actual_vdb["内存总量(GiB)"]), "VDB 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "数据库审计VDB", "云硬盘使用总量(GiB)", actual_vdb["云硬盘总量(GiB)"]), "VDB 云硬盘反向验证失败"
            if actual_apt:
                assert assert_org_quota_usage(iam_page, "攻击预警APT", "cpu使用量(个)", actual_apt["cpu总量(个)"]), "APT cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "攻击预警APT", "内存使用量(GiB)", actual_apt["内存总量(GiB)"]), "APT 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "攻击预警APT", "云硬盘使用总量(GiB)", actual_apt["云硬盘总量(GiB)"]), "APT 云硬盘反向验证失败"
            if actual_waf:
                assert assert_org_quota_usage(iam_page, "WEB应用防火墙WAF", "cpu使用量(个)", actual_waf["cpu总量(个)"]), "WAF cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "WEB应用防火墙WAF", "内存使用量(GiB)", actual_waf["内存总量(GiB)"]), "WAF 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "WEB应用防火墙WAF", "云硬盘使用总量(GiB)", actual_waf["云硬盘总量(GiB)"]), "WAF 云硬盘反向验证失败"
            if actual_usm:
                assert assert_org_quota_usage(iam_page, "堡垒机高级版USM", "cpu使用量(个)", actual_usm["cpu总量(个)"]), "USM cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "堡垒机高级版USM", "内存使用量(GiB)", actual_usm["内存总量(GiB)"]), "USM 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "堡垒机高级版USM", "云硬盘使用总量(GiB)", actual_usm["云硬盘总量(GiB)"]), "USM 云硬盘反向验证失败"

    @allure.title("IAM-项目管理-修改中间件配额")
    def test_iam_modify_middleware_quota(self, iam_page, iam_project):
        """项目修改中间件服务配额（5种中间件）。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1: 进入项目配额页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)
            iam_page.iam_open_project_quota(project_name)

        with allure_step_log("步骤2: 过滤中间件服务"):
            if not filter_quota_service_type(iam_page, "中间件"):
                return

        with allure_step_log("步骤3: 分配中间件配额"):
            mw_services = [
                "AnhanDB(for Redis)", "云搜索服务CSS",
                "分布式消息服务Kafka", "分布式消息服务 RabbitMQ",
                "监控服务Prometheus",
            ]
            mw_quotas = {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000}
            mw_asserts = [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")]
            mw_actuals = {}
            for svc in mw_services:
                actual = modify_and_assert_quota(iam_page, svc, mw_quotas.copy(), mw_asserts)
                if actual:
                    mw_actuals[svc] = actual

        with allure_step_log("步骤6: 反向验证一级组织使用量"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_open_org_quota(iam_project["parent_org_name"])
            for svc, actual in mw_actuals.items():
                assert assert_org_quota_usage(iam_page, svc, "cpu使用量(个)", actual["cpu总量(个)"]), f"{svc} cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, svc, "内存使用量(GiB)", actual["内存总量(GiB)"]), f"{svc} 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, svc, "云硬盘使用总量(GiB)", actual["云硬盘总量(GiB)"]), f"{svc} 云硬盘反向验证失败"

    @allure.title("IAM-项目管理-修改容器服务配额")
    def test_iam_modify_container_quota(self, iam_page, iam_project):
        """项目修改容器服务配额（CCE/SCR）。"""
        project_name = iam_project["project_name"]
        child_org = iam_project["child_org_name"]

        with allure_step_log("步骤1: 进入项目配额页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_goto_project_management(child_org)
            iam_page.iam_open_project_quota(project_name)

        with allure_step_log("步骤2: 过滤容器服务"):
            if not filter_quota_service_type(iam_page, "容器服务"):
                return

        with allure_step_log("步骤3: 分配容器服务配额"):
            ctn_quotas = {"cpu总量(个)": 100, "内存总量(GiB)": 100, "云硬盘总量(GiB)": 1000}
            ctn_asserts = [("cpu使用量(个)", "0/100"), ("内存使用量(GiB)", "0/100"), ("云硬盘使用总量(GiB)", "0/1000")]
            actual_cce = modify_and_assert_quota(iam_page, "云容器引擎CCE", ctn_quotas, ctn_asserts)
            actual_scr = modify_and_assert_quota(iam_page, "容器镜像服务SCR", ctn_quotas, ctn_asserts)

        with allure_step_log("步骤6: 反向验证一级组织使用量"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.iam_open_org_quota(iam_project["parent_org_name"])
            if actual_cce:
                assert assert_org_quota_usage(iam_page, "云容器引擎CCE", "cpu使用量(个)", actual_cce["cpu总量(个)"]), "CCE cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "云容器引擎CCE", "内存使用量(GiB)", actual_cce["内存总量(GiB)"]), "CCE 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "云容器引擎CCE", "云硬盘使用总量(GiB)", actual_cce["云硬盘总量(GiB)"]), "CCE 云硬盘反向验证失败"
            if actual_scr:
                assert assert_org_quota_usage(iam_page, "容器镜像服务SCR", "cpu使用量(个)", actual_scr["cpu总量(个)"]), "SCR cpu反向验证失败"
                assert assert_org_quota_usage(iam_page, "容器镜像服务SCR", "内存使用量(GiB)", actual_scr["内存总量(GiB)"]), "SCR 内存反向验证失败"
                assert assert_org_quota_usage(iam_page, "容器镜像服务SCR", "云硬盘使用总量(GiB)", actual_scr["云硬盘总量(GiB)"]), "SCR 云硬盘反向验证失败"
