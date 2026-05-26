/**
 * Client centralizzato per api.php (backend PHP).
 * Tutti gli endpoint sono GET su /api.php?action=...
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api.php',
  timeout: 30_000,
})

const get = (action, params = {}) => api.get('', { params: { action, ...params } })

// Status & statistiche
export const fetchStatus      = ()      => get('status')
export const fetchAnni        = ()      => get('anni')
export const fetchCategorie   = ()      => get('categorie')
export const fetchRegioni     = ()      => get('regioni')
export const fetchStatistiche = (anno)  => get('statistiche', anno ? { anno } : {})

// Ricerca enti
export const fetchEnti = (params) => get('enti', params)

// Storico singolo ente
export const fetchEnteStorico = (cf) => get('ente', { cf })

// Confronto fino a 5 CF
export const fetchConfronta = (cfs) => api.get('', {
  params: { action: 'confronta', 'cf[]': cfs },
  // axios serializza array come cf[]=A&cf[]=B solo con paramsSerializer
  paramsSerializer: (p) => {
    const parts = [`action=confronta`]
    ;(p['cf[]'] || []).forEach(cf => parts.push(`cf[]=${encodeURIComponent(cf)}`))
    return parts.join('&')
  },
})

// Ricerca ente per nome → restituisce lista {cod_fiscale, denominazione, regione, categoria_principale}
export const fetchCercaCf = (q) => get('cerca_cf', { q })

// Analisi per categoria (tutti gli anni o singolo anno)
export const fetchAnalisiCategorie = (anno) => get('analisi_categorie', anno ? { anno } : {})

// Dettaglio categoria: stats per regione + enti paginati
export const fetchCategoriaDettaglio = (categoria, anno, pagina = 1) =>
  get('categoria_dettaglio', { categoria, anno, pagina })

// Catalogo file per Download
export const fetchFiles = (params) => get('files', params ?? {})

// Analisi inoptato (scelte generiche)
// breakdown: '' | 'regione' | 'categoria'
export const fetchInoptato = ({ categoria, regione, breakdown } = {}) =>
  get('inoptato', {
    ...(categoria  ? { categoria }  : {}),
    ...(regione    ? { regione }    : {}),
    ...(breakdown  ? { breakdown }  : {}),
  })

// Proiezioni forecast (richiede forecast.py già eseguito)
export const fetchForecast = () => get('forecast')

// Classifica (top/crescita/calo/newcomer)
export const fetchClassifica = (params) => get('classifica', params ?? {})

// Province (con cascading da regione)
export const fetchProvince = (regione) => get('province', regione ? { regione } : {})

// Geo: aggregati erogato per regione / provincia / comune
export const fetchGeo = (params) => get('geo', params ?? {})

// NLQ: Natural Language Query (semi-protetto con token HMAC giornaliero)
export const nlqToken = () => get('nlq_token')
export const nlqQuery = (token, q) =>
  api.post('', { token, q }, {
    params: { action: 'nlq' },
    headers: { 'Content-Type': 'application/json' },
  })

// Lead generation: salva email prima del download
export const salvaLead = ({ email, nome, tipo, anno, vuole_newsletter } = {}) =>
  api.post('', new URLSearchParams({
    action: 'salva_lead',
    email,
    ...(nome              ? { nome }              : {}),
    ...(tipo              ? { tipo }              : {}),
    ...(anno              ? { anno }              : {}),
    ...(vuole_newsletter  ? { vuole_newsletter: '1' } : {}),
  }), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
