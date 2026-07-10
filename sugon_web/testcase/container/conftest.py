import pytest

from sugon_web.pages.container import CcePage, ScrPage, SsmPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.data import random_data


@pytest.fixture(scope="function")
def cce_page(page):
    """初始化云容器引擎CCE页面对象。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        CcePage: 云容器引擎页面对象实例。
    """
    return CcePage(page)


@pytest.fixture(scope="function")
def scr_page(page):
    """初始化容器镜像服务SCR页面对象。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        ScrPage: 容器镜像服务页面对象实例。
    """
    return ScrPage(page)


def _build_cce_create_kwargs(params=None):
    """根据参数构建CCE集群创建入参。"""
    params = params or {}
    return {
        "name": params.get("name", f"cce-{random_data(length=3)}"),
        "node_count": params.get("node_count", 4),
        "version": params.get("version", "1.22.17"),
        "container_runtime": params.get("container_runtime", "docker"),
        "proxy_mode": params.get("proxy_mode", "ipvs"),
        "desc": params.get("desc", "测试cce"),
        "network_model": params.get("network_model", "flannel"),
        "volume_size": params.get("volume_size", 50),
        "flavor": params.get("flavor", "4C8G"),
        "vpc_network": params.get("vpc_network", "Autotest"),
        "vpc_subnet": params.get("vpc_subnet", "Autotest"),
    }


def _create_cce_cluster(cce_page, params=None):
    """创建CCE集群并返回资源信息。"""
    create_kwargs = _build_cce_create_kwargs(params)

    cce_page.cce_create(**create_kwargs)
    cce_page.assert_popup_success()

    return create_kwargs


def _cleanup_cce_cluster(cce_page, ssh_host, name):
    """清理CCE集群资源，并后台验证虚机和云硬盘已删除。"""
    cce_page.goto_service(cce_page.service_name)
    cce_page.cce_delete(name)
    cce_page.assert_deleted(name)
    ssh_host.wait_vm_deleted(name, timeout=600)
    ssh_host.wait_volume_deleted(name, timeout=600)


@pytest.fixture(scope="module")
def cce_cluster(browser_context, config, ssh_host, request):
    """创建CCE集群并等待就绪，测试模块结束后自动清理（scope=module）。

    Args:
        browser_context: Playwright 浏览器上下文，由 pytest fixture 提供。
        ssh_host: SSH 主机连接对象，用于查询 MFIP。
        request: pytest 请求对象，用于获取参数化配置。

    request.param 支持的参数：
        name (str): 集群名称，未提供时自动生成随机名称。
        node_count (int): 节点数量，默认4。
        version (str): Kubernetes版本，默认"1.22.17"。
        container_runtime (str): 容器运行时，默认"docker"。
        proxy_mode (str): 代理模式，默认"ipvs"。
        desc (str): 描述，默认"测试cce"。
        network_model (str): 容器网络模型，默认"flannel"。
        volume_size (int): 云硬盘大小，默认50。
        flavor (str): 节点规格，默认"4C8G"。

    Yields:
        dict: 集群资源字典，包含创建参数及运行时信息：
            - name (str): 集群名称
            - node_count (int): 节点数量
            - version (str): Kubernetes版本
            - container_runtime (str): 容器运行时
            - proxy_mode (str): 代理模式
            - network_model (str): 容器网络模型
            - volume_size (int): 云硬盘大小
            - flavor (str): 节点规格
            - node_data (list): UI 节点列表数据
            - master_node_ip (str): 控制节点内网IP
            - worker_node_ip (str): 计算节点内网IP
            - master_mfip (str): SSH 连接控制节点用的 MFIP
            - worker_mfip (str): SSH 连接计算节点用的 MFIP
            - master_node (str): 控制节点名称
            - worker_node (str): 计算节点名称
    """
    from sugon_web.conftest import _create_logged_in_page

    # 临时调试开关：复用环境已有的 CCE 集群（填集群名则复用，空字符串则创建/删除）
    reuse_name = ""

    params = getattr(request, "param", {}) or {}
    page = _create_logged_in_page(browser_context, config)
    cce_page = CcePage(page)

    if reuse_name:
        create_kwargs = _build_cce_create_kwargs({**params, "name": reuse_name})
        cluster_name = create_kwargs["name"]
        with allure_step_log(f"前置操作：检查并复用已有CCE集群 {cluster_name}"):
            cce_page.goto_submenu("集群管理")
            cce_page.wait_for_page_ready()
            try:
                existing_row = cce_page.get_row_data(cluster_name)
            except AssertionError:
                existing_row = None
            if existing_row:
                logger.info(f"复用已有集群 {cluster_name}，跳过创建")
            else:
                raise AssertionError(f"未找到名称为 '{cluster_name}' 的已有CCE集群，请确认集群存在或清空 reuse_name 走创建逻辑")
    else:
        create_kwargs = _build_cce_create_kwargs(params)
        cluster_name = create_kwargs["name"]
        with allure_step_log(f"前置操作：创建CCE集群 {cluster_name}"):
            cce_page.cce_create(**create_kwargs)
            cce_page.assert_popup_success()
            cce_page.assert_status(cluster_name, status="运行中", timeout=1200)

    with allure_step_log(f"前置操作：获取集群 {cluster_name} 运行时信息"):
        node_data = cce_page.get_cluster_node_data(cluster_name)
        assert node_data, f"获取集群 {cluster_name} 节点数据失败，返回空列表"

    master_nodes = [n for n in node_data if n.get("类型") == "控制节点"]
    worker_nodes = [n for n in node_data if n.get("类型") == "计算节点"]
    master_node = master_nodes[0].get("名称") if master_nodes else ""
    worker_node = worker_nodes[0].get("名称") if worker_nodes else ""
    master_node_ip = master_nodes[0].get("内网IP") if master_nodes else ""
    worker_node_ip = worker_nodes[0].get("内网IP") if worker_nodes else ""
    mfip = ssh_host.find_mfip(master_node_ip) if master_node_ip else ""
    worker_mfip = ssh_host.find_mfip(worker_node_ip) if worker_node_ip else ""

    yield {
        "name": cluster_name,
        "master_node_ip": master_node_ip,
        "worker_node_ip": worker_node_ip,
        "master_mfip": mfip,
        "worker_mfip": worker_mfip,
        "master_node": master_node,
        "worker_node": worker_node,
        "cce_page": cce_page,
        **create_kwargs,
    }

    if reuse_name:
        with allure_step_log(f"后置清理：复用集群 {cluster_name}，跳过删除"):
            logger.info(f"集群 {cluster_name} 为环境已有资源，不做清理")
    else:
        with allure_step_log(f"后置清理：删除CCE集群 {cluster_name}"):
            try:
                _cleanup_cce_cluster(cce_page, ssh_host, cluster_name)
            except Exception as e:
                logger.warning(f"清理CCE集群失败（可能已删除）: {e}")
    page.close()


