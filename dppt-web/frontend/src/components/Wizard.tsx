import { useState } from 'react'
import type { ProjectConfig, OutlinePage, TemplateOption, SlideConfig } from '../types'
import { projectApi } from '../api'
import OutlineInput from './OutlineInput'
import TemplateSelect from './TemplateSelect'
import ImageConfig from './ImageConfig'
import SlideEditor from './SlideEditor'
import GenerateCheck from './GenerateCheck'

const STEPS = [
  { id: 1, name: '输入大纲' },
  { id: 2, name: '选择模板' },
  { id: 3, name: '图片配置' },
  { id: 4, name: '页面编辑' },
  { id: 5, name: '检查生成' },
]

const defaultTemplate: TemplateOption = {
  id: 'deepppt-academic',
  name: 'deepPPT 学术风',
  colors: ['#1F3864', '#2E5EAA', '#C00000', '#FFFFFF'],
  layout: '16:9',
  source: 'builtin',
}

export default function Wizard() {
  const [currentStep, setCurrentStep] = useState(1)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [config, setConfig] = useState<ProjectConfig>({
    id: '',
    title: '',
    outline: [],
    template: defaultTemplate,
    slides: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleStart = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await projectApi.create()
      const id = res.data.id
      setProjectId(id)
      setConfig((prev) => ({ ...prev, id }))
    } catch (e) {
      setError('创建项目失败')
    } finally {
      setLoading(false)
    }
  }

  const updateOutline = (outline: OutlinePage[]) => {
    const title = outline[0]?.title || ''
    const slides = outline.map((p) => ({
      page_id: p.id,
      title: p.title,
      body: p.content || '',
      image: null as SlideConfig['image'],
      layout: 'default',
    }))
    setConfig((prev) => ({ ...prev, title, outline, slides }))
  }

  const updateTemplate = (template: TemplateOption) => {
    setConfig((prev) => ({ ...prev, template }))
  }

  const updateSlides = (slides: SlideConfig[]) => {
    setConfig((prev) => ({ ...prev, slides }))
  }

  const canGoNext = () => {
    switch (currentStep) {
      case 1:
        return config.outline.length > 0
      case 2:
        return !!config.template
      default:
        return true
    }
  }

  if (!projectId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-4 text-slate-800">DPPT Web</h1>
          <p className="text-slate-600 mb-6">PPT 大纲到交付的可视化流水线</p>
          <button
            onClick={handleStart}
            disabled={loading}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? '创建中...' : '开始新建 PPT'}
          </button>
          {error && <p className="mt-4 text-red-500">{error}</p>}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* 顶部进度条 */}
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-slate-800">DPPT Web</h1>
            <span className="text-sm text-slate-500">{config.title || '未命名项目'}</span>
          </div>
          <div className="flex items-center gap-2">
            {STEPS.map((step, index) => (
              <div key={step.id} className="flex items-center flex-1">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                    currentStep === step.id
                      ? 'bg-blue-600 text-white'
                      : currentStep > step.id
                      ? 'bg-green-500 text-white'
                      : 'bg-slate-200 text-slate-600'
                  }`}
                >
                  {currentStep > step.id ? '✓' : step.id}
                </div>
                <span className="ml-2 text-sm text-slate-600 hidden sm:block">{step.name}</span>
                {index < STEPS.length - 1 && (
                  <div className={`flex-1 h-1 mx-2 ${currentStep > step.id ? 'bg-green-500' : 'bg-slate-200'}`} />
                )}
              </div>
            ))}
          </div>
        </div>
      </header>

      {/* 内容区 */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-8">
        {currentStep === 1 && (
          <OutlineInput
            projectId={projectId}
            outline={config.outline}
            onChange={updateOutline}
          />
        )}
        {currentStep === 2 && (
          <TemplateSelect
            projectId={projectId}
            selected={config.template}
            onSelect={updateTemplate}
          />
        )}
        {currentStep === 3 && (
          <ImageConfig
            projectId={projectId}
            slides={config.slides}
            onChange={updateSlides}
          />
        )}
        {currentStep === 4 && (
          <SlideEditor
            slides={config.slides}
            template={config.template}
            onChange={updateSlides}
          />
        )}
        {currentStep === 5 && (
          <GenerateCheck
            projectId={projectId}
            config={config}
          />
        )}
      </main>

      {/* 底部导航 */}
      <footer className="bg-white border-t border-slate-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex justify-between">
          <button
            onClick={() => setCurrentStep((s) => Math.max(1, s - 1))}
            disabled={currentStep === 1}
            className="px-6 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            上一步
          </button>
          <button
            onClick={() => setCurrentStep((s) => Math.min(5, s + 1))}
            disabled={currentStep === 5 || !canGoNext()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {currentStep === 4 ? '去生成' : '下一步'}
          </button>
        </div>
      </footer>
    </div>
  )
}
