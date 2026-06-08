from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


def create_labels(ecs_page, *, count=1):
    """批量创建标签并返回实际标签名列表。"""
    label_names = []
    for _ in range(count):
        name = f"label-{random_data()}"
        label_name = ecs_page.create_label(name)
        ecs_page.assert_popup_success("新建标签成功")
        label_names.append(label_name)
        logger.info(f"已创建标签: {label_name}")
    return label_names


def delete_labels(ecs_page, label_names):
    """批量删除标签，供标签类 fixture 统一清理使用。"""
    if not label_names:
        return

    ecs_page.goto_service("弹性云服务器")
    ecs_page.goto_submenu("标签")
    ecs_page.batch_delete_label(label_names)
    logger.info(f"标签清理完成: {label_names}")
