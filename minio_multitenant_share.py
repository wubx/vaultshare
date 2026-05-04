import os
import uuid
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from minio import Minio
from minio.error import S3Error
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
# MinIO 存储层
# ==========================================
class MinIOStorage:
    def __init__(self, endpoint="localhost:9000", access_key="minioadmin", secret_key="minioadmin"):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False  # 开发环境使用 HTTP
        )
        self.data_bucket = "tenant-data"
        self.metadata_bucket = "tenant-metadata"
        self._ensure_buckets()
    
    def _ensure_buckets(self):
        """确保存储桶存在"""
        for bucket in [self.data_bucket, self.metadata_bucket]:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                print(f"[MinIO] 创建存储桶: {bucket}")
    
    def store_encrypted_file(self, tenant_id, file_id, encrypted_data, metadata):
        """存储加密文件和元数据"""
        # 存储加密数据
        data_key = f"{tenant_id}/files/{file_id}.enc"
        self.client.put_object(
            self.data_bucket,
            data_key,
            io.BytesIO(encrypted_data),
            len(encrypted_data)
        )
        
        # 存储元数据
        metadata_key = f"{tenant_id}/metadata/{file_id}.json"
        metadata_json = json.dumps(metadata).encode('utf-8')
        self.client.put_object(
            self.metadata_bucket,
            metadata_key,
            io.BytesIO(metadata_json),
            len(metadata_json)
        )
        
        return {"data_key": data_key, "metadata_key": metadata_key}
    
    def get_encrypted_file(self, tenant_id, file_id):
        """获取加密文件和元数据"""
        try:
            # 获取加密数据
            data_key = f"{tenant_id}/files/{file_id}.enc"
            data_response = self.client.get_object(self.data_bucket, data_key)
            encrypted_data = data_response.read()
            
            # 获取元数据
            metadata_key = f"{tenant_id}/metadata/{file_id}.json"
            metadata_response = self.client.get_object(self.metadata_bucket, metadata_key)
            metadata = json.loads(metadata_response.read().decode('utf-8'))
            
            return encrypted_data, metadata
        except S3Error as e:
            raise FileNotFoundError(f"文件不存在: {tenant_id}/{file_id}")
    
    def store_share_grant(self, share_id, grant_info):
        """存储共享授权信息"""
        grant_key = f"shares/{share_id}/grants.json"
        grant_json = json.dumps(grant_info, indent=2).encode('utf-8')
        self.client.put_object(
            self.metadata_bucket,
            grant_key,
            io.BytesIO(grant_json),
            len(grant_json)
        )
    
    def get_share_grant(self, share_id):
        """获取共享授权信息"""
        try:
            grant_key = f"shares/{share_id}/grants.json"
            response = self.client.get_object(self.metadata_bucket, grant_key)
            return json.loads(response.read().decode('utf-8'))
        except S3Error:
            return None

