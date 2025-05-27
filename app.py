from flask import Flask, request, jsonify, render_template, redirect
import requests
import re
import json
from urllib.parse import urlparse, unquote
import time
from datetime import datetime, timedelta
import threading
from rule_converter import RuleConverter, convert_clash_to_singbox, validate_singbox_rules
from collections import defaultdict

app = Flask(__name__)

# 配置
MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB
RATE_LIMIT_PER_MINUTE = 20

# Flask配置
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_SIZE

# 全局计数器
class GlobalStats:
    def __init__(self):
        self.data = {
            'total_conversions': 0,
            'successful_conversions': 0,
            'failed_conversions': 0,
            'start_time': datetime.now().isoformat(),
            'hourly_requests': [0] * 24,  # 24小时请求统计
            'peak_requests': 0,  # 每分钟最高请求数
            'avg_response_time': 0,  # 平均响应时间(ms)
            'api_calls': 0,  # API调用次数
            'text_conversions': 0,  # 文本转换次数
            'last_hour_index': datetime.now().hour  # 当前小时索引
        }
        self.response_times = []  # 响应时间记录
        self.minute_requests = defaultdict(int)  # 每分钟请求数
    
    def update(self, success=True, response_time=None, is_api_call=False):
        self.data['total_conversions'] += 1
        if success:
            self.data['successful_conversions'] += 1
        else:
            self.data['failed_conversions'] += 1
            
        # 更新API调用或文本转换计数
        if is_api_call:
            self.data['api_calls'] += 1
        else:
            self.data['text_conversions'] += 1
            
        # 更新当前小时的请求数
        current_hour = datetime.now().hour
        if current_hour != self.data['last_hour_index']:
            # 向前移动所有小时数据
            self.data['hourly_requests'] = self.data['hourly_requests'][1:] + [0]
            self.data['last_hour_index'] = current_hour
        
        self.data['hourly_requests'][-1] += 1
        
        # 更新每分钟请求数
        minute_key = datetime.now().strftime('%Y-%m-%d %H:%M')
        self.minute_requests[minute_key] += 1
        
        # 更新峰值
        current_minute_requests = self.minute_requests[minute_key]
        if current_minute_requests > self.data['peak_requests']:
            self.data['peak_requests'] = current_minute_requests
            
        # 更新响应时间
        if response_time:
            self.response_times.append(response_time)
            # 保留最近1000条记录
            if len(self.response_times) > 1000:
                self.response_times = self.response_times[-1000:]
            self.data['avg_response_time'] = int(sum(self.response_times) / len(self.response_times))
            
        # 清理旧的分钟请求数据
        current_time = datetime.now()
        keys_to_remove = []
        for key in self.minute_requests:
            time_obj = datetime.strptime(key, '%Y-%m-%d %H:%M')
            if (current_time - time_obj).total_seconds() > 3600:  # 1小时前的数据
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.minute_requests[key]
    
    def get_api_percentage(self):
        """计算API调用占比"""
        if self.data['total_conversions'] == 0:
            return 0
        return round((self.data['api_calls'] / self.data['total_conversions']) * 100, 1)

conversion_stats = GlobalStats()

# IP限速追踪
rate_limit_tracker = defaultdict(list)

# 线程锁
stats_lock = threading.Lock()
rate_limit_lock = threading.Lock()

def check_rate_limit(ip: str) -> bool:
    with rate_limit_lock:
        now = time.time()
        rate_limit_tracker[ip] = [
            timestamp for timestamp in rate_limit_tracker[ip]
            if now - timestamp < 60
        ]
        
        if len(rate_limit_tracker[ip]) >= RATE_LIMIT_PER_MINUTE:
            return False
        
        rate_limit_tracker[ip].append(now)
        return True

def update_stats(success=True, response_time=None, is_api_call=False):
    with stats_lock:
        conversion_stats.update(success, response_time, is_api_call)

@app.errorhandler(413)
def request_entity_too_large(error):
    update_stats(False, None, False)
    return jsonify({'error': f'Request too large. Maximum size is {MAX_CONTENT_SIZE//1024//1024}MB'}), 413

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stats')
def stats():
    return render_template('stats.html', stats=conversion_stats.data)

