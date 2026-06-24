import json
import os
import re
import shutil
import string
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from random import choices

from sugon_web.config.config import Config
from sugon_web.utils.logger import allure_step_log


IMS_UPLOAD_IMAGE_ENV = "SUGON_IMS_UPLOAD_IMAGE_PATH"
PROJECT_UPLOAD_IMAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "test_data"
    / "ims_images"
    / "cirros-0.5.2"
    / "cirros-0.5.2.raw"
)
LOCAL_UPLOAD_IMAGE_PATH = Path(r"C:\Users\Administrator\Downloads\cirros-0.5.2")


def ims_image_name(*parts: str, suffix_len: int = 4) -> str:
    """生成 IMS 自动化镜像名称，格式为 ims-场景-动作-MMDD-随机后缀。"""
    clean_parts = []
    for part in parts:
        text = re.sub(r"[^a-zA-Z0-9]+", "-", str(part or "").strip().lower()).strip("-")
        if text:
            clean_parts.append(text)
    base = "-".join(clean_parts) or "image"
    if not base.startswith("ims-"):
        base = f"ims-{base}"
    date_part = datetime.now().strftime("%m%d")
    suffix = "".join(choices(string.ascii_lowercase + string.digits, k=suffix_len))
    return f"{base}-{date_part}-{suffix}"


def _choose_available_host(ssh_host):
    """根据 hypervisor 已用 vCPU 选择相对空闲的物理机节点。"""
    result = ssh_host.run("scli hypervisor list --format json")
    data = json.loads(result).get("data", [])
    if not data:
        return ""
    # 选择 vcpus_used 最小的 enabled 节点，返回短主机名（去掉 .cloud.local）
    candidates = [
        h for h in data
        if h.get("status", "").lower() == "enabled"
    ]
    if not candidates:
        return ""
    chosen = min(candidates, key=lambda h: h.get("vcpus_used", float("inf")))
    host = chosen.get("host", "")
    return host.replace(".cloud.local", "") if host else ""


def _get_image_uuid(ssh_host, image_name):
    result = ssh_host.run("scli image list --format json")
    data = json.loads(result).get("data", [])
    for item in data:
        if item.get("name") == image_name:
            return item.get("id", "")
    return ""


def _get_image_detail(ssh_host, image_name):
    image_uuid = _get_image_uuid(ssh_host, image_name)
    if not image_uuid:
        return {}
    return ssh_host.parse_table_output(ssh_host.run(f"scli image show {image_uuid}"))


def _get_ims_config_value(key, default=""):
    ims_config = Config.get("ims", {}) or {}
    return ims_config.get(key, default)


def _get_ims_image_url(key="upload_image_url"):
    url = _get_ims_config_value(key)
    if not url:
        # Fallback: construct from base config when ims section is missing
        image_source = Config.get("image_source", "")
        image_file = Config.get("image", "")
        if image_source and image_file:
            url = f"{image_source}/offlinePackage/image_download/support-fsagent/{image_file}"
        if not url:
            raise AssertionError(f"未配置 IMS 镜像地址: ims.{key}")
    return url


def _download_ims_image(url=None, config_key="upload_image_url"):
    image_url = url or _get_ims_image_url(config_key)
    local_dir = _get_ims_config_value("local_image_dir") or os.path.join(
        tempfile.gettempdir(), "sugon_ims_images"
    )
    os.makedirs(local_dir, exist_ok=True)

    parsed = urllib.parse.urlparse(image_url)
    filename = os.path.basename(parsed.path) or "ims-test-image.raw"
    local_path = os.path.join(local_dir, filename)
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return local_path

    tmp_path = f"{local_path}.download"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    timeout = int(_get_ims_config_value("download_timeout", 1800))
    with urllib.request.urlopen(image_url, timeout=timeout) as response:
        with open(tmp_path, "wb") as file_obj:
            shutil.copyfileobj(response, file_obj)
    if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
        raise AssertionError(f"IMS 镜像下载失败或文件为空: {image_url}")
    os.replace(tmp_path, local_path)
    return local_path


