import os
import uuid
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import json
import io

# ==========================================
# 基础密码学工具函数
# ==========================================
def generate_key(): 
    """生成 256-bit AES 密钥"""
    return AESGCM.generate_key(bit_length=256)

def wrap_key(wrapping_key, key_to_wrap):
    """信封加密：包装密钥"""
    nonce = os.urandom(12)
    return nonce, AESGCM(wrapping_key).encrypt(nonce, key_to_wrap, None)

def unwrap_key(wrapping_key, nonce, encrypted_key):
    """拆包密钥"""
    return AESGCM(wrapping_key).decrypt(nonce, encrypted_key, None)

# ==========================================
# 模拟存储层 (无需真实 MinIO)
# ==========================================
class MockStorage:
    def __init__(self):
        self.data_store = {}  # 模拟数据存储
        self.metadata_store = {}  # 模拟元数据存储
        self.share_grants = {}  # 模拟共享授权
        
    def store_encrypted_file(self, tenant_id, file_id, encrypted_data, metadata):
        """存储加密文件和元数据"""
        data_key = f"{tenant_id}/files/{file_id}.enc"
        metadata_key = f"{tenant_id}/metadata/{file_id}.json"
        
        self.data_store[data_key] = encrypted_data
        self.metadata_store[metadata_key] = metadata
        
        print(f"[MockStorage] 存储文件: {data_key}")
        return {"data_key": data_key, "metadata_key": metadata_key}
    
    def get_encrypted_file(self, tenant_id, file_id):
        """获取加密文件和元数据"""
        data_key = f"{tenant_id}/files/{file_id}.enc"
        metadata_key = f"{tenant_id}/metadata/{file_id}.json"
        
        if data_key not in self.data_store or metadata_key not in self.metadata_store:
            raise FileNotFoundError(f"文件不存在: {tenant_id}/{file_id}")
        
        return self.data_store[data_key], self.metadata_store[metadata_key]
    
    def store_share_grant(self, share_id, grant_info):
        """存储共享授权信息"""
        self.share_grants[share_id] = grant_info
        print(f"[MockStorage] 存储共享授权: {share_id}")
    
    def get_share_grant(self, share_id):
        """获取共享授权信息"""
        return self.share_grants.get(share_id)
    
    def list_tenant_files(self, tenant_id):
        """列出租户的所有文件"""
        files = []
        prefix = f"{tenant_id}/metadata/"
        for key, metadata in self.metadata_store.items():
            if key.startswith(prefix):
                files.append(metadata)
        return files
    
    def get_storage_stats(self):
        """获取存储统计信息"""
        total_files = len(self.data_store)
        total_shares = len(self.share_grants)
        tenants = set()
        
        for key in self.data_store.keys():
            tenant_id = key.split('/')[0]
            tenants.add(tenant_id)
        
        return {
            "total_files": total_files,
            "total_shares": total_shares,
            "total_tenants": len(tenants),
            "tenants": list(tenants)
        }