@app.route('/api/stats')
def api_stats():
    stats_data = conversion_stats.data.copy()
    stats_data['api_percentage'] = conversion_stats.get_api_percentage()
    return jsonify(stats_data)

@app.route('/api/hourly_stats')
def hourly_stats():
    """获取24小时请求统计数据"""
    with stats_lock:
        current_hour = datetime.now().hour
        hours = [(current_hour - i) % 24 for i in range(24, 0, -1)]
        
        # 调整数据顺序使其匹配小时顺序
        data = []
        for i, hour in enumerate(hours):
            offset = (current_hour - hour) % 24
            if offset < len(conversion_stats.data['hourly_requests']):
                data.append(conversion_stats.data['hourly_requests'][-offset-1])
            else:
                data.append(0)
                
        return jsonify({
            'hours': hours,
            'data': data,
            'avg_per_hour': sum(data) // 24 if sum(data) > 0 else 0
        })

@app.route('/rules/<path:url>')
def convert_rules(url):
    client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', '127.0.0.1')
    if not check_rate_limit(client_ip):
        return jsonify({'error': 'Rate limit exceeded. Maximum 20 requests per minute per IP.'}), 429
    
    start_time = time.time()
    try:
        decoded_url = unquote(url)
        
        parsed = urlparse(decoded_url)
        if not parsed.scheme or not parsed.netloc:
            update_stats(False, (time.time() - start_time) * 1000, True)
            return jsonify({'error': 'Invalid URL format'}), 400
        
        headers = {
            'User-Agent': 'clash-to-singbox-converter/1.0'
        }
        
        response = requests.get(decoded_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        if len(response.content) > MAX_CONTENT_SIZE:
            update_stats(False, (time.time() - start_time) * 1000, True)
            return jsonify({'error': f'Content too large. Maximum size is {MAX_CONTENT_SIZE//1024//1024}MB'}), 413
        
        converter = RuleConverter()
        singbox_rules = converter.convert(response.text)
        
        if not validate_singbox_rules(singbox_rules):
            update_stats(False, (time.time() - start_time) * 1000, True)
            return jsonify({'error': 'Invalid conversion result'}), 500
        
        update_stats(True, (time.time() - start_time) * 1000, True)
        
        return jsonify(singbox_rules)
        
    except requests.RequestException as e:
        update_stats(False, (time.time() - start_time) * 1000, True)
        return jsonify({'error': f'Failed to fetch rules: {str(e)}'}), 500
    except Exception as e:
        update_stats(False, (time.time() - start_time) * 1000, True)
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

@app.route('/convert', methods=['POST'])
def convert_text():
    client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', '127.0.0.1')
    if not check_rate_limit(client_ip):
        return jsonify({'error': 'Rate limit exceeded. Maximum 20 requests per minute per IP.'}), 429
    
    start_time = time.time()
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            update_stats(False, (time.time() - start_time) * 1000, False)
            return jsonify({'error': 'Missing content field'}), 400
        
        content = data['content']
        
        if len(content.encode('utf-8')) > MAX_CONTENT_SIZE:
            update_stats(False, (time.time() - start_time) * 1000, False)
            return jsonify({'error': f'Content too large. Maximum size is {MAX_CONTENT_SIZE//1024//1024}MB'}), 413
        
        converter = RuleConverter()
        singbox_rules = converter.convert(content)
        
        if not validate_singbox_rules(singbox_rules):
            update_stats(False, (time.time() - start_time) * 1000, False)
            return jsonify({'error': 'Invalid conversion result'}), 500
        
        update_stats(True, (time.time() - start_time) * 1000, False)
        
        return jsonify(singbox_rules)
        
    except Exception as e:
        update_stats(False, (time.time() - start_time) * 1000, False)
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

@app.route('/api/validate', methods=['POST'])
def validate_rules():
    client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', '127.0.0.1')
    if not check_rate_limit(client_ip):
        return jsonify({'error': 'Rate limit exceeded. Maximum 20 requests per minute per IP.'}), 429
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing JSON data'}), 400
        
        is_valid = validate_singbox_rules(data)
        return jsonify({
            'valid': is_valid,
            'message': 'Valid Sing-box rule format' if is_valid else 'Invalid Sing-box rule format'
        })
        
    except Exception as e:
        return jsonify({'error': f'Validation failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False) 