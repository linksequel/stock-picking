import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime
import warnings
import random
import os
from logger_config import get_unified_logger, log_stock_analysis, log_system_info
warnings.filterwarnings('ignore')

def setup_logger_and_log_stocks(stocks):
    """记录stocks信息到统一日志"""
    # 记录stocks信息
    if stocks is not None and not stocks.empty:
        log_stock_analysis(f"获取到股票数量: {len(stocks)}")
        
        # 记录详细的数据结构信息
        extra_info = {
            "列名": list(stocks.columns),
            "数据形状": str(stocks.shape),
            "数据类型": str(stocks.dtypes.to_dict())
        }
        log_system_info("股票数据结构信息:", extra_info)
        
    else:
        log_stock_analysis("未能获取到股票数据", 'warning')
    
    # 返回统一的logger
    return get_unified_logger('stock_analysis')

def retry_on_failure(max_retries=3, delay=1):
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    # 添加随机延迟，避免请求过快
                    time.sleep(delay + random.random())
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:  # 最后一次重试
                        return None
                    continue
            return None
        return wrapper
    return decorator

@retry_on_failure(max_retries=3, delay=1)
def get_stock_data(stock_code):
    """获取股票数据"""
    try:
        start_date = "20240901"
        end_date = datetime.now().strftime('%Y%m%d')
        
        # 使用akshare获取股票数据
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=start_date, end_date=end_date, adjust="")
        
        if df.empty:
            return None
            
        # 先处理日期列
        df['date'] = pd.to_datetime(df['日期'])
        
        # 重命名列以保持一致性
        df = df.rename(columns={
            '收盘': 'close',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        })
        
        # 设置日期索引
        df.set_index('date', inplace=True)
        
        # 只保留需要的列
        df = df[['open', 'high', 'low', 'close', 'volume']]
        
        return df
    except Exception as e:
        log_stock_analysis(f"获取股票数据失败 {stock_code}: {e}", 'error')
        return None

@retry_on_failure(max_retries=3, delay=1)
def get_all_stocks():
    """获取沪深300成分股代码和名称"""
    try:
        # 使用akshare获取沪深300成分股
        df = ak.index_stock_cons(symbol="000300")
        # 创建标准格式的DataFrame
        stock_data = pd.DataFrame({
            'code': df['品种代码'].tolist(),
            'name': df['品种名称'].tolist()
        })
        
        # 读取补充股票数据
        try:
            supplement_data = pd.read_csv('datas/supplement.csv', encoding='utf-8', dtype={'code': str})
            log_stock_analysis(f"成功读取补充股票数据: {len(supplement_data)} 只股票")
            
            # 合并到主数据中
            stock_data = pd.concat([stock_data, supplement_data], ignore_index=True)
            
        except FileNotFoundError:
            log_stock_analysis("未找到supplement.csv文件，跳过补充数据", 'warning')
        except Exception as e:
            log_stock_analysis(f"读取补充股票数据失败: {e}", 'error')
        
        # 根据code去重，保留第一个出现的记录
        stock_data = stock_data.drop_duplicates(subset=['code'], keep='first')

        # 重置索引并返回
        return stock_data.reset_index(drop=True)
    except Exception as e:
        log_stock_analysis(f"获取沪深300成分股失败: {e}", 'error')
        return None

def EMA(series, periods):
    """计算EMA指标"""
    return series.ewm(span=periods, adjust=False).mean()

def CROSS(series1, series2):
    """判断向上金叉"""
    return (series1 > series2) & (series1.shift(1) <= series2.shift(1))

def BARSLAST(condition):
    """计算上一次条件成立到当前的周期数"""
    result = np.zeros(len(condition))
    count = 0
    last_true = False
    
    for i in range(len(condition)):
        if condition.iloc[i]:
            count = 0
            last_true = True
        elif last_true:
            count += 1
        result[i] = count
    
    return pd.Series(result, index=condition.index)

