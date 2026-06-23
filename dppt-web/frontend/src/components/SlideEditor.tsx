import { useState } from 'react'
import type { SlideConfig, SlideImage, TemplateOption } from '../types'

interface Props {
  slides: SlideConfig[]
  template: TemplateOption
  onChange: (slides: SlideConfig[]) => void
}

const POSITIONS = [
  { value: 'left', label: '左侧' },
  { value: 'right', label: '右侧' },
  { value: 'center', label: '居中' },
  { value: 'banner', label: '横幅' },
  { value: 'corner', label: '角落' },
]

export default function SlideEditor({ slides, template, onChange }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const currentSlide = slides[selectedIndex]

  const updateSlide = (index: number, updates: Partial<SlideConfig>) => {
    const updated = [...slides]
    updated[index] = { ...updated[index], ...updates }
    onChange(updated)
  }

  if (!currentSlide) {
    return <div className="text-slate-500">没有可编辑的页面</div>
  }

  return (
    <div className="flex gap-6 h-[600px]">
      {/* 左侧页面列表 */}
      <div className="w-64 bg-white rounded-xl border border-slate-200 p-4 overflow-y-auto">
        <h3 className="font-semibold mb-3">页面列表</h3>
        <div className="space-y-2">
          {slides.map((slide, index) => (
            <button
              key={slide.page_id}
              onClick={() => setSelectedIndex(index)}
              className={`w-full text-left p-3 rounded-lg text-sm transition-colors ${
                selectedIndex === index
                  ? 'bg-blue-50 border-blue-200 border'
                  : 'hover:bg-slate-50 border border-transparent'
              }`}
            >
              <span className="font-medium">{index + 1}. {slide.title || '无标题'}</span>
              {slide.image && <span className="ml-2 text-xs text-blue-600">有图</span>}
            </button>
          ))}
        </div>
      </div>

      {/* 中央预览 */}
      <div className="flex-1 bg-white rounded-xl border border-slate-200 p-6 flex items-center justify-center">
        <div
          className="relative bg-white border-2 border-slate-200 rounded-lg overflow-hidden"
          style={{
            width: template.layout === '4:3' ? '480px' : '640px',
            height: template.layout === '4:3' ? '360px' : '360px',
          }}
        >
          <div
            className="absolute top-0 left-0 right-0 h-2"
            style={{ backgroundColor: template.colors[0] }}
          />
          <div className="p-6">
            <h2 className="text-xl font-bold text-slate-800 mb-4">{currentSlide.title || '页面标题'}</h2>
            <div className="flex gap-4">
              {(currentSlide.image?.position === 'left' || currentSlide.image?.position === 'center') && currentSlide.image?.url && (
                <img src={currentSlide.image.url} alt="" className="w-32 h-24 object-contain bg-slate-100 rounded" />
              )}
              <p className="text-sm text-slate-600 flex-1 whitespace-pre-wrap">{currentSlide.body || '页面内容'}</p>
              {currentSlide.image?.position === 'right' && currentSlide.image?.url && (
                <img src={currentSlide.image.url} alt="" className="w-32 h-24 object-contain bg-slate-100 rounded" />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 右侧属性面板 */}
      <div className="w-80 bg-white rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold mb-4">页面属性</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">标题</label>
            <input
              type="text"
              value={currentSlide.title}
              onChange={(e) => updateSlide(selectedIndex, { title: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">正文</label>
            <textarea
              value={currentSlide.body}
              onChange={(e) => updateSlide(selectedIndex, { body: e.target.value })}
              rows={6}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm resize-none"
            />
          </div>

          {currentSlide.image && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">图片位置</label>
              <select
                value={currentSlide.image.position}
                onChange={(e) =>
                  updateSlide(selectedIndex, {
                    image: { ...currentSlide.image!, position: e.target.value as SlideImage['position'] },
                  })
                }
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm"
              >
                {POSITIONS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
