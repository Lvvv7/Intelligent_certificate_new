# state_manager.py
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """任务状态枚举"""
    IDLE = "idle"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"

class ErrorType(Enum):
    """错误类型枚举"""
    NONE = ""
    USERNAME_PASSWORD_ERROR = "username_or_password_error"
    INVALID_CERTIFICATE_STATUS = "invalid_certificate_status"
    PRINTER_ERROR = "printer_error"
    TIME_ERROR = "time_error"
    CAPTCHA_ERROR = "captcha_error"

class CertificationState:
    """证件处理状态"""
    def __init__(self):
        self.status: TaskStatus = TaskStatus.IDLE
        self.success: bool = False
        self.message: str = ''
        self.last_login_time: Optional[float] = None
        self.error_type: ErrorType = ErrorType.NONE
        self.error_message: str = ''
        self.user_type: str = ''
        self.document_type: str = ''
        self.system_num: str = ''
        self.cert_name: str = ''
        self.username: str = ''
        self.trace_id: str = ''
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'status': self.status.value,
            'success': self.success,
            'message': self.message,
            'last_login_time': self.last_login_time,
            'error_type': self.error_type.value,
            'error_message': self.error_message,
            'user_type': self.user_type,
            'document_type': self.document_type,
            'system_num': self.system_num,
            'cert_name': self.cert_name,
            'username': self.username,
            'trace_id': self.trace_id
        }

class StateManager:
    """线程安全的状态管理器"""
    
    def __init__(self, session_timeout: int = 1800):
        self._state = CertificationState()
        self._lock = threading.RLock()  # 使用可重入锁
        self.session_timeout = session_timeout
        
    def get_state(self) -> CertificationState:
        """获取当前状态的副本"""
        with self._lock:
            # 返回状态的副本，避免外部直接修改
            new_state = CertificationState()
            new_state.__dict__.update(self._state.__dict__)
            return new_state
    
    def is_processing(self) -> bool:
        """检查是否正在处理"""
        with self._lock:
            return self._state.status == TaskStatus.PROCESSING
    
    def is_expired(self) -> bool:
        """检查会话是否过期"""
        with self._lock:
            if self._state.last_login_time is None:
                return True
            return time.time() - self._state.last_login_time > self.session_timeout
    
    def start_processing(self, username: str, user_type: str, document_type: str) -> bool:
        """开始处理任务"""
        with self._lock:
            if self._state.status == TaskStatus.PROCESSING:
                return False
            
            # 重置状态
            self._state.status = TaskStatus.PROCESSING
            self._state.success = False
            self._state.message = '正在处理中...'
            self._state.error_type = ErrorType.NONE
            self._state.error_message = ''
            self._state.username = username
            self._state.user_type = user_type
            self._state.document_type = document_type
            self._state.trace_id = f"{int(time.time())}_{username}"
            
            # 设置系统编号
            if document_type in ["1", "2", "3", "4"]:
                self._state.system_num = '1'
            elif document_type in ["5", "6", "7", "8"]:
                self._state.system_num = '2'
            else:
                self._state.system_num = ''
            
            logger.info(f"开始处理任务: 用户={username}, 类型={user_type}, 证件={document_type}")
            return True
    
    def complete_success(self, message: str, cert_name: str = '') -> None:
        """完成任务-成功"""
        with self._lock:
            self._state.status = TaskStatus.SUCCESS
            self._state.success = True
            self._state.message = message
            self._state.last_login_time = time.time()
            self._state.cert_name = cert_name
            logger.info(f"任务完成成功: {message}")
    
    def complete_failure(self, message: str, error_type: ErrorType, cert_name: str = '') -> None:
        """完成任务-失败"""
        with self._lock:
            self._state.status = TaskStatus.FAILED
            self._state.success = False
            self._state.message = message
            self._state.error_type = error_type
            self._state.error_message = message
            self._state.last_login_time = time.time()
            self._state.cert_name = cert_name
            logger.error(f"任务完成失败: {message}, 错误类型: {error_type.value}")
    
    def set_document_info(self, user_type: str, document_type: str) -> None:
        """设置文档信息"""
        with self._lock:
            self._state.user_type = user_type
            self._state.document_type = document_type
            
            # 设置系统编号
            if document_type in ["1", "2", "3", "4"]:
                self._state.system_num = '1'
            elif document_type in ["5", "6", "7", "8"]:
                self._state.system_num = '2'
            else:
                self._state.system_num = ''
    
    def set_cert_name(self, cert_name: str) -> None:
        """设置证件名称"""
        with self._lock:
            self._state.cert_name = cert_name
    
    def reset(self) -> None:
        """重置状态"""
        with self._lock:
            self._state = CertificationState()
            logger.info("状态已重置")
    
    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        with self._lock:
            if self._state.status == TaskStatus.PROCESSING:
                return {
                    'success': False,
                    'msg': '正在处理中，请稍后查询',
                    'status': self._state.status.value
                }
            
            if self._state.last_login_time is None:
                return {
                    'success': False,
                    'msg': '尚未执行登录操作',
                    'status': TaskStatus.IDLE.value
                }
            
            if self.is_expired():
                return {
                    'success': False,
                    'msg': '登录状态已过期，请重新执行登录',
                    'status': TaskStatus.EXPIRED.value
                }
            
            return {
                'success': self._state.success,
                'msg': self._state.message,
                'error_type': self._state.error_type.value,
                'status': self._state.status.value
            }

# 创建全局状态管理器实例
state_manager = StateManager()