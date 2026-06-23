import { useState } from 'react'
import type { ProjectConfig } from '../types'
import { generateApi } from '../api'

interface Props {
  projectId: string
  config: ProjectConfig
}

export default function GenerateCheck({ projectId, config }: Props) {
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<{ status: string; output_path: string; message: string } | null>(null)
  const [error, setError] = useState('')

  const checks = [
    { label: '已输入大纲', pass: config.outline.length > 0 },
    { label: '已选择模板', pass: !!config.template },
    { label: '每页有标题', pass: config.slides.every((s) => s.title.trim()) },
    { label: '没有纯文字页（至少部分页面有图）', pass: config.slides.some((s) => s.image) },
  ]

  const allPassed = checks.every((c) => c.pass)

  const handleGenerate = async () => {
    setGenerating(true)
    setError('')
    try {
      const res = await generateApi.generate(projectId, config)
      setResult(res.data)
    } catch (e) {
      setError('生成失败，请重试')
    } finally {
      setGenerating(false)
    }
  }

  const handleDownload = async () => {
    try {
      const res = await generateApi.download(projectId)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${config.title || 'output'}.pptx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (e) {
      setError('下载失败')
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold mb-4">生成前检查</h2>
        <div className="space-y-3">
          {checks.map((check) => (
            <div key={check.label} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <span className="text-slate-700">{check.label}</span>
              <span className={`px-3 py-1 rounded-full text-sm ${check.pass ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                {check.pass ? '通过' : '未通过'}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-center">
        <button
          onClick={handleGenerate}
          disabled={generating || !allPassed}
          className="px-8 py-3 bg-blue-600 text-white text-lg font-medium rounded-xl hover:bg-blue-700 disabled:opacity-50"
        >
          {generating ? '生成中...' : '生成 PPTX'}
        </button>
      </div>

      {error && <p className="text-center text-red-500">{error}</p>}

      {result && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
          <h3 className="text-lg font-semibold text-green-800 mb-2">✓ {result.message}</h3>
          <button
            onClick={handleDownload}
            className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            下载 PPTX
          </button>
        </div>
      )}
    </div>
  )
}
