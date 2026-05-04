"""
性能测试和基准测试工具
测试多租户共享系统在不同负载下的性能表现
"""

import time
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from mock_multitenant_demo import MockStorage, TenantProvider, MultiTenantCloudServices, TenantConsumer
import random
import string

class PerformanceTester:
    def __init__(self):
        self.storage = MockStorage()
        self.cloud_services = MultiTenantCloudServices(self.storage)
        self.providers = {}
        self.consumers = {}
        self.test_results = {}
    
    def generate_test_data(self, size_kb=1):
        """生成测试数据"""
        size_bytes = size_kb * 1024
        return ''.join(random.choices(string.ascii_letters + string.digits, k=size_bytes))
    
    def setup_test_environment(self, num_providers=5, num_consumers=10):
        """设置测试环境"""
        print(f"设置测试环境: {num_providers} 个提供方, {num_consumers} 个消费方")
        
        # 创建提供方租户
        for i in range(num_providers):
            tenant_id = f"provider_{i:03d}"
            provider = TenantProvider(tenant_id, self.storage)
            self.cloud_services.register_tenant(tenant_id, provider.tmk)
            self.providers[tenant_id] = provider
        
        # 创建消费方租户
        for i in range(num_consumers):
            tenant_id = f"consumer_{i:03d}"
            consumer = TenantConsumer(tenant_id)
            self.consumers[tenant_id] = consumer
        
        print(f"✓ 环境设置完成")
    
    def test_file_upload_performance(self, num_files=100, file_size_kb=10):
        """测试文件上传性能"""
        print(f"\n=== 文件上传性能测试 ===")
        print(f"文件数量: {num_files}, 文件大小: {file_size_kb}KB")
        
        upload_times = []
        provider = list(self.providers.values())[0]
        
        start_time = time.time()
        
        for i in range(num_files):
            test_data = self.generate_test_data(file_size_kb)
            
            file_start = time.time()
            file_id = provider.upload_file(f"test_file_{i:04d}.txt", test_data.encode('utf-8'))
            file_end = time.time()
            
            upload_times.append(file_end - file_start)
            
            if (i + 1) % 20 == 0:
                print(f"  已上传 {i + 1}/{num_files} 个文件")
        
        total_time = time.time() - start_time
        
        results = {
            'total_files': num_files,
            'file_size_kb': file_size_kb,
            'total_time': total_time,
            'avg_upload_time': statistics.mean(upload_times),
            'min_upload_time': min(upload_times),
            'max_upload_time': max(upload_times),
            'throughput_files_per_sec': num_files / total_time,
            'throughput_mb_per_sec': (num_files * file_size_kb) / (total_time * 1024)
        }
        
        self.test_results['upload_performance'] = results
        
        print(f"✓ 上传完成")
        print(f"  总时间: {total_time:.2f}s")
        print(f"  平均上传时间: {results['avg_upload_time']:.4f}s")
        print(f"  吞吐量: {results['throughput_files_per_sec']:.2f} 文件/秒")
        print(f"  数据吞吐量: {results['throughput_mb_per_sec']:.2f} MB/秒")
        
        return results
    
    def test_concurrent_access(self, num_threads=20, num_accesses_per_thread=10):
        """测试并发访问性能"""
        print(f"\n=== 并发访问性能测试 ===")
        print(f"并发线程: {num_threads}, 每线程访问次数: {num_accesses_per_thread}")
        
        # 准备测试数据
        provider = list(self.providers.values())[0]
        test_files = []
        
        for i in range(5):
            test_data = self.generate_test_data(5)  # 5KB 文件
            file_id = provider.upload_file(f"concurrent_test_{i}.txt", test_data.encode('utf-8'))
            test_files.append(file_id)
        
        # 创建共享
        share_id = provider.create_share(
            "concurrent_test_share",
            test_files,
            list(self.consumers.keys())
        )
        
        access_times = []
        errors = []
        
        def worker_thread(thread_id):
            """工作线程函数"""
            thread_times = []
            thread_errors = []
            
            consumer = list(self.consumers.values())[thread_id % len(self.consumers)]
            
            for i in range(num_accesses_per_thread):
                file_id = random.choice(test_files)
                
                try:
                    start_time = time.time()
                    consumer.access_shared_file(share_id, file_id, self.cloud_services)
                    end_time = time.time()
                    
                    thread_times.append(end_time - start_time)
                except Exception as e:
                    thread_errors.append(str(e))
            
            return thread_times, thread_errors
        
        # 执行并发测试
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(num_threads)]
            
            for future in as_completed(futures):
                thread_times, thread_errors = future.result()
                access_times.extend(thread_times)
                errors.extend(thread_errors)
        
        total_time = time.time() - start_time
        total_accesses = num_threads * num_accesses_per_thread
        successful_accesses = len(access_times)
        
        results = {
            'num_threads': num_threads,
            'total_accesses': total_accesses,
            'successful_accesses': successful_accesses,
            'failed_accesses': len(errors),
            'success_rate': successful_accesses / total_accesses,
            'total_time': total_time,
            'avg_access_time': statistics.mean(access_times) if access_times else 0,
            'throughput_accesses_per_sec': successful_accesses / total_time,
            'errors': errors[:10]  # 只保留前10个错误
        }
        
        self.test_results['concurrent_access'] = results
        
        print(f"✓ 并发测试完成")
        print(f"  总访问次数: {total_accesses}")
        print(f"  成功访问: {successful_accesses}")
        print(f"  成功率: {results['success_rate']:.2%}")
        print(f"  平均访问时间: {results['avg_access_time']:.4f}s")
        print(f"  并发吞吐量: {results['throughput_accesses_per_sec']:.2f} 访问/秒")
        
        return results
    
    def test_scalability(self, max_tenants=100, step=20):
        """测试系统扩展性"""
        print(f"\n=== 系统扩展性测试 ===")
        print(f"最大租户数: {max_tenants}, 步长: {step}")
        
        scalability_results = []
        
        for num_tenants in range(step, max_tenants + 1, step):
            print(f"\n测试 {num_tenants} 个租户...")
            
            # 重置环境
            self.storage = MockStorage()
            self.cloud_services = MultiTenantCloudServices(self.storage)
            self.providers = {}
            self.consumers = {}
            
            # 创建租户
            setup_start = time.time()
            self.setup_test_environment(num_tenants // 2, num_tenants // 2)
            setup_time = time.time() - setup_start
            
            # 测试文件上传
            upload_start = time.time()
            provider = list(self.providers.values())[0]
            test_data = self.generate_test_data(1)  # 1KB 文件
            
            for i in range(10):  # 上传10个文件
                provider.upload_file(f"scale_test_{i}.txt", test_data.encode('utf-8'))
            
            upload_time = time.time() - upload_start
            
            # 测试访问性能
            access_start = time.time()
            stats = self.cloud_services.get_system_stats()
            access_time = time.time() - access_start
            
            result = {
                'num_tenants': num_tenants,
                'setup_time': setup_time,
                'upload_time': upload_time,
                'access_time': access_time,
                'memory_usage_estimate': len(str(self.storage.data_store)) + len(str(self.storage.metadata_store))
            }
            
            scalability_results.append(result)
            
            print(f"  设置时间: {setup_time:.3f}s")
            print(f"  上传时间: {upload_time:.3f}s")
            print(f"  访问时间: {access_time:.3f}s")
        
        self.test_results['scalability'] = scalability_results
        
        print(f"\n✓ 扩展性测试完成")
        return scalability_results
    
    def test_memory_usage(self, num_files=1000, file_size_kb=10):
        """测试内存使用情况"""
        print(f"\n=== 内存使用测试 ===")
        print(f"文件数量: {num_files}, 文件大小: {file_size_kb}KB")
        
        import sys
        
        initial_size = sys.getsizeof(self.storage.data_store) + sys.getsizeof(self.storage.metadata_store)
        
        provider = list(self.providers.values())[0]
        
        memory_snapshots = []
        
        for i in range(0, num_files, 100):
            # 上传100个文件
            for j in range(100):
                if i + j >= num_files:
                    break
                
                test_data = self.generate_test_data(file_size_kb)
                provider.upload_file(f"memory_test_{i+j:04d}.txt", test_data.encode('utf-8'))
            
            # 记录内存使用
            current_size = sys.getsizeof(self.storage.data_store) + sys.getsizeof(self.storage.metadata_store)
            memory_snapshots.append({
                'files_uploaded': min(i + 100, num_files),
                'memory_bytes': current_size,
                'memory_mb': current_size / (1024 * 1024)
            })
            
            print(f"  已上传 {min(i + 100, num_files)} 个文件, 内存使用: {current_size / (1024 * 1024):.2f} MB")
        
        results = {
            'initial_memory': initial_size,
            'final_memory': memory_snapshots[-1]['memory_bytes'],
            'memory_growth': memory_snapshots[-1]['memory_bytes'] - initial_size,
            'memory_per_file': (memory_snapshots[-1]['memory_bytes'] - initial_size) / num_files,
            'snapshots': memory_snapshots
        }
        
        self.test_results['memory_usage'] = results
        
        print(f"✓ 内存测试完成")
        print(f"  初始内存: {initial_size / (1024 * 1024):.2f} MB")
        print(f"  最终内存: {results['final_memory'] / (1024 * 1024):.2f} MB")
        print(f"  平均每文件: {results['memory_per_file'] / 1024:.2f} KB")
        
        return results
    
    def generate_performance_report(self, output_file="performance_report.json"):
        """生成性能测试报告"""
        import json
        from datetime import datetime
        
        report = {
            'test_timestamp': datetime.now().isoformat(),
            'test_environment': {
                'num_providers': len(self.providers),
                'num_consumers': len(self.consumers)
            },
            'test_results': self.test_results,
            'summary': {
                'total_tests': len(self.test_results),
                'test_types': list(self.test_results.keys())
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 性能报告已生成: {output_file}")
        return report

def run_full_performance_test():
    """运行完整的性能测试套件"""
    print("=== 多租户共享系统性能测试套件 ===\n")
    
    tester = PerformanceTester()
    
    # 设置测试环境
    tester.setup_test_environment(num_providers=5, num_consumers=10)
    
    # 运行各项测试
    tester.test_file_upload_performance(num_files=50, file_size_kb=5)
    tester.test_concurrent_access(num_threads=10, num_accesses_per_thread=5)
    tester.test_memory_usage(num_files=200, file_size_kb=5)
    tester.test_scalability(max_tenants=50, step=10)
    
    # 生成报告
    tester.generate_performance_report("reports/performance_report.json")
    
    print("\n=== 性能测试完成 ===")

if __name__ == "__main__":
    run_full_performance_test()