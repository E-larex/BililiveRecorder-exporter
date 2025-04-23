# 使用官方Python轻量级镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 5000

# 设置环境变量（可选）
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# 运行应用
CMD ["flask", "run"]