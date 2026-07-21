from typing import Any

from sugon_web.config.config import Config
from sugon_web.utils.logger import allure_step_log, logger


def _oss_api_request(
    oss_page,
    method: str,
    path: str,
    params: dict[str, str] | None = None,
    json_body: dict | None = None,
) -> dict:
    """通过浏览器上下文直接调用 OSS 内部 API。

    自动从 localStorage 读取 token 与 regionId，适用于 teardown 阶段快速清理。
    """
    import json
    import urllib.parse

    host = Config.get("host")
    base_url = f"https://{host}:30000/api/sugoncloud-oss-api"
    url = base_url + path
    if params:
        url = url + "?" + urllib.parse.urlencode(params)

    headers = oss_page._oss_api_headers()
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    result = oss_page.page.evaluate(
        """async ({url, headers, method, body}) => {
            const opts = { method, headers };
            if (body) opts.body = JSON.stringify(body);
            const resp = await fetch(url, opts);
            const text = await resp.text();
            try { return JSON.parse(text); } catch(e) { return { _raw: text, _status: resp.status }; }
        }""",
        {"url": url, "headers": headers, "method": method, "body": json_body},
    )
    return result or {}


def _oss_api_list_all_objects(oss_page, bucket_name: str) -> list[str]:
    """通过 OSS API 列出桶内所有对象键（含文件夹占位对象），支持分页。"""
    keys: list[str] = []
    marker = ""
    for _ in range(20):
        params = {
            "bucket_name": bucket_name,
            "delimiter": "",
            "encoding_type": "url",
            "marker": marker,
            "max_keys": "1000",
            "prefix": "",
        }
        resp = _oss_api_request(oss_page, "GET", "/api/ossObject/page", params)
        if not resp or not resp.get("success"):
            raise AssertionError(f"列出桶 {bucket_name} 对象失败: {resp}")

        content = resp.get("content") or {}
        for item in content.get("objectSummaries") or []:
            key = item.get("objectKey")
            if key and key not in keys:
                keys.append(key)
        for item in content.get("extendCommonPrefixes") or []:
            key = item.get("objectKey")
            if key and key not in keys:
                keys.append(key)

        if not content.get("truncated"):
            break
        marker = content.get("nextMarker") or content.get("marker") or ""
        if not marker:
            break
    return keys


def _oss_api_delete_object(oss_page, bucket_name: str, object_key: str) -> None:
    """通过 OSS API 删除指定对象键，包括当前对象及所有历史版本。"""
    import urllib.parse

    encoded_key = urllib.parse.quote(object_key, safe="")
    params = {"bucketName": bucket_name, "ossObjectKey": encoded_key}

    # 1. 先尝试普通删除（兼容未开启版本控制的桶）
    resp1 = _oss_api_request(oss_page, "DELETE", "/api/ossObject", params)
    # 2. 再彻底删除所有版本（兼容开启版本控制的桶）
    resp2 = _oss_api_request(oss_page, "DELETE", "/api/ossObject/all/objectVersions", params)

    # 若两次 API 均明确失败，仅记录警告；teardown 阶段优先保证桶删除流程继续
    if resp1 and not resp1.get("success") and resp2 and not resp2.get("success"):
        logger.warning(
            f"API 删除对象 {bucket_name}/{object_key} 两次尝试均未成功: {resp1} / {resp2}"
        )


def _empty_oss_bucket_via_ui(oss_page, bucket_name: str) -> None:
    """通过 UI 交互清空桶内对象与碎片（API 不可用时回退使用）。"""
    with allure_step_log(f"UI 清空OSS桶: {bucket_name}"):
        # 1. 删除对象（含文件夹）
        for _ in range(10):
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            if not objects:
                break
            for obj in objects:
                try:
                    oss_page.oss_bucket_delete_object(bucket_name, obj)
                except Exception:
                    try:
                        oss_page.oss_bucket_delete_folder(bucket_name, obj)
                    except Exception as e2:
                        logger.warning(f"UI 删除 {bucket_name}/{obj} 失败: {e2}")

        # 2. 删除碎片
        try:
            fragments = oss_page.oss_bucket_get_fragments(bucket_name)
            for f in fragments:
                try:
                    oss_page.oss_bucket_delete_fragment(bucket_name, f.get("objectKey", f))
                except Exception as e:
                    logger.warning(f"UI 删除碎片 {bucket_name}/{f} 失败: {e}")
        except Exception as e:
            logger.warning(f"UI 获取碎片列表失败: {e}")


