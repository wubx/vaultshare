#!/usr/bin/env python3
"""
多租户共享系统管理工具
提供命令行接口来管理租户、文件和共享
"""

import argparse
import json
import sys
from datetime import datetime
from mock_multitenant_demo import MockStorage, TenantProvider, MultiTenantCloudServices, TenantConsumer

class ShareManager:
    def __init__(self):
        self.storage = MockStorage()
        self.cloud_services = MultiTenantCloudServices(self.storage)
        self.providers = {}
        self.consumers = {}
    
    def create_tenant(self, tenant_id, tenant_type="provider"):
        """创建租户"""
        if tenant_type == "provider":
            provider = TenantProvider(tenant_id, self.storage)
            self.cloud_services.register_tenant(tenant_id, provider.tmk)
            self.providers[tenant_id] = provider
            print(f"✓ 创建提供方租户: {tenant_id}")
        else:
            consumer = TenantConsumer(tenant_id)
            self.consumers[tenant_id] = consumer
            print(f"✓ 创建消费方租户: {tenant_id}")
    
    def upload_file(self, tenant_id, filename, content, tags=None):
        """上传文件"""
        if tenant_id not in self.providers:
            print(f"✗ 租户不存在: {tenant_id}")
            return None
        
        provider = self.providers[tenant_id]
        file_id = provider.upload_file(filename, content.encode('utf-8'), tags)
        print(f"✓ 文件上传成功: {filename} -> {file_id}")
        return file_id
    
    def create_share(self, provider_id, share_name, file_ids, consumer_ids, description=""):
        """创建共享"""
        if provider_id not in self.providers:
            print(f"✗ 提供方租户不存在: {provider_id}")
            return None
        
        provider = self.providers[provider_id]
        try:
            share_id = provider.create_share(share_name, file_ids, consumer_ids, description)
            print(f"✓ 共享创建成功: {share_name} -> {share_id}")
            return share_id
        except Exception as e:
            print(f"✗ 共享创建失败: {e}")
            return None
    
    def access_file(self, consumer_id, share_id, file_id):
        """访问共享文件"""
        if consumer_id not in self.consumers:
            # 自动创建消费者
            self.create_tenant(consumer_id, "consumer")
        
        consumer = self.consumers[consumer_id]
        return consumer.access_shared_file(share_id, file_id, self.cloud_services)
    
    def list_files(self, tenant_id):
        """列出租户文件"""
        if tenant_id in self.providers:
            files = self.providers[tenant_id].list_my_files()
            print(f"\n{tenant_id} 的文件:")
            for file_info in files:
                print(f"  {file_info['file_id']}: {file_info['filename']} ({file_info['size']} bytes)")
        else:
            print(f"✗ 租户不存在: {tenant_id}")
    
    def list_shares(self, tenant_id):
        """列出租户共享"""
        if tenant_id in self.providers:
            shares = self.providers[tenant_id].list_my_shares()
            print(f"\n{tenant_id} 的共享:")
            for share in shares:
                print(f"  {share['share_id']}: {share['share_name']}")
                print(f"    状态: {share['status']}")
                print(f"    消费者: {', '.join(share['consumer_tenants'])}")
                print(f"    访问次数: {share['access_count']}")
        else:
            print(f"✗ 租户不存在: {tenant_id}")
    
    def show_stats(self):
        """显示系统统计"""
        stats = self.cloud_services.get_system_stats()
        print("\n=== 系统统计 ===")
        print(f"总文件数: {stats['total_files']}")
        print(f"总共享数: {stats['total_shares']}")
        print(f"总租户数: {stats['total_tenants']}")
        print(f"总访问次数: {stats['total_accesses']}")
        print(f"成功访问次数: {stats['successful_accesses']}")
        print(f"访问成功率: {stats['success_rate']:.2%}")
        print(f"租户列表: {', '.join(stats['tenants'])}")
    
    def show_access_logs(self, tenant_id=None):
        """显示访问日志"""
        logs = self.cloud_services.get_access_logs(tenant_id)
        print(f"\n=== 访问日志 {'(' + tenant_id + ')' if tenant_id else ''} ===")
        for log in logs:
            status_icon = "✓" if log["status"] == "success" else "✗"
            print(f"{status_icon} {log['timestamp'][:19]} | {log['consumer_tenant']} -> {log['file_id']} | {log['status']}")

def main():
    parser = argparse.ArgumentParser(description="多租户共享系统管理工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 创建租户
    tenant_parser = subparsers.add_parser('create-tenant', help='创建租户')
    tenant_parser.add_argument('tenant_id', help='租户ID')
    tenant_parser.add_argument('--type', choices=['provider', 'consumer'], default='provider', help='租户类型')
    
    # 上传文件
    upload_parser = subparsers.add_parser('upload', help='上传文件')
    upload_parser.add_argument('tenant_id', help='租户ID')
    upload_parser.add_argument('filename', help='文件名')
    upload_parser.add_argument('content', help='文件内容')
    upload_parser.add_argument('--tags', nargs='*', help='文件标签')
    
    # 创建共享
    share_parser = subparsers.add_parser('create-share', help='创建共享')
    share_parser.add_argument('provider_id', help='提供方租户ID')
    share_parser.add_argument('share_name', help='共享名称')
    share_parser.add_argument('file_ids', nargs='+', help='文件ID列表')
    share_parser.add_argument('consumer_ids', nargs='+', help='消费方租户ID列表')
    share_parser.add_argument('--description', default='', help='共享描述')
    
    # 访问文件
    access_parser = subparsers.add_parser('access', help='访问共享文件')
    access_parser.add_argument('consumer_id', help='消费方租户ID')
    access_parser.add_argument('share_id', help='共享ID')
    access_parser.add_argument('file_id', help='文件ID')
    
    # 列出文件
    list_files_parser = subparsers.add_parser('list-files', help='列出租户文件')
    list_files_parser.add_argument('tenant_id', help='租户ID')
    
    # 列出共享
    list_shares_parser = subparsers.add_parser('list-shares', help='列出租户共享')
    list_shares_parser.add_argument('tenant_id', help='租户ID')
    
    # 显示统计
    subparsers.add_parser('stats', help='显示系统统计')
    
    # 显示日志
    logs_parser = subparsers.add_parser('logs', help='显示访问日志')
    logs_parser.add_argument('--tenant', help='指定租户ID')
    
    # 运行演示
    subparsers.add_parser('demo', help='运行演示场景')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = ShareManager()
    
    if args.command == 'create-tenant':
        manager.create_tenant(args.tenant_id, args.type)
    
    elif args.command == 'upload':
        manager.upload_file(args.tenant_id, args.filename, args.content, args.tags)
    
    elif args.command == 'create-share':
        manager.create_share(args.provider_id, args.share_name, args.file_ids, args.consumer_ids, args.description)
    
    elif args.command == 'access':
        manager.access_file(args.consumer_id, args.share_id, args.file_id)
    
    elif args.command == 'list-files':
        manager.list_files(args.tenant_id)
    
    elif args.command == 'list-shares':
        manager.list_shares(args.tenant_id)
    
    elif args.command == 'stats':
        manager.show_stats()
    
    elif args.command == 'logs':
        manager.show_access_logs(args.tenant)
    
    elif args.command == 'demo':
        from mock_multitenant_demo import run_enhanced_demo
        run_enhanced_demo()

if __name__ == "__main__":
    main()