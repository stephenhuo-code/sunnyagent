# ============================================
# Stage 1: Builder - 安装编译依赖和 Python 包
# ============================================
FROM python:3.11-slim AS builder

# 安装编译工具（某些包需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt /tmp/

# 安装 Python 包到用户目录（便于复制）
RUN pip install --user --no-cache-dir -r /tmp/requirements.txt

# ============================================
# Stage 2: Runtime - 最小化运行时镜像
# ============================================
FROM python:3.11-slim

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PDF 处理
    poppler-utils \
    qpdf \
    # 字体（可选，用于图表中文显示）
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 复制预编译的 Python 包
COPY --from=builder /root/.local /root/.local

# 设置 PATH
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# 创建工作目录和输出目录
WORKDIR /workspace
RUN mkdir -p /output && chmod 777 /output

# 保持容器运行（用于容器池）
CMD ["sleep", "infinity"]