# ==========================================
# 多租户提供方 (增强版)
# ==========================================
class TenantProvider:
    def __init__(self, tenant_id, storage):
        self.tenant_id = tenant_id
        self.storage = storage
        self.tmk = generate_key()
        self.shares = {}
        self.uploaded_files = {}
        
    def upload_file(self, filename, plaintext_data, tags=None):
        """上传并加密文件"""
        file_id = str(uuid.uuid4())
        
        # 生成文件密钥并加密
        fk = generate_key()
        nonce_data = os.urandom(12)
        encrypted_data = AESGCM(fk).encrypt(nonce_data, plaintext_data, None)
        
        # 包装文件密钥
        nonce_fk, wrapped_fk = wrap_key(self.tmk, fk)
        
        # 准备元数据
        metadata = {
            "file_id": file_id,
            "filename": filename,
            "tenant_id": self.tenant_id,
            "wrapped_fk": wrapped_fk.hex(),
            "nonce_fk": nonce_fk.hex(),
            "nonce_data": nonce_data.hex(),
            "upload_time": datetime.now().isoformat(),
            "size": len(plaintext_data),
            "tags": tags or []
        }
        
        # 存储文件
        storage_info = self.storage.store_encrypted_file(
            self.tenant_id, file_id, encrypted_data, metadata
        )
        
        self.uploaded_files[file_id] = metadata
        
        print(f"[租户 {self.tenant_id}] 上传文件 '{filename}' (ID: {file_id})")
        return file_id
    
    def create_share(self, share_name, file_ids, consumer_tenants, description=""):
        """创建跨租户共享"""
        share_id = f"{self.tenant_id}_{share_name}_{str(uuid.uuid4())[:8]}"
        
        # 验证文件存在
        for file_id in file_ids:
            if file_id not in self.uploaded_files:
                raise ValueError(f"文件不存在: {file_id}")
        
        share_info = {
            "share_id": share_id,
            "share_name": share_name,
            "description": description,
            "provider_tenant": self.tenant_id,
            "file_ids": file_ids,
            "consumer_tenants": consumer_tenants,
            "created_time": datetime.now().isoformat(),
            "status": "active",
            "access_count": 0
        }
        
        self.storage.store_share_grant(share_id, share_info)
        self.shares[share_id] = share_info
        
        print(f"[租户 {self.tenant_id}] 创建共享 '{share_name}' -> {consumer_tenants}")
        return share_id
    
    def list_my_files(self):
        """列出我的文件"""
        return list(self.uploaded_files.values())
    
    def list_my_shares(self):
        """列出我的共享"""
        return list(self.shares.values())
    
    def get_share_stats(self, share_id):
        """获取共享统计"""
        if share_id in self.shares:
            return self.storage.get_share_grant(share_id)
        return None

# ==========================================
# 多租户云服务层 (增强版)
# ==========================================
class MultiTenantCloudServices:
    def __init__(self, storage):
        self.storage = storage
        self.tenant_providers = {}
        self.access_logs = []
        
    def register_tenant(self, tenant_id, provider_tmk):
        """注册租户"""
        self.tenant_providers[tenant_id] = provider_tmk
        print(f"[云服务] 注册租户: {tenant_id}")
    
    def authorize_and_decrypt_file(self, consumer_tenant_id, share_id, file_id):
        """授权并解密文件密钥"""
        # 记录访问日志
        access_log = {
            "timestamp": datetime.now().isoformat(),
            "consumer_tenant": consumer_tenant_id,
            "share_id": share_id,
            "file_id": file_id,
            "status": "pending"
        }
        
        try:
            # 验证权限
            share_info = self.storage.get_share_grant(share_id)
            if not share_info:
                raise PermissionError(f"共享不存在: {share_id}")
            
            if share_info["status"] != "active":
                raise PermissionError(f"共享已被撤销: {share_id}")
            
            if consumer_tenant_id not in share_info["consumer_tenants"]:
                raise PermissionError(f"租户 {consumer_tenant_id} 无权访问")
            
            if file_id not in share_info["file_ids"]:
                raise PermissionError(f"文件不在共享范围内")
            
            # 获取文件和解密
            provider_tenant = share_info["provider_tenant"]
            provider_tmk = self.tenant_providers[provider_tenant]
            
            encrypted_data, metadata = self.storage.get_encrypted_file(provider_tenant, file_id)
            
            wrapped_fk = bytes.fromhex(metadata["wrapped_fk"])
            nonce_fk = bytes.fromhex(metadata["nonce_fk"])
            file_key = unwrap_key(provider_tmk, nonce_fk, wrapped_fk)
            
            # 更新访问统计
            share_info["access_count"] += 1
            self.storage.store_share_grant(share_id, share_info)
            
            access_log["status"] = "success"
            print(f"[云服务] 授权成功: {consumer_tenant_id} -> {file_id}")
            
            return file_key, encrypted_data, metadata
            
        except Exception as e:
            access_log["status"] = "failed"
            access_log["error"] = str(e)
            raise
        finally:
            self.access_logs.append(access_log)
    
    def get_access_logs(self, tenant_id=None):
        """获取访问日志"""
        if tenant_id:
            return [log for log in self.access_logs 
                   if log["consumer_tenant"] == tenant_id]
        return self.access_logs
    
    def get_system_stats(self):
        """获取系统统计"""
        storage_stats = self.storage.get_storage_stats()
        
        total_accesses = len(self.access_logs)
        successful_accesses = len([log for log in self.access_logs 
                                 if log["status"] == "success"])
        
        return {
            **storage_stats,
            "total_accesses": total_accesses,
            "successful_accesses": successful_accesses,
            "success_rate": successful_accesses / total_accesses if total_accesses > 0 else 0
        }

