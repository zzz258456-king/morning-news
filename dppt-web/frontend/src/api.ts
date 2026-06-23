import axios from 'axios'

const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

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
  position: string
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

export const projectApi = {
  create: () => api.post('/projects'),
  get: (id: string) => api.get(`/projects/${id}`),
}

export const outlineApi = {
  upload: (projectId: string, text: string, file?: File) => {
    const formData = new FormData()
    if (text) formData.append('text', text)
    if (file) formData.append('file', file)
    return api.post(`/projects/${projectId}/outline`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  get: (projectId: string) => api.get(`/projects/${projectId}/outline`),
}

export const templateApi = {
  get: (projectId: string) => api.post(`/projects/${projectId}/templates`),
  refresh: (projectId: string) => api.post(`/projects/${projectId}/templates/refresh`),
}

export const imageApi = {
  search: (projectId: string, pageId: string) =>
    api.post(`/projects/${projectId}/slides/${pageId}/images`),
  upload: (projectId: string, pageId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/projects/${projectId}/slides/${pageId}/images/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const generateApi = {
  generate: (projectId: string, config: ProjectConfig) =>
    api.post(`/projects/${projectId}/generate`, { config }),
  download: (projectId: string) =>
    api.get(`/projects/${projectId}/download`, { responseType: 'blob' }),
}
