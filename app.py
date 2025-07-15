from flask import Flask, render_template, jsonify, request
from stock_signals import get_all_stock_signals
import threading
import time
import json
from datetime import datetime
import os
import webbrowser

app = Flask(__name__)

# 用于存储股票信号的全局变量
global_signals = []
last_update_time = None
update_lock = threading.Lock()

def update_signals():
    """更新股票信号数据"""
    global global_signals, last_update_time
    with update_lock:
        print("开始更新股票信号...")
        signals = get_all_stock_signals()
        global_signals = signals
        last_update_time = datetime.now()
        
        # 保存数据到文件
        with open('stock_signals.json', 'w', encoding='utf-8') as f:
            json.dump({'signals': signals, 'update_time': last_update_time.strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False)
        print("股票信号更新完成")

def load_cached_signals():
    """从缓存文件加载信号数据"""
    global global_signals, last_update_time
    try:
        if os.path.exists('stock_signals.json'):
            with open('stock_signals.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                global_signals = data['signals']
                last_update_time = datetime.strptime(data['update_time'], '%Y-%m-%d %H:%M:%S')
                print("已从缓存加载股票信号数据")
    except Exception as e:
        print(f"加载缓存数据出错: {e}")

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

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

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
    
    return jsonify({
        'signals': filtered_signals,
        'update_time': last_update_time.strftime('%Y-%m-%d %H:%M:%S') if last_update_time else None
    })

def open_browser():
    """在新线程中打开浏览器"""
    time.sleep(1.5)  # 等待服务器启动
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    # 启动时加载缓存数据
    load_cached_signals()
    # 如果需要更新，则更新数据
    if should_update():
        update_signals()
    
    print("\n=== 股票信号分析系统启动 ===")
    print("正在启动本地服务器...")
    print("服务器地址: http://127.0.0.1:5000")
    print("您可以在浏览器中访问上述地址查看结果")
    print("=========================\n")
    
    # 在新线程中打开浏览器
    threading.Thread(target=open_browser).start()
    
    # 启动Flask应用
    app.run(debug=True, port=5000)