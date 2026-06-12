import pytest

from sugon_web.pages.container import CcePage
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


@pytest.fixture(scope="class")
def cce_cluster(browser_context, config, ssh_host, request):
    """创建CCE集群并等待就绪，测试类结束后自动清理。

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
            - mfip (str): SSH 连接用的 MFIP
            - master_node (str): 控制节点名称
            - worker_node (str): 计算节点名称
    """
    from sugon_web.conftest import _create_logged_in_page

    params = getattr(request, "param", {}) or {}
    page = _create_logged_in_page(browser_context, config)
    cce_page = CcePage(page)

    create_kwargs = _build_cce_create_kwargs(params)
    cluster_name = create_kwargs["name"]


    with allure_step_log(f"前置操作：创建CCE集群 {cluster_name}"):
        cce_page.cce_create(**create_kwargs)
        cce_page.assert_popup_success()
        cce_page.assert_status(cluster_name, status="运行中", timeout=1200)

    with allure_step_log(f"前置操作：获取集群 {cluster_name} 运行时信息"):
        node_data = cce_page.get_cluster_node_data(cluster_name)
        assert node_data, f"获取集群 {cluster_name} 节点数据失败，返回空列表"

        # 按节点类型分类，供不同用例选择
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
    }

    with allure_step_log(f"后置清理：删除CCE集群 {cluster_name}"):
        try:
            _cleanup_cce_cluster(cce_page, ssh_host, cluster_name)
        except Exception as e:
            logger.warning(f"清理CCE集群失败（可能已删除）: {e}")
        finally:
            page.close()


@pytest.fixture(scope="class")
def storage_class(browser_context, config, cce_cluster):
    """创建云硬盘存储类型并在测试类结束后自动清理。

    Yields:
        dict: 包含 name (str) 和 cluster_name (str)
    """
    from sugon_web.conftest import _create_logged_in_page

    cluster_name = cce_cluster["name"]
    sc_name = f"evs-sc-{random_data(length=4)}"
    page = _create_logged_in_page(browser_context, config)
    cce_page = CcePage(page)

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
        finally:
            page.close()
