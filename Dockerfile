# RoadLens 运行镜像
# 构建: docker build -t roadlens .
# 运行: docker run --rm -p 8124:8124 roadlens
#   访问: http://localhost:8124
FROM python:3.14-slim

# shapely / pyproj 依赖 GEOS / PROJ 运行库
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgeos-c1v5 proj-bin \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn>=21.0

# 再拷贝应用代码
COPY . .

# 运行时用户数据目录（容器内），建议用挂载卷持久化
RUN mkdir -p /app/workspace

EXPOSE 8124

# 以 gunicorn 提供生产级 WSGI 服务（server.app 暴露 app 对象）
# 线程模式适配 shapely 计算与后台清理线程
CMD ["gunicorn", "--bind", "0.0.0.0:8124", "--workers", "2", "--threads", "4", "--timeout", "120", "server.app:app"]