def calculate_macd_indicators(df):
    """计算MACD相关指标"""
    # 基础参数
    SHORT = 12
    LONG = 26
    MID = 9
    
    # 基础MACD计算
    df['DIF'] = (EMA(df['close'], SHORT) - EMA(df['close'], LONG)) * 100
    df['DEA'] = EMA(df['DIF'], MID)
    df['MACD'] = 2 * (df['DIF'] - df['DEA'])
    
    # MACD柱状图历史数据
    df['MACD1'] = df['MACD']
    df['MACD2'] = df['MACD1'].shift(1)  # MACDSR: 1周期前的MACD
    df['MACD3'] = df['MACD1'].shift(2)  # MACDSSR: 2周期前的MACD
    
    # MACD顶底转折信号
    df['MACD顶转'] = (df['MACD2'] > df['MACD3']) & (df['MACD2'] > df['MACD1'])
    df['MACD底转'] = (df['MACD3'] > df['MACD2']) & (df['MACD1'] > df['MACD2'])
    
    # 金叉和死叉
    df['金叉'] = CROSS(df['DIF'], df['DEA'])
    df['死叉'] = CROSS(df['DEA'], df['DIF'])
    
    # 计算各周期金叉死叉位置
    df['M1'] = BARSLAST(df['金叉'])  # 最近一次金叉的位置
    df['N1'] = BARSLAST(df['死叉'])  # 最近一次死叉的位置
    
    # 计算M2和M3（到当前的周期数）
    df['M2'] = 0  # 初始化M2
    df['M3'] = 0  # 初始化M3
    
    for i in range(len(df)):
        # 获取当前位置之前的所有金叉位置
        prev_data = df.iloc[:i+1]
        cross_positions = prev_data[prev_data['金叉']].index
        
        if len(cross_positions) >= 2:  # 至少有两次金叉才能计算M2
            second_last_cross = cross_positions[-2]  # 倒数第二次金叉位置
            df.loc[df.index[i], 'M2'] = len(df.loc[second_last_cross:df.index[i]]) - 1
            
        if len(cross_positions) >= 3:  # 至少有三次金叉才能计算M3
            third_last_cross = cross_positions[-3]  # 倒数第三次金叉位置
            df.loc[df.index[i], 'M3'] = len(df.loc[third_last_cross:df.index[i]]) - 1
    
    # 填充NaN值
    df['M2'] = df['M2'].fillna(0)
    df['M3'] = df['M3'].fillna(0)
    
    # 计算N2和N3（到当前的周期数）
    df['N2'] = 0  # 初始化N2
    df['N3'] = 0  # 初始化N3
    
    for i in range(len(df)):
        # 获取当前位置之前的所有死叉位置
        prev_data = df.iloc[:i+1]
        cross_positions = prev_data[prev_data['死叉']].index
        
        if len(cross_positions) >= 2:  # 至少有两次死叉才能计算N2
            second_last_cross = cross_positions[-2]  # 倒数第二次死叉位置
            df.loc[df.index[i], 'N2'] = len(df.loc[second_last_cross:df.index[i]]) - 1
            
        if len(cross_positions) >= 3:  # 至少有三次死叉才能计算N3
            third_last_cross = cross_positions[-3]  # 倒数第三次死叉位置
            df.loc[df.index[i], 'N3'] = len(df.loc[third_last_cross:df.index[i]]) - 1
    
    # 填充NaN值
    df['N2'] = df['N2'].fillna(0)
    df['N3'] = df['N3'].fillna(0)
    
    # 计算各周期高低点位置
    for i in range(len(df)):
        m1 = int(df['M1'].iloc[i])
        
        # 初始化列（如果不存在）
        for col in ['CH1', 'CH2', 'CH3', 'DIFH1', 'DIFH2', 'DIFH3']:
            if col not in df.columns:
                df[col] = 0
        
        # CH1和DIFH1：M1+1日内的最高值
        if i >= m1:
            start_idx = max(0, i-m1-1)  # M1+1日前的位置
            df.loc[df.index[i], 'CH1'] = df['close'].iloc[start_idx:i+1].max()
            df.loc[df.index[i], 'DIFH1'] = df['DIF'].iloc[start_idx:i+1].max()
        
        # CH2和DIFH2：M1+1日前的CH1和DIFH1
        if i > m1:
            ref_idx = i - (m1 + 1)  # 向前推M1+1日
            if ref_idx >= 0:
                df.loc[df.index[i], 'CH2'] = df['CH1'].iloc[ref_idx]
                df.loc[df.index[i], 'DIFH2'] = df['DIFH1'].iloc[ref_idx]
        
        # CH3和DIFH3：M1+1日前的CH2和DIFH2
        if i > m1:
            ref_idx = i - (m1 + 1)  # 向前推M1+1日
            if ref_idx >= 0:
                df.loc[df.index[i], 'CH3'] = df['CH2'].iloc[ref_idx]
                df.loc[df.index[i], 'DIFH3'] = df['DIFH2'].iloc[ref_idx]
        
        n1 = int(df['N1'].iloc[i])
        
        # 初始化列（如果不存在）
        for col in ['CL1', 'CL2', 'CL3', 'DIFL1', 'DIFL2', 'DIFL3']:
            if col not in df.columns:
                df[col] = 0
        
        # CL1和DIFL1：N1+1日内的最低值
        if i >= n1:
            start_idx = max(0, i-n1-1)  # N1+1日前的位置
            df.loc[df.index[i], 'CL1'] = df['close'].iloc[start_idx:i+1].min()
            df.loc[df.index[i], 'DIFL1'] = df['DIF'].iloc[start_idx:i+1].min()
        
        # CL2和DIFL2：N1+1日前的CL1和DIFL1
        if i > n1:
            ref_idx = i - (n1 + 1)  # 向前推N1+1日
            if ref_idx >= 0:
                df.loc[df.index[i], 'CL2'] = df['CL1'].iloc[ref_idx]
                df.loc[df.index[i], 'DIFL2'] = df['DIFL1'].iloc[ref_idx]
        
        # CL3和DIFL3：N1+1日前的CL2和DIFL2
        if i > n1:
            ref_idx = i - (n1 + 1)  # 向前推N1+1日
            if ref_idx >= 0:
                df.loc[df.index[i], 'CL3'] = df['CL2'].iloc[ref_idx]
                df.loc[df.index[i], 'DIFL3'] = df['DIFL2'].iloc[ref_idx]
    
    # 计算PDIFH2和MDIFH2
    df['PDIFH2'] = df.apply(lambda x: 
        int(np.log10(abs(x['DIFH2']))) - 1 if x['DIFH2'] > 0 
        else int(np.log10(abs(x['DIFH2']))) - 1 if x['DIFH2'] < 0 
        else 0, axis=1)
    df['MDIFH2'] = df.apply(lambda x: 
        int(x['DIFH2'] / (10 ** x['PDIFH2'])) if x['PDIFH2'] != 0 
        else int(x['DIFH2']), axis=1)

    # 计算PDIFH3和MDIFH3
    df['PDIFH3'] = df.apply(lambda x: 
        int(np.log10(abs(x['DIFH3']))) - 1 if x['DIFH3'] > 0 
        else int(np.log10(abs(x['DIFH3']))) - 1 if x['DIFH3'] < 0 
        else 0, axis=1)
    df['MDIFH3'] = df.apply(lambda x: 
        int(x['DIFH3'] / (10 ** x['PDIFH3'])) if x['PDIFH3'] != 0 
        else int(x['DIFH3']), axis=1)

    # 计算MDIFT2和MDIFT3
    df['MDIFT2'] = df.apply(lambda x: 
        int(x['DIF'] / (10 ** x['PDIFH2'])) if x['PDIFH2'] != 0 
        else int(x['DIF']), axis=1)
    df['MDIFT3'] = df.apply(lambda x: 
        int(x['DIF'] / (10 ** x['PDIFH3'])) if x['PDIFH3'] != 0 
        else int(x['DIF']), axis=1)

    # 计算PDIFL2和MDIFL2（底背离）
    df['PDIFL2'] = df.apply(lambda x: 
        int(np.log10(abs(x['DIFL2']))) - 1 if x['DIFL2'] > 0 
        else int(np.log10(abs(x['DIFL2']))) - 1 if x['DIFL2'] < 0 
        else 0, axis=1)
    df['MDIFL2'] = df.apply(lambda x: 
        int(x['DIFL2'] / (10 ** x['PDIFL2'])) if x['PDIFL2'] != 0 
        else int(x['DIFL2']), axis=1)

    # 计算PDIFL3和MDIFL3
    df['PDIFL3'] = df.apply(lambda x: 
        int(np.log10(abs(x['DIFL3']))) - 1 if x['DIFL3'] > 0 
        else int(np.log10(abs(x['DIFL3']))) - 1 if x['DIFL3'] < 0 
        else 0, axis=1)
    df['MDIFL3'] = df.apply(lambda x: 
        int(x['DIFL3'] / (10 ** x['PDIFL3'])) if x['PDIFL3'] != 0 
        else int(x['DIFL3']), axis=1)

    # 计算MDIFB2和MDIFB3
    df['MDIFB2'] = df.apply(lambda x: 
        int(x['DIF'] / (10 ** x['PDIFL2'])) if x['PDIFL2'] != 0 
        else int(x['DIF']), axis=1)
    df['MDIFB3'] = df.apply(lambda x: 
        int(x['DIF'] / (10 ** x['PDIFL3'])) if x['PDIFL3'] != 0 
        else int(x['DIF']), axis=1)
    
    # 直接顶背离和隔峰顶背离判断
    df['直接顶背离'] = ((df['CH1'] > df['CH2']) & 
                    (df['MDIFT2'] < df['MDIFH2']) & 
                    ((df['MACD'] > 0) & (df['MACD'].shift(1) > 0)) & 
                    (df['MDIFT2'] >= df['MDIFT2'].shift(1)))
    
    df['隔峰顶背离'] = ((df['CH1'] > df['CH3']) & (df['CH3'] > df['CH2']) &
                    (df['MDIFT3'] < df['MDIFH3']) & 
                    ((df['MACD'] > 0) & (df['MACD'].shift(1) > 0)) & 
                    (df['MDIFT3'] >= df['MDIFT3'].shift(1)))
    
    # 直接底背离和隔峰底背离判断
    df['直接底背离'] = ((df['CL1'] < df['CL2']) & 
                    (df['MDIFB2'] > df['MDIFL2']) & 
                    ((df['MACD'] < 0) & (df['MACD'].shift(1) < 0)) & 
                    (df['MDIFB2'] <= df['MDIFB2'].shift(1)))
    
    df['隔峰底背离'] = ((df['CL1'] < df['CL3']) & (df['CL3'] < df['CL2']) &
                    (df['MDIFB3'] > df['MDIFL3']) & 
                    ((df['MACD'] < 0) & (df['MACD'].shift(1) < 0)) & 
                    (df['MDIFB3'] <= df['MDIFB3'].shift(1)))
    
    # 顶底背离信号合并
    df['T'] = df['直接顶背离'] | df['隔峰顶背离']
    df['B'] = df['直接底背离'] | df['隔峰底背离']
    
    # 顶底背离确认信号(TG和BG)
    # 将布尔值转换为0/1，以便使用乘法代替AND
    df['直接顶背离_num'] = df['直接顶背离'].astype(int)
    df['隔峰顶背离_num'] = df['隔峰顶背离'].astype(int)
    df['直接底背离_num'] = df['直接底背离'].astype(int)
    df['隔峰底背离_num'] = df['隔峰底背离'].astype(int)
    
    # TG: 使用乘法实现AND操作，与通达信保持一致
    df['TG'] = (((df['MDIFT2'] < df['MDIFT2'].shift(1)).astype(int) * 
                 df['直接顶背离_num'].shift(1)) > 0) | \
               (((df['MDIFT3'] < df['MDIFT3'].shift(1)).astype(int) * 
                 df['隔峰顶背离_num'].shift(1)) > 0)
    
    # BG: 同样使用乘法实现AND操作
    df['BG'] = (((df['MDIFB2'] > df['MDIFB2'].shift(1)).astype(int) * 
                 df['直接底背离_num'].shift(1)) > 0) | \
               (((df['MDIFB3'] > df['MDIFB3'].shift(1)).astype(int) * 
                 df['隔峰底背离_num'].shift(1)) > 0)
    
    # 删除临时列
    df = df.drop(['直接顶背离_num', '隔峰顶背离_num', '直接底背离_num', '隔峰底背离_num'], axis=1)
    
    # 钝化信号
    df['底钝化'] = df['B']  
    df['顶钝化'] = df['T'] | df['TG']
    
    # 背离消失条件
    df['顶背离消失'] = (df['直接顶背离'].shift(1) & (df['DIFH1'] >= df['DIFH2'])) | \
                    (df['隔峰顶背离'].shift(1) & (df['DIFH1'] >= df['DIFH3']))
    
    df['底背离消失'] = (df['直接底背离'].shift(1) & (df['DIFL1'] <= df['DIFL2'])) | \
                    (df['隔峰底背离'].shift(1) & (df['DIFL1'] <= df['DIFL3']))
    
    # 结构信号
    df['顶结构'] = df['TG']
    df['底结构'] = df['BG']
    
    # 最终背离信号
    df['顶背离'] = df['T'] | df['顶结构']
    df['底背离'] = df['B'] | df['底结构']
    
    # 买卖信号
    df['GOLDEN_CROSS'] = CROSS(df['DIF'], df['DEA'])
    df['DEATH_CROSS'] = CROSS(df['DEA'], df['DIF'])
    
    df['低位金叉'] = df['GOLDEN_CROSS'] & (df['DIF'] < -0.1)
    df['二次金叉'] = (df['GOLDEN_CROSS'] & 
                   (df['DEA'] < 0) & 
                   (df['金叉'].rolling(21).sum() == 2))
    
    # 趋势判断
    # 计算120和250日内MACD最大值
    df['MACD120_MAX'] = df['MACD'].rolling(120).max()
    df['MACD250_MAX'] = df['MACD'].rolling(250).max()
    
    # 计算BARSLAST(MACD=HHV(MACD,120))
    df['MACD120_POS'] = 0
    df['MACD250_POS'] = 0
    
    # 计算MACD120和MACD250
    for i in range(len(df)):
        # 对于MACD120
        if i >= 120:
            window = df['MACD'].iloc[i-120:i+1]
            max_pos = window[window == window.max()].index[-1]  # 找到最近的最大值位置
            df.loc[df.index[i], 'MACD120'] = df.loc[max_pos, 'MACD'] / 2
        else:
            df.loc[df.index[i], 'MACD120'] = df.loc[df.index[i], 'MACD'] / 2
            
        # 对于MACD250
        if i >= 250:
            window = df['MACD'].iloc[i-250:i+1]
            max_pos = window[window == window.max()].index[-1]  # 找到最近的最大值位置
            df.loc[df.index[i], 'MACD250'] = df.loc[max_pos, 'MACD'] / 2
        else:
            df.loc[df.index[i], 'MACD250'] = df.loc[df.index[i], 'MACD'] / 2
    
    # 顶底成立条件
    df['顶成立'] = (df['顶钝化'] & df['DEATH_CROSS'] & df['顶结构'])
    df['底成立'] = (df['底钝化'] & df['GOLDEN_CROSS'] & df['底结构'])
    
    # XG信号和强势区判断
    df['XG'] = (df['MACD120'] != df['MACD120'].shift(1))
    df['强势区'] = (df['MACD'] >= df['MACD250'])
    
    # 主升判断
    df['主升'] = (df['XG'] & 
                (df['XG'] > df['XG'].shift(1)) & 
                df['强势区'] & 
                (df['强势区'] > df['强势区'].shift(1)))
    
    # 删除临时列
    df = df.drop(['MACD120_MAX', 'MACD250_MAX', 'MACD120_POS', 'MACD250_POS', 'XG'], axis=1)
    
    # 填充所有可能的NaN值
    df = df.fillna(0)
    
    return df

