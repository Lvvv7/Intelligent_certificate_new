# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import logging

# 导入自定义模块
from state_manager import state_manager, ErrorType
from config_manager import config_manager
from decorators import validate_json_request, check_processing_status, handle_exceptions
from certificate_automation import CertificateAutomation
from db_operations import add_certification_record

app = Flask(__name__)
CORS(app)

# 配置日志
def setup_logging():
    """设置日志配置"""
    import os
    log_dir = config_manager.log_dir  # 调用配置管理器中的property方法获取log的路径
    os.makedirs(log_dir, exist_ok=True)

    # 设置日志记录
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'app.log'), encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

setup_logging()
logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器

class CertificationService:
    """证件处理服务类"""
    
    def __init__(self):
        self.automation = CertificateAutomation()  # 初始化自动化处理类，后续所有浏览器操作均通过该实例
    
    def process_certification(self, username: str, password: str) -> None:
        """处理证件申请"""
        state = state_manager.get_state()  # 通过状态管理器获取当前状态
        
        try:
            if state.system_num == '1':  #如果当前状态的系统编号是1
                success, message = self.automation.system1_function(username, password)
            elif state.system_num == '2':
                # TODO: 实现系统2的处理逻辑
                success, message = False, "系统2暂未实现"
            else:
                success, message = False, "未知的系统编号"
            
            # 设置证件名称
            cert_name = config_manager.get_document_name(state.document_type)  # 调用配置管理器中的方法通过document_type获取对应的证件名称
            
            if success:  # 如果处理成功，调用状态管理器的complete_success方法
                state_manager.complete_success(message, cert_name)  # 更新状态信息
            else:
                # 根据消息判断错误类型
                error_type = self._determine_error_type(message)  # 通过错误信息来确定错误类型
                state_manager.complete_failure(message, error_type, cert_name)  # 更新状态信息
                
        except Exception as e:
            logger.error(f"处理证件申请时发生异常: {str(e)}", exc_info=True)
            error_type = self._determine_error_type(str(e))
            cert_name = config_manager.get_document_name(state.document_type)
            state_manager.complete_failure(f"系统错误: {str(e)}", error_type, cert_name)  # 执行过程中出现异常，更新状态信息
        finally:
            # 记录到数据库
            self._save_to_database(username)
    
    def _determine_error_type(self, message: str) -> ErrorType:
        """根据错误消息确定错误类型"""
        message_lower = message.lower()
        
        if "用户名" in message or "密码" in message:
            return ErrorType.USERNAME_PASSWORD_ERROR
        elif "证件状态" in message:
            return ErrorType.INVALID_CERTIFICATE_STATUS
        elif "打印" in message:
            return ErrorType.PRINTER_ERROR
        elif "验证码" in message:
            return ErrorType.CAPTCHA_ERROR
        elif "超时" in message or "timeout" in message_lower:
            return ErrorType.TIME_ERROR
        else:
            return ErrorType.TIME_ERROR
        
    
    def _save_to_database(self, username: str) -> None:
        """保存结果到数据库"""
        state = state_manager.get_state()
        
        try:
            error_message = f"{state.error_type.value}:{state.error_message}" if state.error_type != ErrorType.NONE else ""
            
            add_certification_record(
                user_account=username,
                name=state.cert_name,
                cert_type='法人' if state.user_type == 'corporate' else '个人',
                status_code=0 if state.success else 1,
                error_types=error_message
            )
        except Exception as e:
            logger.error(f"保存到数据库失败: {str(e)}")

# 创建服务实例
certification_service = CertificationService()

def background_task(username: str, password: str):
    """后台任务执行函数"""
    logger.info(f"开始后台处理任务: 用户={username}")
    certification_service.process_certification(username, password)
    logger.info(f"后台任务完成: 用户={username}")