# ==========================================
# 多租户消费方 (增强版)
# ==========================================
class TenantConsumer:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self.accessed_files = []
        
    def access_shared_file(self, share_id, file_id, cloud_services):
        """访问共享文件"""
        print(f"\n>>> [租户 {self.tenant_id}] 访问共享文件 {file_id}")
        
        try:
            file_key, encrypted_data, metadata = cloud_services.authorize_and_decrypt_file(
                self.tenant_id, share_id, file_id
            )
            
            # 解密文件
            nonce_data = bytes.fromhex(metadata["nonce_data"])
            decrypted_data = AESGCM(file_key).decrypt(nonce_data, encrypted_data, None)
            
            # 记录访问历史
            access_record = {
                "share_id": share_id,
                "file_id": file_id,
                "filename": metadata["filename"],
                "access_time": datetime.now().isoformat(),
                "file_size": metadata["size"]
            }
            self.accessed_files.append(access_record)
            
            print(f"    ✓ 文件: {metadata['filename']}")
            print(f"    ✓ 内容: {decrypted_data.decode('utf-8')}")
            print(f"    ✓ 大小: {metadata['size']} bytes")
            
            return decrypted_data
            
        except Exception as e:
            print(f"    ✗ 访问失败: {e}")
            return None
    
    def list_accessed_files(self):
        """列出访问过的文件"""
        return self.accessed_files

# ==========================================
# 演示场景 (增强版)
# ==========================================
def run_enhanced_demo():
    print("=== 增强版多租户共享系统演示 ===\n")
    
    # 初始化系统
    storage = MockStorage()
    cloud_services = MultiTenantCloudServices(storage)
    
    # 创建租户
    print("1. 创建租户...")
    provider_a = TenantProvider("company_a", storage)
    provider_b = TenantProvider("company_b", storage)
    consumer_c = TenantConsumer("company_c")
    consumer_d = TenantConsumer("company_d")
    
    # 注册租户
    cloud_services.register_tenant("company_a", provider_a.tmk)
    cloud_services.register_tenant("company_b", provider_b.tmk)
    
    # 上传文件
    print("\n2. 上传文件...")
    file1 = provider_a.upload_file("财务报告.txt", b"Q3营收: 1000万, 利润: 200万", ["财务", "季报"])
    file2 = provider_a.upload_file("用户数据.txt", b"活跃用户: 5万, 增长率: 15%", ["用户", "分析"])
    file3 = provider_b.upload_file("产品路线图.txt", b"AI功能开发, 移动端优化", ["产品", "规划"])
    
    # 创建共享
    print("\n3. 创建共享...")
    share1 = provider_a.create_share("财务数据", [file1], ["company_c"], "Q3财务数据共享")
    share2 = provider_b.create_share("产品信息", [file3], ["company_c", "company_d"], "产品规划共享")
    
    # 访问共享文件
    print("\n4. 访问共享文件...")
    consumer_c.access_shared_file(share1, file1, cloud_services)
    consumer_c.access_shared_file(share2, file3, cloud_services)
    consumer_d.access_shared_file(share2, file3, cloud_services)
    
    # 尝试未授权访问
    print("\n5. 未授权访问测试...")
    consumer_d.access_shared_file(share1, file1, cloud_services)
    
    # 显示统计信息
    print("\n6. 系统统计...")
    stats = cloud_services.get_system_stats()
    print(f"    总文件数: {stats['total_files']}")
    print(f"    总共享数: {stats['total_shares']}")
    print(f"    总租户数: {stats['total_tenants']}")
    print(f"    访问成功率: {stats['success_rate']:.2%}")
    
    # 显示访问历史
    print("\n7. 访问历史...")
    for log in cloud_services.get_access_logs():
        status_icon = "✓" if log["status"] == "success" else "✗"
        print(f"    {status_icon} {log['consumer_tenant']} -> {log['file_id']} ({log['status']})")
    
    print("\n=== 演示完成 ===")

if __name__ == "__main__":
    run_enhanced_demo()