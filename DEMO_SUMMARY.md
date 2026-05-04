# 多租户加密数据共享系统 — Demo 总结

> 适用于 PPT 演讲，覆盖背景、核心原理、演示流程、技术亮点、扩展方向。

---

## 一、背景与问题

企业间数据协作场景（如财务报告共享、产品数据开放）面临两个核心矛盾：

- **数据要共享**：合作方需要读取数据
- **数据要保密**：原始数据不能泄露，密钥不能外传

传统方案（直接传文件、共享账号）无法同时满足两点。本 Demo 展示了一套基于**信封加密 + 云服务层代理鉴权**的解决方案。

---

## 二、密钥层级设计（main.py）

系统采用 4 层密钥体系，自上而下层层包装：

```
根密钥 (RK)
  └─ 包装 → 账户主密钥 (AMK)
               └─ 包装 → 表主密钥 (TMK)
                            └─ 包装 → 文件密钥 (FK)
                                         └─ 加密 → 真实数据
```

**核心思想**：
- 真实数据只用最底层的 FK 加密
- FK 被 TMK 包装后存入存储，裸 FK 从不落盘
- 读取时自上而下逐层解包，FK 仅在内存中短暂存在，用后即清

**加密算法**：AES-256-GCM（认证加密，防篡改）

---

## 三、数据共享机制（share.py）

参考 Snowflake Data Sharing 设计，定义三个角色：

| 角色 | 职责 |
|------|------|
| **Provider（提供方）** | 拥有 TMK，负责加密上传数据，决定授权给谁 |
| **Cloud Services（云服务层）** | 中央鉴权中心，代理解包 FK，不暴露 TMK |
| **Consumer（消费方）** | 发起查询，临时获取 FK，解密后立即清除密钥 |

**共享流程**：

```
1. Provider 上传数据
   明文 → [FK 加密] → 密文存 S3
   FK   → [TMK 包装] → wrapped_FK 存 S3

2. Provider 执行 GRANT
   云服务层元数据：consumer_A 有权访问

3. Consumer 发起查询
   → 向云服务层申请 FK
   → 云服务层验权 → 解包 FK → 通过安全通道下发
   → Consumer 内存解密 → 读取明文 → 清除 FK

4. Provider 执行 REVOKE
   仅修改云服务层元数据，S3 数据无需变动
   → Consumer 再次查询 → 鉴权失败 → 拒绝访问
```

**关键安全保证**：Consumer 永远拿不到 Provider 的 TMK，只能按需获取单次 FK。

---

## 四、多租户扩展（mock_multitenant_demo.py）

在单租户基础上扩展为多租户架构：

- 每个租户（company_a、company_b…）拥有**独立的 TMK**，密钥空间完全隔离
- 存储路径按租户隔离：`{tenant_id}/files/{file_id}.enc`
- 共享粒度细化到**文件级**，一个 Share 可包含多个文件，授权给多个消费方租户
- 云服务层维护所有租户的 TMK 注册表，统一鉴权

**演示场景**：
1. company_a 上传财务报告、用户数据
2. company_b 上传产品路线图
3. company_a 将财务报告共享给 company_c
4. company_b 将产品路线图共享给 company_c、company_d
5. company_d 尝试访问 company_a 的财务报告 → **被拒绝**
6. 系统输出访问日志和成功率统计

---

## 五、生产级存储（minio_multitenant_share.py）

将 MockStorage 替换为真实 MinIO 对象存储：

| 存储桶 | 内容 |
|--------|------|
| `tenant-data` | 加密文件（.enc） |
| `tenant-metadata` | 文件元数据 + 共享授权（.json） |

数据与权限分离存储，支持独立的访问控制策略。

---

## 六、安全审计（security_audit.py）

覆盖以下验证项：

- **密钥隔离性**：验证各租户 TMK 唯一且不重复，熵值 ≥ 7.5
- **访问控制**：授权访问成功、未授权访问被拦截、撤销后访问失败
- **密钥不泄露**：Consumer 无法获取 Provider TMK
- **合规检查**：AES-256 标准、审计日志完整性

---

## 七、性能基准（performance_test.py）

| 测试项 | 结果（测试环境） |
|--------|----------------|
| 文件上传吞吐 | ~100 文件/秒（1KB） |
| 并发访问 | ~50 次/秒（10 并发） |
| 元数据内存占用 | ~2KB / 文件 |
| 支持租户规模 | 1000+ |

---

## 八、技术亮点总结

1. **零信任共享**：数据共享不等于密钥共享，消费方只获得临时 FK
2. **撤销零成本**：REVOKE 只改元数据，不动存储数据，瞬间生效
3. **租户强隔离**：密钥空间和存储路径双重隔离，租户间无法越权
4. **认证加密**：AES-256-GCM 同时保证机密性和完整性，防止数据篡改
5. **用后即焚**：FK 仅在计算节点内存中短暂存在，查询结束立即清除

---

## 九、扩展方向

**短期**：
- 密钥轮换（TMK 定期更新，重新包装 FK）
- 共享过期时间（TTL）
- 文件版本管理

**长期**：
- 集成企业 SSO / LDAP
- 多云存储支持（S3、Azure Blob、GCS）
- 数据血缘追踪
- GDPR 合规（数据删除权、可移植性）

---

## 十、Demo 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 演示1：密钥层级原理
python3 main.py

# 演示2：数据共享核心机制
python3 share.py

# 演示3：多租户完整场景（无需 MinIO）
python3 mock_multitenant_demo.py

# 演示4：安全审计
python3 security_audit.py

# 演示5：性能测试
python3 performance_test.py

# 演示6：真实 MinIO（需 Docker）
docker-compose up -d
python3 minio_multitenant_share.py
```
