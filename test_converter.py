#!/usr/bin/env python3
"""
测试 Clash 规则转换器功能
"""

import json
import requests
import time

def test_text_conversion():
    """测试文本转换功能"""
    print("🧪 测试文本转换功能...")
    
    test_content = """
# 这是注释
.steamserver.net
.dl.playstation.net
example.com
test.domain.org
# 另一个注释
!excluded.domain.com
th1s_rule5et_1s_m4d3_by_5ukk4w_ruleset.skk.moe
"""
    
    url = "http://localhost:8080/convert"
    data = {"content": test_content}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            print("✅ 文本转换成功")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"❌ 文本转换失败: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_url_conversion():
    """测试URL转换功能"""
    print("\n🧪 测试URL转换功能...")
    
    test_url = "https://gitlab.com/SukkaW/ruleset.skk.moe/-/raw/master/List/domainset/game-download.conf?ref_type=heads"
    api_url = f"http://localhost:8080/rules/{test_url}"
    
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            result = response.json()
            print("✅ URL转换成功")
            
            # 检查结果格式
            if "rules" in result and "version" in result:
                print(f"📊 转换结果包含 {len(result['rules'])} 个规则组")
                if result["rules"]:
                    first_rule = result["rules"][0]
                    if "domain_suffix" in first_rule:
                        print(f"📝 域名后缀规则数量: {len(first_rule['domain_suffix'])}")
            print("✨ 转换格式正确")
        else:
            print(f"❌ URL转换失败: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_stats_api():
    """测试统计API"""
    print("\n🧪 测试统计API...")
    
    url = "http://localhost:8080/api/stats"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print("✅ 统计API正常")
            print(f"📊 总转换次数: {stats['total_conversions']}")
            print(f"✅ 成功转换: {stats['successful_conversions']}")
            print(f"❌ 失败转换: {stats['failed_conversions']}")
            print(f"⏰ 启动时间: {stats['start_time']}")
        else:
            print(f"❌ 统计API失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_web_pages():
    """测试Web页面"""
    print("\n🧪 测试Web页面...")
    
    pages = [
        ("主页", "http://localhost:8080/"),
        ("统计页面", "http://localhost:8080/stats")
    ]
    
    for name, url in pages:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"✅ {name} 访问正常")
            else:
                print(f"❌ {name} 访问失败: {response.status_code}")
        except Exception as e:
            print(f"❌ {name} 请求失败: {e}")

def main():
    print("🎯 Clash to Singbox 转换器测试")
    print("=" * 50)
    
    # 等待服务启动
    print("⏳ 等待服务启动...")
    for i in range(10):
        try:
            response = requests.get("http://localhost:8080/", timeout=5)
            if response.status_code == 200:
                print("✅ 服务已启动")
                break
        except:
            time.sleep(1)
    else:
        print("❌ 服务未启动，请先运行 python app.py")
        return
    
    # 运行测试
    test_web_pages()
    test_text_conversion()
    test_url_conversion()
    test_stats_api()
    
    print("\n" + "=" * 50)
    print("🎉 测试完成！")

if __name__ == "__main__":
    main() 