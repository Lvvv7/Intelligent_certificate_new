# decorators.py
from functools import wraps
from flask import jsonify
from state_manager import state_manager
import logging

logger = logging.getLogger(__name__)

def validate_json_request(required_fields=None):  # 验证JSON请求是否合法装饰器
    """验证JSON请求装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request
            
            if not request.is_json:
                return jsonify({'error': '请求必须是JSON格式'}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({'error': '请求数据不能为空'}), 400
            
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return jsonify({'error': f'缺少必要参数: {", ".join(missing_fields)}'}), 400
                
                # 验证字段不为空
                empty_fields = [field for field in required_fields if not data.get(field)]
                if empty_fields:
                    return jsonify({'error': f'以下参数不能为空: {", ".join(empty_fields)}'}), 400
            
            return f(data, *args, **kwargs)
        return decorated_function
    return decorator

def check_processing_status(f):
    """检查是否正在处理的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if state_manager.is_processing():
            return jsonify({'message': '有任务正在处理中，请稍后再试'}), 429
        return f(*args, **kwargs)
    return decorated_function

def handle_exceptions(f):
    """统一异常处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"{f.__name__}接口错误: {str(e)}", exc_info=True)
            return jsonify({'error': f'服务器内部错误: {str(e)}'}), 500
    return decorated_function