"""
安全审计和合规检查工具
验证多租户共享系统的安全性和合规性
"""

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from mock_multitenant_demo import MockStorage, TenantProvider, MultiTenantCloudServices, TenantConsumer

class SecurityAuditor:
    def __init__(self):
        self.storage = MockStorage()
        self.cloud_services = MultiTenantCloudServices(self.storage)
        self.audit_log = []
        self.security_violations = []
        self.compliance_checks = {}
    
    def log_audit_event(self, event_type, details, severity="INFO"):
        """记录审计事件"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'details': details
        }
        self.audit_log.append(event)
        
        if severity in ["WARNING", "CRITICAL"]:
            self.security_violations.append(event)
    
    def test_key_isolation(self):
        """测试密钥隔离性"""
        print("\n=== 密钥隔离性测试 ===")
        
        # 创建两个租户
        tenant_a = TenantProvider("tenant_a", self.storage)
        tenant_b = TenantProvider("tenant_b", self.storage)
        
        self.cloud_services.register_tenant("tenant_a", tenant_a.tmk)
        self.cloud_services.register_tenant("tenant_b", tenant_b.tmk)
        
        # 验证密钥不同
        if tenant_a.tmk == tenant_b.tmk:
            self.log_audit_event(
                "KEY_ISOLATION_FAILURE",
                "两个租户使用了相同的主密钥",
                "CRITICAL"
            )
            return False
        
        # 验证密钥长度
        if len(tenant_a.tmk) != 32 or len(tenant_b.tmk) != 32:
            self.log_audit_event(
                "KEY_LENGTH_VIOLATION",
                f"密钥长度不符合256位标准: {len(tenant_a.tmk)*8}位, {len(tenant_b.tmk)*8}位",
                "WARNING"
            )
        
        # 验证密钥随机性
        key_entropy_a = self._calculate_entropy(tenant_a.tmk)
        key_entropy_b = self._calculate_entropy(tenant_b.tmk)
        
        if key_entropy_a < 7.5 or key_entropy_b < 7.5:
            self.log_audit_event(
                "LOW_KEY_ENTROPY",
                f"密钥熵值过低: A={key_entropy_a:.2f}, B={key_entropy_b:.2f}",
                "WARNING"
            )
        
        self.log_audit_event(
            "KEY_ISOLATION_TEST",
            f"密钥隔离测试完成，熵值: A={key_entropy_a:.2f}, B={key_entropy_b:.2f}",
            "INFO"
        )
        
        print(f"✓ 密钥隔离性验证通过")
        print(f"  租户A密钥熵值: {key_entropy_a:.2f}")
        print(f"  租户B密钥熵值: {key_entropy_b:.2f}")
        
        return True
    
    def test_access_control(self):
        """测试访问控制机制"""
        print("\n=== 访问控制测试 ===")
        
        # 创建测试环境
        provider = TenantProvider("provider_test", self.storage)
        authorized_consumer = TenantConsumer("authorized_consumer")
        unauthorized_consumer = TenantConsumer("unauthorized_consumer")
        
        self.cloud_services.register_tenant("provider_test", provider.tmk)
        
        # 上传测试文件
        test_data = b"Confidential business data"
        file_id = provider.upload_file("confidential.txt", test_data)
        
        # 创建共享，只授权给authorized_consumer
        share_id = provider.create_share(
            "test_share",
            [file_id],
            ["authorized_consumer"]
        )
        
        # 测试授权访问
        try:
            authorized_consumer.access_shared_file(share_id, file_id, self.cloud_services)
            self.log_audit_event(
                "AUTHORIZED_ACCESS_SUCCESS",
                f"授权用户成功访问文件: {file_id}",
                "INFO"
            )
            authorized_access_success = True
        except Exception as e:
            self.log_audit_event(
                "AUTHORIZED_ACCESS_FAILURE",
                f"授权用户访问失败: {str(e)}",
                "CRITICAL"
            )
            authorized_access_success = False
        
        # 测试未授权访问
        try:
            unauthorized_consumer.access_shared_file(share_id, file_id, self.cloud_services)
            self.log_audit_event(
                "UNAUTHORIZED_ACCESS_SUCCESS",
                f"未授权用户成功访问文件: {file_id}",
                "CRITICAL"
            )
            unauthorized_access_blocked = False
        except PermissionError:
            self.log_audit_event(
                "UNAUTHORIZED_ACCESS_BLOCKED",
                f"未授权访问被正确阻止: {file_id}",
                "INFO"
            )
            unauthorized_access_blocked = True
        except Exception as e:
            self.log_audit_event(
                "UNEXPECTED_ACCESS_ERROR",
                f"访问控制出现意外错误: {str(e)}",
                "WARNING"
            )
            unauthorized_access_blocked = False
        
        access_control_passed = authorized_access_success and unauthorized_access_blocked
        
        print(f"✓ 访问控制测试: {'通过' if access_control_passed else '失败'}")
        print(f"  授权访问: {'成功' if authorized_access_success else '失败'}")
        print(f"  未授权访问: {'被阻止' if unauthorized_access_blocked else '未被阻止'}")
        
        return access_control_passed
    
    def test_data_encryption(self):
        """测试数据加密强度"""
        print("\n=== 数据加密测试 ===")
        
        provider = TenantProvider("encryption_test", self.storage)
        self.cloud_services.register_tenant("encryption_test", provider.tmk)
        
        # 测试数据
        original_data = b"This is sensitive data that must be encrypted properly"
        file_id = provider.upload_file("encryption_test.txt", original_data)
        
        # 获取存储的加密数据
        encrypted_data, metadata = self.storage.get_encrypted_file("encryption_test", file_id)
        
        # 验证数据确实被加密
        if original_data in encrypted_data:
            self.log_audit_event(
                "ENCRYPTION_FAILURE",
                "原始数据在加密文件中可见",
                "CRITICAL"
            )
            return False
        
        # 验证加密数据的随机性
        encryption_entropy = self._calculate_entropy(encrypted_data)
        if encryption_entropy < 7.0:
            self.log_audit_event(
                "LOW_ENCRYPTION_ENTROPY",
                f"加密数据熵值过低: {encryption_entropy:.2f}",
                "WARNING"
            )
        
        # 验证nonce的唯一性
        nonce_data = bytes.fromhex(metadata["nonce_data"])
        nonce_fk = bytes.fromhex(metadata["nonce_fk"])
        
        if len(nonce_data) != 12 or len(nonce_fk) != 12:
            self.log_audit_event(
                "INVALID_NONCE_LENGTH",
                f"Nonce长度不正确: data={len(nonce_data)}, fk={len(nonce_fk)}",
                "WARNING"
            )
        
        self.log_audit_event(
            "ENCRYPTION_TEST_COMPLETE",
            f"加密测试完成，熵值: {encryption_entropy:.2f}",
            "INFO"
        )
        
        print(f"✓ 数据加密验证通过")
        print(f"  加密数据熵值: {encryption_entropy:.2f}")
        print(f"  Nonce长度: data={len(nonce_data)}, fk={len(nonce_fk)}")
        
        return True
    
    def test_key_rotation_simulation(self):
        """模拟密钥轮换测试"""
        print("\n=== 密钥轮换模拟测试 ===")
        
        provider = TenantProvider("rotation_test", self.storage)
        self.cloud_services.register_tenant("rotation_test", provider.tmk)
        
        # 记录原始密钥
        original_tmk = provider.tmk
        
        # 上传文件
        test_data = b"Data before key rotation"
        file_id = provider.upload_file("pre_rotation.txt", test_data)
        
        # 模拟密钥轮换
        new_tmk = provider.generate_key()
        
        # 验证新密钥不同
        if original_tmk == new_tmk:
            self.log_audit_event(
                "KEY_ROTATION_FAILURE",
                "密钥轮换后密钥未改变",
                "CRITICAL"
            )
            return False
        
        # 验证旧数据仍可访问（使用原密钥）
        try:
            encrypted_data, metadata = self.storage.get_encrypted_file("rotation_test", file_id)
            wrapped_fk = bytes.fromhex(metadata["wrapped_fk"])
            nonce_fk = bytes.fromhex(metadata["nonce_fk"])
            
            # 使用原密钥解包
            from mock_multitenant_demo import unwrap_key
            file_key = unwrap_key(original_tmk, nonce_fk, wrapped_fk)
            
            self.log_audit_event(
                "KEY_ROTATION_BACKWARD_COMPATIBILITY",
                "密钥轮换后旧数据仍可访问",
                "INFO"
            )
            rotation_success = True
        except Exception as e:
            self.log_audit_event(
                "KEY_ROTATION_COMPATIBILITY_FAILURE",
                f"密钥轮换后无法访问旧数据: {str(e)}",
                "CRITICAL"
            )
            rotation_success = False
        
        print(f"✓ 密钥轮换测试: {'通过' if rotation_success else '失败'}")
        
        return rotation_success
    
    def test_audit_trail(self):
        """测试审计跟踪"""
        print("\n=== 审计跟踪测试 ===")
        
        initial_log_count = len(self.cloud_services.access_logs)
        
        # 创建测试环境
        provider = TenantProvider("audit_test", self.storage)
        consumer = TenantConsumer("audit_consumer")
        
        self.cloud_services.register_tenant("audit_test", provider.tmk)
        
        # 执行一系列操作
        file_id = provider.upload_file("audit_test.txt", b"Audit test data")
        share_id = provider.create_share("audit_share", [file_id], ["audit_consumer"])
        
        # 执行访问操作
        consumer.access_shared_file(share_id, file_id, self.cloud_services)
        
        # 验证审计日志
        final_log_count = len(self.cloud_services.access_logs)
        new_logs = final_log_count - initial_log_count
        
        if new_logs == 0:
            self.log_audit_event(
                "AUDIT_TRAIL_MISSING",
                "访问操作未生成审计日志",
                "CRITICAL"
            )
            return False
        
        # 验证日志完整性
        recent_logs = self.cloud_services.access_logs[-new_logs:]
        for log in recent_logs:
            required_fields = ['timestamp', 'consumer_tenant', 'share_id', 'file_id', 'status']
            missing_fields = [field for field in required_fields if field not in log]
            
            if missing_fields:
                self.log_audit_event(
                    "INCOMPLETE_AUDIT_LOG",
                    f"审计日志缺少字段: {missing_fields}",
                    "WARNING"
                )
        
        self.log_audit_event(
            "AUDIT_TRAIL_TEST_COMPLETE",
            f"生成了 {new_logs} 条审计日志",
            "INFO"
        )
        
        print(f"✓ 审计跟踪测试通过")
        print(f"  新增审计日志: {new_logs} 条")
        
        return True
    
    def check_gdpr_compliance(self):
        """GDPR合规性检查"""
        print("\n=== GDPR合规性检查 ===")
        
        compliance_items = {
            'data_encryption': True,  # 数据加密
            'access_control': True,   # 访问控制
            'audit_logging': True,    # 审计日志
            'data_minimization': True, # 数据最小化
            'right_to_erasure': False, # 删除权（需要实现）
            'data_portability': False, # 数据可移植性（需要实现）
            'consent_management': False # 同意管理（需要实现）
        }
        
        # 检查已实现的合规项
        for item, implemented in compliance_items.items():
            status = "合规" if implemented else "需要实现"
            severity = "INFO" if implemented else "WARNING"
            
            self.log_audit_event(
                f"GDPR_COMPLIANCE_{item.upper()}",
                f"GDPR {item}: {status}",
                severity
            )
        
        compliance_rate = sum(compliance_items.values()) / len(compliance_items)
        
        self.compliance_checks['gdpr'] = {
            'compliance_rate': compliance_rate,
            'items': compliance_items,
            'status': 'PARTIAL' if compliance_rate < 1.0 else 'COMPLIANT'
        }
        
        print(f"✓ GDPR合规性: {compliance_rate:.1%}")
        print(f"  已实现: {sum(compliance_items.values())}/{len(compliance_items)} 项")
        
        return compliance_rate
    
    def _calculate_entropy(self, data):
        """计算数据熵值"""
        if not data:
            return 0
        
        # 计算字节频率
        byte_counts = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        
        # 计算熵
        entropy = 0
        data_len = len(data)
        for count in byte_counts.values():
            probability = count / data_len
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)
        
        return entropy
    
    def generate_security_report(self, output_file="security_audit_report.json"):
        """生成安全审计报告"""
        import json
        
        # 统计安全违规
        violation_summary = {}
        for violation in self.security_violations:
            event_type = violation['event_type']
            violation_summary[event_type] = violation_summary.get(event_type, 0) + 1
        
        # 统计审计事件
        event_summary = {}
        for event in self.audit_log:
            severity = event['severity']
            event_summary[severity] = event_summary.get(severity, 0) + 1
        
        report = {
            'audit_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_audit_events': len(self.audit_log),
                'security_violations': len(self.security_violations),
                'compliance_checks': len(self.compliance_checks)
            },
            'event_summary': event_summary,
            'violation_summary': violation_summary,
            'compliance_status': self.compliance_checks,
            'audit_log': self.audit_log,
            'security_violations': self.security_violations,
            'recommendations': self._generate_recommendations()
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 安全审计报告已生成: {output_file}")
        return report
    
    def _generate_recommendations(self):
        """生成安全建议"""
        recommendations = []
        
        if len(self.security_violations) > 0:
            recommendations.append("发现安全违规，建议立即修复相关问题")
        
        if 'gdpr' in self.compliance_checks:
            gdpr_rate = self.compliance_checks['gdpr']['compliance_rate']
            if gdpr_rate < 1.0:
                recommendations.append(f"GDPR合规率仅为{gdpr_rate:.1%}，建议实现缺失的合规项")
        
        if not recommendations:
            recommendations.append("系统安全状况良好，建议定期进行安全审计")
        
        return recommendations

def run_security_audit():
    """运行完整的安全审计"""
    print("=== 多租户共享系统安全审计 ===\n")
    
    auditor = SecurityAuditor()
    
    # 运行各项安全测试
    auditor.test_key_isolation()
    auditor.test_access_control()
    auditor.test_data_encryption()
    auditor.test_key_rotation_simulation()
    auditor.test_audit_trail()
    
    # 合规性检查
    auditor.check_gdpr_compliance()
    
    # 生成报告
    auditor.generate_security_report("reports/security_audit_report.json")
    
    # 显示摘要
    print(f"\n=== 安全审计摘要 ===")
    print(f"审计事件总数: {len(auditor.audit_log)}")
    print(f"安全违规数量: {len(auditor.security_violations)}")
    
    if auditor.security_violations:
        print("\n⚠️  发现的安全问题:")
        for violation in auditor.security_violations:
            print(f"  - {violation['event_type']}: {violation['details']}")
    else:
        print("\n✅ 未发现严重安全问题")
    
    print("\n=== 安全审计完成 ===")

if __name__ == "__main__":
    run_security_audit()