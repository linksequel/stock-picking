import logging
import os
from datetime import datetime


def get_unified_logger(name=None):
    """
    获取统一配置的日志器
    
    Args:
        name: logger名称，如果不指定则使用调用模块的名称
    
    Returns:
        logger实例
    """
    if name is None:
        name = __name__
    
    logger = logging.getLogger(name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 确保log目录存在
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 按日期命名日志文件
    today = datetime.now().strftime('%Y-%m-%d')
    log_filename = os.path.join(log_dir, f'{today}.log')
    
    # 设置日志级别
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 设置格式器
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def setup_flask_logging(app):
    """
    为Flask应用配置日志
    
    Args:
        app: Flask应用实例
    """
    # 获取统一的logger
    logger = get_unified_logger('flask_app')
    
    # 设置Flask应用的logger
    app.logger.handlers.clear()
    app.logger.addHandler(logger.handlers[0])  # 文件处理器
    app.logger.addHandler(logger.handlers[1])  # 控制台处理器
    app.logger.setLevel(logging.INFO)
    
    return logger


def log_system_info(message, extra_info=None):
    """
    记录系统信息日志
    
    Args:
        message: 主要消息
        extra_info: 额外信息字典
    """
    logger = get_unified_logger('system')
    logger.info(message)
    
    if extra_info:
        for key, value in extra_info.items():
            logger.info(f"  - {key}: {value}")


def log_stock_analysis(message, level='info'):
    """
    记录股票分析相关日志
    
    Args:
        message: 日志消息
        level: 日志级别 ('info', 'warning', 'error', 'debug')
    """
    logger = get_unified_logger('stock_analysis')
    
    level_map = {
        'info': logger.info,
        'warning': logger.warning,
        'error': logger.error,
        'debug': logger.debug
    }
    
    log_func = level_map.get(level.lower(), logger.info)
    log_func(message)


def log_api_request(endpoint, params=None, result_count=None):
    """
    记录API请求日志
    
    Args:
        endpoint: API端点
        params: 请求参数
        result_count: 返回结果数量
    """
    logger = get_unified_logger('api')
    
    message = f"API请求: {endpoint}"
    if params:
        message += f" 参数: {params}"
    if result_count is not None:
        message += f" 返回结果: {result_count}条"
    
    logger.info(message)


def cleanup_old_logs(keep_days=30):
    """
    清理旧的日志文件
    
    Args:
        keep_days: 保留天数，默认30天
    """
    import glob
    from datetime import timedelta
    
    log_dir = 'log'
    if not os.path.exists(log_dir):
        return
    
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    log_files = glob.glob(os.path.join(log_dir, '*.log'))
    
    logger = get_unified_logger('system')
    cleaned_count = 0
    
    for log_file in log_files:
        try:
            # 从文件名提取日期
            filename = os.path.basename(log_file)
            if filename.count('-') >= 2:  # 格式如 2025-01-01.log
                date_str = filename.replace('.log', '')
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                if file_date < cutoff_date:
                    os.remove(log_file)
                    cleaned_count += 1
                    logger.info(f"删除旧日志文件: {log_file}")
        except Exception as e:
            logger.warning(f"删除日志文件失败 {log_file}: {e}")
    
    if cleaned_count > 0:
        logger.info(f"清理完成，共删除 {cleaned_count} 个旧日志文件") 