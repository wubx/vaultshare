import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def generate_key():
    """生成 256-bit (32 bytes) 的 AES 主密钥"""
    return AESGCM.generate_key(bit_length=256)

def wrap_key(wrapping_key, key_to_wrap):
    """
    密钥包装（信封加密）：使用上层密钥加密下层密钥
    """
    aesgcm = AESGCM(wrapping_key)
    nonce = os.urandom(12) # AES-GCM 需要一个唯一的 nonce (随机数)
    encrypted_key = aesgcm.encrypt(nonce, key_to_wrap, None)
    return nonce, encrypted_key

def unwrap_key(wrapping_key, nonce, encrypted_key):
    """
    密钥拆包：使用上层密钥解密出下层密钥
    """
    aesgcm = AESGCM(wrapping_key)
    return aesgcm.decrypt(nonce, encrypted_key, None)

# ==========================================
# 1. 密钥生成阶段 (初始化)
# ==========================================
print("--- 1. 初始化密钥层级 ---")
root_key = generate_key()           # 根密钥 (RK)
account_master_key = generate_key() # 账户主密钥 (AMK)
table_master_key = generate_key()   # 表主密钥 (TMK)
file_key = generate_key()           # 文件密钥 (FK)
print("所有密钥已生成完毕 (现实中存储在硬件安全模块 HSM 或密钥管理服务中)。\n")

# ==========================================
# 2. 密钥包装阶段 (自上而下)
# ==========================================
# 层层嵌套：RK -> AMK -> TMK -> FK
print("--- 2. 执行信封加密 (Key Wrapping) ---")
nonce_amk, enc_amk = wrap_key(root_key, account_master_key)
nonce_tmk, enc_tmk = wrap_key(account_master_key, table_master_key)
nonce_fk, enc_fk   = wrap_key(table_master_key, file_key)
print("密钥已完成层层包装！\n")

# ==========================================
# 3. 数据加密阶段 (仅使用最底层的文件密钥)
# ==========================================
print("--- 3. 写入并加密真实业务数据 ---")
data_to_encrypt = b"Hello Snowflake! This is top secret payload."
print(f"原始数据: {data_to_encrypt.decode('utf-8')}")

aesgcm_file = AESGCM(file_key)
nonce_data = os.urandom(12)
encrypted_data = aesgcm_file.encrypt(nonce_data, data_to_encrypt, None)
print(f"存入磁盘的密文 (Hex): {encrypted_data.hex()}\n")

# ==========================================
# 4. 数据读取与解密阶段 (自上而下解锁)
# ==========================================
print("--- 4. 读取数据并自上而下解密 ---")
# 1. 拿 Root Key 解开 AMK
decrypted_amk = unwrap_key(root_key, nonce_amk, enc_amk)
# 2. 拿解开的 AMK 解开 TMK
decrypted_tmk = unwrap_key(decrypted_amk, nonce_tmk, enc_tmk)
# 3. 拿解开的 TMK 解开 FK
decrypted_fk = unwrap_key(decrypted_tmk, nonce_fk, enc_fk)

# 4. 最后拿 FK 解开真实数据
aesgcm_file_dec = AESGCM(decrypted_fk)
decrypted_data = aesgcm_file_dec.decrypt(nonce_data, encrypted_data, None)

print(f"最终解密数据: {decrypted_data.decode('utf-8')}")