def empty_oss_bucket(oss_page, bucket_name: str) -> None:
    """清空 OSS 桶内所有对象、文件夹、碎片及多版本数据。

    优先调用 OSS 内部 API 快速清空；API 失败时回退到 UI 交互清空。
    """
    with allure_step_log(f"清空OSS桶: {bucket_name}"):
        # 1. 清理碎片（多段上传任务）
        try:
            fragments = oss_page.oss_bucket_list_fragments_via_api(bucket_name)
            for f in fragments:
                try:
                    oss_page.oss_bucket_delete_fragment_via_api(
                        bucket_name, f["objectKey"], f["uploadId"]
                    )
                except Exception as e:
                    logger.warning(f"删除碎片 {bucket_name}/{f['objectKey']} 失败: {e}")
        except Exception as e:
            logger.warning(f"通过 API 获取碎片列表失败: {e}")

        # 2. 清理对象（含文件夹占位与所有版本）
        try:
            keys = _oss_api_list_all_objects(oss_page, bucket_name)
            for key in keys:
                try:
                    _oss_api_delete_object(oss_page, bucket_name, key)
                except Exception as e:
                    logger.warning(f"API 删除对象 {bucket_name}/{key} 失败: {e}")
        except Exception as e:
            logger.warning(f"通过 API 列出对象失败，回退到 UI 清空: {e}")
            _empty_oss_bucket_via_ui(oss_page, bucket_name)


def _oss_api_delete_bucket(oss_page, bucket_name: str) -> None:
    """通过 OSS 内部 API 直接删除桶（桶须已为空）。"""
    import urllib.parse

    encoded = urllib.parse.quote(bucket_name, safe="")
    resp = _oss_api_request(oss_page, "DELETE", f"/api/bucket/{encoded}")
    if resp and not resp.get("success"):
        raise AssertionError(f"API 删除桶 {bucket_name} 失败: {resp}")


