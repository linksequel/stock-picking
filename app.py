from flask import Flask, render_template, jsonify, request
from stock_signals import get_all_stock_signals
import threading
import time
import json
from datetime import datetime, timedelta
import os
import webbrowser
import pandas as pd
import akshare as ak
from logger_config import setup_flask_logging, log_system_info, log_api_request, get_unified_logger, cleanup_old_logs

app = Flask(__name__)

# 设置Flask应用的统一日志
setup_flask_logging(app)

# 用于存储股票信号的全局变量
global_signals = []
last_update_time = None
update_lock = threading.Lock()

def update_signals():
    """更新股票信号数据"""
    global global_signals, last_update_time
    logger = get_unified_logger('flask_app')
    
    with update_lock:
        logger.info("开始更新股票信号...")
        signals = get_all_stock_signals()
        global_signals = signals
        last_update_time = datetime.now()
        
        # 保存数据到文件
        with open('stock_signals.json', 'w', encoding='utf-8') as f:
            json.dump({'signals': signals, 'update_time': last_update_time.strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False)
        
        # 保存为CSV文件
        save_signals_to_csv(signals)
        logger.info("股票信号更新完成")

def save_signals_to_csv(signals):
    """将信号数据保存为CSV文件"""
    if not signals:
        return

    # 时间校验：如果当前时间在15:31之前，则不保存
    current_time = datetime.now()
    logger = get_unified_logger('flask_app')
    
    if current_time.hour < 15 or (current_time.hour == 15 and current_time.minute < 31):
        logger.info(f"当前时间 {current_time.strftime('%H:%M')} 在15:31之前，暂不保存信号")
        return 

    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    history_dir = os.path.join(current_dir, 'history')
    
    # 创建history目录
    if not os.path.exists(history_dir):
        os.makedirs(history_dir)
    
    # 只保存有信号的股票
    csv_data = []
    for signal in signals:
        # 检查是否有任何信号为True
        if any(signal['signals'].values()):
            row = {
                'code': signal['code'],
                'name': signal['name'],
                'date': signal['date'],
                'close': signal['close']
            }
            # 添加所有信号
            for signal_name, signal_value in signal['signals'].items():
                row[signal_name] = signal_value
            csv_data.append(row)
    
    # 创建DataFrame并保存
    df = pd.DataFrame(csv_data)
    today = datetime.now().strftime('%Y%m%d')
    csv_filename = os.path.join(history_dir, f'signals_{today}.csv')
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    
    logger = get_unified_logger('flask_app')
    logger.info(f"信号数据已保存到: {csv_filename}，共保存 {len(csv_data)} 只有信号的股票")

def load_cached_signals():
    """从缓存文件加载信号数据"""
    global global_signals, last_update_time
    logger = get_unified_logger('flask_app')
    
    try:
        if os.path.exists('stock_signals.json'):
            with open('stock_signals.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                global_signals = data['signals']
                last_update_time = datetime.strptime(data['update_time'], '%Y-%m-%d %H:%M:%S')
                logger.info("已从缓存加载股票信号数据")
    except Exception as e:
        logger.error(f"加载缓存数据出错: {e}")

def should_update():
    """判断是否需要更新数据"""
    if last_update_time is None:
        return True
    now = datetime.now()
    # 如果是交易时间（9:30-15:00）且距离上次更新超过5分钟，则更新
    if (now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and now.hour < 15:
        return (now - last_update_time).seconds >= 1800
    # 非交易时间，每天更新一次
    return (now - last_update_time).days >= 1

def get_stock_prices_after_days(stock_code, signal_date_obj, days=5):
    """获取股票在信号日期后N天内每天的价格"""
    try:
        # 确保股票代码格式正确
        if not isinstance(stock_code, str):
            stock_code = str(stock_code)
        
        # 确保股票代码是6位数字格式
        if len(stock_code) != 6 or not stock_code.isdigit():
            logger = get_unified_logger('flask_app')
            logger.error(f"股票代码格式错误: {stock_code}")
            return None
        
        days_diff = (datetime.now().date() - signal_date_obj.date()).days

        start_date = (signal_date_obj + timedelta(days=1)).strftime('%Y%m%d')
        gap = min(days, days_diff)
        end_date = (signal_date_obj + timedelta(days=gap)).strftime('%Y%m%d')
        
        # 获取股票数据
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                               start_date=start_date,
                               end_date=end_date,
                               adjust="")
        
        if df.empty:
            logger = get_unified_logger('flask_app')
            logger.warning(f"股票 {stock_code} 数据为空")
            return None
        
        # 处理日期列并排序
        df['date'] = pd.to_datetime(df['日期'])
        df = df.sort_values('date')
        
        # 只返回实际存在的交易日数据，不进行错误填充
        daily_prices = []
        for i in range(len(df)):
            row = df.iloc[i]
            daily_prices.append({
                'date': row['日期'],
                'close': row['收盘'],
                'day': i + 1
            })
        
        return daily_prices
            
    except Exception as e:
        logger = get_unified_logger('flask_app')
        logger.error(f"获取股票 {stock_code} 后续价格失败: {e}")
        return None

def load_signals_from_csv():
    """从CSV文件加载信号数据"""
    signals_by_date = {}
    
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    history_dir = os.path.join(current_dir, 'history')
    
    # 查找history目录下的所有信号CSV文件
    logger = get_unified_logger('flask_app')
    
    if not os.path.exists(history_dir):
        logger.warning(f"History目录不存在: {history_dir}")
        return signals_by_date
    
    csv_files = [f for f in os.listdir(history_dir) if f.startswith('signals_') and f.endswith('.csv')]
    logger.info(f"找到 {len(csv_files)} 个CSV文件: {csv_files}")
    
    for csv_file in sorted(csv_files, reverse=True):  # 按文件名倒序，最新的在前
        try:
            file_path = os.path.join(history_dir, csv_file)
            df = pd.read_csv(file_path, encoding='utf-8-sig', dtype={'code': str})
            
            # 按日期分组
            for _, row in df.iterrows():
                date = row['date']
                if date not in signals_by_date:
                    signals_by_date[date] = []
                
                # 构建信号字典
                signals = {}
                for col in df.columns:
                    if col not in ['code', 'name', 'date', 'close']:
                        signals[col] = row[col]
                
                stock_data = {
                    'code': row['code'],
                    'name': row['name'],
                    'close': row['close'],
                    'signals': signals
                }
                signals_by_date[date].append(stock_data)
                
        except Exception as e:
            logger.error(f"读取CSV文件 {csv_file} 失败: {e}")
    
    return signals_by_date

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/history')
def history():
    """历史信号页面"""
    return render_template('history.html')

@app.route('/api/signals')
def get_signals():
    """获取股票信号API"""
    # 获取筛选条件
    signal_type = request.args.get('signal_type', '')
    
    if should_update():
        update_signals()
    
    filtered_signals = []
    for stock in global_signals:
        if signal_type:
            if stock['signals'].get(signal_type, False):
                filtered_signals.append(stock)
        else:
            # 如果没有指定信号类型，返回所有有任何信号的股票
            if any(stock['signals'].values()):
                filtered_signals.append(stock)
    
    # 记录API请求日志
    log_api_request('/api/signals', {'signal_type': signal_type}, len(filtered_signals))
    
    return jsonify({
        'signals': filtered_signals,
        'update_time': last_update_time.strftime('%Y-%m-%d %H:%M:%S') if last_update_time else None
    })

@app.route('/api/history')
def get_history():
    # """获取历史信号数据API"""
    # days = request.args.get('days', 5, type=int)
    days = 5
    signals_by_date = load_signals_from_csv()
    
    # 过滤掉今天的数据
    today = datetime.now().date()
    filtered_signals_by_date = {}
    
    # 记录API请求
    log_api_request('/api/history', {'days': days})
    
    # 为每个股票计算后续每天的涨幅
    for date_str, stocks in signals_by_date.items():
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        # 如果signal_date是今天，跳过不返回给前端
        if date_obj.date() == today:
            continue
            
        filtered_signals_by_date[date_str] = stocks
        
        for stock in stocks:
            # 只处理有信号的股票
            if any(stock['signals'].values()):
                daily_prices = get_stock_prices_after_days(stock['code'], date_obj, days)
                if daily_prices is not None:
                    stock['daily_prices'] = daily_prices
                    # 计算每天的涨幅（后一天相对前一天的涨幅）
                    stock['daily_changes'] = []
                    prev_price = stock['close']  # 从信号日收盘价开始
                    for price_data in daily_prices:
                        current_price = price_data['close']
                        change = ((current_price - prev_price) / prev_price) * 100
                        stock['daily_changes'].append({
                            'day': price_data['day'],
                            'date': price_data['date'],
                            'price': current_price,
                            'change': change
                        })
                        prev_price = current_price  # 更新前一天价格
                    
                    # 计算累积涨幅（最后一天相对信号日的涨幅）
                    if daily_prices:
                        last_price = daily_prices[-1]['close']
                        accumulate_number = float(((last_price - stock['close']) / stock['close']) * 100)

                        bullish_signals = {"主升", "底成立", "底结构", "底背离", "底钝化"}
                        signals = stock['signals']

                        has_bullish_signal = any(signals.get(signal, False) for signal in bullish_signals)
                        has_bear_signal = not has_bullish_signal

                        status = (accumulate_number > 0 and has_bullish_signal) or (
                                    accumulate_number < 0 and has_bear_signal)
                        
                        stock['accumulate'] = {
                            "number": accumulate_number,
                            "status": status
                        }
                    else:
                        stock['accumulate'] = {
                            "number": 0.0,
                            "status": False
                        }
                else:
                    stock['daily_prices'] = None
                    stock['daily_changes'] = None
                    stock['accumulate'] = None
    
    return jsonify({
        'signals_by_date': filtered_signals_by_date,
        'days': days
    })

def open_browser():
    """在新线程中打开浏览器"""
    time.sleep(1.5)  # 等待服务器启动
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    # 清理旧日志文件
    cleanup_old_logs(keep_days=30)
    
    # 启动时加载缓存数据
    load_cached_signals()
    # 如果需要更新，则更新数据
    if should_update():
        update_signals()
    
    logger = get_unified_logger('flask_app')
    logger.info("=== 股票信号分析系统启动 ===")
    
    # 判断是否为生产环境
    is_production = os.environ.get('FLASK_ENV') == 'production'
    
    if is_production:
        logger.info("正在启动生产服务器...")
        logger.info("服务器地址: http://0.0.0.0:5000")
        logger.info("历史信号页面: http://0.0.0.0:5000/history")
        logger.info("=============================")
        # 生产环境配置
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        logger.info("正在启动本地服务器...")
        logger.info("服务器地址: http://127.0.0.1:5000")
        logger.info("历史信号页面: http://127.0.0.1:5000/history")
        logger.info("您可以在浏览器中访问上述地址查看结果")
        logger.info("=============================")
        
        # 在新线程中打开浏览器
        threading.Thread(target=open_browser).start()
        
        # 启动Flask应用
        app.run(debug=True, port=5000)