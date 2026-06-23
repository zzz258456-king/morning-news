import { useState, useEffect } from 'react'
import type { TemplateOption } from '../types'
import { templateApi } from '../api'

interface Props {
  projectId: string
  selected: TemplateOption
  onSelect: (template: TemplateOption) => void
}

export default function TemplateSelect({ projectId, selected, onSelect }: Props) {
  const [templates, setTemplates] = useState<TemplateOption[]>([])
  const [loading, setLoading] = useState(false)
  const [layout, setLayout] = useState(selected?.layout || '16:9')

  const fetchTemplates = async (refresh = false) => {
    setLoading(true)
    try {
      const api = refresh ? templateApi.refresh : templateApi.get
      const res = await api(projectId)
      setTemplates(res.data.templates)
      if (res.data.templates.length > 0 && !refresh) {
        onSelect(res.data.templates[0])
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTemplates()
  }, [projectId])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">选择模板</h2>
        <div className="flex items-center gap-4">
          <select
            value={layout}
            onChange={(e) => setLayout(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
          >
            <option value="16:9">16:9</option>
            <option value="4:3">4:3</option>
          </select>
          <button
            onClick={() => fetchTemplates(true)}
            disabled={loading}
            className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {loading ? '刷新中...' : '刷新模板'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {templates.map((template) => (
          <div
            key={template.id}
            onClick={() => onSelect({ ...template, layout })}
            className={`cursor-pointer rounded-xl border-2 p-5 transition-all ${
              selected?.id === template.id
                ? 'border-blue-600 bg-blue-50'
                : 'border-slate-200 bg-white hover:border-blue-300'
            }`}
          >
            <div className="flex gap-2 mb-3">
              {template.colors.map((color, i) => (
                <div
                  key={i}
                  className="w-8 h-8 rounded-full border border-slate-200"
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
            <h3 className="font-semibold text-slate-800">{template.name}</h3>
            <p className="text-sm text-slate-500 mt-1">比例：{layout}</p>
            <p className="text-xs text-slate-400 mt-1">来源：{template.source === 'builtin' ? '内置' : '搜索'}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
