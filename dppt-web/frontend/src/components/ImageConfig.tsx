import { useRef } from 'react'
import type { SlideConfig, SlideImage } from '../types'
import { imageApi } from '../api'

interface Props {
  projectId: string
  slides: SlideConfig[]
  onChange: (slides: SlideConfig[]) => void
}

export default function ImageConfig({ projectId, slides, onChange }: Props) {
  const fileInputRefs = useRef<{ [key: string]: HTMLInputElement | null }>({})

  const updateSlideImage = (index: number, image: SlideImage | null) => {
    const updated = [...slides]
    updated[index] = { ...updated[index], image }
    onChange(updated)
  }

  const handleSearch = async (index: number) => {
    const slide = slides[index]
    try {
      const res = await imageApi.search(projectId, slide.page_id)
      const images = res.data.images
      if (images.length > 0) {
        updateSlideImage(index, {
          source: 'search',
          url: images[0].url,
          position: 'right',
        })
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleUpload = async (index: number, file: File) => {
    const slide = slides[index]
    try {
      const res = await imageApi.upload(projectId, slide.page_id, file)
      updateSlideImage(index, {
        source: 'upload',
        local_path: res.data.image.local_path,
        position: 'right',
      })
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">图片配置</h2>
      <p className="text-sm text-slate-500">为每页选择配图，可自动搜索或上传本地图片</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {slides.map((slide, index) => (
          <div key={slide.page_id} className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="font-medium text-slate-800 mb-3 truncate">{slide.title || `第 ${index + 1} 页`}</h3>

            {slide.image?.url ? (
              <img
                src={slide.image.url}
                alt={slide.title}
                className="w-full h-40 object-contain bg-slate-100 rounded-lg mb-3"
              />
            ) : slide.image?.local_path ? (
              <div className="w-full h-40 bg-slate-100 rounded-lg mb-3 flex items-center justify-center text-slate-500 text-sm">
                已上传：{slide.image.local_path.split('\\').pop()}
              </div>
            ) : (
              <div className="w-full h-40 bg-slate-100 rounded-lg mb-3 flex items-center justify-center text-slate-400 text-sm">
                暂无配图
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => handleSearch(index)}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                自动搜索
              </button>
              <button
                onClick={() => fileInputRefs.current[slide.page_id]?.click()}
                className="px-3 py-1.5 text-sm border border-slate-300 rounded-md text-slate-700 hover:bg-slate-50"
              >
                上传图片
              </button>
              <input
                ref={(el) => { fileInputRefs.current[slide.page_id] = el }}
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) handleUpload(index, file)
                }}
                className="hidden"
              />
              {slide.image && (
                <button
                  onClick={() => updateSlideImage(index, null)}
                  className="px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-md"
                >
                  移除
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
