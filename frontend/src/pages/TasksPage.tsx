import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ListVideo,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  ArrowRight,
  RefreshCw
} from 'lucide-react'
import { taskApi } from '@/lib/api'
import { cn, getStatusColor } from '@/lib/utils'
import type { TaskStatusResponse, TaskStatus } from '@/types'
import toast from 'react-hot-toast'

interface TaskItem extends TaskStatusResponse {
  video_url?: string
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [loading, setLoading] = useState(true)

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const response = await taskApi.list()
      setTasks(response)
    } catch (error) {
      toast.error('获取任务列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTasks()
    // 每30秒刷新一次
    const interval = setInterval(fetchTasks, 30000)
    return () => clearInterval(interval)
  }, [])

  const getStatusIcon = (status: TaskStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-400" />
      case 'processing':
        return <Loader2 className="w-5 h-5 text-yellow-400 animate-spin" />
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-400" />
      default:
        return <Clock className="w-5 h-5 text-white/40" />
    }
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">任务列表</h1>
          <p className="text-white/60">查看所有视频处理任务</p>
        </div>
        <button
          onClick={fetchTasks}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-all"
        >
          <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          <span>刷新</span>
        </button>
      </div>

      {/* Tasks List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-white/40 animate-spin" />
        </div>
      ) : tasks.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center">
          <ListVideo className="w-16 h-16 text-white/20 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white/60 mb-2">暂无任务</h3>
          <p className="text-white/40 mb-6">创建一个新任务开始视频分析</p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500 text-white font-medium hover:opacity-90 transition-opacity"
          >
            <span>创建任务</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {tasks.map((task, index) => (
            <motion.div
              key={task.task_id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: index * 0.1 }}
            >
              <Link
                to={`/tasks/${task.task_id}`}
                className="block glass rounded-xl p-6 hover:bg-white/10 transition-all group"
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    {getStatusIcon(task.status)}
                    <span className="font-mono text-white/80">
                      {task.task_id}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className={cn('text-sm', getStatusColor(task.status))}>
                      {task.status === 'completed' && '已完成'}
                      {task.status === 'processing' && '处理中'}
                      {task.status === 'pending' && '等待中'}
                      {task.status === 'failed' && '失败'}
                    </span>
                    <span className="text-white/40 text-sm">
                      {formatDate(task.created_at)}
                    </span>
                    <ArrowRight className="w-4 h-4 text-white/20 group-hover:text-white/60 transition-colors" />
                  </div>
                </div>

                {/* Progress */}
                <div className="flex items-center gap-2">
                  {(['asr', 'llm', 'clip', 'vl', 'fusion'] as const).map((stage) => (
                    <div
                      key={stage}
                      className={cn(
                        'flex-1 h-1.5 rounded-full',
                        task.progress[stage] === 'completed' && 'bg-green-400',
                        task.progress[stage] === 'processing' && 'bg-yellow-400',
                        task.progress[stage] === 'failed' && 'bg-red-400',
                        task.progress[stage] === 'pending' && 'bg-white/10'
                      )}
                    />
                  ))}
                </div>

                {/* Stage Labels */}
                <div className="flex items-center gap-2 mt-2">
                  {['ASR', 'LLM', 'Clip', 'VL', 'Fusion'].map((label, i) => (
                    <div
                      key={label}
                      className="flex-1 text-center text-xs text-white/40"
                    >
                      {label}
                    </div>
                  ))}
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}