def analyze_stock_signals(stock_code, stock_name):
    """分析单个股票的信号"""
    df = get_stock_data(stock_code)
    if df is None or len(df) < 120:  # 确保有足够的数据进行分析
        return None
    
    try:
        df = calculate_macd_indicators(df)
        latest = df.iloc[-1]  # 获取最新一天的数据
        
        signals = {
            'code': stock_code,
            'name': stock_name,
            'date': df.index[-1].strftime('%Y-%m-%d'),
            'close': latest['close'],
            'signals': {
                '顶钝化': bool(latest['顶钝化']),
                '底钝化': bool(latest['底钝化']),
                '顶结构': bool(latest['顶结构']),
                '底结构': bool(latest['底结构']),
                '顶背离': bool(latest['顶背离']),
                '底背离': bool(latest['底背离']),
                '主升': bool(latest['主升']),
                '顶成立': bool(latest['顶成立']),
                '底成立': bool(latest['底成立'])
            }
        }
        return signals
    except Exception as e:
        # 静默跳过错误，不显示错误信息
        return None

from concurrent.futures import ProcessPoolExecutor
import time

def process_single_stock(args):
    """处理单个股票的信号（用于多进程）"""
    code, name = args
    try:
        return analyze_stock_signals(code, name)
    except Exception as e:
        # 静默跳过错误，不显示错误信息
        return None

