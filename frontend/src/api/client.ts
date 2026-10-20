import axios from 'axios'

export const api = axios.create({
  baseURL: '',
  timeout: 60000
})

export async function getSummary() {
  return (await api.get('/api/dashboard/summary')).data
}

export async function calcProfile(payload: any) {
  return (await api.post('/api/profile/calculate', payload)).data
}

export async function chat(question: string, topK = 6) {
  return (await api.post('/api/rag/chat', { question, top_k: topK })).data
}

export async function agentChat(payload: any) {
  return (await api.post('/api/agent/chat', payload)).data
}

export async function getChatHistory(sessionId: string) {
  return (await api.get(`/api/chat/history/${sessionId}`)).data
}

export async function retrieve(question: string, topK = 6) {
  return (await api.post('/api/rag/retrieve', { question, top_k: topK })).data
}

export async function logFood(items: any[], note = '') {
  return (await api.post('/api/food/log', { items, note })).data
}

export async function getFoodRecords() {
  return (await api.get('/api/food/records')).data
}

export async function recognizeFood(file: File, mealType = '拍照记录') {
  const form = new FormData()
  form.append('file', file)
  form.append('meal_type', mealType)
  return (await api.post('/api/food/recognize', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })).data
}

export async function knowledgeStats() {
  return (await api.get('/api/knowledge/stats')).data
}

export async function saveBodyMetric(payload: any) {
  return (await api.post('/api/memory/body-metrics', payload)).data
}

export async function getBodyMetrics() {
  return (await api.get('/api/memory/body-metrics')).data
}

export async function getPublicConfig() {
  return (await api.get('/api/config/public')).data
}

export async function clearFoodRecords() {
  return (await api.post('/api/admin/clear-food-records')).data
}

export async function clearAllData() {
  return (await api.post('/api/admin/clear-all-data')).data
}