@app.route('/api/document_type', methods=['POST'])
@handle_exceptions
@validate_json_request(['user_type', 'document_type'])
def document_type(data):
    """文档类型接口"""
    user_type = data['user_type']
    document_type = data['document_type']
    
    # 验证参数值
    if user_type not in ['corporate', 'individual']:
        return jsonify({'error': 'user_type参数值无效，必须是corporate或individual'}), 400
    
    if not config_manager.validate_document_type(document_type):
        return jsonify({'error': 'document_type参数值无效'}), 400
    
    # 设置状态
    state_manager.set_document_info(user_type, document_type)
    
    return jsonify({
        'message': f'证件类型已设置为: {document_type}',
        'cert_name': config_manager.get_document_name(document_type)
    }), 200

@app.route('/api/corporate_login', methods=['POST'])
@handle_exceptions
@validate_json_request(['username', 'password'])
@check_processing_status
def corporate_login(data):
    """法人登录接口"""
    username = data['username']
    password = data['password']
    
    # 获取当前状态
    state = state_manager.get_state()
    
    # 检查是否已设置证件类型
    if not state.document_type:
        return jsonify({'error': '请先设置document_type'}), 400
    
    # 开始处理任务
    if not state_manager.start_processing(username, 'corporate', state.document_type):
        return jsonify({'message': '有任务正在处理中，请稍后再试'}), 429
    
    # 启动后台任务
    thread = threading.Thread(target=background_task, args=(username, password))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': '登录请求已接收，正在后台处理',
        'status': 'processing',
        'trace_id': state_manager.get_state().trace_id
    }), 200

@app.route('/api/individual_login', methods=['POST'])
@handle_exceptions
@validate_json_request(['username', 'password'])
@check_processing_status
def individual_login(data):
    """个人登录接口"""
    username = data['username']
    password = data['password']
    
    # 获取当前状态
    state = state_manager.get_state()
    
    # 检查是否已设置证件类型
    if not state.document_type:
        return jsonify({'error': '请先设置document_type'}), 400
    
    # 开始处理任务
    if not state_manager.start_processing(username, 'individual', state.document_type):
        return jsonify({'message': '有任务正在处理中，请稍后再试'}), 429
    
    # 启动后台任务
    thread = threading.Thread(target=background_task, args=(username, password))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': '登录请求已接收，正在后台处理',
        'status': 'processing',
        'trace_id': state_manager.get_state().trace_id
    }), 200

@app.route('/api/print_status', methods=['GET'])
@handle_exceptions
def check_print_status():
    """打印状态查询接口"""
    status_info = state_manager.get_status_info()
    
    if status_info['success'] is False and status_info.get('status') == 'processing':
        return jsonify(status_info), 204
    elif status_info['success'] is False and status_info.get('status') in ['idle', 'expired']:
        return jsonify(status_info), 410
    else:
        return jsonify(status_info), 200

@app.route('/api/clear_data', methods=['GET'])
@handle_exceptions
def clear_data():
    """清除数据接口"""
    import os
    import shutil
    
    try:
        extract_path = config_manager.extract_path
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        os.makedirs(extract_path, exist_ok=True)
        img_dir = config_manager.img_dir
        if os.path.exists(img_dir):
            shutil.rmtree(img_dir)
        os.makedirs(img_dir, exist_ok=True)
        
        # 重置状态
        state_manager.reset()
        
        return jsonify({'message': '提取数据和状态已清除'}), 200
    except Exception as e:
        logger.error(f"清除数据失败: {str(e)}")
        return jsonify({'error': f'清除数据失败: {str(e)}'}), 500

@app.route('/api/system_status', methods=['GET'])
@handle_exceptions
def system_status():
    """系统状态接口"""
    state = state_manager.get_state()
    return jsonify({
        'system_info': {
            'status': state.status.value,
            'current_task': {
                'user_type': state.user_type,
                'document_type': state.document_type,
                'cert_name': state.cert_name,
                'trace_id': state.trace_id
            } if state.status.value != 'idle' else None
        }
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': '接口不存在'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': '服务器内部错误'}), 500

if __name__ == '__main__':
    # 确保必要目录存在
    import os
    os.makedirs(config_manager.img_dir, exist_ok=True)
    os.makedirs(config_manager.log_dir, exist_ok=True)
    
    # 启动Flask应用
    flask_config = config_manager.flask_config
    logger.info(f"启动Flask应用: http://{flask_config['host']}:{flask_config['port']}")
    app.run(**flask_config)