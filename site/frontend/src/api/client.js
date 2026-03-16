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