# ==========================================
# 多租户提供方
# ==========================================
class TenantProvider:
    def __init__(self, tenant_id, storage):
        self.tenant_id = tenant_id
        self.storage = storage
        # 每个租户有自己的主密钥 (TMK)
        self.tmk = generate_key()
        self.shares = {}  # share_id -> share_info
        
    def upload_file(self, filename, plaintext_data):
        """上传并加密文件到 MinIO"""
        file_id = str(uuid.uuid4())
        
        # 1. 生成文件密钥 (FK)
        fk = generate_key()
        
        # 2. 用 FK 加密数据
        nonce_data = os.urandom(12)
        encrypted_data = AESGCM(fk).encrypt(nonce_data, plaintext_data, None)
        
        # 3. 用 TMK 包装 FK
        nonce_fk, wrapped_fk = wrap_key(self.tmk, fk)
        
        # 4. 准备元数据
        metadata = {
            "file_id": file_id,
            "filename": filename,
            "tenant_id": self.tenant_id,
            "wrapped_fk": wrapped_fk.hex(),
            "nonce_fk": nonce_fk.hex(),
            "nonce_data": nonce_data.hex(),
            "upload_time": datetime.now().isoformat(),
            "size": len(plaintext_data)
        }
        
        # 5. 存储到 MinIO
        storage_info = self.storage.store_encrypted_file(
            self.tenant_id, file_id, encrypted_data, metadata
        )
        
        print(f"[租户 {self.tenant_id}] 文件 '{filename}' 已加密上传到 MinIO")
        print(f"  文件ID: {file_id}")
        print(f"  存储路径: {storage_info['data_key']}")
        
        return file_id
    
    def create_share(self, share_name, file_ids, consumer_tenants):
        """创建跨租户共享"""
        share_id = f"{self.tenant_id}_{share_name}_{str(uuid.uuid4())[:8]}"
        
        share_info = {
            "share_id": share_id,
            "share_name": share_name,
            "provider_tenant": self.tenant_id,
            "file_ids": file_ids,
            "consumer_tenants": consumer_tenants,
            "created_time": datetime.now().isoformat(),
            "status": "active"
        }
        
        # 存储共享授权信息到 MinIO
        self.storage.store_share_grant(share_id, share_info)
        self.shares[share_id] = share_info
        
        print(f"[租户 {self.tenant_id}] 创建共享 '{share_name}'")
        print(f"  共享ID: {share_id}")
        print(f"  授权租户: {consumer_tenants}")
        print(f"  共享文件: {file_ids}")
        
        return share_id
    
    def revoke_share(self, share_id):
        """撤销共享"""
        if share_id in self.shares:
            share_info = self.shares[share_id]
            share_info["status"] = "revoked"
            share_info["revoked_time"] = datetime.now().isoformat()
            
            # 更新 MinIO 中的授权信息
            self.storage.store_share_grant(share_id, share_info)
            
            print(f"[租户 {self.tenant_id}] 已撤销共享: {share_id}")
        else:
            print(f"[租户 {self.tenant_id}] 共享不存在: {share_id}")

# ==========================================
# 多租户云服务层 (权限控制中心)
# ==========================================
class MultiTenantCloudServices:
    def __init__(self, storage):
        self.storage = storage
        self.tenant_providers = {}  # tenant_id -> TenantProvider
    
    def register_tenant(self, tenant_id, provider_tmk):
        """注册租户及其主密钥"""
        self.tenant_providers[tenant_id] = provider_tmk
        print(f"[云服务] 注册租户: {tenant_id}")
    
    def authorize_and_decrypt_file(self, consumer_tenant_id, share_id, file_id):
        """授权并解密文件密钥"""
        # 1. 验证共享权限
        share_info = self.storage.get_share_grant(share_id)
        if not share_info:
            raise PermissionError(f"共享不存在: {share_id}")
        
        if share_info["status"] != "active":
            raise PermissionError(f"共享已被撤销: {share_id}")
        
        if consumer_tenant_id not in share_info["consumer_tenants"]:
            raise PermissionError(f"��户 {consumer_tenant_id} 无权访问共享 {share_id}")
        
        if file_id not in share_info["file_ids"]:
            raise PermissionError(f"文件 {file_id} 不在共享范围内")
        
        # 2. 获取提供方租户的主密钥
        provider_tenant = share_info["provider_tenant"]
        if provider_tenant not in self.tenant_providers:
            raise RuntimeError(f"提供方租户 {provider_tenant} 未注册")
        
        provider_tmk = self.tenant_providers[provider_tenant]
        
        # 3. 从 MinIO 获取加密文件和元数据
        encrypted_data, metadata = self.storage.get_encrypted_file(provider_tenant, file_id)
        
        # 4. 解包文件密钥
        wrapped_fk = bytes.fromhex(metadata["wrapped_fk"])
        nonce_fk = bytes.fromhex(metadata["nonce_fk"])
        file_key = unwrap_key(provider_tmk, nonce_fk, wrapped_fk)
        
        print(f"[云服务] 授权通过，为租户 {consumer_tenant_id} 解包文件密钥")
        
        return file_key, encrypted_data, metadata

