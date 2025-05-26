from flask import Flask, request, jsonify, render_template, redirect
import requests
import re
import json
from urllib.parse import urlparse, unquote
import time
from datetime import datetime
import threading

app = Flask(__name__)

# 全局计数器
conversion_stats = {
    'total_conversions': 0,
    'successful_conversions': 0,
    'failed_conversions': 0,
    'start_time': datetime.now().isoformat()
}

# 线程锁
stats_lock = threading.Lock()

def update_stats(success=True):
    with stats_lock:
        conversion_stats['total_conversions'] += 1
        if success:
            conversion_stats['successful_conversions'] += 1
        else:
            conversion_stats['failed_conversions'] += 1

def parse_clash_rules(content):
    """解析Clash格式规则为Singbox格式"""
    lines = content.strip().split('\n')
    
    # 分类存储不同类型的规则
    domain_suffixes = []
    domains = []
    domain_keywords = []
    
    for line in lines:
        line = line.strip()
        
        # 跳过注释和空行
        if not line or line.startswith('#') or line.startswith('//'):
            continue
        
        # 解析 Clash 格式规则
        if line.startswith('DOMAIN-SUFFIX,'):
            domain = line[14:].strip()
            if domain:
                domain_suffixes.append(domain)
        elif line.startswith('DOMAIN,'):
            domain = line[7:].strip()
            if domain:
                domains.append(domain)
        elif line.startswith('DOMAIN-KEYWORD,'):
            keyword = line[15:].strip()
            if keyword:
                domain_keywords.append(keyword)
        elif line.startswith('USER-AGENT,') or line.startswith('PROCESS-NAME,'):
            # 跳过不支持的规则类型
            continue
        else:
            # 处理以点开头的域名后缀（旧格式）
            if line.startswith('.'):
                domain_suffixes.append(line[1:])
            elif line and not line.startswith('!'):
                # 普通域名（旧格式）
                domains.append(line)
    
    # 构建Singbox规则集格式
    rules = []
    
    if domain_suffixes:
        rules.append({
            "domain_suffix": domain_suffixes
        })
    
    if domains:
        rules.append({
            "domain": domains
        })
    
    if domain_keywords:
        rules.append({
            "domain_keyword": domain_keywords
        })
    
    return {
        "rules": rules,
        "version": 2
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stats')
def stats():
    return render_template('stats.html', stats=conversion_stats)

@app.route('/api/stats')
def api_stats():
    return jsonify(conversion_stats)

@app.route('/rules/<path:url>')
def convert_rules(url):
    try:
        # URL解码
        decoded_url = unquote(url)
        
        # 验证URL格式
        parsed = urlparse(decoded_url)
        if not parsed.scheme or not parsed.netloc:
            update_stats(False)
            return jsonify({'error': 'Invalid URL format'}), 400
        
        # 获取远程规则文件
        headers = {
            'User-Agent': 'clash-to-singbox-converter/1.0'
        }
        
        response = requests.get(decoded_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 转换规则
        singbox_rules = parse_clash_rules(response.text)
        
        update_stats(True)
        
        # 返回JSON格式
        return jsonify(singbox_rules)
        
    except requests.RequestException as e:
        update_stats(False)
        return jsonify({'error': f'Failed to fetch rules: {str(e)}'}), 500
    except Exception as e:
        update_stats(False)
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

@app.route('/convert', methods=['POST'])
def convert_text():
    """处理直接文本转换"""
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({'error': 'Missing content field'}), 400
        
        content = data['content']
        singbox_rules = parse_clash_rules(content)
        
        update_stats(True)
        return jsonify(singbox_rules)
        
    except Exception as e:
        update_stats(False)
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False) 