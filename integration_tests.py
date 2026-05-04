#!/usr/bin/env python3
"""
集成测试套件 - 端到端测试多租户共享系统
"""

import unittest
import tempfile
import shutil
import os
from datetime import datetime
from mock_multitenant_demo import MockStorage, TenantProvider, MultiTenantCloudServices, TenantConsumer

class TestMultiTenantSystem(unittest.TestCase):
    """多租户系统集成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.storage = MockStorage()
        self.cloud_services = MultiTenantCloudServices(self.storage)
        self.test_data_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.test_data_dir, ignore_errors=True)
    
    def test_basic_file_sharing_workflow(self):
        """测试基本文件共享流程"""
        # 1. 创建租户
        provider = TenantProvider("test_provider", self.storage)
        consumer = TenantConsumer("test_consumer")
        
        self.cloud_services.register_tenant("test_provider", provider.tmk)
        
        # 2. 上传文件
        test_content = b"Test file content for sharing"
        file_id = provider.upload_file("test_file.txt", test_content)
        
        self.assertIsNotNone(file_id)
        self.assertIn(file_id, provider.uploaded_files)
        
        # 3. 创建共享
        share_id = provider.create_share(
            "test_share", 
            [file_id], 
            ["test_consumer"],
            "Test file sharing"
        )
        
        self.assertIsNotNone(share_id)
        self.assertIn(share_id, provider.shares)
        
        # 4. 消费者访问文件
        decrypted_data = consumer.access_shared_file(share_id, file_id, self.cloud_services)
        
        self.assertEqual(decrypted_data, test_content)
        
        # 5. 验证审计日志
        logs = self.cloud_services.get_access_logs()
        self.assertGreater(len(logs), 0)
        
        latest_log = logs[-1]
        self.assertEqual(latest_log['consumer_tenant'], "test_consumer")
        self.assertEqual(latest_log['file_id'], file_id)
        self.assertEqual(latest_log['status'], 'success')
    
    def test_access_control_enforcement(self):
        """测试访问控制执行"""
        # 创建提供方和两个消费方
        provider = TenantProvider("access_provider", self.storage)
        authorized_consumer = TenantConsumer("authorized_user")
        unauthorized_consumer = TenantConsumer("unauthorized_user")
        
        self.cloud_services.register_tenant("access_provider", provider.tmk)
        
        # 上传文件
        file_id = provider.upload_file("restricted_file.txt", b"Restricted content")
        
        # 只授权给一个消费者
        share_id = provider.create_share(
            "restricted_share",
            [file_id],
            ["authorized_user"]
        )
        
        # 授权用户应该能访问
        decrypted_data = authorized_consumer.access_shared_file(
            share_id, file_id, self.cloud_services
        )
        self.assertEqual(decrypted_data, b"Restricted content")
        
        # 未授权用户应该被拒绝
        with self.assertRaises(PermissionError):
            unauthorized_consumer.access_shared_file(
                share_id, file_id, self.cloud_services
            )
    
    def test_multi_tenant_isolation(self):
        """测试多租户隔离"""
        # 创建两个提供方租户
        provider_a = TenantProvider("tenant_a", self.storage)
        provider_b = TenantProvider("tenant_b", self.storage)
        
        self.cloud_services.register_tenant("tenant_a", provider_a.tmk)
        self.cloud_services.register_tenant("tenant_b", provider_b.tmk)
        
        # 验证密钥隔离
        self.assertNotEqual(provider_a.tmk, provider_b.tmk)
        
        # 各自上传文件
        file_a = provider_a.upload_file("file_a.txt", b"Content from tenant A")
        file_b = provider_b.upload_file("file_b.txt", b"Content from tenant B")
        
        # 验证文件隔离 - 租户A不能直接访问租户B的文件
        with self.assertRaises(FileNotFoundError):
            self.storage.get_encrypted_file("tenant_a", file_b)
        
        with self.assertRaises(FileNotFoundError):
            self.storage.get_encrypted_file("tenant_b", file_a)
    
    def test_share_lifecycle_management(self):
        """测试共享生命周期管理"""
        provider = TenantProvider("lifecycle_provider", self.storage)
        consumer = TenantConsumer("lifecycle_consumer")
        
        self.cloud_services.register_tenant("lifecycle_provider", provider.tmk)
        
        # 上传文件
        file_id = provider.upload_file("lifecycle_test.txt", b"Lifecycle test content")
        
        # 创建共享
        share_id = provider.create_share(
            "lifecycle_share",
            [file_id],
            ["lifecycle_consumer"]
        )
        
        # 验证共享处于活跃状态
        share_info = self.storage.get_share_grant(share_id)
        self.assertEqual(share_info['status'], 'active')
        
        # 消费者可以访问
        decrypted_data = consumer.access_shared_file(share_id, file_id, self.cloud_services)
        self.assertEqual(decrypted_data, b"Lifecycle test content")
        
        # 撤销共享
        provider.revoke_share(share_id)
        
        # 验证共享状态已更新
        updated_share_info = self.storage.get_share_grant(share_id)
        self.assertEqual(updated_share_info['status'], 'revoked')
        
        # 消费者不能再访问
        with self.assertRaises(PermissionError):
            consumer.access_shared_file(share_id, file_id, self.cloud_services)
    
    def test_batch_operations(self):
        """测试批量操作"""
        provider = TenantProvider("batch_provider", self.storage)
        self.cloud_services.register_tenant("batch_provider", provider.tmk)
        
        # 批量上传文件
        file_ids = []
        for i in range(10):
            content = f"Batch file {i} content".encode('utf-8')
            file_id = provider.upload_file(f"batch_file_{i}.txt", content)
            file_ids.append(file_id)
        
        # 验证所有文件都已上传
        self.assertEqual(len(file_ids), 10)
        for file_id in file_ids:
            self.assertIn(file_id, provider.uploaded_files)
        
        # 创建批量共享
        share_id = provider.create_share(
            "batch_share",
            file_ids,
            ["batch_consumer_1", "batch_consumer_2"]
        )
        
        # 验证共享包含所有文件
        share_info = self.storage.get_share_grant(share_id)
        self.assertEqual(len(share_info['file_ids']), 10)
        self.assertEqual(set(share_info['file_ids']), set(file_ids))
    
    def test_concurrent_access_safety(self):
        """测试并发访问安全性"""
        import threading
        import time
        
        provider = TenantProvider("concurrent_provider", self.storage)
        self.cloud_services.register_tenant("concurrent_provider", provider.tmk)
        
        # 上传测试文件
        file_id = provider.upload_file("concurrent_test.txt", b"Concurrent access test")
        share_id = provider.create_share("concurrent_share", [file_id], ["concurrent_consumer"])
        
        # 并发访问测试
        results = []
        errors = []
        
        def access_worker():
            try:
                consumer = TenantConsumer("concurrent_consumer")
                data = consumer.access_shared_file(share_id, file_id, self.cloud_services)
                results.append(data)
            except Exception as e:
                errors.append(str(e))
        
        # 启动多个并发线程
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=access_worker)
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证结果
        self.assertEqual(len(errors), 0, f"并发访问出现错误: {errors}")
        self.assertEqual(len(results), 5)
        
        # 所有结果应该相同
        for result in results:
            self.assertEqual(result, b"Concurrent access test")
    
    def test_error_handling_and_recovery(self):
        """测试错误处理和恢复"""
        provider = TenantProvider("error_provider", self.storage)
        consumer = TenantConsumer("error_consumer")
        
        self.cloud_services.register_tenant("error_provider", provider.tmk)
        
        # 测试访问不存在的共享
        with self.assertRaises(PermissionError):
            consumer.access_shared_file("nonexistent_share", "nonexistent_file", self.cloud_services)
        
        # 测试访问不存在的文件
        file_id = provider.upload_file("test_file.txt", b"Test content")
        share_id = provider.create_share("test_share", [file_id], ["error_consumer"])
        
        with self.assertRaises(PermissionError):
            consumer.access_shared_file(share_id, "nonexistent_file", self.cloud_services)
        
        # 测试未注册租户的密钥访问
        unregistered_provider = TenantProvider("unregistered", self.storage)
        unregistered_file = unregistered_provider.upload_file("unregistered.txt", b"Unregistered content")
        
        # 尝试通过云服务访问未注册租户的文件应该失败
        with self.assertRaises(RuntimeError):
            # 手动构造共享信息来测试
            fake_share_info = {
                "share_id": "fake_share",
                "provider_tenant": "unregistered",
                "file_ids": [unregistered_file],
                "consumer_tenants": ["error_consumer"],
                "status": "active"
            }
            self.storage.store_share_grant("fake_share", fake_share_info)
            consumer.access_shared_file("fake_share", unregistered_file, self.cloud_services)

class TestSystemIntegration(unittest.TestCase):
    """系统集成测试"""
    
    def setUp(self):
        self.storage = MockStorage()
        self.cloud_services = MultiTenantCloudServices(self.storage)
    
    def test_system_statistics_accuracy(self):
        """测试系统统计准确性"""
        # 初始状态
        initial_stats = self.storage.get_storage_stats()
        self.assertEqual(initial_stats['total_files'], 0)
        self.assertEqual(initial_stats['total_shares'], 0)
        
        # 创建租户和文件
        provider = TenantProvider("stats_provider", self.storage)
        self.cloud_services.register_tenant("stats_provider", provider.tmk)
        
        # 上传文件
        for i in range(3):
            provider.upload_file(f"stats_file_{i}.txt", f"Content {i}".encode())
        
        # 创建共享
        files = list(provider.uploaded_files.keys())
        provider.create_share("stats_share", files, ["stats_consumer"])
        
        # 验证统计
        final_stats = self.storage.get_storage_stats()
        self.assertEqual(final_stats['total_files'], 3)
        self.assertEqual(final_stats['total_shares'], 1)
        self.assertEqual(final_stats['total_tenants'], 1)
    
    def test_audit_log_completeness(self):
        """测试审计日志完整性"""
        provider = TenantProvider("audit_provider", self.storage)
        consumer = TenantConsumer("audit_consumer")
        
        self.cloud_services.register_tenant("audit_provider", provider.tmk)
        
        initial_log_count = len(self.cloud_services.access_logs)
        
        # 执行一系列操作
        file_id = provider.upload_file("audit_file.txt", b"Audit test content")
        share_id = provider.create_share("audit_share", [file_id], ["audit_consumer"])
        
        # 成功访问
        consumer.access_shared_file(share_id, file_id, self.cloud_services)
        
        # 失败访问
        try:
            consumer.access_shared_file("nonexistent_share", file_id, self.cloud_services)
        except PermissionError:
            pass
        
        # 验证日志记录
        final_logs = self.cloud_services.access_logs
        new_logs = final_logs[initial_log_count:]
        
        self.assertEqual(len(new_logs), 2)  # 一次成功，一次失败
        
        # 验证成功日志
        success_log = new_logs[0]
        self.assertEqual(success_log['status'], 'success')
        self.assertEqual(success_log['consumer_tenant'], 'audit_consumer')
        
        # 验证失败日志
        failure_log = new_logs[1]
        self.assertEqual(failure_log['status'], 'failed')
        self.assertIn('error', failure_log)

def run_integration_tests():
    """运行集成测试套件"""
    print("=== 多租户共享系统集成测试 ===\n")
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestMultiTenantSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 生成测试报告
    generate_test_report(result)
    
    return result.wasSuccessful()

def generate_test_report(test_result):
    """生成测试报告"""
    import json
    
    report = {
        'test_timestamp': datetime.now().isoformat(),
        'summary': {
            'tests_run': test_result.testsRun,
            'failures': len(test_result.failures),
            'errors': len(test_result.errors),
            'success_rate': (test_result.testsRun - len(test_result.failures) - len(test_result.errors)) / test_result.testsRun if test_result.testsRun > 0 else 0
        },
        'failures': [
            {
                'test': str(test),
                'traceback': traceback
            }
            for test, traceback in test_result.failures
        ],
        'errors': [
            {
                'test': str(test),
                'traceback': traceback
            }
            for test, traceback in test_result.errors
        ]
    }
    
    # 确保reports目录存在
    os.makedirs('reports', exist_ok=True)
    
    with open('reports/integration_test_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== 测试报告摘要 ===")
    print(f"总测试数: {report['summary']['tests_run']}")
    print(f"成功率: {report['summary']['success_rate']:.1%}")
    print(f"失败数: {report['summary']['failures']}")
    print(f"错误数: {report['summary']['errors']}")
    
    if report['summary']['failures'] > 0 or report['summary']['errors'] > 0:
        print(f"\n⚠️  测试报告已保存: reports/integration_test_report.json")
    else:
        print(f"\n✅ 所有测试通过！")

if __name__ == "__main__":
    success = run_integration_tests()
    exit(0 if success else 1)