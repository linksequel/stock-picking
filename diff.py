"""
@Author: suqiulin
@Email: 72405483@cityu-dg.edu.cn
@Date: 2025/7/16
"""
import json

def compare_json(json1_path, json2_path):
    with open(json1_path, 'r', encoding='utf-8') as f1, open(json2_path, 'r', encoding='utf-8') as f2:
        data1 = json.load(f1)
        data2 = json.load(f2)

    code_data1 = {item["code"]: item for item in data1["signals"]}
    code_data2 = {item["code"]: item for item in data2["signals"]}

    all_codes = set(code_data1.keys()).union(set(code_data2.keys()))
    diffs = []
    for code in all_codes:
        item1 = code_data1.get(code, {})
        item2 = code_data2.get(code, {})
        keys1 = set(item1.keys())
        keys2 = set(item2.keys())
        all_keys = keys1.union(keys2)
        for key in all_keys:
            if key != "code" and item1.get(key) != item2.get(key):
                diffs.append({
                    "code": code,
                    "key": key,
                    "value_in_json1": item1.get(key),
                    "value_in_json2": item2.get(key)
                })
    return diffs

# 假设json1.json和json2.json是你要比较的两个文件路径
json1_path = 'stock_signals.json'
json2_path = 'others.json'
differences = compare_json(json1_path, json2_path)
for diff in differences:
    print(diff)