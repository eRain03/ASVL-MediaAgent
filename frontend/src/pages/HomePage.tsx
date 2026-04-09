import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Video,
  Upload,
  Sparkles,
  Zap,
  Eye,
  Brain,
  ArrowRight,
  Loader2,
  Wand2
} from 'lucide-react'
import { taskApi, videoApi } from '@/lib/api'
import toast from 'react-hot-toast'

export default function HomePage() {
  const navigate = useNavigate()
  const [videoUrl, setVideoUrl] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [forceVl, setForceVl] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!videoUrl.trim() && !selectedFile) {
      toast.error('请输入视频URL或选择本地视频文件')
      return
    }

    setLoading(true)
    try {
      let payload: { video_url?: string; video_id?: string; options: { language: string; vl_enabled: boolean; force_vl?: boolean } } = {
        options: {
          language: 'zh',
          vl_enabled: true,
          force_vl: forceVl,
        },
      }

      if (selectedFile) {
        const uploadResult = await videoApi.upload(selectedFile)
        payload = {
          ...payload,
          video_id: uploadResult.video_id,
          video_url: uploadResult.video_url,
        }
      } else {
        payload = {
          ...payload,
          video_url: videoUrl,
        }
      }

      const result = await taskApi.create(payload)
      toast.success('任务创建成功！')
      navigate(`/tasks/${result.task_id}`)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '创建任务失败')
    } finally {
      setLoading(false)
    }
  }

  const handlePickFile = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null
    setSelectedFile(file)
    if (file) {
      setVideoUrl('')
      toast.success(`已选择文件：${file.name}`)
    }
  }

  const features = [
    {
      icon: Video,
      title: 'ASR 语音识别',
      description: '硅基流动SenseVoice精确转录，支持音频事件检测',
      color: 'from-blue-500 to-cyan-500',
    },
    {
      icon: Brain,
      title: 'LLM 语义理解',
      description: '智能分段、重要性评分、视觉需求判定',
      color: 'from-purple-500 to-pink-500',
    },
    {
      icon: Eye,
      title: 'VL 视觉理解',
      description: '多模态视觉分析，动作识别、场景理解',
      color: 'from-pink-500 to-rose-500',
    },
    {
      icon: Zap,
      title: '智能融合',
      description: '双模态对齐、冲突检测、看点分析',
      color: 'from-amber-500 to-orange-500',
    },
  ]

  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <section className="relative py-20">
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/20 rounded-full blur-3xl" />
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-accent-500/20 rounded-full blur-3xl" />
        </div>

        <div className="relative text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 mb-6">
              <Sparkles className="w-4 h-4 text-primary-400" />
              <span className="text-sm text-white/60">多模态视频理解引擎</span>
            </div>

            <h1 className="text-5xl md:text-6xl font-bold mb-6">
              <span className="gradient-text">ASVL</span>
              <br />
              <span className="text-white/90">视频智能解析平台</span>
            </h1>

            <p className="text-xl text-white/60 max-w-2xl mx-auto mb-10">
              通过 ASR + LLM + VL 实现视频内容的结构化解析、关键片段提取和语义增强
            </p>
          </motion.div>

          {/* URL Input */}
          <motion.form
            onSubmit={handleSubmit}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="max-w-2xl mx-auto"
          >
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-primary-500 to-accent-500 rounded-2xl blur-xl opacity-20" />
              <div className="relative glass rounded-2xl p-2">
                <div className="flex items-center gap-2">
                  <div className="flex-1 flex items-center gap-3 bg-white/5 rounded-xl px-4 py-3">
                    <Video className="w-5 h-5 text-white/40" />
                    <input
                      type="url"
                      value={videoUrl}
                      onChange={(e) => {
                        setVideoUrl(e.target.value)
                        if (e.target.value) {
                          setSelectedFile(null)
                        }
                      }}
                      placeholder={selectedFile ? `已选择文件：${selectedFile.name}` : '输入视频URL或上传视频文件...'}
                      className="flex-1 bg-transparent border-none outline-none text-white placeholder-white/40"
                    />
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="video/*"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handlePickFile}
                    className="p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                  >
                    <Upload className="w-5 h-5 text-white/60" />
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-6 py-3 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500 text-white font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
                  >
                    {loading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <>
                        <span>开始分析</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </div>
                {/* 深度分析选项 */}
                <div className="mt-4 flex justify-center">
                  <label
                    htmlFor="deepAnalysis"
                    className={`flex items-center gap-3 px-4 py-2 rounded-xl cursor-pointer transition-all ${
                      forceVl
                        ? 'bg-gradient-to-r from-accent-500/20 to-primary-500/20 border border-accent-500/30'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                    }`}
                  >
                    <div className={`w-5 h-5 rounded-md flex items-center justify-center transition-colors ${
                      forceVl
                        ? 'bg-accent-500'
                        : 'bg-white/10 border border-white/20'
                    }`}>
                      {forceVl && (
                        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                    <input
                      type="checkbox"
                      id="deepAnalysis"
                      checked={forceVl}
                      onChange={(e) => setForceVl(e.target.checked)}
                      className="hidden"
                    />
                    <Wand2 className={`w-4 h-4 transition-colors ${
                      forceVl ? 'text-accent-400' : 'text-white/40'
                    }`} />
                    <span className={`text-sm font-medium transition-colors ${
                      forceVl ? 'text-white' : 'text-white/60'
                    }`}>
                      深度分析
                    </span>
                    <span className="text-xs text-white/40">
                      强制启用视觉分析
                    </span>
                  </label>
                </div>
              </div>
            </div>
          </motion.form>
        </div>
      </section>

      {/* Features Section */}
      <section>
        <div className="text-center mb-10">
          <h2 className="text-3xl font-bold text-white mb-3">核心能力</h2>
          <p className="text-white/60">四大模块协同工作，实现端到端视频理解</p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => {
            const Icon = feature.icon
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="group"
              >
                <div className="glass rounded-2xl p-6 h-full hover:bg-white/10 transition-all">
                  <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${feature.color} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-white/60 text-sm">
                    {feature.description}
                  </p>
                </div>
              </motion.div>
            )
          })}
        </div>
      </section>

      {/* Stats Section */}
      <section className="glass rounded-2xl p-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div>
            <div className="text-4xl font-bold gradient-text mb-2">ASR</div>
            <div className="text-white/60 text-sm">语音转文字</div>
          </div>
          <div>
            <div className="text-4xl font-bold gradient-text mb-2">LLM</div>
            <div className="text-white/60 text-sm">语义理解</div>
          </div>
          <div>
            <div className="text-4xl font-bold gradient-text mb-2">VL</div>
            <div className="text-white/60 text-sm">视觉分析</div>
          </div>
          <div>
            <div className="text-4xl font-bold gradient-text mb-2">融合</div>
            <div className="text-white/60 text-sm">多模态对齐</div>
          </div>
        </div>
      </section>
    </div>
  )
}