#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试股票代码去重功能
"""

import pandas as pd
from stock_signals import get_all_stocks

def simulate_duplicate_data():
    """模拟包含重复数据的情况"""
    # 创建包含重复股票代码的测试数据
    test_data = pd.DataFrame({
        'code': ['000001', '000002', '000001', '600036', '000002', '600519'],
        'name': ['平安银行', '万科A', '平安银行重复', '招商银行', '万科A重复', '贵州茅台']
    })
    
    print("原始数据（包含重复）:")
    print(test_data)
    print(f"原始数据长度: {len(test_data)}")
    
    # 应用去重逻辑
    deduplicated = test_data.drop_duplicates(subset=['code'], keep='first')
    deduplicated = deduplicated.reset_index(drop=True)
    
    print("\n去重后的数据:")
    print(deduplicated)
    print(f"去重后数据长度: {len(deduplicated)}")
    
    # 检查重复情况
    duplicates = test_data[test_data.duplicated(subset=['code'], keep=False)]
    print(f"\n重复的记录:")
    print(duplicates)
    
    return deduplicated

def test_real_data():
    """测试真实的沪深300数据"""
    print("=" * 60)
    print("测试真实沪深300数据的去重功能")
    print("=" * 60)
    
    try:
        stocks = get_all_stocks()
        
        if stocks is not None:
            print(f"获取到股票数据: {len(stocks)} 条")
            print(f"股票代码唯一性检查:")
            
            # 检查是否有重复的股票代码
            duplicate_codes = stocks[stocks.duplicated(subset=['code'], keep=False)]
            
            if len(duplicate_codes) > 0:
                print(f"发现 {len(duplicate_codes)} 条重复记录:")
                print(duplicate_codes)
            else:
                print("✓ 没有发现重复的股票代码")
            
            
            # 检查数据完整性
            print(f"\n数据完整性检查:")
            print(f"- 总数据量: {len(stocks)}")
            print(f"- 唯一code数量: {len(stocks['code'].unique())}")
            print(f"- 唯一name数量: {len(stocks['name'].unique())}")
            print(f"- 是否有空值: {stocks.isnull().any().any()}")
            
        else:
            print("无法获取股票数据，可能是网络问题")
            
    except Exception as e:
        print(f"测试过程中出错: {e}")

def check_data_quality(df):
    """检查数据质量"""
    print("\n数据质量报告:")
    print("-" * 40)
    print(f"总记录数: {len(df)}")
    print(f"唯一股票代码数: {df['code'].nunique()}")
    print(f"唯一股票名称数: {df['name'].nunique()}")
    print(f"重复代码数: {len(df) - df['code'].nunique()}")
    print(f"重复名称数: {len(df) - df['name'].nunique()}")
    
    # 检查代码格式
    invalid_codes = df[~df['code'].str.match(r'^\d{6}$')]
    if len(invalid_codes) > 0:
        print(f"无效格式的股票代码: {len(invalid_codes)} 个")
        print(invalid_codes[['code', 'name']])
    else:
        print("✓ 所有股票代码格式正确（6位数字）")

if __name__ == "__main__":
    print("测试股票代码去重功能")
    print("=" * 60)
    
    # 1. 模拟测试
    print("1. 模拟重复数据测试:")
    simulated_data = simulate_duplicate_data()
    check_data_quality(simulated_data)
    
    print("\n")
    
    # 2. 真实数据测试
    print("2. 真实沪深300数据测试:")
    test_real_data() 