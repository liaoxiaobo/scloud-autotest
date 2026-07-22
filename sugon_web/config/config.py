import os
import re
import threading
import yaml
from types import MappingProxyType

from sugon_web.utils.logger import logger


class Config:
    """三层合并配置管理（base.yaml + env.yaml + CLI），线程安全。

    每个线程拥有独立的配置副本，通过 threading.local() 隔离，
    避免多线程/并发场景下的配置串扰。

    使用方式：
        Config.load(host="172.22.1.190")          # 加载并合并配置
        Config.override(browser="chromium")       # 动态覆盖
        Config.set("_node_count", 3)              # 运行时写入
        Config.get("host")                         # 读取单项
        Config.get()                               # 读取全部（只读视图）
    """

    _local = threading.local()

    @classmethod
    def load(cls, host):
        """加载配置文件，根据 host 参数合并特定环境配置。

        Args:
            host: 要加载的特定环境配置，如果为 None 则使用 base.yaml 中的 host 值
        """
        with open(os.path.join(os.path.dirname(__file__), "base.yaml"), encoding="utf-8") as f:
            base_cfg = yaml.safe_load(f)

        with open(os.path.join(os.path.dirname(__file__), "env.yaml"), encoding="utf-8") as f:
            env_cfg = yaml.safe_load(f)

        if host is None:
            host = base_cfg.get("host")
            if host is None:
                error_msg = "错误: base.yaml中未找到host配置，且命令行未提供--host参数"
                logger.error(error_msg)
                raise ValueError(error_msg)

        matched_host_config = None
        if "env" in env_cfg:
            for host_config in env_cfg["env"]:
                if host_config.get("host") == host:
                    matched_host_config = host_config
                    break

        merged = base_cfg.copy()
        if matched_host_config:
            merged.update(matched_host_config)
            logger.info(f"读取环境 {host} 的特定配置")
        else:
            merged["host"] = host
            logger.info(f"未找到环境 {host} 的特定配置")

        merged["host"] = host
        merged["base_url"] = f"https://{host}:30000"
        logger.info(f"生成 base_url: {merged['base_url']}")

        cls._local.config = merged

    @classmethod
    def override(cls, browser=None, headless=None, stor=None, user_role=None):
        """通过代码动态覆盖部分配置（通常用于命令行参数注入）。"""
        cfg = cls._ensure_config()

        if browser is not None:
            valid_browsers = ["chromium", "firefox", "webkit"]
            if browser not in valid_browsers:
                error_msg = f"无效的浏览器类型: {browser}。支持的选项: {valid_browsers}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            cfg["browser"] = browser
            logger.info(f"配置命令行参数 browser={browser}")

        if headless is not None:
            cfg["headless"] = headless.lower() == "true"
            logger.info(f"配置命令行参数 headless={cfg['headless']}")

        if stor is not None:
            cfg["stor"] = stor
            logger.info(f"配置命令行参数 stor={stor}")

        if user_role is not None:
            valid_roles = ["admin", "dept_admin", "user"]
            if user_role not in valid_roles:
                error_msg = f"无效的用户角色: {user_role}。支持的选项: {valid_roles}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            cfg["user_role"] = user_role
            logger.info(f"配置命令行参数 user_role={user_role}")

    @classmethod
    def get(cls, key=None, default=None):
        """获取配置值。

        Args:
            key: 配置项的键，如果为 None 则返回所有配置（只读视图）
            default: 当 key 不存在时的默认值

        Returns:
            如果 key 为 None，返回 MappingProxyType 只读视图；
            否则返回指定配置值或默认值
        """
        cfg = getattr(cls._local, "config", {})
        if key is None:
            return MappingProxyType(cfg)
        return cfg.get(key, default)

    @classmethod
    def set(cls, key, value):
        """运行时写入配置项。

        替代直接操作 Config._config 的野路子，确保线程安全。

        Args:
            key: 配置项键名
            value: 配置项值
        """
        cfg = cls._ensure_config()
        cfg[key] = value

    @classmethod
    def _ensure_config(cls):
        """确保当前线程的配置字典已初始化。"""
        if not hasattr(cls._local, "config"):
            cls._local.config = {}
        return cls._local.config
