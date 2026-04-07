# ASVL - 多模态视频理解引擎

<div align="center">
    
**通过 ASR + LLM + VL 实现视频内容的结构化解析、关键片段提取和语义增强**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[在线演示](#) · [API文档](#) · [问题反馈](#)

</div>

---

## ✨ 核心特性

### 🎯 多模态理解

| 模块 | 功能 | 技术 |
|------|------|------|
| **ASR** | 语音转文字，句级时间戳 | 阿里云ASR / Faster-Whisper |
| **LLM** | 语义分段、重要性评分、视觉需求判定 | qwen3-vl-plus |
| **VL** | 动作识别、UI理解、场景分析 | qwen3-vl-plus |
| **Fusion** | 双模态对齐、冲突检测、语义增强 | 自研融合算法 |

### 🚀 性能优化

针对高频视频分析场景的智能优化策略：

#### 1️⃣ 流式处理 - 节省 90% 带宽

```
传统方式：下载完整视频 → 提取音频 → 分析    [5GB 视频]
优化方式：FFmpeg流式提取音频 → 直接分析      [500MB 音频流]
```

- ASR阶段只拉取音频流，不下载视频文件
- VL阶段按需下载片段，避免完整视频存储
- FFmpeg直接从URL读取，零本地存储

#### 2️⃣ 智能预筛选 - 精准资源分配

| 视频类型 | 时长 | 处理策略 |
|----------|------|----------|
| 短视频 | ≤30s | 全量分析（成本低） |
| 中等视频 | 30s-3min | ASR + LLM + Top 20% VL |
| 长视频 | ≥3min | 采样分析（开头+中间+结尾） |

#### 3️⃣ 视频指纹去重 - 避免重复处理

```python
# 计算视频指纹
video_hash = perceptual_hash(video_url)

# 已处理过？直接返回缓存结果
if cache.get(video_hash):
    return cached_result
```

- 相同视频不同URL自动识别
- 转发、搬运内容不重复分析
- 缓存结果秒级返回

### 🎨 抖音/快手优化

针对短视频平台特点的特殊优化：

- **元数据利用**：封面图、标题、热度预判价值
- **短视频友好**：15-60秒视频低成本全量分析
- **快速筛选**：基于热度指标智能降级处理

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         视频URL输入                              │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     视频指纹去重                                 │
│              已处理过？直接返回缓存结果                           │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     智能时长分类                                 │
│      短视频(≤30s) / 中等(30s-3min) / 长视频(≥3min)             │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    流式音频提取 (FFmpeg)                         │
│                  不下载视频，只拉取音频流                         │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    ASR 语音识别                                  │
│                 阿里云ASR / Faster-Whisper                       │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    LLM 语义理解                                   │
│          分段 → 评分 → 视觉需求判定 → 摘要生成                    │
└─────────────────────────────┬───────────────────────────────────┘
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
            importance > 0.7      importance ≤ 0.7
                    ↓                   ↓
    ┌───────────────────────┐    只输出文本分析
    │   流式下载视频片段      │
    │   (need_vision=true)   │
    └───────────┬───────────┘
                ↓
    ┌───────────────────────┐
    │    VL 视觉理解         │
    │  动作识别 / UI理解      │
    └───────────┬───────────┘
                ↓
    ┌───────────────────────┐
    │    多模态融合          │
    │  文本-视觉对齐 / 增强   │
    └───────────┬───────────┘
                ↓
    ┌───────────────────────┐
    │    结构化输出          │
    │  高亮片段 / 摘要 / 标签 │
    └───────────────────────┘
```

---
### 任务调度层
```text
            API层
              ↓
        任务队列（Kafka / Redis）
              ↓
 ┌────────┬────────┬────────┬────────┐
 ↓        ↓        ↓        ↓        ↓
ASR    LLM    Clip    VL    Fusion
Worker Worker Worker Worker Worker
```

---
---

## 📊 处理流程

### 单个视频分析流程

```
视频URL → 指纹去重 → 时长分类 → 流式音频 → ASR → LLM分析
                                                ↓
                                        need_vision=true?
                                           ↓         ↓
                                          Yes        No
                                           ↓         ↓
                                    流式下载片段   跳过
                                           ↓
                                       VL分析
                                           ↓
                                      融合输出
```

### 批量视频分析策略

| 场景 | 视频数量 | 策略 |
|------|----------|------|
| 实时分析 | 单个 | 完整流水线 |
| 批量处理 | 10-100 | 并行Worker + 去重 |
| 大规模 | 1000+ | 采样 + 热度筛选 + 缓存 |

---

## 🛠️ 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+ (前端)
- PostgreSQL 15+
- Redis 7+
- FFmpeg 6.0+

### 安装部署

```bash
# 克隆项目
git clone https://github.com/your-repo/asvl.git
cd asvl

# 安装Python依赖
pip install -e .

# 安装前端依赖
cd frontend && npm install && cd ..

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入API密钥

# 启动服务 (Docker Compose)
docker compose up -d

# 或手动启动
uvicorn asvl.main:app --host 0.0.0.0 --port 8000 &
celery -A asvl.workers.celery_app worker --loglevel=info &
cd frontend && npm run dev &
```

### API使用

```bash
# 创建分析任务
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "options": {
      "language": "zh",
      "vl_enabled": true
    }
  }'