def _resolve_ims_upload_image_path(config_key="upload_image_url"):
    """获取 IMS 标准上传镜像文件，优先使用本地/项目固定文件。

    Jenkins 推荐把镜像预置到项目目录，或设置 SUGON_IMS_UPLOAD_IMAGE_PATH。
    如果本地文件不存在，再回退到 ims.upload_image_url 下载。
    """
    env_path = os.environ.get(IMS_UPLOAD_IMAGE_ENV, "").strip()
    candidates = [
        *( [Path(env_path), Path(f"{env_path}.raw")] if env_path else [] ),
        PROJECT_UPLOAD_IMAGE_PATH,
        LOCAL_UPLOAD_IMAGE_PATH,
        Path(f"{LOCAL_UPLOAD_IMAGE_PATH}.raw"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return _download_ims_image(config_key=config_key)


def _get_ecs_fixed_ip(ecs_page, ecs_name, row=None):
    row = row or ecs_page.get_row_data(ecs_name)
    ip_text = row.get("IP地址", "")
    fixed_match = re.search(r"固定[:：]\s*([0-9]+(?:\.[0-9]+){3})", ip_text)
    if fixed_match:
        return fixed_match.group(1)

    ip_matches = re.findall(r"[0-9]+(?:\.[0-9]+){3}", ip_text)
    if ip_matches:
        return ip_matches[-1]
    raise AssertionError(f"未从 ECS {ecs_name} 的 IP地址字段解析到固定IP: {ip_text}")


def _bind_mfip_for_ecs(ecs_page, ops_page, ecs_name, network="Autotest"):
    row = ecs_page.get_row_data(ecs_name)
    fixed_ip = _get_ecs_fixed_ip(ecs_page, ecs_name, row=row)
    project = row.get("项目名称") or "默认项目"
    # 并行无头模式下：先显式导航到平台网络，避免 bind_mfip 内部重复导航导致左侧菜单检测失败
    ops_page.goto_service("基础设施", force=True)
    ops_page.wait_for_page_ready()
    ops_page.goto_submenu("平台网络")
    # 直接调用 mfip_create（@submenu 装饰器会检查当前已在平台网络下，跳过重复导航）
    ops_page.mfip_create(project, network, fixed_ip)
    ops_page.assert_popup_success("执行成功")
    ops_page.mfip_search(fixed_ip)
    mfip = ops_page.get_row_data(fixed_ip).get("管理IP地址")
    return fixed_ip, mfip


def _cleanup_ecs_and_mfip(ecs_page, ops_page, ecs_name=None, fixed_ip=None, mfip=None):
    # 先清理 MFIP，避免 ECS 删除后 MFIP 已被级联释放导致搜索不到
    if mfip:
        with allure_step_log(f"清理 MFIP {mfip} (固定IP {fixed_ip})"):
            try:
                ops_page.close_dialog_if_exists()
                ops_page.goto_service("基础设施")
                ops_page.goto_submenu("平台网络")
                ops_page.mfip_search(mfip, search_by="管理IP")
                ops_page.mfip_delete(mfip)
            except Exception as exc:
                ops_page.logger.warning(f"清理 MFIP {mfip} 失败: {exc}")

    if ecs_name:
        with allure_step_log(f"清理 ECS {ecs_name}"):
            try:
                ecs_page.close_dialog_if_exists()
                ecs_page.goto_service("弹性云服务器")
                ecs_page.service_name = "弹性云服务器"
                ecs_page.goto_submenu("弹性云服务器")
                ecs_page.search(ecs_name)
                if ecs_page.get_row_by_name(ecs_name) is not None:
                    ecs_page.ecs_remove(ecs_name)
                    ecs_page.ecs_delete(ecs_name)
                    ecs_page.assert_deleted(ecs_name)
            except Exception as exc:
                ecs_page.logger.warning(f"清理 ECS {ecs_name} 失败: {exc}")


def _cleanup_image(ecs_page, image_name):
    if not image_name:
        return
    with allure_step_log(f"清理镜像 {image_name}"):
        try:
            ecs_page.close_dialog_if_exists()
            ecs_page.goto_service("弹性云服务器")
            ecs_page.service_name = "弹性云服务器"
            ecs_page.goto_submenu("镜像服务")
            ecs_page.search(image_name)
            if ecs_page.get_row_by_name(image_name) is not None:
                ecs_page.ecs_image_delete(image_name)
                ecs_page.assert_deleted(image_name, refresh=True)
        except Exception as exc:
            ecs_page.logger.warning(f"清理镜像 {image_name} 失败: {exc}")
