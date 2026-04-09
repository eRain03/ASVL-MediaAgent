// API Types
export interface TaskCreateRequest {
  video_url?: string
  video_id?: string
  options?: TaskOptions
}

export interface VideoUploadResponse {
  video_id: string
  video_url: string
  filename: string
  size: number
}

export interface TaskOptions {
  language?: string
  vl_enabled?: boolean
  vl_top_k?: number
  callback_url?: string
}

export interface TaskCreateResponse {
  task_id: string
  status: TaskStatus
  created_at: string
}

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface TaskProgress {
  asr: TaskStatus
  llm: TaskStatus
  clip: TaskStatus
  vl: TaskStatus
  fusion: TaskStatus
}

export interface TaskStatusResponse {
  task_id: string
  status: TaskStatus
  progress: TaskProgress
  created_at: string
  updated_at: string
  error_message?: string
}

export interface ASRSegment {
  start: number
  end: number
  text: string
  confidence: number
}

export interface LLMResult {
  id: string
  start: number
  end: number
  text: string
  importance: number
  type: SegmentType
  need_vision: boolean
  confidence: number
}

export type SegmentType =
  | '核心观点'
  | '操作演示'
  | '情绪表达'
  | '背景信息'
  | '数据分析'
  | 'UI操作'

export interface VLResult {
  clip_id: string
  vision_summary: string
  actions: string[]
  objects: string[]
  scene_description?: string
  confidence: number
}

export interface Highlight {
  type: SegmentType
  text: string
  time: [number, number]
  importance: number
  visual_explanation?: string
  clip_url?: string
  user_attraction?: UserAttraction
  audio_context?: string
}

export interface AlignmentIssue {
  segment_id: string
  status: 'consistent' | 'conflict' | 'insufficient'
  text_claim: string
  vision_finding: string
  reason?: string
}

export interface VLResultInfo {
  clip_id: string
  segment_id?: string
  vision_summary: string
  actions: string[]
  objects: string[]
  scene_description?: string
  confidence: number
}

export interface UserAttraction {
  attraction_type: string
  description: string
  confidence: number
  evidence: string[]
}

export interface TaskResult {
  task_id: string
  video_id: string
  status: TaskStatus
  summary?: string
  duration?: number
  segments?: LLMResult[]
  vl_results?: VLResultInfo[]
  highlights?: Highlight[]
  alignment_issues?: AlignmentIssue[]
  asr_segments?: ASRSegment[]
}