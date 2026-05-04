# 多租户 MinIO 共享系统

基于原始 `share.py` 的多租户文件共享系统，使用 MinIO 作为对象存储。

## 系统架构

### 核心组件

1. **TenantProvider (租户提供方)**
   - 每个租户有独立的主密钥 (TMK)
   - 负责文件加密上传到 MinIO
   - 创建和管理跨租户共享

2. **MultiTenantCloudServices (云服务层)**
   - 中央权限控制中心
   - 验证共享权限
   - 代理解密文件密钥

3. **TenantConsumer (租户消费方)**
   - 通过云服务层访问共享文件
   - 临时获取解密密钥，用后即焚

4. **MinIOStorage (存储层)**
   - 分离存储加密数据和元数据
   - 支持租户隔离的存储结构

### 安全特性

- **信封加密**: 文件用随机密钥加密，密钥用租户主密钥包装
- **租户隔离**: 每个租户有独立的存储空间和密钥
- **权限控制**: 细粒度的文件级共享权限
- **密钥管理**: 消费方永远无法获得提供方的主密钥

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 MinIO 服务

使用 Docker 启动本地 MinIO:

```bash
docker run -p 9000:9000 -p 9001:9001 \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  minio/minio server /data --console-address ":9001"
```

### 3. 运行演示

```bash
python minio_multitenant_share.py
```

## 存储结构

### MinIO 存储桶

- `tenant-data`: 存储加密文件
- `tenant-metadata`: 存储文件元数据和共享权限

### 目录结构

```
tenant-data/
├── company_a/
│   └── files/
│       ├── uuid1.enc
│       └── uuid2.enc
└── company_b/
    └── files/
        └── uuid3.enc

tenant-metadata/
├── company_a/
│   └── metadata/
│       ├── uuid1.json
│       └── uuid2.json
├── company_b/
│   └── metadata/
│       └── uuid3.json
└── shares/
    ├── share_id_1/
    │   └── grants.json
    └── share_id_2/
        └── grants.json
```

## 使用示例

### 创建租户提供方

```python
storage = MinIOStorage()
provider = TenantProvider("company_a", storage)

# 上传文件
file_id = provider.upload_file("report.txt", b"Confidential data")
```

### 创建跨租户共享

```python
share_id = provider.create_share(
    share_name="financial_data",
    file_ids=[file_id],
    consumer_tenants=["company_b", "company_c"]
)
```

### 消费方访问共享文件

```python
consumer = TenantConsumer("company_b")
consumer.access_shared_file(share_id, file_id, cloud_services)
```

### 撤销共享

```python
provider.revoke_share(share_id)
```

## 演示场景

运行脚本将展示以下场景:

1. 多个租户上传加密文件到 MinIO
2. 创建跨租户文件共享
3. 授权租户访问共享文件
4. 未授权访问被拒绝
5. 共享撤销后访问失败

## 配置选项

### MinIO 连接配置

```python
storage = MinIOStorage(
    endpoint="localhost:9000",
    access_key="minioadmin", 
    secret_key="minioadmin"
)
```

### 生产环境配置

- 使用 HTTPS 连接 (`secure=True`)
- 配置适当的访问凭证
- 设置存储桶策略和生命周期规则
- 启用服务端加密 (SSE)

## 扩展功能

- 文件版本管理
- 共享过期时间
- 审计日志
- 批量文件操作
- 文件预览和搜索