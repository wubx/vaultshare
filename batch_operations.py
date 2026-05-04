#!/usr/bin/env python3
"""
批量操作工具 - 支持批量文件上传和共享管理
"""

import json
import csv
import os
from pathlib import Path
from mock_multitenant_demo import MockStorage, TenantProvider, MultiTenantCloudServices, TenantConsumer

class BatchOperations:
    def __init__(self):
        self.storage = MockStorage()
        self.cloud_services = MultiTenantCloudServices(self.storage)
        self.providers = {}
        self.consumers = {}
    
    def load_config(self, config_file):
        """从配置文件加载租户和文件信息"""
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 创建租户
        for tenant in config.get('tenants', []):
            tenant_id = tenant['id']
            tenant_type = tenant.get('type', 'provider')
            
            if tenant_type == 'provider':
                provider = TenantProvider(tenant_id, self.storage)
                self.cloud_services.register_tenant(tenant_id, provider.tmk)
                self.providers[tenant_id] = provider
                print(f"✓ 创建提供方租户: {tenant_id}")
            else:
                consumer = TenantConsumer(tenant_id)
                self.consumers[tenant_id] = consumer
                print(f"✓ 创建消费方租户: {tenant_id}")
        
        return config
    
    def batch_upload_from_csv(self, tenant_id, csv_file):
        """从CSV文件批量上传"""
        if tenant_id not in self.providers:
            print(f"✗ 租户不存在: {tenant_id}")
            return []
        
        provider = self.providers[tenant_id]
        uploaded_files = []
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = row['filename']
                content = row['content']
                tags = row.get('tags', '').split(',') if row.get('tags') else []
                
                try:
                    file_id = provider.upload_file(filename, content.encode('utf-8'), tags)
                    uploaded_files.append({
                        'filename': filename,
                        'file_id': file_id,
                        'status': 'success'
                    })
                    print(f"✓ 上传成功: {filename}")
                except Exception as e:
                    uploaded_files.append({
                        'filename': filename,
                        'file_id': None,
                        'status': 'failed',
                        'error': str(e)
                    })
                    print(f"✗ 上传失败: {filename} - {e}")
        
        return uploaded_files
    
    def batch_create_shares(self, config):
        """批量创建共享"""
        shares_created = []
        
        for share_config in config.get('shares', []):
            provider_id = share_config['provider_id']
            share_name = share_config['share_name']
            file_patterns = share_config.get('file_patterns', [])
            consumer_ids = share_config['consumer_ids']
            description = share_config.get('description', '')
            
            if provider_id not in self.providers:
                print(f"✗ 提供方租户不存在: {provider_id}")
                continue
            
            provider = self.providers[provider_id]
            
            # 根据模式匹配文件
            file_ids = []
            for file_info in provider.list_my_files():
                filename = file_info['filename']
                file_id = file_info['file_id']
                
                # 简单的模式匹配
                for pattern in file_patterns:
                    if pattern in filename or pattern == '*':
                        file_ids.append(file_id)
                        break
            
            if not file_ids:
                print(f"✗ 没有找到匹配的文件: {file_patterns}")
                continue
            
            try:
                share_id = provider.create_share(share_name, file_ids, consumer_ids, description)
                shares_created.append({
                    'share_name': share_name,
                    'share_id': share_id,
                    'file_count': len(file_ids),
                    'status': 'success'
                })
                print(f"✓ 共享创建成功: {share_name} ({len(file_ids)} 个文件)")
            except Exception as e:
                shares_created.append({
                    'share_name': share_name,
                    'share_id': None,
                    'status': 'failed',
                    'error': str(e)
                })
                print(f"✗ 共享创建失败: {share_name} - {e}")
        
        return shares_created
    
    def export_report(self, output_file):
        """导出系统报告"""
        stats = self.cloud_services.get_system_stats()
        logs = self.cloud_services.get_access_logs()
        
        report = {
            'generated_at': str(datetime.now()),
            'system_stats': stats,
            'tenants': {
                'providers': list(self.providers.keys()),
                'consumers': list(self.consumers.keys())
            },
            'files': [],
            'shares': [],
            'access_logs': logs
        }
        
        # 收集文件信息
        for tenant_id, provider in self.providers.items():
            for file_info in provider.list_my_files():
                report['files'].append({
                    'tenant_id': tenant_id,
                    **file_info
                })
        
        # 收集共享信息
        for tenant_id, provider in self.providers.items():
            for share_info in provider.list_my_shares():
                report['shares'].append(share_info)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 报告已导出: {output_file}")

def main():
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="批量操作工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 从配置文件初始化
    init_parser = subparsers.add_parser('init', help='从配置文件初始化系统')
    init_parser.add_argument('config_file', help='配置文件路径')
    
    # 批量上传
    upload_parser = subparsers.add_parser('batch-upload', help='从CSV批量上传文件')
    upload_parser.add_argument('tenant_id', help='租户ID')
    upload_parser.add_argument('csv_file', help='CSV文件路径')
    
    # 导出报告
    report_parser = subparsers.add_parser('export-report', help='导出系统报告')
    report_parser.add_argument('output_file', help='输出文件路径')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    batch_ops = BatchOperations()
    
    if args.command == 'init':
        config = batch_ops.load_config(args.config_file)
        batch_ops.batch_create_shares(config)
    
    elif args.command == 'batch-upload':
        batch_ops.batch_upload_from_csv(args.tenant_id, args.csv_file)
    
    elif args.command == 'export-report':
        batch_ops.export_report(args.output_file)

if __name__ == "__main__":
    main()