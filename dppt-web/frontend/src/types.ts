export interface OutlinePage {
  id: string
  title: string
  content?: string
  notes?: string
}

export interface TemplateOption {
  id: string
  name: string
  colors: string[]
  layout: string
  source: string
}

export interface SlideImage {
  source: string
  url?: string
  local_path?: string
  position: 'left' | 'right' | 'center' | 'banner' | 'corner'
}

export interface SlideConfig {
  page_id: string
  title: string
  body: string
  image?: SlideImage | null
  layout: string
}

export interface ProjectConfig {
  id: string
  title: string
  outline: OutlinePage[]
  template: TemplateOption
  slides: SlideConfig[]
  output_path?: string
}
