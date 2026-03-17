/**
 * Client Axios centralizzato per le chiamate all'API FastAPI.
 * Il base URL punta all'API stessa; in sviluppo Vite fa da proxy.
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000,
})

// Status & statistiche
export const fetchStatus      = ()           => api.get('/status')
export const fetchAnni        = ()           => api.get('/anni')
export const fetchCategorie   = ()           => api.get('/categorie')
export const fetchStatistiche = (anno)       => api.get('/statistiche', { params: anno ? { anno } : {} })

// Ricerca enti
export const fetchEnti = (params) => api.get('/enti', { params })

// Storico ente
export const fetchEnteStorico = (cf) => api.get(`/enti/${encodeURIComponent(cf)}`)

// Catalogo download
export const fetchFiles = (params) => axios.get('/download/files', { params })

// ── Pipeline (protette da X-Pipeline-Key) ─────────────────────────────────
const _pipelineHeaders = (key) => ({ headers: { 'X-Pipeline-Key': key } })

export const pipelineAnalyze   = (key, anni)    => api.get('/pipeline/analyze', {
  ..._pipelineHeaders(key),
  params: anni ? { anni } : {},
})
export const pipelineRun       = (key, payload) => api.post('/pipeline/run',  payload, _pipelineHeaders(key))
export const pipelineJobs      = (key)          => api.get('/pipeline/jobs',          _pipelineHeaders(key))
export const pipelineJobDetail = (key, jobId)   => api.get(`/pipeline/jobs/${jobId}`, _pipelineHeaders(key))
export const pipelineJobDelete = (key, jobId)   => api.delete(`/pipeline/jobs/${jobId}`, _pipelineHeaders(key))
