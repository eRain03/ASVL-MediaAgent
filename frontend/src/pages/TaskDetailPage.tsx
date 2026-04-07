import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Video,
  FileText,
  Eye,
  Sparkles,
  AlertTriangle,
  Play,
  Download
} from 'lucide-react'
import { taskApi } from '@/lib/api'
import { cn, formatTimestamp, getSegmentTypeColor, getStatusColor } from '@/lib/utils'
import type { TaskStatusResponse, TaskResult, LLMResult, Highlight } from '@/types'
import toast from 'react-hot-toast'

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null)
  const [taskResult, setTaskResult] = useState<TaskResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'segments' | 'highlights' | 'alignment'>('highlights')

  useEffect(() => {
    if (!taskId) return

    const fetchData = async () => {
      try {
        const status = await taskApi.getStatus(taskId)
        setTaskStatus(status)

        if (status.status === 'completed') {
          const result = await taskApi.getResult(taskId)
          setTaskResult(result)
        }
      } catch (error) {
        toast.error('获取任务信息失败')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [taskId])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-white/40 animate-spin" />
      </div>
    )
  }

  if (!taskStatus) {
    return (
      <div className="text-center py-20">
        <h2 className="text-2xl font-bold text-white/60 mb-4">任务不存在</h2>
        <Link to="/tasks" className="text-primary-400 hover:underline">
          返回任务列表
        </Link>
      </div>
    )
  }

  const getStageStatus = (stage: keyof typeof taskStatus.progress) => {
    const status = taskStatus.progress[stage]
    if (status === 'completed') return <CheckCircle className="w-5 h-5 text-green-400" />
    if (status === 'processing') return <Loader2 className="w-5 h-5 text-yellow-400 animate-spin" />
    if (status === 'failed') return <XCircle className="w-5 h-5 text-red-400" />
    return <Clock className="w-5 h-5 text-white/30" />
  }

  const stages = [
    { key: 'asr', label: 'ASR', icon: Video, desc: '语音识别' },
    { key: 'llm', label: 'LLM', icon: FileText, desc: '语义理解' },
    { key: 'clip', label: 'Clip', icon: Play, desc: '视频裁剪' },
    { key: 'vl', label: 'VL', icon: Eye, desc: '视觉分析' },
    { key: 'fusion', label: 'Fusion', icon: Sparkles, desc: '多模态融合' },
  ]

  return (
    <div className="space-y-8">
      {/* Back Button */}
      <Link
        to="/tasks"
        className="inline-flex items-center gap-2 text-white/60 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>返回任务列表</span>
      </Link>

      {/* Task Header */}
      <div className="glass rounded-2xl p-6">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2 font-mono">
              {taskId}
            </h1>
            <p className="text-white/60">
              创建于 {new Date(taskStatus.created_at).toLocaleString('zh-CN')}
            </p>
          </div>
          <div className={cn('px-4 py-2 rounded-lg text-sm font-medium', getStatusColor(taskStatus.status))}>
            {taskStatus.status === 'completed' && '已完成'}
            {taskStatus.status === 'processing' && '处理中'}
            {taskStatus.status === 'pending' && '等待中'}
            {taskStatus.status === 'failed' && '失败'}
          </div>
        </div>

        {/* Progress Steps */}
        <div className="grid grid-cols-5 gap-4">
          {stages.map((stage, index) => {
            const Icon = stage.icon
            const isActive = taskStatus.progress[stage.key] === 'processing'
            const isCompleted = taskStatus.progress[stage.key] === 'completed'

            return (
              <motion.div
                key={stage.key}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className={cn(
                  'relative p-4 rounded-xl text-center transition-all',
                  isCompleted && 'bg-green-500/10 border border-green-500/20',
                  isActive && 'bg-yellow-500/10 border border-yellow-500/20',
                  !isCompleted && !isActive && 'bg-white/5'
                )}
              >
                <div className="flex justify-center mb-2">
                  {getStageStatus(stage.key as keyof typeof taskStatus.progress)}
                </div>
                <div className="text-sm font-medium text-white mb-1">{stage.label}</div>
                <div className="text-xs text-white/40">{stage.desc}</div>
              </motion.div>
            )
          })}
        </div>

        {/* Error Message */}
        {taskStatus.error_message && (
          <div className="mt-4 p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-red-400 mb-1">处理失败</div>
              <div className="text-red-300/60 text-sm">{taskStatus.error_message}</div>
            </div>
          </div>
        )}
      </div>

      {/* Results */}
      {taskStatus.status === 'completed' && taskResult && (
        <div className="space-y-6">
          {/* Summary */}
          {taskResult.summary && (
            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary-400" />
                内容摘要
              </h2>
              <p className="text-white/70 leading-relaxed">{taskResult.summary}</p>
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-2">
            {[
              { key: 'highlights', label: '高亮片段', count: taskResult.highlights?.length || 0 },
              { key: 'segments', label: '所有分段', count: taskResult.segments?.length || 0 },
              { key: 'alignment', label: '对齐问题', count: taskResult.alignment_issues?.length || 0 },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as any)}
                className={cn(
                  'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                  activeTab === tab.key
                    ? 'bg-white/10 text-white'
                    : 'text-white/40 hover:text-white hover:bg-white/5'
                )}
              >
                {tab.label}
                <span className="ml-2 px-2 py-0.5 rounded bg-white/10 text-xs">
                  {tab.count}
                </span>
              </button>
            ))}
          </div>

          {/* Highlights Tab */}
          {activeTab === 'highlights' && taskResult.highlights && (
            <div className="space-y-4">
              {taskResult.highlights.map((highlight, index) => (
                <HighlightCard key={index} highlight={highlight} index={index} />
              ))}
            </div>
          )}

          {/* Segments Tab */}
          {activeTab === 'segments' && taskResult.segments && (
            <div className="space-y-3">
              {taskResult.segments.map((segment, index) => (
                <SegmentCard key={segment.id} segment={segment} index={index} />
              ))}
            </div>
          )}

          {/* Alignment Tab */}
          {activeTab === 'alignment' && taskResult.alignment_issues && (
            <div className="space-y-4">
              {taskResult.alignment_issues.length === 0 ? (
                <div className="glass rounded-xl p-8 text-center">
                  <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-3" />
                  <div className="text-white/60">所有文本与视觉内容一致</div>
                </div>
              ) : (
                taskResult.alignment_issues.map((issue, index) => (
                  <div key={index} className="glass rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-3">
                      {issue.status === 'conflict' ? (
                        <AlertTriangle className="w-5 h-5 text-yellow-400" />
                      ) : (
                        <Eye className="w-5 h-5 text-white/40" />
                      )}
                      <span className="font-mono text-sm text-white/60">
                        {issue.segment_id}
                      </span>
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs',
                        issue.status === 'conflict' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-white/10 text-white/60'
                      )}>
                        {issue.status}
                      </span>
                    </div>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs text-white/40 mb-1">文本描述</div>
                        <div className="text-white/70 text-sm">{issue.text_claim}</div>
                      </div>
                      <div>
                        <div className="text-xs text-white/40 mb-1">视觉发现</div>
                        <div className="text-white/70 text-sm">{issue.vision_finding}</div>
                      </div>
                    </div>
                    {issue.reason && (
                      <div className="mt-3 text-xs text-white/40">{issue.reason}</div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function HighlightCard({ highlight, index }: { highlight: Highlight; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="glass rounded-xl p-5 hover:bg-white/10 transition-all"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className={cn(
            'px-3 py-1 rounded-lg text-xs font-medium border',
            getSegmentTypeColor(highlight.type)
          )}>
            {highlight.type}
          </span>
          <span className="text-white/40 text-sm font-mono">
            {formatTimestamp(highlight.time[0])} - {formatTimestamp(highlight.time[1])}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {highlight.clip_url && (
            <button className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
              <Play className="w-4 h-4 text-white/60" />
            </button>
          )}
        </div>
      </div>
      <p className="text-white/80 leading-relaxed mb-2">{highlight.text}</p>
      {highlight.visual_explanation && (
        <div className="p-3 rounded-lg bg-white/5 mt-3">
          <div className="text-xs text-accent-400 mb-1">视觉补充</div>
          <div className="text-white/60 text-sm">{highlight.visual_explanation}</div>
        </div>
      )}
      <div className="flex items-center gap-2 mt-3">
        <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-primary-500 to-accent-500 rounded-full"
            style={{ width: `${highlight.importance * 100}%` }}
          />
        </div>
        <span className="text-xs text-white/40">
          {Math.round(highlight.importance * 100)}%
        </span>
      </div>
    </motion.div>
  )
}

function SegmentCard({ segment, index }: { segment: LLMResult; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03 }}
      className="glass rounded-lg p-4 hover:bg-white/5 transition-all"
    >
      <div className="flex items-center gap-3 mb-2">
        <span className="text-xs font-mono text-white/40">
          {formatTimestamp(segment.start)} - {formatTimestamp(segment.end)}
        </span>
        <span className={cn(
          'px-2 py-0.5 rounded text-xs',
          getSegmentTypeColor(segment.type)
        )}>
          {segment.type}
        </span>
        {segment.need_vision && (
          <span className="px-2 py-0.5 rounded text-xs bg-accent-500/20 text-accent-300">
            需要视觉
          </span>
        )}
      </div>
      <p className="text-white/70 text-sm line-clamp-2">{segment.text}</p>
    </motion.div>
  )
}