#!/bin/bash

# 多租户共享系统快速启动脚本

echo "=== 多租户 MinIO 共享系统 ==="
echo

# 检查依赖
echo "1. 检查 Python 依赖..."
if ! python3 -c "import cryptography, minio" 2>/dev/null; then
    echo "安装依赖包..."
    pip3 install -r requirements.txt
fi

# 创建必要目录
echo "2. 创建目录结构..."
mkdir -p config data logs reports

# 运行演示场景
echo "3. 可用的演示命令:"
echo
echo "   # 运行基础演示"
echo "   python3 mock_multitenant_demo.py"
echo
echo "   # 运行完整 MinIO 演示 (需要 MinIO 服务)"
echo "   python3 minio_multitenant_share.py"
echo
echo "   # 使用管理工具"
echo "   python3 share_manager.py demo"
echo
echo "   # 从配置文件初始化系统"
echo "   python3 batch_operations.py init config/system_config.json"
echo
echo "   # 批量上传文件"
echo "   python3 batch_operations.py batch-upload company_a data/company_a_files.csv"
echo
echo "   # 导出系统报告"
echo "   python3 batch_operations.py export-report reports/system_report.json"
echo

# 启动 MinIO (可选)
if command -v docker &> /dev/null; then
    echo "4. 启动 MinIO 服务 (可选):"
    echo "   docker-compose up -d"
    echo "   访问 MinIO 控制台: http://localhost:9001"
    echo "   用户名: minioadmin"
    echo "   密码: minioadmin"
else
    echo "4. Docker 未安装，跳过 MinIO 服务启动"
fi

echo
echo "=== 准备完成 ==="