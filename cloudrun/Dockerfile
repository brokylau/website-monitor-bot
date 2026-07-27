FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TZ=Asia/Shanghai

# Git 用于读取和更新 GitHub 仓库
# curl 便于后续网络诊断
# tzdata 用于北京时间
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        git \
        curl \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

# 安装 Python 包、Chromium 和 Chromium 所需 Linux 依赖
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && python -m playwright install --with-deps chromium

COPY entrypoint.sh /app/entrypoint.sh
COPY git-askpass.sh /app/git-askpass.sh

RUN chmod +x /app/entrypoint.sh \
    && chmod +x /app/git-askpass.sh

WORKDIR /workspace

ENTRYPOINT ["/app/entrypoint.sh"]