@pytest.fixture(scope="module")
def storage_class(cce_cluster):
    """创建模块级共享 StorageClass，供同一模块内资源操作类用例复用。

    复用 cce_cluster fixture 创建的 page，避免额外打开新标签页。

    Yields:
        dict: 包含 name (str) 和 cluster_name (str)
    """
    cluster_name = cce_cluster["name"]
    sc_name = f"evs-sc-{random_data(length=4)}"
    cce_page = cce_cluster["cce_page"]

    with allure_step_log(f"前置操作：创建 StorageClass {sc_name}"):
        cce_page.goto_submenu("集群管理")
        cce_page.goto_detail_page(cluster_name, tab_name="存储类型")
        cce_page.storage_class_create(
            name=sc_name,
            volume_type=cce_page.volume_type,
            fstype="ext4",
            encrypt=False,
            access_mode="ReadWriteOnce"
        )
        cce_page.assert_popup_success()

    yield {"name": sc_name, "cluster_name": cluster_name}

    with allure_step_log(f"后置清理：删除 StorageClass {sc_name}"):
        try:
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="存储类型")
            cce_page.storage_class_delete(sc_name)
        except Exception as e:
            logger.warning(f"清理 StorageClass 失败（可能已删除）: {e}")
        # page 由 cce_cluster fixture 在后置清理中统一关闭


def _build_scr_create_kwargs(params=None):
    """根据参数构建 SCR 实例创建入参。"""
    params = params or {}
    return {
        "name": params.get("name", f"scr-{random_data(length=4)}"),
        "version": params.get("version"),
        "cluster": params.get("cluster", "Autotest"),
        "network": params.get("network", "Autotest"),
        "subnet": params.get("subnet", "Autotest"),
        "instance_type": params.get("instance_type", "ALONE"),
        "storage_type": params.get("storage_type", "EVS"),
        "volume_type": params.get("volume_type"),
        "volume_size": params.get("volume_size", 10),
        "flavor": params.get("flavor", "4C8G"),
    }


def _create_scr_instance(scr_page, params=None):
    """创建 SCR 实例并返回资源信息。"""
    create_kwargs = _build_scr_create_kwargs(params)
    scr_page.scr_create(**create_kwargs)
    scr_page.assert_popup_success()
    return create_kwargs