# ==========================================
# 多租户消费方
# ==========================================
class TenantConsumer:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
    
    def access_shared_file(self, share_id, file_id, cloud_services):
        """访问共享文件"""
        print(f"\n>>> [租户 {self.tenant_id}] 请求访问共享文件")
        print(f"    共享ID: {share_id}")
        print(f"    文件ID: {file_id}")
        
        try:
            # 1. 通过云服务层获取解密密钥
            file_key, encrypted_data, metadata = cloud_services.authorize_and_decrypt_file(
                self.tenant_id, share_id, file_id
            )
            
            # 2. 解密文件内容
            nonce_data = bytes.fromhex(metadata["nonce_data"])
            decrypted_data = AESGCM(file_key).decrypt(nonce_data, encrypted_data, None)
            
            print(f"[租户 {self.tenant_id}] 成功访问文件: {metadata['filename']}")
            print(f"    文件内容: {decrypted_data.decode('utf-8')}")
            print(f"    文件大小: {metadata['size']} bytes")
            print(f"    上传时间: {metadata['upload_time']}")
            
            # 3. 清理内存中的密钥
            file_key = None
            
        except Exception as e:
            print(f"[租户 {self.tenant_id}] 访问失败: {e}")

# ==========================================
# 演示场景
# ==========================================
if __name__ == "__main__":
    print("=== 多租户 MinIO 共享系统演示 ===\n")
    
    # 初始化 MinIO 存储
    print("1. 初始化 MinIO 存储...")
    storage = MinIOStorage()
    
    # 初始化云服务层
    cloud_services = MultiTenantCloudServices(storage)
    
    # 创建租户提供方
    print("\n2. 创建租户提供方...")
    provider_a = TenantProvider("company_a", storage)
    provider_b = TenantProvider("company_b", storage)
    
    # 注册租户到云服务
    cloud_services.register_tenant("company_a", provider_a.tmk)
    cloud_services.register_tenant("company_b", provider_b.tmk)
    
    # 创建消费方租户
    consumer_c = TenantConsumer("company_c")
    consumer_d = TenantConsumer("company_d")
    
    print("\n3. 租户A上传文件...")
    file1_id = provider_a.upload_file("financial_report_q3.txt", b"Company A Q3 Revenue: $10M, Profit: $2M")
    file2_id = provider_a.upload_file("user_analytics.txt", b"Company A Active Users: 50K, Growth: +15%")
    
    print("\n4. 租户B上传文件...")
    file3_id = provider_b.upload_file("product_roadmap.txt", b"Company B Product Roadmap: AI Features, Mobile App")
    
    print("\n5. 租户A创建共享给租户C...")
    share1_id = provider_a.create_share("financial_data", [file1_id], ["company_c"])
    
    print("\n6. 租户B创建共享给租户C和D...")
    share2_id = provider_b.create_share("product_info", [file3_id], ["company_c", "company_d"])
    
    print("\n7. 租户C访问租户A的共享文件...")
    consumer_c.access_shared_file(share1_id, file1_id, cloud_services)
    
    print("\n8. 租户C访问租户B的共享文件...")
    consumer_c.access_shared_file(share2_id, file3_id, cloud_services)
    
    print("\n9. 租户D访问租户B的共享文件...")
    consumer_d.access_shared_file(share2_id, file3_id, cloud_services)
    
    print("\n10. 租户D尝试访问租户A的文件（无权限）...")
    consumer_d.access_shared_file(share1_id, file1_id, cloud_services)
    
    print("\n11. 租户A撤销共享...")
    provider_a.revoke_share(share1_id)
    
    print("\n12. 租户C再次尝试访问被撤销的共享...")
    consumer_c.access_shared_file(share1_id, file1_id, cloud_services)
    
    print("\n=== 演示完成 ===")