import logging
import time
import os


def setup_logger():
    """获取标准的 logger 实例，日志输出由 pytest 统一管理"""
    logger = logging.getLogger(__name__)
    # logger.setLevel(logging.INFO)
    #
    # # 控制台处理器
    # ch = logging.StreamHandler()
    # ch.setLevel(logging.INFO)
    #
    # # 获取项目根目录，确保logs文件夹始终在项目根目录下
    # project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # log_dir = os.path.join(project_root, "logs")
    # if not os.path.exists(log_dir):
    #     os.makedirs(log_dir)
    #
    # # 文件处理器（按日期分割）
    # fh = logging.FileHandler(f"{log_dir}/test_{time.strftime('%Y%m%d')}.log", encoding='utf-8')
    # fh.setLevel(logging.INFO)
    #
    # # 格式
    # formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    # ch.setFormatter(formatter)
    # fh.setFormatter(formatter)
    #
    # logger.addHandler(ch)
    # logger.addHandler(fh)
    return logger


logger = setup_logger()
