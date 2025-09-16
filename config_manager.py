# config_manager.py
import configparser
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    配置管理器
    
    包含的配置项:
    - IMG_DIR: 测试图片目录
    - EDGE_DRIVER_PATH: Edge浏览器驱动路径
    - MAX_RETRY: 最大重试次数
    - SESSION_TIMEOUT: 会话超时时间（秒）
    - HEADLESS: 是否启用无头模式
    - EXTRACT_PATH: 解压文件目录
    - DOWNLOAD_DIR: 下载文件目录
    - PRINTER_NAME: 打印机名称
    - PDFTO_PRINTER_EXE: PDF打印工具路径
    - LOG_DIR: 日志目录
    - FLASK配置: host, port, debug
    - 证件类型映射: document_set
    - 证件URL映射: document_url

    
    """
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()
        
        # 证件类型映射
        self.document_set = {
            '1': '食品经营许可证',
            '2': '小餐饮登记证',
            '3': '小作坊登记证',
            '4': '食品生产许可证',
            # ... 其他证件类型
        }
        
        # 证件URL映射
        self.document_url = {
            '1': "https://zhjg.scjdglj.gxzf.gov.cn:10001/TopFDOAS/topic/homePage.action?currentLink=foodOp",
            '2': "https://zhjg.scjdglj.gxzf.gov.cn:10001/TopFDOAS/topic/homePage.action?currentLink=smallCatering",
            '3': "https://zhjg.scjdglj.gxzf.gov.cn:10001/TopFDOAS/topic/homePage.action?currentLink=smallShop",
            '4': "https://zhjg.scjdglj.gxzf.gov.cn:10001/TopFDOAS/topic/homePage.action?currentLink=foodPdt",
            # ... 其他URL
        }
    
    def _load_config(self) -> None:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding='utf-8')
            logger.info(f"配置文件已加载: {self.config_file}")
        else:
            logger.warning(f"配置文件不存在: {self.config_file}，使用默认配置")
    
    def get_resource_path(self, relative_path: str) -> str:
        """获取资源路径"""
        base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    
    @property
    def img_dir(self) -> str:  # 测试图片目录
        return self.get_resource_path(self.config.get('DEFAULT', 'IMG_DIR', fallback='test-image'))
    
    @property
    def edge_driver_path(self) -> str:  # Edge浏览器驱动路径
        return self.get_resource_path(self.config.get('DEFAULT', 'EDGE_DRIVER_PATH', fallback=r'browser_driver\msedgedriver.exe'))
    
    @property
    def max_retry(self) -> int:  # 最大重试次数
        return self.config.getint('DEFAULT', 'MAX_RETRY', fallback=5)
    
    @property
    def session_timeout(self) -> int:  # 会话超时时间（秒）
        return self.config.getint('DEFAULT', 'SESSION_TIMEOUT', fallback=1800)
    
    @property
    def headless(self) -> bool:  # 是否启用无头模式
        return self.config.getboolean('DEFAULT', 'HEADLESS', fallback=False)
    
    @property
    def extract_path(self) -> str:  # 解压文件目录
        return self.get_resource_path(self.config.get('DEFAULT', 'EXTRACT_PATH', fallback='extract'))
    
    @property
    def download_dir(self) -> str:  # 下载文件目录
        return self.get_resource_path(self.config.get('DEFAULT', 'DOWNLOAD_DIR', fallback='downloads'))
    
    @property
    def printer_name(self) -> str:  # 打印机名称
        return self.config.get('PRINTER', 'PRINTER_NAME', fallback="TestPrinter")
    
    @property
    def pdfto_printer_exe(self) -> str:  # PDF打印工具路径
        return self.get_resource_path(self.config.get('PRINTER', 'PDFTO_PRINTER_EXE', fallback=r'printer\PDFtoPrinter.exe'))
    
    @property
    def log_dir(self) -> str:  # 日志目录
        return self.get_resource_path(self.config.get('DEFAULT', 'LOG_DIR', fallback='logs'))
    
    @property
    def flask_config(self) -> Dict[str, Any]:  # Flask配置
        """获取Flask配置"""
        return {
            'host': self.config.get('DEFAULT', 'HOST', fallback='0.0.0.0'),
            'port': self.config.getint('DEFAULT', 'PORT', fallback=8848),
            'debug': self.config.getboolean('DEFAULT', 'DEBUG', fallback=True)
        }
    
    def get_document_name(self, document_type: str) -> str:
        """获取证件名称"""
        return self.document_set.get(document_type, 'unknown证件')
    
    def get_document_url(self, document_type: str) -> str:
        """获取证件URL"""
        return self.document_url.get(document_type, '')
    
    def validate_document_type(self, document_type: str) -> bool:
        """验证证件类型是否有效"""
        return document_type in self.document_set

# 创建全局配置管理器实例
config_manager = ConfigManager()