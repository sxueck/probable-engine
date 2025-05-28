"""
Clash to Sing-box Rule Converter Module

支持完整的Clash规则格式转换为Sing-box规则格式，包括Rule Providers规则集
基于官方文档：
- Clash: https://clash.wiki/configuration/rules.html
- Clash Rule Providers: https://clash.wiki/premium/rule-providers.html
- Sing-box: https://sing-box.sagernet.org/zh/configuration/rule-set/headless-rule/
"""

import re
import json
import yaml
import argparse
import time
import os
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlparse
import ipaddress


class RuleConverter:
    """Clash规则到Sing-box规则的转换器"""
    
    def __init__(self):
        self.supported_clash_rules = {
            'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'GEOIP', 
            'IP-CIDR', 'IP-CIDR6', 'SRC-IP-CIDR', 'SRC-PORT', 
            'DST-PORT', 'PROCESS-PATH', 'MATCH',
            'GEOSITE', 'URL-REGEX'
        }
        
        self.rule_stats = {
            'total_rules': 0,
            'converted_rules': 0,
            'skipped_rules': 0,
            'unsupported_rules': 0,
            'processing_time': 0.0,
            'file_size': 0,
            'rule_provider_format': None
        }
    
    def detect_rule_provider_format(self, content: str) -> Optional[str]:
        """检测Rule Provider格式类型"""
        content = content.strip()
        
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict) and 'payload' in data:
                return 'yaml'
        except:
            pass
        
        # 检查是否是YAML格式的简单判断
        if content.startswith('payload:'):
            return 'yaml'
        
        # 检查是否包含YAML语法特征
        if ':\n' in content or '  - ' in content or content.startswith('- '):
            try:
                fixed_content = content
                if not content.startswith('payload:') and ('  - ' in content or content.startswith('- ')):
                    fixed_content = 'payload:\n' + content
                
                data = yaml.safe_load(fixed_content)
                if isinstance(data, dict) and 'payload' in data:
                    return 'yaml'
            except:
                pass
        
        # 检查是否是纯文本格式
        lines = content.split('\n')
        non_comment_lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
        
        if non_comment_lines:
            # 检查是否包含Clash规则格式
            clash_format_count = sum(1 for line in non_comment_lines[:10] 
                                   if ',' in line and any(line.upper().startswith(rule_type + ',') 
                                   for rule_type in self.supported_clash_rules))
            
            # 检查是否包含域名格式
            domain_format_count = sum(1 for line in non_comment_lines[:10] 
                                    if line.startswith('.') or self.is_valid_domain(line))
            
            if clash_format_count > 0:
                return 'text-classical'
            elif domain_format_count > 0:
                return 'text-domain'
            else:
                return 'text-ipcidr'
        
        return None
    
    def parse_rule_provider_yaml(self, content: str) -> List[str]:
        """解析YAML格式的Rule Provider"""
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict) and 'payload' in data:
                return data['payload']
        except Exception as e:
            print(f"YAML解析错误: {e}")
        return []
    
    def parse_rule_provider_text(self, content: str) -> List[str]:
        """解析文本格式的Rule Provider"""
        lines = content.strip().split('\n')
        rules = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                rules.append(line)
        
        return rules
    
    def convert_rule_provider(self, content: str, behavior: str = None) -> Dict[str, Any]:
        """转换Rule Provider格式"""
        format_type = self.detect_rule_provider_format(content)
        self.rule_stats['rule_provider_format'] = format_type
        
        if not format_type:
            return self.convert(content)
        
        # 解析规则
        if format_type == 'yaml':
            rules = self.parse_rule_provider_yaml(content)
        else:
            rules = self.parse_rule_provider_text(content)
        
        # 根据behavior类型处理规则
        if behavior:
            return self.convert_by_behavior(rules, behavior)
        else:
            # 自动检测behavior类型
            return self.convert_with_auto_behavior(rules, format_type)
    
    def convert_by_behavior(self, rules: List[str], behavior: str) -> Dict[str, Any]:
        """根据指定的behavior类型转换规则"""
        converted_rules = []
        
        for rule in rules:
            self.rule_stats['total_rules'] += 1
            
            if behavior == 'domain':
                if rule.startswith('.'):
                    converted_rules.append(self.convert_domain_suffix_rule(rule[1:]))
                elif self.is_valid_domain(rule):
                    converted_rules.append(self.convert_domain_rule(rule))
                else:
                    self.rule_stats['skipped_rules'] += 1
                    continue
            elif behavior == 'ipcidr':
                try:
                    ipaddress.ip_network(rule, strict=False)
                    converted_rules.append(self.convert_ip_cidr_rule(rule))
                except ValueError:
                    self.rule_stats['skipped_rules'] += 1
                    continue
            elif behavior == 'classical':
                parsed_rule = self.parse_rule_line(rule)
                if parsed_rule:
                    converted_rule = self.convert_single_rule(parsed_rule)
                    if converted_rule:
                        converted_rules.append(converted_rule)
                    else:
                        self.rule_stats['skipped_rules'] += 1
                        continue
                else:
                    self.rule_stats['skipped_rules'] += 1
                    continue
            
            self.rule_stats['converted_rules'] += 1
        
        rules = self.merge_rules(converted_rules)
        
        return {
            "rules": rules,
            "version": 2
        }
    
    def convert_with_auto_behavior(self, rules: List[str], format_type: str) -> Dict[str, Any]:
        """自动检测behavior类型并转换规则"""
        if format_type == 'text-classical':
            return self.convert_by_behavior(rules, 'classical')
        elif format_type == 'text-domain':
            return self.convert_by_behavior(rules, 'domain')
        elif format_type == 'text-ipcidr':
            return self.convert_by_behavior(rules, 'ipcidr')
        elif format_type == 'yaml':
            # YAML格式，需要检测payload中的规则类型
            if not rules:
                return {"rules": [], "version": 2}
            
            # 检测规则类型
            sample_rules = rules[:10]
            clash_format_count = sum(1 for rule in sample_rules 
                                   if ',' in rule and any(rule.upper().startswith(rule_type + ',') 
                                   for rule_type in self.supported_clash_rules))
            
            domain_format_count = sum(1 for rule in sample_rules 
                                    if rule.startswith('.') or self.is_valid_domain(rule))
            
            ip_format_count = 0
            for rule in sample_rules:
                try:
                    ipaddress.ip_network(rule, strict=False)
                    ip_format_count += 1
                except ValueError:
                    pass
            
            # 根据检测结果选择behavior
            if clash_format_count > 0:
                return self.convert_by_behavior(rules, 'classical')
            elif ip_format_count > domain_format_count:
                return self.convert_by_behavior(rules, 'ipcidr')
            else:
                return self.convert_by_behavior(rules, 'domain')
        else:
            # 混合格式，逐行检测
            return self.convert('\n'.join(rules))

    def parse_rule_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析单行规则，支持Clash格式和纯域名格式"""
        line = line.strip()
        
        # 跳过注释和空行
        if not line or line.startswith('#') or line.startswith('//') or line.startswith('!'):
            return None
        
        # 检查是否是Clash格式规则
        if ',' in line and any(line.upper().startswith(rule_type + ',') for rule_type in self.supported_clash_rules):
            # Clash格式: TYPE,ARGUMENT,POLICY(,no-resolve)
            parts = [part.strip() for part in line.split(',')]
            if len(parts) < 2:
                return None
            
            rule_type = parts[0].upper()
            argument = parts[1] if len(parts) > 1 else ""
            policy = parts[2] if len(parts) > 2 else ""
            no_resolve = len(parts) > 3 and parts[3].lower() == 'no-resolve'
            
            return {
                'type': rule_type,
                'argument': argument,
                'policy': policy,
                'no_resolve': no_resolve,
                'original': line
            }
        else:
            # 纯域名格式
            if line.startswith('.'):
                # 域名后缀
                return {
                    'type': 'DOMAIN-SUFFIX',
                    'argument': line[1:],
                    'policy': '',
                    'no_resolve': False,
                    'original': line
                }
            elif self.is_valid_domain(line):
                # 完整域名
                return {
                    'type': 'DOMAIN',
                    'argument': line,
                    'policy': '',
                    'no_resolve': False,
                    'original': line
                }
        
        return None
    
    def convert_domain_rule(self, argument: str) -> Dict[str, List[str]]:
        """转换DOMAIN规则"""
        return {"domain": [argument]}
    
    def convert_domain_suffix_rule(self, argument: str) -> Dict[str, List[str]]:
        """转换DOMAIN-SUFFIX规则"""
        return {"domain_suffix": [argument]}
    
    def convert_domain_keyword_rule(self, argument: str) -> Dict[str, List[str]]:
        """转换DOMAIN-KEYWORD规则"""
        return {"domain_keyword": [argument]}
    
    def convert_geoip_rule(self, argument: str) -> Dict[str, List[str]]:
        """转换GEOIP规则"""
        return {"geoip": [argument.upper()]}
    
    def convert_geosite_rule(self, argument: str) -> Dict[str, List[str]]:
        """转换GEOSITE规则"""
        return {"geosite": [argument.lower()]}
    
    def convert_ip_cidr_rule(self, argument: str, is_ipv6: bool = False) -> Dict[str, List[str]]:
        """转换IP-CIDR和IP-CIDR6规则"""
        try:
            if is_ipv6:
                ipaddress.IPv6Network(argument, strict=False)
            else:
                ipaddress.IPv4Network(argument, strict=False)
            return {"ip_cidr": [argument]}
        except ValueError:
            return {}
    
    def convert_src_ip_cidr_rule(self, argument: str) -> Dict[str, List[str]]:
        """转换SRC-IP-CIDR规则"""
        try:
            ipaddress.IPv4Network(argument, strict=False)
            return {"source_ip_cidr": [argument]}
        except ValueError:
            return {}
    
    def convert_port_rule(self, argument: str, is_source: bool = False) -> Dict[str, List[int]]:
        """转换端口规则"""
        try:
            if '-' in argument:
                # 端口范围
                start, end = argument.split('-', 1)
                start_port, end_port = int(start.strip()), int(end.strip())
                if 1 <= start_port <= end_port <= 65535:
                    field_name = "source_port_range" if is_source else "port_range"
                    return {field_name: [f"{start_port}:{end_port}"]}
            else:
                # 单个端口
                port = int(argument)
                if 1 <= port <= 65535:
                    field_name = "source_port" if is_source else "port"
                    return {field_name: [port]}
        except ValueError:
            pass
        return {}
    
    def convert_process_rule(self, argument: str, is_path: bool = False) -> Dict[str, List[str]]:
        """转换进程规则"""
        field_name = "process_path"
        return {field_name: [argument]}
    
    def convert_url_regex_rule(self, argument: str) -> Dict[str, List[str]]:
        """转换URL-REGEX规则"""
        return {"domain_regex": [argument]}
    
    def convert_single_rule(self, parsed_rule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """转换单个规则"""
        rule_type = parsed_rule['type']
        argument = parsed_rule['argument']
        
        if rule_type == 'DOMAIN':
            return self.convert_domain_rule(argument)
        elif rule_type == 'DOMAIN-SUFFIX':
            return self.convert_domain_suffix_rule(argument)
        elif rule_type == 'DOMAIN-KEYWORD':
            return self.convert_domain_keyword_rule(argument)
        elif rule_type == 'GEOIP':
            return self.convert_geoip_rule(argument)
        elif rule_type == 'GEOSITE':
            return self.convert_geosite_rule(argument)
        elif rule_type == 'IP-CIDR':
            return self.convert_ip_cidr_rule(argument, False)
        elif rule_type == 'IP-CIDR6':
            return self.convert_ip_cidr_rule(argument, True)
        elif rule_type == 'SRC-IP-CIDR':
            return self.convert_src_ip_cidr_rule(argument)
        elif rule_type == 'SRC-PORT':
            return self.convert_port_rule(argument, True)
        elif rule_type == 'DST-PORT':
            return self.convert_port_rule(argument, False)
        elif rule_type == 'PROCESS-PATH':
            return self.convert_process_rule(argument, True)
        elif rule_type == 'URL-REGEX':
            return self.convert_url_regex_rule(argument)
        elif rule_type == 'MATCH':
            return None
        else:
            return None
    
    def merge_rules(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not rules:
            return []
        
        merged = {}
        
        for rule in rules:
            if not rule:
                continue
                
            for key, value in rule.items():
                if key not in merged:
                    merged[key] = set()
                
                if isinstance(value, list):
                    merged[key].update(value)
                else:
                    merged[key].add(value)
        
        result = []
        for key, value_set in merged.items():
            if value_set:
                unique_values = list(value_set)
                result.append({key: unique_values})
        
        return result
    
    def is_valid_domain(self, domain: str) -> bool:
        """验证域名格式"""
        if not domain or len(domain) > 253:
            return False
        
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, domain))
    
    def convert(self, content: str, behavior: str = None) -> Dict[str, Any]:
        """主转换方法"""
        start_time = time.time()
        
        self.rule_stats = {
            'total_rules': 0,
            'converted_rules': 0,
            'skipped_rules': 0,
            'unsupported_rules': 0,
            'processing_time': 0.0,
            'file_size': len(content.encode('utf-8')),
            'rule_provider_format': None
        }
        
        if not content or not content.strip():
            return {
                "rules": [],
                "version": 2
            }
        
        # 检查是否是Rule Provider格式
        if behavior or self.detect_rule_provider_format(content):
            result = self.convert_rule_provider(content, behavior)
        else:
            lines = content.strip().split('\n')
            converted_rules = []
            
            valid_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    valid_lines.append(line)
            
            self.rule_stats['total_rules'] = len(valid_lines)
            
            for line in valid_lines:
                parsed_rule = self.parse_rule_line(line)
                if not parsed_rule:
                    self.rule_stats['skipped_rules'] += 1
                    continue
                
                converted_rule = self.convert_single_rule(parsed_rule)
                if converted_rule:
                    converted_rules.append(converted_rule)
                    self.rule_stats['converted_rules'] += 1
                else:
                    if parsed_rule['type'] in self.supported_clash_rules:
                        self.rule_stats['skipped_rules'] += 1
                    else:
                        self.rule_stats['unsupported_rules'] += 1
            
            rules = self.merge_rules(converted_rules)
            result = {
                "rules": rules,
                "version": 2
            }
        
        self.rule_stats['processing_time'] = time.time() - start_time
        return result
    
    def get_conversion_stats(self) -> Dict[str, Any]:
        """获取转换统计信息"""
        return self.rule_stats.copy()
    
    def print_benchmark(self):
        """打印性能基准数据"""
        stats = self.get_conversion_stats()
        
        print("\n" + "="*50)
        print("转换性能基准数据")
        print("="*50)
        print(f"文件大小: {stats['file_size']:,} 字节 ({stats['file_size']/1024:.2f} KB)")
        print(f"处理时间: {stats['processing_time']:.4f} 秒")
        print(f"处理速度: {stats['file_size']/1024/stats['processing_time']:.2f} KB/s")
        print(f"规则格式: {stats['rule_provider_format'] or '传统格式'}")
        print()
        print("规则统计:")
        print(f"  总规则数: {stats['total_rules']:,}")
        print(f"  成功转换: {stats['converted_rules']:,}")
        print(f"  跳过规则: {stats['skipped_rules']:,}")
        print(f"  不支持规则: {stats['unsupported_rules']:,}")
        print(f"  转换成功率: {stats['converted_rules']/max(stats['total_rules'], 1)*100:.2f}%")
        print("="*50)


def convert_clash_to_singbox(content: str, behavior: str = None) -> Dict[str, Any]:
    """便捷函数：转换Clash规则到Sing-box格式"""
    converter = RuleConverter()
    return converter.convert(content, behavior)


def validate_singbox_rules(rules: Dict[str, Any]) -> bool:
    """验证Sing-box规则格式"""
    if not isinstance(rules, dict):
        return False
    
    if 'version' not in rules or rules['version'] != 2:
        return False
    
    if 'rules' not in rules or not isinstance(rules['rules'], list):
        return False
    
    return True


def main():
    """CLI主函数"""
    parser = argparse.ArgumentParser(
        description='Clash规则转换为Sing-box规则集格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python rule_converter.py input.txt -o output.json
  python rule_converter.py rules.yaml -b domain -o domain_rules.json
  python rule_converter.py clash_rules.txt --behavior classical --benchmark
        """
    )
    
    parser.add_argument('input', help='输入文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径 (默认: 输出到控制台)')
    parser.add_argument('-b', '--behavior', 
                       choices=['domain', 'ipcidr', 'classical'],
                       help='Rule Provider行为类型 (domain/ipcidr/classical)')
    parser.add_argument('--benchmark', action='store_true',
                       help='显示性能基准数据')
    parser.add_argument('--pretty', action='store_true',
                       help='格式化JSON输出')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not os.path.exists(args.input):
        print(f"错误: 输入文件 '{args.input}' 不存在")
        return 1
    
    # 读取输入文件
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"错误: 无法读取输入文件: {e}")
        return 1
    
    # 转换规则
    converter = RuleConverter()
    try:
        result = converter.convert(content, args.behavior)
    except Exception as e:
        print(f"错误: 转换失败: {e}")
        return 1
    
    # 输出结果
    json_output = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(json_output)
            print(f"转换完成，结果已保存到: {args.output}")
        except Exception as e:
            print(f"错误: 无法写入输出文件: {e}")
            return 1
    else:
        print(json_output)
    
    # 显示基准数据
    if args.benchmark:
        converter.print_benchmark()
    
    return 0


if __name__ == '__main__':
    exit(main()) 