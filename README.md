# Clash to Singbox 规则转换工具

一个用于将 Clash 格式规则实时转换为 Singbox 规则集格式的 Web 服务。

## 功能特性

- 🔄 实时转换 Clash 规则为 Singbox 格式
- 🌐 支持远程 URL 规则文件转换
- 📝 支持直接文本内容转换
- 📊 转换统计和监控
- 🐳 Docker 容器化部署
- 💻 美观的 Web 界面

## 支持的规则格式

### 输入格式 (Clash)
```
# 注释行会被忽略
.steamserver.net
example.com
pf-cdn-content-prod.azureedge.net
```

### 输出格式 (Singbox)
```json
{
  "rules": [
    {
      "domain_suffix": [
        "steamserver.net",
        "example.com"
      ]
    }
  ],
  "version": 2
}
```

## 快速开始

### 使用 Docker Compose (推荐)

1. 克隆项目
```bash
git clone <repository-url>
cd clash-to-singbox-converter
```

2. 构建并启动服务
```bash
docker-compose up -d
```

3. 访问服务
- 主页: http://localhost:8080
- 统计页面: http://localhost:8080/stats

### 使用 Docker

```bash
# 构建镜像
docker build -t clash-to-singbox .

# 运行容器
docker run -d -p 8080:8080 --name clash-to-singbox-converter clash-to-singbox
```

### 本地开发

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 运行应用
```bash
python app.py
```

## API 接口

### 1. URL 规则转换
```
GET /rules/{clash_rule_url}
```

**示例:**
```bash
curl "http://localhost:8080/rules/https://gitlab.com/SukkaW/ruleset.skk.moe/-/raw/master/List/domainset/game-download.conf"
```

### 2. 文本内容转换
```
POST /convert
Content-Type: application/json
```

**请求体:**
```json
{
  "content": ".steamserver.net\nexample.com"
}
```

### 3. 获取统计信息
```
GET /api/stats
```

**响应:**
```json
{
  "total_conversions": 100,
  "successful_conversions": 95,
  "failed_conversions": 5,
  "start_time": "2024-01-01T00:00:00.000000"
}
```

## Benchmark

```
==================================================
转换性能基准数据
==================================================
文件大小: 1,432,357 字节 (1398.79 KB)
处理时间: 0.5844 秒
处理速度: 2393.62 KB/s
规则格式: text-classical

规则统计:
  总规则数: 39,531
  成功转换: 39,531
  跳过规则: 0
  不支持规则: 0
  转换成功率: 100.00%
==================================================
```