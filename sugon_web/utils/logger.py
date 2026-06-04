import io
import allure
import logging
import time
import os
from contextlib import contextmanager
from pathlib import Path


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

class StepLogCollector:
    def __init__(self, logger_name=None):
        self.log_buffer = io.StringIO()
        self.buffer_handler = None
        self.target_logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()

    def __enter__(self):
        # 创建缓冲区处理器
        self.buffer_handler = logging.StreamHandler(self.log_buffer)
        self.buffer_handler.setLevel(logging.INFO)

        # 设置日志格式
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d [%(levelname)s] %(filename)s:%(lineno)d %(message)s"
        )
        self.buffer_handler.setFormatter(formatter)

        # 只添加缓冲区处理器，保留原有的控制台处理器
        self.target_logger.addHandler(self.buffer_handler)
        self.target_logger.setLevel(logging.INFO)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 移除缓冲区处理器
        self.target_logger.removeHandler(self.buffer_handler)

        # 获取并附加日志内容到allure
        log_content = self.log_buffer.getvalue()
        if log_content.strip():
            allure_report_dir = os.environ.get("_ALLURE_REPORT_DIR")
            if allure_report_dir:
                Path(allure_report_dir).mkdir(parents=True, exist_ok=True)
            allure.attach(
                log_content,
                name="步骤日志",
                attachment_type=allure.attachment_type.TEXT
            )

        self.log_buffer.close()

@contextmanager #声明一个上下文管理器  普通函数支持with语法
def allure_step_log(step_name): #step_name用例步骤
    with allure.step(step_name): #添加步骤 步骤记录在日志器
        with StepLogCollector() as collector:
            yield collector #暂停执行