def create_oss_bucket(
    oss_page,
    name: str,
    region: str = "RegionOne",
    az_strategy: str = "MULTI_AZ",
    storage_class: str = "标准存储",
    bucket_strategy: str = "私有",
    is_encryption: bool = True,
    data_read: bool = False,
    tags: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """创建 OSS 对象存储桶。

    完整流程：导航到对象存储服务页面 -> 等待页面就绪 -> 调用页面方法创建桶。

    Args:
        oss_page: OssPage 页面对象。
        name: 桶名称。
        region: 区域，默认 "RegionOne"。
        az_strategy: 数据冗余存储策略，默认 "MULTI_AZ"。
        storage_class: 默认存储类别，默认 "标准存储"。
        bucket_strategy: 桶策略，默认 "私有"。
        is_encryption: 是否开启默认加密，默认 True。
        data_read: 归档数据直读，默认 False。
        tags: 标签列表，默认 None。

    Returns:
        dict: 包含 name 及所有实际使用参数的完整字典。
    """
    with allure_step_log(f"创建OSS桶: {name}"):
        oss_page.goto_service("对象存储")
        oss_page.wait_for_page_ready()
        oss_page.oss_bucket_create(
            name=name,
            region=region,
            az_strategy=az_strategy,
            storage_class=storage_class,
            bucket_strategy=bucket_strategy,
            is_encryption=is_encryption,
            data_read=data_read,
            tags=tags,
        )

    return {
        "name": name,
        "region": region,
        "az_strategy": az_strategy,
        "storage_class": storage_class,
        "bucket_strategy": bucket_strategy,
        "is_encryption": is_encryption,
        "data_read": data_read,
        "tags": tags,
    }


def delete_oss_bucket(oss_page, name: str) -> None:
    """删除 OSS 对象存储桶。

    删除前先强制清空桶内对象、碎片及多版本数据，再优先通过 API 删除桶；
    API 删除失败时回退到 UI 删除流程。若桶已不存在则跳过删除并记录日志。

    Args:
        oss_page: OssPage 页面对象。
        name: 要删除的桶名称。
    """
    with allure_step_log(f"删除OSS桶: {name}"):
        try:
            # 先关闭可能残留的弹窗/抽屉，避免遮挡后续导航/搜索操作
            oss_page.close_dialog_if_exists()
            try:
                oss_page._close_task_drawer_if_exists()
            except Exception:
                pass

            # 关键：删除前先清空桶，确保非空桶也能被删除
            try:
                empty_oss_bucket(oss_page, name)
            except Exception as e:
                logger.warning(f"清空桶 {name} 失败，仍尝试继续删除桶: {e}")

            # 优先通过 API 删除桶（teardown 阶段不需要再验证 UI 删除流程）
            try:
                _oss_api_delete_bucket(oss_page, name)
            except Exception as e:
                logger.warning(f"API 删除桶 {name} 失败，回退到 UI 删除: {e}")
                oss_page._goto_bucket_list()
                oss_page.oss_bucket_delete(name)

            # 校验桶已从列表消失
            oss_page._goto_bucket_list()
            oss_page.assert_deleted(name)
        except Exception as e:
            if "未找到" in str(e) or "not found" in str(e).lower():
                logger.info(f"OSS桶 {name} 已不存在，跳过删除")
                return
            logger.error(f"删除OSS桶 {name} 失败: {e}")
            raise


def upload_oss_object(oss_page, bucket_name: str, file_path: str) -> dict[str, Any]:
    """上传对象到指定 OSS 桶。

    Args:
        oss_page: OssPage 页面对象。
        bucket_name: 目标桶名称。
        file_path: 本地文件绝对路径。

    Returns:
        dict: 包含 object_name（对象名称，取文件名）及 file_path。
    """
    import os

    object_name = os.path.basename(file_path)
    with allure_step_log(f"上传对象到桶 {bucket_name}: {object_name}"):
        oss_page.goto_service("对象存储")
        oss_page.wait_for_page_ready()
        oss_page.oss_bucket_upload_object(bucket_name, file_path)

    return {"object_name": object_name, "file_path": file_path}


def delete_oss_object(oss_page, bucket_name: str, object_name: str) -> None:
    """删除 OSS 桶内指定对象。

    若对象已不存在则跳过删除并记录日志。

    Args:
        oss_page: OssPage 页面对象。
        bucket_name: 桶名称。
        object_name: 对象名称。
    """
    with allure_step_log(f"删除对象 {bucket_name}/{object_name}"):
        try:
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            if object_name not in objects:
                logger.info(f"对象 {bucket_name}/{object_name} 已不存在，跳过删除")
                return
            oss_page.oss_bucket_delete_object(bucket_name, object_name)
            # 删除为异步，轮询确认对象已从列表消失（每次 get_objects 会重新导航刷新）
            for _ in range(4):
                objects = oss_page.oss_bucket_get_objects(bucket_name)
                if object_name not in objects:
                    return
                oss_page.page.wait_for_timeout(3000)
            raise AssertionError(f"对象 {object_name} 删除后仍存在于桶 {bucket_name}")
        except Exception as e:
            if "已不存在" in str(e) or "not found" in str(e).lower():
                logger.info(f"对象 {bucket_name}/{object_name} 已不存在，跳过删除")
                return
            logger.error(f"删除对象 {bucket_name}/{object_name} 失败: {e}")
            raise