def _cleanup_scr_instance(scr_page, ssh_host, name):
    """清理 SCR 实例资源，并后台验证虚机已删除。"""
    scr_page.goto_service(scr_page.service_name)
    scr_page.goto_submenu("实例管理")
    scr_page.scr_delete(name)
    scr_page.assert_deleted(name, timeout=600)
    ssh_host.wait_vm_deleted(name, timeout=600)


@pytest.fixture(scope="class")
def scr_instance(browser_context, config, ssh_host, request):
    """创建 SCR 单机实例并等待就绪，测试类结束后自动清理。

    Args:
        browser_context: Playwright 浏览器上下文，由 pytest fixture 提供。
        config: 配置对象。
        ssh_host: SSH 主机连接对象，用于后台验证。
        request: pytest 请求对象，用于获取参数化配置。

    request.param 支持的参数：
        name (str): 实例名称，未提供时自动生成随机名称。
        version (str): 仓库版本，默认使用页面初始化选项。
        cluster (str): 集群名称，默认 "Autotest"。
        network (str): 专有网络名称，默认 "Autotest"。
        subnet (str): 子网名称，默认 "Autotest"。
        instance_type (str): 实例类型，默认 "ALONE"。
        storage_type (str): 存储类型，默认 "EVS"。
        volume_type (str): 云硬盘类型，默认从配置读取。
        volume_size (int): 云硬盘大小(GiB)，默认 5。
        flavor (str): 规格名称，默认 "4C8G"。

    Yields:
        dict: 实例资源字典，包含创建参数及运行时信息：
            - name (str): 实例名称
            - id (str): 实例 ID
            - instance_type (str): 实例类型
            - storage_type (str): 存储类型
            - cluster (str): 集群名称
            - network (str): 专有网络名称
            - subnet (str): 子网名称
            - volume_size (int): 云硬盘大小
            - flavor (str): 规格名称
    """
    from sugon_web.conftest import _create_logged_in_page

    params = getattr(request, "param", {}) or {}
    page = _create_logged_in_page(browser_context, config)
    scr_page = ScrPage(page)

    create_kwargs = _build_scr_create_kwargs(params)
    instance_name = create_kwargs["name"]

    with allure_step_log(f"前置操作：创建 SCR 实例 {instance_name}"):
        scr_page.scr_create(**create_kwargs)
        scr_page.assert_popup_success()
        scr_page.assert_status(instance_name, status="运行中", timeout=1200)

    with allure_step_log(f"前置操作：获取 SCR 实例 {instance_name} 详情"):
        row_data = scr_page.get_row_data(instance_name)
        instance_id = row_data.get("ID", "") if row_data else ""

    yield {
        "name": instance_name,
        "id": instance_id,
        **create_kwargs,
    }

    with allure_step_log(f"后置清理：删除 SCR 实例 {instance_name}"):
        try:
            _cleanup_scr_instance(scr_page, ssh_host, instance_name)
        except Exception as e:
            logger.warning(f"清理 SCR 实例失败（可能已删除）: {e}")
        finally:
            page.close()


@pytest.fixture(scope="function")
def ssm_page(page):
    """初始化服务治理SSM页面对象。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        SsmPage: 服务治理SSM页面对象实例。
    """
    return SsmPage(page)


@pytest.fixture(scope="module")
def mesh_instance(browser_context, config, cce_cluster, request):
    """创建模块级共享 SSM 网格实例，供同一模块内资源操作类用例复用。

    Args:
        browser_context: Playwright 浏览器上下文，由 pytest fixture 提供。
        config: 配置对象。
        cce_cluster: 模块级 CCE 集群 fixture。
        request: pytest 请求对象。

    Yields:
        dict: 网格实例资源字典：
            - name (str): 网格实例名称
            - cluster_name (str): 所属CCE集群名称
            - page (Page): 登录页面实例
            - ssm_page (SsmPage): SSM页面对象实例
    """
    from sugon_web.conftest import _create_logged_in_page

    page = _create_logged_in_page(browser_context, config)
    ssm_page = SsmPage(page)
    cluster_name = cce_cluster["name"]
    name = f"mesh-{random_data(length=4)}"

    with allure_step_log(f"前置操作：创建共享网格实例 {name}，使用集群 {cluster_name}"):
        ssm_page.mesh_create(name=name, cluster=cluster_name)
        ssm_page.assert_popup_success()
        ssm_page.assert_status(name, status="安装完成", timeout=1800, refresh=True)

    yield {
        "name": name,
        "cluster_name": cluster_name,
        "page": page,
        "ssm_page": ssm_page,
    }

    with allure_step_log(f"后置清理：删除共享网格实例 {name}"):
        try:
            ssm_page.mesh_delete(name)
            ssm_page.assert_deleted(name, timeout=600)
        except Exception as e:
            logger.warning(f"清理共享网格实例失败（可能已删除）: {e}")
        finally:
            page.close()
