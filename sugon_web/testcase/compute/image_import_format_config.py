from sugon_web.config.config import Config


DEFAULT_IMAGE_IMPORT_FORMAT_URLS = {
    "VMDK": "http://172.22.5.66:9090/offlinePackage/image_download/support-fsagent/centos7.9_test.vmdk",
    "VHD": "http://172.22.5.66:9090/offlinePackage/image_download/support-fsagent/centos7.9_test.vhd",
    "VHDX": "http://172.22.5.66:9090/offlinePackage/image_download/support-fsagent/centos7.9_test.vhdx",
    "QCOW2": "http://172.22.5.66:9090/offlinePackage/image_download/support-fsagent/centos7.9.qcow2",
    "ISO_Kylin": "http://172.22.5.177/offlinePackage/cloud-os/cloud-kylin-v10sp3-2403-amd64-4.19.90-89.19-20260520.iso",
    "ISO_Anolis": "http://172.22.5.177/offlinePackage/cloud-os/cloud-anolis-8.6-amd64-5.10.134-18-20260601.iso",
}


def get_image_import_format_url(format_name: str) -> str:
    """Return the image URL for a format case, with environment config override support."""
    configured_urls = Config.get("image_import_format_urls", {}) or {}
    url = configured_urls.get(format_name) or DEFAULT_IMAGE_IMPORT_FORMAT_URLS.get(format_name)
    if not url:
        raise AssertionError(f"未配置镜像导入格式 {format_name} 的 URL")
    return url
