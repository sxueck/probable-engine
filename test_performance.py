#!/usr/bin/env python3
import requests
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8080"

def test_rate_limit():
    """测试IP限速功能"""
    print("测试IP限速功能...")
    
    def make_request(i):
        try:
            response = requests.post(f"{BASE_URL}/convert", 
                                   json={"content": f".example{i}.com"})
            return response.status_code, response.json()
        except Exception as e:
            return None, str(e)
    
    # 快速发送25个请求 (超过20个限制)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request, i) for i in range(25)]
        results = [future.result() for future in futures]
    
    success_count = sum(1 for status, _ in results if status == 200)
    rate_limited_count = sum(1 for status, _ in results if status == 429)
    
    print(f"成功请求: {success_count}")
    print(f"被限速请求: {rate_limited_count}")
    print(f"限速功能{'正常' if rate_limited_count > 0 else '异常'}")
    print()

def test_performance_consistency():
    """测试性能一致性"""
    print("测试性能一致性...")
    
    test_content = """
    .steamserver.net
    .example.com
    .test.org
    """ * 100
    
    times = []
    for i in range(3):
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/convert", 
                               json={"content": test_content})
        request_time = time.time() - start_time
        times.append(request_time)
        print(f"第{i+1}次请求时间: {request_time:.4f}秒")
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)
    print(f"平均时间: {avg_time:.4f}秒")
    print(f"性能变化范围: {min_time:.4f}s - {max_time:.4f}s")
    print()

def test_size_limit():
    """测试大小限制"""
    print("测试大小限制...")
    
    # 创建一个超过10MB的内容
    large_content = ".example.com\n" * (1024 * 1024)  # 约15MB
    
    try:
        response = requests.post(f"{BASE_URL}/convert", 
                               json={"content": large_content})
        if response.status_code == 413:
            print("大小限制功能正常")
        else:
            print(f"大小限制可能异常，状态码: {response.status_code}")
    except Exception as e:
        print(f"请求异常: {e}")
    print()

def test_stats_persistence():
    """测试统计数据持久化"""
    print("测试统计数据持久化...")
    
    # 获取当前统计
    stats1 = requests.get(f"{BASE_URL}/api/stats").json()
    
    # 发送几个请求
    for i in range(3):
        requests.post(f"{BASE_URL}/convert", 
                     json={"content": f".test{i}.com"})
    
    # 再次获取统计
    stats2 = requests.get(f"{BASE_URL}/api/stats").json()
    
    print(f"初始统计: {stats1}")
    print(f"更新统计: {stats2}")
    print(f"统计增长: {stats2['total_conversions'] - stats1['total_conversions']}")
    print(f"统计持久化{'正常' if stats2['total_conversions'] > stats1['total_conversions'] else '异常'}")
    print()

def test_performance_improvement():
    """测试性能提升"""
    print("测试性能提升...")
    
    # 创建一个较大的测试内容
    test_content = "\n".join([f".domain{i}.com" for i in range(1000)])
    
    # 多次测试取平均
    times = []
    for i in range(5):
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/convert", 
                               json={"content": test_content})
        process_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            conversion_stats = data.get('conversion_stats', {})
            actual_convert_time = conversion_stats.get('processing_time', 0)
            times.append(actual_convert_time)
            print(f"第{i+1}次测试 - 总时间: {process_time:.4f}s, 转换时间: {actual_convert_time:.4f}s")
    
    if times:
        avg_time = sum(times) / len(times)
        print(f"平均转换时间: {avg_time:.4f}秒")
        print(f"转换速度: {len(test_content.encode('utf-8'))/1024/avg_time:.2f} KB/s")
    print()

def main():
    print("Clash to Singbox 转换器性能测试")
    print("=" * 50)
    
    try:
        # 检查服务是否运行
        response = requests.get(f"{BASE_URL}/api/stats", timeout=5)
        print(f"服务状态: 正常运行")
        print()
    except Exception as e:
        print(f"无法连接到服务: {e}")
        return
    
    # 运行各项测试
    test_stats_persistence()
    test_performance_consistency()
    test_performance_improvement()
    test_size_limit()
    test_rate_limit()
    
    print("所有测试完成!")

if __name__ == "__main__":
    main() 