import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

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
# 角色 1：Provider (数据提供方)
# ==========================================
class ProviderAccount:
    def __init__(self):
        # 提供方拥有自己的表主密钥 (TMK)
        self.tmk = generate_key() 

    def encrypt_and_store(self, plaintext_data):
        """模拟将数据加密并存入共享存储 (如 S3)"""
        # 1. 生成一次性的底层文件密钥 (FK)
        fk = generate_key()
        
        # 2. 用 FK 加密真实数据
        nonce_data = os.urandom(12)
        encrypted_data = AESGCM(fk).encrypt(nonce_data, plaintext_data, None)
        
        # 3. 用自己的 TMK 包装 (加密) FK
        nonce_fk, wrapped_fk = wrap_key(self.tmk, fk)
        
        # 存入 S3 的只有密文和被包裹的密钥（任何人拿到这段数据都没用）
        return {
            "encrypted_data": encrypted_data,
            "nonce_data": nonce_data,
            "wrapped_fk": wrapped_fk,
            "nonce_fk": nonce_fk
        }

# ==========================================
# 角色 2：Cloud Services (全知全能的云服务层)
# ==========================================
class CloudServicesLayer:
    def __init__(self, provider_tmk):
        # 云服务层全托管，所以它拥有访问 Provider TMK 的能力
        self.provider_tmk = provider_tmk 
        self.share_grants = set() # 记录谁有权限访问 (元数据)

    def create_share(self, consumer_name):
        """Provider 执行 GRANT 授权"""
        self.share_grants.add(consumer_name)
        print(f"[云服务层] 元数据更新：已授权 {consumer_name} 访问共享数据。")

    def drop_share(self, consumer_name):
        """Provider 执行 REVOKE 撤销授权"""
        self.share_grants.discard(consumer_name)
        print(f"[云服务层] 元数据更新：已撤销 {consumer_name} 的访问权限。")

    def request_file_key(self, consumer_name, wrapped_fk, nonce_fk):
        """Consumer 发起查询时，云服务层负责鉴权并下发密钥"""
        if consumer_name not in self.share_grants:
            raise PermissionError(f"云服务层拦截：{consumer_name} 没有读取该 Share 的权限！")
        
        # 鉴权通过！云服务层代表 Provider 拆开 FK
        print(f"[云服务层] 鉴权通过。正在解包底层文件密钥 (FK) 并通过安全通道下发给 {consumer_name} 的计算节点...")
        return unwrap_key(self.provider_tmk, nonce_fk, wrapped_fk)

# ==========================================
# 角色 3：Consumer (数据消费方)
# ==========================================
class ConsumerAccount:
    def __init__(self, name):
        self.name = name

    def execute_query(self, s3_storage, cloud_services):
        print(f"\n>>> [{self.name}] 正在启动 Virtual Warehouse 执行 SELECT 查询...")
        try:
            # 1. 计算节点向云服务层申请这一批数据的文件密钥 (FK)
            # 注意：消费者永远拿不到 Provider 的 TMK，只能按需索取 FK
            memory_fk = cloud_services.request_file_key(
                self.name, 
                s3_storage["wrapped_fk"], 
                s3_storage["nonce_fk"]
            )
            
            # 2. 在计算节点的内存中解密数据
            decrypted_data = AESGCM(memory_fk).decrypt(
                s3_storage["nonce_data"], 
                s3_storage["encrypted_data"], 
                None
            )
            print(f"[{self.name}] 查询成功！获得明文数据: '{decrypted_data.decode('utf-8')}'")
            
            # 3. 查询结束，计算节点立即清空内存中的密钥
            memory_fk = None 
            
        except Exception as e:
            print(f"[{self.name}] 查询失败: {e}")

# ==========================================
# 剧情演示
# ==========================================
if __name__ == "__main__":
    print("=== 初始化 Snowflake 环境 ===")
    provider = ProviderAccount()
    cloud_services = CloudServicesLayer(provider.tmk)
    
    consumer_a = ConsumerAccount("消费者A")
    consumer_b = ConsumerAccount("黑客B")

    print("\n=== 1. Provider 写入数据到底层存储 ===")
    # 数据加密后变成一堆乱码，存在 S3 上
    s3_storage_mock = provider.encrypt_and_store(b"Q3 Financial Report: Revenue +50%")
    print("数据已完成信封加密并安全存放于 S3。")

    print("\n=== 2. Provider 创建 Share 给消费者A ===")
    cloud_services.create_share("消费者A")

    print("\n=== 3. 消费者A 发起查询 ===")
    consumer_a.execute_query(s3_storage_mock, cloud_services)

    print("\n=== 4. 未经授权的 黑客B 尝试发起查询 ===")
    consumer_b.execute_query(s3_storage_mock, cloud_services)

    print("\n=== 5. Provider 决定停止共享 (Drop Share) ===")
    # 注意：这里仅仅是改了云服务层的一个状态，完全不用去动 S3 里庞大的数据
    cloud_services.drop_share("消费者A")

    print("\n=== 6. 消费者A 再次发起查询 ===")
    consumer_a.execute_query(s3_storage_mock, cloud_services)
