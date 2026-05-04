#!/usr/bin/env python3
"""
系统监控和健康检查工具
实时监控多租户共享系统的运行状态
"""

import time
import psutil
import threading
from datetime import datetime, timedelta
from collections import deque
import json
from mock_multitenant_demo import MockStorage, TenantProvider, MultiTenantCloudServices, TenantConsumer

class SystemMonitor:
    def __init__(self, storage, cloud_services):
        self.storage = storage
        self.cloud_services = cloud_services
        self.metrics_history = deque(maxlen=1000)  # 保留最近1000个数据点
        self.alerts = []
        self.monitoring_active = False
        self.thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'response_time': 1.0,
            'error_rate': 0.05,
            'storage_usage': 90.0
        }
    
    def start_monitoring(self, interval=30):
        """启动系统监控"""
        self.monitoring_active = True
        monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        monitor_thread.daemon = True
        monitor_thread.start()
        print(f"✓ 系统监控已启动，采集间隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止系统监控"""
        self.monitoring_active = False
        print("✓ 系统监控已停止")
    
    def _monitor_loop(self, interval):
        """监控循环"""
        while self.monitoring_active:
            try:
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                self._check_alerts(metrics)
                time.sleep(interval)
            except Exception as e:
                print(f"监控错误: {e}")
                time.sleep(interval)
    
    def _collect_metrics(self):
        """收集系统指标"""
        timestamp = datetime.now()
        
        # 系统资源指标
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 应用指标
        storage_stats = self.storage.get_storage_stats()
        access_logs = self.cloud_services.get_access_logs()
        
        # 计算错误率
        recent_logs = [log for log in access_logs 
                      if datetime.fromisoformat(log['timestamp']) > timestamp - timedelta(minutes=5)]
        
        total_recent = len(recent_logs)
        failed_recent = len([log for log in recent_logs if log['status'] == 'failed'])
        error_rate = failed_recent / total_recent if total_recent > 0 else 0
        
        # 计算平均响应时间 (模拟)
        avg_response_time = 0.1 + (cpu_percent / 100) * 0.5  # 基于CPU使用率模拟
        
        metrics = {
            'timestamp': timestamp.isoformat(),
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'memory_total_gb': memory.total / (1024**3),
                'disk_percent': disk.percent,
                'disk_used_gb': disk.used / (1024**3),
                'disk_total_gb': disk.total / (1024**3)
            },
            'application': {
                'total_files': storage_stats['total_files'],
                'total_shares': storage_stats['total_shares'],
                'total_tenants': storage_stats['total_tenants'],
                'total_accesses': len(access_logs),
                'recent_accesses': total_recent,
                'error_rate': error_rate,
                'avg_response_time': avg_response_time
            }
        }
        
        return metrics
    
    def _check_alerts(self, metrics):
        """检查告警条件"""
        alerts_triggered = []
        
        # CPU使用率告警
        if metrics['system']['cpu_percent'] > self.thresholds['cpu_usage']:
            alerts_triggered.append({
                'type': 'HIGH_CPU_USAGE',
                'severity': 'WARNING',
                'message': f"CPU使用率过高: {metrics['system']['cpu_percent']:.1f}%",
                'value': metrics['system']['cpu_percent'],
                'threshold': self.thresholds['cpu_usage']
            })
        
        # 内存使用率告警
        if metrics['system']['memory_percent'] > self.thresholds['memory_usage']:
            alerts_triggered.append({
                'type': 'HIGH_MEMORY_USAGE',
                'severity': 'WARNING',
                'message': f"内存使用率过高: {metrics['system']['memory_percent']:.1f}%",
                'value': metrics['system']['memory_percent'],
                'threshold': self.thresholds['memory_usage']
            })
        
        # 响应时间告警
        if metrics['application']['avg_response_time'] > self.thresholds['response_time']:
            alerts_triggered.append({
                'type': 'HIGH_RESPONSE_TIME',
                'severity': 'WARNING',
                'message': f"响应时间过长: {metrics['application']['avg_response_time']:.3f}s",
                'value': metrics['application']['avg_response_time'],
                'threshold': self.thresholds['response_time']
            })
        
        # 错误率告警
        if metrics['application']['error_rate'] > self.thresholds['error_rate']:
            alerts_triggered.append({
                'type': 'HIGH_ERROR_RATE',
                'severity': 'CRITICAL',
                'message': f"错误率过高: {metrics['application']['error_rate']:.2%}",
                'value': metrics['application']['error_rate'],
                'threshold': self.thresholds['error_rate']
            })
        
        # 存储空间告警
        if metrics['system']['disk_percent'] > self.thresholds['storage_usage']:
            alerts_triggered.append({
                'type': 'HIGH_STORAGE_USAGE',
                'severity': 'CRITICAL',
                'message': f"存储空间不足: {metrics['system']['disk_percent']:.1f}%",
                'value': metrics['system']['disk_percent'],
                'threshold': self.thresholds['storage_usage']
            })
        
        # 记录新告警
        for alert in alerts_triggered:
            alert['timestamp'] = datetime.now().isoformat()
            self.alerts.append(alert)
            print(f"🚨 [{alert['severity']}] {alert['message']}")
    
    def get_current_status(self):
        """获取当前系统状态"""
        if not self.metrics_history:
            return {"status": "NO_DATA", "message": "暂无监控数据"}
        
        latest_metrics = self.metrics_history[-1]
        
        # 计算健康评分
        health_score = 100
        
        if latest_metrics['system']['cpu_percent'] > 70:
            health_score -= 20
        if latest_metrics['system']['memory_percent'] > 80:
            health_score -= 20
        if latest_metrics['application']['error_rate'] > 0.01:
            health_score -= 30
        if latest_metrics['application']['avg_response_time'] > 0.5:
            health_score -= 15
        
        # 确定状态
        if health_score >= 90:
            status = "HEALTHY"
            status_color = "🟢"
        elif health_score >= 70:
            status = "WARNING"
            status_color = "🟡"
        else:
            status = "CRITICAL"
            status_color = "🔴"
        
        return {
            "status": status,
            "status_color": status_color,
            "health_score": health_score,
            "latest_metrics": latest_metrics,
            "active_alerts": len([a for a in self.alerts[-10:] 
                                if datetime.fromisoformat(a['timestamp']) > 
                                datetime.now() - timedelta(minutes=30)])
        }
    
    def get_performance_trends(self, hours=24):
        """获取性能趋势"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_metrics = [
            m for m in self.metrics_history 
            if datetime.fromisoformat(m['timestamp']) > cutoff_time
        ]
        
        if not recent_metrics:
            return {"message": "暂无足够的历史数据"}
        
        # 计算趋势
        cpu_values = [m['system']['cpu_percent'] for m in recent_metrics]
        memory_values = [m['system']['memory_percent'] for m in recent_metrics]
        response_times = [m['application']['avg_response_time'] for m in recent_metrics]
        error_rates = [m['application']['error_rate'] for m in recent_metrics]
        
        trends = {
            'time_range_hours': hours,
            'data_points': len(recent_metrics),
            'cpu_usage': {
                'avg': sum(cpu_values) / len(cpu_values),
                'min': min(cpu_values),
                'max': max(cpu_values),
                'current': cpu_values[-1] if cpu_values else 0
            },
            'memory_usage': {
                'avg': sum(memory_values) / len(memory_values),
                'min': min(memory_values),
                'max': max(memory_values),
                'current': memory_values[-1] if memory_values else 0
            },
            'response_time': {
                'avg': sum(response_times) / len(response_times),
                'min': min(response_times),
                'max': max(response_times),
                'current': response_times[-1] if response_times else 0
            },
            'error_rate': {
                'avg': sum(error_rates) / len(error_rates),
                'min': min(error_rates),
                'max': max(error_rates),
                'current': error_rates[-1] if error_rates else 0
            }
        }
        
        return trends
    
    def generate_health_report(self, output_file="health_report.json"):
        """生成健康检查报告"""
        status = self.get_current_status()
        trends = self.get_performance_trends()
        
        # 统计告警
        alert_summary = {}
        recent_alerts = [a for a in self.alerts 
                        if datetime.fromisoformat(a['timestamp']) > 
                        datetime.now() - timedelta(hours=24)]
        
        for alert in recent_alerts:
            alert_type = alert['type']
            alert_summary[alert_type] = alert_summary.get(alert_type, 0) + 1
        
        report = {
            'report_timestamp': datetime.now().isoformat(),
            'system_status': status,
            'performance_trends': trends,
            'alert_summary': {
                'total_alerts_24h': len(recent_alerts),
                'alert_types': alert_summary,
                'recent_alerts': recent_alerts[-10:]  # 最近10个告警
            },
            'thresholds': self.thresholds,
            'recommendations': self._generate_health_recommendations(status, trends)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 健康检查报告已生成: {output_file}")
        return report
    
    def _generate_health_recommendations(self, status, trends):
        """生成健康建议"""
        recommendations = []
        
        if status['health_score'] < 70:
            recommendations.append("系统健康状况不佳，建议立即检查系统资源使用情况")
        
        if 'cpu_usage' in trends and trends['cpu_usage']['avg'] > 60:
            recommendations.append("CPU使用率较高，考虑优化应用性能或增加计算资源")
        
        if 'memory_usage' in trends and trends['memory_usage']['avg'] > 70:
            recommendations.append("内存使用率较高，检查是否存在内存泄漏或考虑增加内存")
        
        if 'response_time' in trends and trends['response_time']['avg'] > 0.3:
            recommendations.append("响应时间较长，建议优化数据库查询或增加缓存")
        
        if 'error_rate' in trends and trends['error_rate']['avg'] > 0.01:
            recommendations.append("错误率偏高，检查应用日志并修复相关问题")
        
        if status['active_alerts'] > 5:
            recommendations.append("活跃告警较多，建议优先处理关键告警")
        
        if not recommendations:
            recommendations.append("系统运行状况良好，建议继续保持当前配置")
        
        return recommendations

class HealthChecker:
    def __init__(self, storage, cloud_services):
        self.storage = storage
        self.cloud_services = cloud_services
    
    def run_health_checks(self):
        """运行健康检查"""
        print("=== 系统健康检查 ===\n")
        
        checks = [
            self._check_storage_connectivity,
            self._check_encryption_functionality,
            self._check_access_control,
            self._check_audit_logging,
            self._check_performance_baseline
        ]
        
        results = []
        
        for check in checks:
            try:
                result = check()
                results.append(result)
                status_icon = "✅" if result['status'] == 'PASS' else "❌"
                print(f"{status_icon} {result['name']}: {result['message']}")
            except Exception as e:
                results.append({
                    'name': check.__name__,
                    'status': 'ERROR',
                    'message': f"检查失败: {str(e)}"
                })
                print(f"❌ {check.__name__}: 检查失败 - {str(e)}")
        
        # 计算总体健康状况
        passed_checks = len([r for r in results if r['status'] == 'PASS'])
        total_checks = len(results)
        health_percentage = (passed_checks / total_checks) * 100
        
        print(f"\n=== 健康检查摘要 ===")
        print(f"通过检查: {passed_checks}/{total_checks}")
        print(f"健康度: {health_percentage:.1f}%")
        
        if health_percentage == 100:
            print("🎉 系统健康状况优秀")
        elif health_percentage >= 80:
            print("⚠️  系统基本健康，有少量问题需要关注")
        else:
            print("🚨 系统存在严重问题，需要立即处理")
        
        return results
    
    def _check_storage_connectivity(self):
        """检查存储连接性"""
        try:
            stats = self.storage.get_storage_stats()
            return {
                'name': '存储连接性检查',
                'status': 'PASS',
                'message': f"存储正常，当前有 {stats['total_files']} 个文件"
            }
        except Exception as e:
            return {
                'name': '存储连接性检查',
                'status': 'FAIL',
                'message': f"存储连接失败: {str(e)}"
            }
    
    def _check_encryption_functionality(self):
        """检查加密功能"""
        try:
            # 创建测试租户
            test_provider = TenantProvider("health_check_test", self.storage)
            
            # 测试加密上传
            test_data = b"Health check test data"
            file_id = test_provider.upload_file("health_test.txt", test_data)
            
            # 验证文件已加密存储
            encrypted_data, metadata = self.storage.get_encrypted_file("health_check_test", file_id)
            
            if test_data in encrypted_data:
                return {
                    'name': '加密功能检查',
                    'status': 'FAIL',
                    'message': "数据未正确加密"
                }
            
            return {
                'name': '加密功能检查',
                'status': 'PASS',
                'message': "加密功能正常"
            }
        except Exception as e:
            return {
                'name': '加密功能检查',
                'status': 'FAIL',
                'message': f"加密功能异常: {str(e)}"
            }
    
    def _check_access_control(self):
        """检查访问控制"""
        try:
            # 创建测试环境
            provider = TenantProvider("ac_test_provider", self.storage)
            consumer = TenantConsumer("ac_test_consumer")
            
            self.cloud_services.register_tenant("ac_test_provider", provider.tmk)
            
            # 上传文件但不创建共享
            file_id = provider.upload_file("access_test.txt", b"Access control test")
            
            # 尝试未授权访问
            try:
                consumer.access_shared_file("nonexistent_share", file_id, self.cloud_services)
                return {
                    'name': '访问控制检查',
                    'status': 'FAIL',
                    'message': "未授权访问未被阻止"
                }
            except PermissionError:
                return {
                    'name': '访问控制检查',
                    'status': 'PASS',
                    'message': "访问控制正常工作"
                }
        except Exception as e:
            return {
                'name': '访问控制检查',
                'status': 'FAIL',
                'message': f"访问控制检查异常: {str(e)}"
            }
    
    def _check_audit_logging(self):
        """检查审计日志"""
        try:
            initial_log_count = len(self.cloud_services.access_logs)
            
            # 执行一个操作来生成日志
            provider = TenantProvider("audit_test_provider", self.storage)
            consumer = TenantConsumer("audit_test_consumer")
            
            self.cloud_services.register_tenant("audit_test_provider", provider.tmk)
            
            file_id = provider.upload_file("audit_test.txt", b"Audit test")
            share_id = provider.create_share("audit_share", [file_id], ["audit_test_consumer"])
            
            consumer.access_shared_file(share_id, file_id, self.cloud_services)
            
            final_log_count = len(self.cloud_services.access_logs)
            
            if final_log_count > initial_log_count:
                return {
                    'name': '审计日志检查',
                    'status': 'PASS',
                    'message': f"审计日志正常，新增 {final_log_count - initial_log_count} 条记录"
                }
            else:
                return {
                    'name': '审计日志检查',
                    'status': 'FAIL',
                    'message': "审计日志未正确记录"
                }
        except Exception as e:
            return {
                'name': '审计日志检查',
                'status': 'FAIL',
                'message': f"审计日志检查异常: {str(e)}"
            }
    
    def _check_performance_baseline(self):
        """检查性能基线"""
        try:
            # 简单的性能测试
            provider = TenantProvider("perf_test_provider", self.storage)
            
            start_time = time.time()
            
            # 上传10个小文件
            for i in range(10):
                provider.upload_file(f"perf_test_{i}.txt", b"Performance test data")
            
            upload_time = time.time() - start_time
            
            if upload_time > 5.0:  # 如果上传10个文件超过5秒
                return {
                    'name': '性能基线检查',
                    'status': 'FAIL',
                    'message': f"性能低于基线，上传耗时 {upload_time:.2f}s"
                }
            else:
                return {
                    'name': '性能基线检查',
                    'status': 'PASS',
                    'message': f"性能正常，上传耗时 {upload_time:.2f}s"
                }
        except Exception as e:
            return {
                'name': '性能基线检查',
                'status': 'FAIL',
                'message': f"性能检查异常: {str(e)}"
            }

def main():
    """主函数 - 演示监控和健康检查"""
    print("=== 系统监控和健康检查演示 ===\n")
    
    # 初始化系统
    storage = MockStorage()
    cloud_services = MultiTenantCloudServices(storage)
    
    # 创建一些测试数据
    provider = TenantProvider("demo_provider", storage)
    consumer = TenantConsumer("demo_consumer")
    
    cloud_services.register_tenant("demo_provider", provider.tmk)
    
    file_id = provider.upload_file("demo_file.txt", b"Demo file content")
    share_id = provider.create_share("demo_share", [file_id], ["demo_consumer"])
    
    # 运行健康检查
    health_checker = HealthChecker(storage, cloud_services)
    health_results = health_checker.run_health_checks()
    
    # 启动监控
    monitor = SystemMonitor(storage, cloud_services)
    monitor.start_monitoring(interval=5)  # 5秒间隔用于演示
    
    print(f"\n监控运行中... (按 Ctrl+C 停止)")
    
    try:
        # 模拟一些活动
        for i in range(12):  # 运行1分钟
            time.sleep(5)
            
            # 模拟访问
            consumer.access_shared_file(share_id, file_id, cloud_services)
            
            # 每30秒显示一次状态
            if (i + 1) % 6 == 0:
                status = monitor.get_current_status()
                print(f"\n{status['status_color']} 系统状态: {status['status']} (健康度: {status['health_score']}%)")
    
    except KeyboardInterrupt:
        print(f"\n\n停止监控...")
    
    finally:
        monitor.stop_monitoring()
        
        # 生成报告
        print(f"\n生成监控报告...")
        monitor.generate_health_report("reports/health_report.json")
        
        # 显示趋势
        trends = monitor.get_performance_trends(hours=1)
        if 'cpu_usage' in trends:
            print(f"\n=== 性能趋势 (最近1小时) ===")
            print(f"CPU使用率: 平均 {trends['cpu_usage']['avg']:.1f}%, 当前 {trends['cpu_usage']['current']:.1f}%")
            print(f"内存使用率: 平均 {trends['memory_usage']['avg']:.1f}%, 当前 {trends['memory_usage']['current']:.1f}%")
            print(f"响应时间: 平均 {trends['response_time']['avg']:.3f}s, 当前 {trends['response_time']['current']:.3f}s")
        
        print(f"\n=== 监控演示完成 ===")

if __name__ == "__main__":
    main()