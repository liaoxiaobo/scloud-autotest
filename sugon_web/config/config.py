import os
import yaml
from sugon_web.utils.logger import logger


class Config:
    # 通过类变量加载一次配置，供所有调用共享，避免重复加载
    _config = {}

    @classmethod
    def load(cls, host):
        """
        加载配置文件，根据host参数合并特定环境配置

        Args:
            host: 要加载的特定环境配置，如果为None则使用base.yaml中的host值
        """
        # 加载基础配置
        with open(os.path.join(os.path.dirname(__file__), "base.yaml"), encoding='utf-8') as f:
            base_cfg = yaml.safe_load(f)

        # 加载环境配置
        with open(os.path.join(os.path.dirname(__file__), "env.yaml"), encoding='utf-8') as f:
            env_cfg = yaml.safe_load(f)

        # 如果未提供host参数，则使用base.yaml中的host值
        if host is None:
            host = base_cfg.get("host")
            if host is None:
                # 如果base.yaml中也没有host，则抛出错误
                error_msg = "错误: base.yaml中未找到host配置，且命令行未提供--host参数"
                logger.error(error_msg)
                raise ValueError(error_msg)

        # 查找匹配的环境配置
        matched_host_config = None
        if "env" in env_cfg:
            for host_config in env_cfg["env"]:
                if host_config.get("host") == host:
                    matched_host_config = host_config
                    break

        # 使用基础配置作为默认配置
        cls._config = base_cfg.copy()  # 使用base的副本，避免修改原始配置

        # 如果找到了匹配的环境配置，则合并
        if matched_host_config:
            # 合并基础配置和特定环境配置
            cls._config.update(matched_host_config)
            logger.info(f"读取环境 {host} 的特定配置")
        else:
            # 修复：确保配置字典中的 host 与传入参数一致
            cls._config["host"] = host
            # 如果没有找到匹配的环境配置，只使用基础配置
            logger.info(f"未找到环境 {host} 的特定配置")

        # 修复：确保配置字典中的 host 与传入参数一致
        cls._config["host"] = host

        # 生成 base_url
        base_url = f"https://{host}:30000"
        cls._config["base_url"] = base_url
        logger.info(f"生成 base_url: {base_url}")

    @classmethod
    def override(cls, browser=None, headless=None, stor=None, username=None, password=None):
        """
        通过代码动态覆盖部分配置（通常用于命令行参数注入）
        """
        if browser is not None:
            # 校验浏览器类型是否有效
            valid_browsers = ["chromium", "firefox", "webkit"]
            if browser not in valid_browsers:
                error_msg = f"无效的浏览器类型: {browser}。支持的选项: {valid_browsers}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            cls._config["browser"] = browser
            logger.info(f"配置命令行参数 browser={browser}")
        if headless is not None:
            # 将字符串转为布尔值
            hbool = True if headless.lower() == "true" else False
            cls._config["headless"] = hbool
            logger.info(f"配置命令行参数 headless={hbool}")
        if stor is not None:
            cls._config["stor"] = stor
            logger.info(f"配置命令行参数 stor={stor}")
        if username is not None:
            cls._config["username"] = username
            logger.info(f"配置命令行参数 username={username}")
        if password is not None:
            cls._config["password"] = password
            logger.info(f"配置命令行参数 password={password}")

    @classmethod
    def get(cls, key=None, default=None):
        """
        获取配置值

        Args:
            key: 配置项的键，如果为空则返回所有配置
            default: 当key不存在时的默认值

        Returns:
            如果key为None，返回整个配置字典
            否则返回指定配置值或默认值
        """
        if key is None:
            return cls._config
        return cls._config.get(key, default)
