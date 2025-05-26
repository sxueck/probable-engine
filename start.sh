#!/bin/bash

echo "🚀 启动 Clash to Singbox 转换工具..."

# 检查是否有虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python -m venv venv
fi

# 激活虚拟环境
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

echo "📥 安装依赖..."
pip install -r requirements.txt

echo "🌐 启动服务..."
echo "访问地址: http://localhost:8080"
echo "统计页面: http://localhost:8080/stats"
echo "按 Ctrl+C 停止服务"

python app.py 