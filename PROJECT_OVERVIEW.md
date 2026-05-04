# VaultShare - 项目总览

基于 `share.py` 开发的企业级多租户文件共享系统，支持 MinIO 对象存储，提供完整的安全、性能和合规解决方案。

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   租户提供方     │    │   云服务层       │    │   租户消费方     │
│  TenantProvider │◄──►│ CloudServices   │◄──►│ TenantConsumer  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MinIO 对象存储层                              │
│  ┌─────────────┐              ┌─────────────┐                   │
│  │ tenant-data │              │tenant-metadata│                 │
│  │   加密文件   │              │   元数据&权限  │                 │
│  └─────────────┘              └─────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
rk_crypto/
├── 核心模块
│   ├── share.py                    # 原始共享系统
│   ├── minio_multitenant_share.py  # MinIO多租户实现
│   └── mock_multitenant_demo.py    # 模拟演示版本
│
├── 管理工具
│   ├── share_manager.py            # 命令行管理工具
│   ├── batch_operations.py         # 批量操作工具
│   └── setup.sh                    # 快速启动脚本
│
├── 测试和审计
│   ├── performance_test.py         # 性能基准测试
│   └── security_audit.py           # 安全审计工具
│
├── 配置和数据
│   ├── config/
│   │   └── system_config.json      # 系统配置
│   ├── data/
│   │   ├── company_a_files.csv     # 测试数据A
│   │   └── company_b_files.csv     # 测试数据B
│   └── docker-compose.yml          # MinIO容器配置
│
└── 文档
    ├── README.md                   # 详细文档
    ├── requirements.txt            # Python依赖
    └── PROJECT_OVERVIEW.md         # 本文件
```

## 🚀 快速开始

### 1. 环境准备
```bash
# 克隆项目
git clone <repository>
cd rk_crypto

# 安装依赖
pip install -r requirements.txt

# 运行设置脚本
chmod +x setup.sh
./setup.sh
```

### 2. 启动 MinIO (可选)
```bash
# 使用 Docker Compose
docker-compose up -d

# 访问控制台: http://localhost:9001
# 用户名: minioadmin
# 密码: minioadmin
```

### 3. 运行演示
```bash
# 基础演示 (无需MinIO)
python3 mock_multitenant_demo.py

# 完整MinIO演示
python3 minio_multitenant_share.py

# 使用管理工具
python3 share_manager.py demo
```

## 🔧 核心功能

### 安全特性
- **信封加密**: 文件密钥 + 租户主密钥双重保护
- **租户隔离**: 完全独立的密钥空间和存储
- **细粒度权限**: 文件级访问控制
- **审计跟踪**: 完整的操作日志记录

### 存储特性
- **MinIO集成**: 企业级对象存储支持
- **元数据分离**: 数据与权限信息分离存储
- **扩展性**: 支持大规模租户和文件
- **高可用**: 分布式存储架构

### 管理特性
- **命令行工具**: 完整的CLI管理界面
- **批量操作**: CSV导入、批量共享创建
- **性能监控**: 实时性能指标和报告
- **合规检查**: GDPR等合规性验证

## 📊 使用场景

### 1. 企业数据共享
```bash
# 创建提供方租户
python3 share_manager.py create-tenant company_a provider

# 上传敏感文件
python3 share_manager.py upload company_a "财务报告.txt" "Q3营收数据..."

# 创建跨企业共享
python3 share_manager.py create-share company_a financial_data [file_id] company_b
```

### 2. 批量数据迁移
```bash
# 从CSV批量上传
python3 batch_operations.py batch-upload company_a data/company_a_files.csv

# 从配置文件初始化
python3 batch_operations.py init config/system_config.json
```

### 3. 性能测试
```bash
# 运行性能基准测试
python3 performance_test.py

# 查看测试报告
cat reports/performance_report.json
```

### 4. 安全审计
```bash
# 运行安全审计
python3 security_audit.py

# 查看审计报告
cat reports/security_audit_report.json
```

## 🔍 技术细节

### 加密流程
1. **文件上传**: 生成随机文件密钥(FK) → AES-GCM加密文件
2. **密钥包装**: 租户主密钥(TMK)包装FK → 存储wrapped_fk
3. **权限控制**: 云服务层验证权限 → 代理解包FK
4. **文件访问**: 临时获取FK → 解密文件 → 清理密钥

### 存储结构
```
MinIO存储桶:
├── tenant-data/
│   └── {tenant_id}/files/{file_id}.enc
└── tenant-metadata/
    ├── {tenant_id}/metadata/{file_id}.json
    └── shares/{share_id}/grants.json
```

### 权限模型
- **租户级隔离**: 每个租户独立的密钥和存储空间
- **共享级授权**: 基于share_id的访问控制
- **文件级权限**: 细粒度的文件访问管理
- **时间控制**: 支持共享过期和撤销

## 📈 性能指标

基于测试环境的性能数据:
- **文件上传**: ~100 文件/秒 (1KB文件)
- **并发访问**: ~50 访问/秒 (10并发)
- **内存使用**: ~2KB/文件 (元数据)
- **扩展性**: 支持1000+租户

## 🛡️ 安全合规

### 已实现
- ✅ 数据加密 (AES-256-GCM)
- ✅ 访问控制 (基于权限)
- ✅ 审计日志 (完整跟踪)
- ✅ 密钥隔离 (租户独立)

### 待实现
- ⏳ 数据删除权 (GDPR)
- ⏳ 数据可移植性
- ⏳ 同意管理
- ⏳ 密钥轮换

## 🔄 扩展方向

### 短期优化
- 实现密钥轮换机制
- 添加文件版本管理
- 支持共享过期时间
- 增强审计功能

### 长期规划
- 集成企业SSO
- 支持多云存储
- 实现数据血缘追踪
- 添加机器学习分析

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交代码变更
4. 运行测试套件
5. 提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

---

**注意**: 这是一个演示项目，生产环境使用前请进行充分的安全评估和测试。