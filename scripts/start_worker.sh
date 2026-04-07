#!/bin/bash
# 启动Celery Worker

# 设置环境
export PYTHONPATH=/app

# 启动不同队列的worker
celery -A asvl.workers.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    -Q asr,llm,clip,vl,fusion,default