def get_all_stock_signals():
    """获取所有股票的信号"""
    stocks = get_all_stocks()
    # 使用包装好的日志函数
    logger = setup_logger_and_log_stocks(stocks)
    if stocks is None:
        return []
    
    all_signals = []
    total = len(stocks)
    processed = 0
    start_time = time.time()
    
    # 使用进程池处理股票数据
    with ProcessPoolExecutor(max_workers=4) as executor:
        # 创建任务列表
        stock_list = list(zip(stocks['code'], stocks['name']))
        
        # 分批提交任务，避免同时发送太多请求
        batch_size = 50
        batch_count = 0  # 批次计数器
        total_batches = (len(stock_list) + batch_size - 1) // batch_size  # 总批次数
        
        for i in range(0, len(stock_list), batch_size):
            batch_count += 1
            batch = stock_list[i:i+batch_size]
            futures = [executor.submit(process_single_stock, (code, name)) for code, name in batch]
            
            # 记录批次信息到日志
            log_stock_analysis(f"正在处理第 {batch_count}/{total_batches} 批，此批次包含 {len(futures)} 个任务")
            
            # 处理结果
            for future in futures:
                try:
                    result = future.result()
                    if result is not None:
                        all_signals.append(result)
                    processed += 1
                    
                    # 每处理100个股票才显示一次进度
                    if processed % 100 == 0 or processed == total:
                        progress = (processed / total) * 100
                        elapsed_time = time.time() - start_time
                        estimated_total_time = (elapsed_time / processed) * total if processed > 0 else 0
                        remaining_time = max(0, estimated_total_time - elapsed_time)
                        
                        log_stock_analysis(f"处理进度: {processed}/{total} ({progress:.1f}%) - "
                              f"已用时: {int(elapsed_time)}秒 - "
                              f"预计剩余: {int(remaining_time)}秒")
                    
                except Exception:
                    pass
            
            # 批次间添加延迟，避免请求过快
            time.sleep(2)
    
    total_time = int(time.time() - start_time)
    log_stock_analysis(f"处理完成! 总用时: {total_time}秒")
    log_stock_analysis(f"成功处理: {len(all_signals)}/{total} 只股票")
    
    return all_signals 