# 响应
{
  "task_id": "task_xxx",
  "status": "pending",
  "created_at": "2024-01-01T00:00:00"
}

# 查询任务状态
curl http://localhost:8000/api/v1/tasks/task_xxx/

# 获取分析结果
curl http://localhost:8000/api/v1/tasks/task_xxx/result/
```

---

## ⚙️ 配置说明

### 环境变量

```bash
# LLM/VL配置 (qwen3-vl-plus)
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://apis.iflow.cn/v1
LLM_MODEL=qwen3-vl-plus

# 并发控制 (关键!)
LLM_MAX_CONCURRENT=1    # API同时只能1个请求

# 阿里云ASR
ALIYUN_ASR_APP_KEY=xxx
ALIYUN_ASR_ACCESS_KEY=xxx
ALIYUN_ASR_SECRET_KEY=xxx

# 成本控制
VL_TOP_K_PERCENT=0.2    # 只处理Top 20%高价值片段
MAX_CLIPS_PER_VIDEO=50

# 流式处理
STREAM_AUDIO_ENABLED=true
STREAM_CLIP_ENABLED=true

# 视频指纹去重
DEDUP_ENABLED=true
DEDUP_CACHE_TTL=86400   # 缓存24小时
```

### 智能预筛选配置

```python
# configs/settings.py
VIDEO_DURATION_THRESHOLDS = {
    "short": 30,      # ≤30秒: 全量分析
    "medium": 180,    # 30s-3min: ASR+LLM+Top VL
    "long": 180,      # ≥3min: 采样分析
}

IMPORTANCE_THRESHOLD_FOR_VL = 0.7  # 高于0.7才做VL分析
```

---

## 📈 性能指标

### 资源节省效果

| 优化项 | 传统方式 | 优化后 | 节省 |
|--------|----------|--------|------|
| 网络带宽 | 5GB/视频 | 500MB/视频 | **90%** |
| 本地存储 | 5GB/视频 | 100MB/片段 | **98%** |
| 重复处理 | 每次完整分析 | 缓存命中 | **100%** |
| VL调用 | 全量 | Top 20% | **80%** |

### 处理速度

| 视频时长 | ASR | LLM | VL(可选) | 总计 |
|----------|-----|-----|----------|------|
| 30秒 | 5s | 3s | 2s | ~10s |
| 3分钟 | 15s | 10s | 5s | ~30s |
| 10分钟 | 45s | 20s | 10s | ~75s |

---

## 🎯 使用场景

### 内容审核
- 自动识别违规内容
- 关键片段提取审核
- 文本+视觉双重校验

### 知识提取
- 教程视频结构化
- 操作步骤提取
- 关键知识点标注

### 内容创作
- 精彩片段自动剪辑
- 视频摘要生成
- 热点内容发现

### 数据分析
- 视频内容标签化
- 用户行为分析
- 内容趋势洞察

---

## 🔧 技术栈

### 后端
- **框架**: FastAPI + Uvicorn
- **任务队列**: Celery + Redis
- **数据库**: PostgreSQL + SQLAlchemy
- **ASR**: 阿里云ASR / Faster-Whisper
- **LLM/VL**: qwen3-vl-plus (OpenAPI兼容)

### 前端
- **框架**: React 18 + TypeScript
- **构建**: Vite
- **样式**: Tailwind CSS
- **动画**: Framer Motion

### 基础设施
- **容器化**: Docker + Docker Compose
- **视频处理**: FFmpeg
- **存储**: 阿里云OSS / 本地存储

---

## 📁 项目结构

```
asvl/
├── asvl/                    # 后端代码
│   ├── core/                # 核心模块
│   │   ├── asr/            # ASR语音识别
│   │   ├── llm/            # LLM语义理解
│   │   ├── clipper/        # 视频裁剪
│   │   ├── vl/             # 视觉理解
│   │   └── fusion/         # 多模态融合
│   ├── workers/            # Celery任务
│   ├── api/                # API路由
│   ├── db/                 # 数据库模型
│   └── utils/              # 工具函数
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── pages/         # 页面组件
│   │   ├── components/    # UI组件
│   │   └── lib/           # 工具库
│   └── package.json
├── configs/                # 配置文件
│   ├── settings.py        # 全局配置
│   └── prompts/           # Prompt模板
├── tests/                  # 测试代码
├── docker-compose.yml      # Docker配置
└── pyproject.toml          # Python依赖
```

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢服务商

- [阿里云ASR](https://www.aliyun.com/product/nls) - 语音识别服务
- [qwen3-vl-plus](https://qwenlm.github.io/) - 多模态大模型
---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star！⭐**

Made with ❤️ by ASVL Team

</div>
