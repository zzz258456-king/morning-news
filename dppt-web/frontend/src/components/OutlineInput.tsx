import { useState, useRef } from 'react'
import type { OutlinePage } from '../types'
import { outlineApi } from '../api'

interface Props {
  projectId: string
  outline: OutlinePage[]
  onChange: (outline: OutlinePage[]) => void
}

export default function OutlineInput({ projectId, outline, onChange }: Props) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleTextSubmit = async () => {
    if (!text.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await outlineApi.upload(projectId, text)
      onChange(res.data.outline)
    } catch (e) {
      setError('解析失败，请检查输入')
    } finally {
      setLoading(false)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const res = await outlineApi.upload(projectId, '', file)
      if (res.data.outline?.length > 0) {
        onChange(res.data.outline)
      } else if (res.data.error) {
        setError(res.data.error)
      }
    } catch (e) {
      setError('文件上传失败')
    } finally {
      setLoading(false)
    }
  }

  const handleEditTitle = (index: number, title: string) => {
    const updated = [...outline]
    updated[index] = { ...updated[index], title }
    onChange(updated)
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold mb-4">输入 PPT 大纲</h2>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="粘贴 Markdown 或纯文本大纲，每行一个页面标题..."
          className="w-full h-40 p-4 border border-slate-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <div className="mt-4 flex items-center gap-4">
          <button
            onClick={handleTextSubmit}
            disabled={loading || !text.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? '解析中...' : '解析大纲'}
          </button>
          <span className="text-slate-400">或</span>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
          >
            上传文件
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.docx,.pdf,.pptx,.ppt"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>
        {error && <p className="mt-3 text-red-500 text-sm">{error}</p>}
      </div>

      {outline.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-md font-semibold mb-4">解析预览（{outline.length} 页）</h3>
          <div className="space-y-2">
            {outline.map((page, index) => (
              <div key={page.id} className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                <span className="text-sm text-slate-500 w-16">第 {index + 1} 页</span>
                <input
                  type="text"
                  value={page.title}
                  onChange={(e) => handleEditTitle(index, e.target.value)}
                  className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm"
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
