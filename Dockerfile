FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# 复制代码
COPY . .

# 创建必要目录
RUN mkdir -p logs videos clips temp

# 暴露端口
EXPOSE 8000

# 默认命令
CMD ["uvicorn", "asvl.main:app", "--host", "0.0.0.0", "--port", "8000"]