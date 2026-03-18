<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-10 space-y-6">

    <!-- Intestazione -->
    <div class="mb-2">
      <h1 class="mb-1">Gestione Pipeline</h1>
      <p class="text-gray-500">Scarica e aggiorna i dati 5×1000 dall'Agenzia delle Entrate, step by step.</p>
    </div>

    <!-- ── STEP 1: ACCESSO ─────────────────────────────────────── -->
    <div class="card">
      <div class="flex items-start gap-4">
        <div class="w-10 h-10 bg-brand-50 rounded-xl flex items-center justify-center flex-shrink-0">
          <svg class="w-5 h-5 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/>
          </svg>
        </div>
        <div class="flex-1">
          <h2 class="mb-3">Accesso</h2>
          <div class="flex gap-3 items-center">
            <input
              v-model="apiKey"
              type="password"
              placeholder="API key pipeline…"
              class="input-field flex-1"
              @keyup.enter="analyzeFiles"
            />
            <button
              @click="analyzeFiles"
              :disabled="!apiKey || loadingAnalysis"
              class="btn-primary inline-flex items-center gap-2 whitespace-nowrap"
            >
              <svg v-if="!loadingAnalysis" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
              </svg>
              <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              {{ loadingAnalysis ? 'Analisi…' : 'Analizza' }}
            </button>
          </div>
          <div v-if="authError" class="mt-2 flex items-center gap-1.5 text-sm text-red-600">
            <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
            {{ authError }}
          </div>
          <p class="mt-2 text-xs text-gray-400">La chiave viene salvata solo in sessione, non permanentemente.</p>
        </div>
      </div>
    </div>

    <!-- ── STEP 2: STATO FILE ──────────────────────────────────── -->
    <div v-if="analysis" class="card">
      <div class="flex items-center justify-between mb-5">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-emerald-50 rounded-xl flex items-center justify-center flex-shrink-0">
            <svg class="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
            </svg>
          </div>
          <h2>Stato file</h2>
        </div>
        <button
          @click="analyzeFiles"
          :disabled="loadingAnalysis"
          class="btn-secondary text-xs inline-flex items-center gap-1.5"
        >
          <svg class="w-3.5 h-3.5" :class="loadingAnalysis ? 'animate-spin' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          {{ loadingAnalysis ? 'Aggiornamento…' : 'Aggiorna' }}
        </button>
      </div>

      <!-- Riepilogo badge -->
      <div class="flex flex-wrap gap-2 mb-5">
        <span class="inline-flex items-center gap-1.5 bg-green-50 text-green-700 border border-green-200 px-3 py-1.5 rounded-full text-sm font-medium">
          <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>
          Download: {{ analysis.riepilogo.download }}
        </span>
        <span class="inline-flex items-center gap-1.5 bg-blue-50 text-blue-700 border border-blue-200 px-3 py-1.5 rounded-full text-sm font-medium">
          <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
          Categorie: {{ analysis.riepilogo.categorie }}
        </span>
        <span
          :class="etlBadgeClass"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border"
        >
          <span :class="etlDotClass" class="w-1.5 h-1.5 rounded-full"></span>
          ETL: {{ analysis.riepilogo.etl }}
        </span>
      </div>

      <!-- Griglia anni -->
      <div class="flex items-center justify-between mb-2">
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Anni disponibili
          <span class="font-mono text-gray-700 ml-1">{{ totalAnniOk }}/{{ totalAnni }}</span>
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="(stato, anno) in analysis.download"
          :key="anno"
          :title="stato.status === 'ok' ? `Aggiornato ${stato.age_days} giorni fa` : 'Non ancora scaricato'"
          :class="annoBadgeClass(stato.status)"
          class="px-2.5 py-1 rounded-md text-xs font-mono font-semibold border"
        >
          {{ anno }}
        </span>
      </div>
      <div class="flex gap-5 mt-3 text-xs text-gray-400">
        <span class="flex items-center gap-1.5">
          <span class="inline-block w-2.5 h-2.5 rounded-sm bg-green-50 border border-green-300"></span>
          presente
        </span>
        <span class="flex items-center gap-1.5">
          <span class="inline-block w-2.5 h-2.5 rounded-sm bg-red-50 border border-red-300"></span>
          mancante
        </span>
      </div>
    </div>

    <!-- ── STEP 3: CONFIGURAZIONE ──────────────────────────────── -->
    <div v-if="analysis && !activeJob" class="card">
      <div class="flex items-center gap-3 mb-5">
        <div class="w-10 h-10 bg-violet-50 rounded-xl flex items-center justify-center flex-shrink-0">
          <svg class="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
          </svg>
        </div>
        <h2>Configurazione</h2>
      </div>

      <!-- Selezione anni -->
      <div class="mb-6">
        <div class="flex items-center justify-between mb-3">
          <label class="text-sm font-semibold text-gray-700">Anni da elaborare</label>
          <div class="flex gap-3 text-xs">
            <button @click="selectMissing" class="text-brand-600 hover:text-brand-700 font-medium">Solo mancanti</button>
            <button @click="selectAll" class="text-brand-600 hover:text-brand-700 font-medium">Tutti</button>
            <button @click="selectedAnni = []" class="text-gray-400 hover:text-gray-600">Nessuno</button>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <label
            v-for="(stato, anno) in analysis.download"
            :key="anno"
            class="cursor-pointer select-none"
          >
            <input
              type="checkbox"
              :value="parseInt(anno)"
              v-model="selectedAnni"
              class="sr-only peer"
            />
            <span
              class="inline-block px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-all
                     peer-checked:bg-brand-600 peer-checked:text-white peer-checked:border-brand-600
                     hover:border-brand-400"
              :class="stato.status === 'ok'
                ? 'bg-green-50 border-green-200 text-green-700'
                : 'bg-red-50 border-red-200 text-red-600'"
            >
              {{ anno }}
            </span>
          </label>
        </div>
        <p v-if="selectedAnni.length === 0" class="mt-2 text-xs text-amber-600 flex items-center gap-1">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
          Seleziona almeno un anno per avviare la pipeline.
        </p>
      </div>

      <!-- Step da eseguire -->
      <div class="mb-6">
        <label class="text-sm font-semibold text-gray-700 block mb-3">Step da eseguire</label>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <label
            v-for="s in availableSteps"
            :key="s.id"
            class="flex items-center gap-3 p-3 rounded-lg border cursor-pointer select-none transition-all"
            :class="selectedSteps.includes(s.id)
              ? 'bg-brand-50 border-brand-300'
              : 'bg-gray-50 border-gray-200 hover:border-gray-300'"
          >
            <input
              type="checkbox"
              :value="s.id"
              v-model="selectedSteps"
              :disabled="s.required"
              class="rounded border-gray-300 accent-brand-600"
            />
            <span class="text-sm text-gray-800 font-medium flex-1">{{ s.label }}</span>
            <span v-if="s.badge" class="badge bg-gray-100 text-gray-500 text-xs">{{ s.badge }}</span>
          </label>
        </div>
      </div>

      <!-- Opzioni avanzate -->
      <div class="mb-6">
        <button
          @click="showAdvanced = !showAdvanced"
          class="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <svg class="w-4 h-4 transition-transform" :class="showAdvanced ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
          Opzioni avanzate
        </button>
        <div v-if="showAdvanced" class="mt-3 space-y-2 pl-5 border-l-2 border-gray-100">
          <label class="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-gray-50">
            <input type="checkbox" v-model="opts.forceAll" class="rounded border-gray-300 accent-brand-600" />
            <span class="text-sm text-gray-700">Forza ri-download anche degli anni già presenti</span>
          </label>
          <label class="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-gray-50">
            <input type="checkbox" v-model="opts.noRunts" class="rounded border-gray-300 accent-brand-600" />
            <span class="text-sm text-gray-700">Salta il merge con RUNTS (registro ETS)</span>
          </label>
          <label class="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-gray-50">
            <input type="checkbox" v-model="opts.sourcePdf" class="rounded border-gray-300 accent-brand-600" />
            <span class="text-sm text-gray-700">Usa PDF come fonte <span class="text-gray-400">(default: CSV)</span></span>
          </label>
        </div>
      </div>

      <!-- Pulsante avvio -->
      <button
        @click="startPipeline"
        :disabled="selectedAnni.length === 0 || selectedSteps.length === 0 || starting"
        class="btn-primary w-full sm:w-auto px-8 py-3 text-base font-semibold inline-flex items-center justify-center gap-2"
      >
        <svg v-if="!starting" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <svg v-else class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
        {{ starting ? 'Avvio in corso…' : 'Avvia Pipeline' }}
      </button>
    </div>

    <!-- ── STEP 4: ESECUZIONE / LOG ────────────────────────────── -->
    <div v-if="activeJob" class="card">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gray-900 rounded-xl flex items-center justify-center flex-shrink-0">
            <svg class="w-5 h-5 text-emerald-400" :class="activeJob.status === 'running' ? 'animate-pulse' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
            </svg>
          </div>
          <h2>Esecuzione</h2>
        </div>
        <span :class="jobStatusClass" class="badge text-xs font-semibold px-3 py-1.5">
          {{ jobStatusLabel }}
        </span>
      </div>

      <!-- Metadati job -->
      <div class="flex flex-wrap gap-x-5 gap-y-1 mb-4 text-xs text-gray-400 bg-gray-50 rounded-lg px-4 py-2.5 border border-gray-100">
        <span>Avviato: <strong class="text-gray-600">{{ formatDate(activeJob.started_at) }}</strong></span>
        <span v-if="activeJob.finished_at">Terminato: <strong class="text-gray-600">{{ formatDate(activeJob.finished_at) }}</strong></span>
        <span>Anni: <strong class="text-gray-600 font-mono">{{ activeJob.anni || 'tutti' }}</strong></span>
        <span>Step: <strong class="text-gray-600 font-mono">{{ activeJob.steps.join(', ') }}</strong></span>
      </div>

      <!-- Log viewer -->
      <div class="rounded-xl overflow-hidden border border-gray-800">
        <div class="bg-gray-900 px-4 py-2 flex items-center gap-2 border-b border-gray-800">
          <span class="w-3 h-3 rounded-full bg-red-500 opacity-70"></span>
          <span class="w-3 h-3 rounded-full bg-yellow-500 opacity-70"></span>
          <span class="w-3 h-3 rounded-full bg-green-500 opacity-70"></span>
          <span class="ml-2 text-xs text-gray-500 font-mono">pipeline.log</span>
          <span v-if="activeJob.status === 'running'" class="ml-auto flex items-center gap-1.5 text-xs text-emerald-400">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            live
          </span>
        </div>
        <div
          ref="logBox"
          class="bg-gray-950 text-emerald-400 text-xs font-mono p-4 h-80 overflow-y-auto whitespace-pre-wrap leading-relaxed"
        >{{ logContent || 'In attesa dei log…' }}</div>
      </div>

      <!-- Azioni post-job -->
      <div v-if="activeJob.status !== 'running'" class="mt-4 flex flex-wrap gap-3">
        <button @click="resetAndAnalyze" class="btn-primary inline-flex items-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Nuova analisi
        </button>
        <button @click="activeJob = null" class="btn-secondary">
          Configura altra esecuzione
        </button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, nextTick, onUnmounted } from 'vue'
import {
  pipelineAnalyze,
  pipelineRun,
  pipelineJobDetail,
} from '../api/client.js'

// ── Stato ─────────────────────────────────────────────────────────────────
const apiKey          = ref(sessionStorage.getItem('pipeline_key') || '')
const loadingAnalysis = ref(false)
const authError       = ref('')
const analysis        = ref(null)
const selectedAnni    = ref([])
const showAdvanced    = ref(false)
const starting        = ref(false)
const activeJob       = ref(null)
const logContent      = ref('')
const logBox          = ref(null)
let pollTimer         = null

const opts = ref({
  forceAll:  false,
  noRunts:   false,
  sourcePdf: false,
})

const availableSteps = [
  { id: 'download',  label: 'Download elenco completo', required: false },
  { id: 'categorie', label: 'Download per categoria',   required: false, badge: 'richiede categorie.xlsx' },
  { id: 'etl',       label: 'Elaborazione (ETL)',        required: false },
  { id: 'report',    label: 'Report Excel',              required: false, badge: 'opzionale' },
  { id: 'gsheets',   label: 'Upload Google Sheets',      required: false, badge: 'opt-in' },
]

const selectedSteps = ref(['download', 'etl'])

// ── Computed ───────────────────────────────────────────────────────────────
const totalAnni   = computed(() => analysis.value ? Object.keys(analysis.value.download).length : 0)
const totalAnniOk = computed(() => analysis.value
  ? Object.values(analysis.value.download).filter(s => s.status === 'ok').length
  : 0
)

const etlBadgeClass = computed(() => {
  const s = analysis.value?.riepilogo?.etl
  if (s === 'ok')      return 'bg-green-50 text-green-700'
  if (s === 'stale')   return 'bg-amber-50 text-amber-700'
  return 'bg-red-50 text-red-700'
})
const etlDotClass = computed(() => {
  const s = analysis.value?.riepilogo?.etl
  if (s === 'ok')    return 'bg-green-500'
  if (s === 'stale') return 'bg-amber-500'
  return 'bg-red-500'
})

const jobStatusClass = computed(() => {
  const s = activeJob.value?.status
  if (s === 'running')   return 'bg-blue-100 text-blue-700'
  if (s === 'completed') return 'bg-green-100 text-green-700'
  return 'bg-red-100 text-red-700'
})
const jobStatusLabel = computed(() => {
  const s = activeJob.value?.status
  if (s === 'running')   return '⏳ In esecuzione'
  if (s === 'completed') return '✅ Completato'
  return '❌ Errore'
})

// ── Metodi ─────────────────────────────────────────────────────────────────
function annoBadgeClass(status) {
  return status === 'ok'
    ? 'bg-green-50 border-green-300 text-green-700'
    : 'bg-red-50 border-red-300 text-red-600'
}

function selectMissing() {
  selectedAnni.value = Object.entries(analysis.value.download)
    .filter(([, s]) => s.status !== 'ok')
    .map(([a]) => parseInt(a))
}

function selectAll() {
  selectedAnni.value = Object.keys(analysis.value.download).map(a => parseInt(a))
}

async function analyzeFiles() {
  if (!apiKey.value) return
  authError.value = ''
  loadingAnalysis.value = true
  try {
    sessionStorage.setItem('pipeline_key', apiKey.value)
    const res = await pipelineAnalyze(apiKey.value)
    analysis.value = res.data
    // Pre-seleziona anni mancanti
    selectedAnni.value = (res.data.anni_mancanti_download || [])
    // Pre-seleziona step suggeriti (escludi gsheets di default)
    const suggeriti = (res.data.steps_necessari || []).filter(s => s !== 'gsheets' && s !== 'report')
    if (suggeriti.length) selectedSteps.value = suggeriti
  } catch (e) {
    if (e.response?.status === 401) {
      authError.value = 'API key non valida.'
      sessionStorage.removeItem('pipeline_key')
    } else {
      authError.value = `Errore: ${e.response?.data?.detail || e.message}`
    }
  } finally {
    loadingAnalysis.value = false
  }
}

async function startPipeline() {
  starting.value = true
  try {
    const payload = {
      anni:          selectedAnni.value.sort().join(','),
      steps:         selectedSteps.value,
      skip_gsheets:  !selectedSteps.value.includes('gsheets'),
      skip_report:   !selectedSteps.value.includes('report'),
      no_runts:      opts.value.noRunts,
      source:        opts.value.sourcePdf ? 'pdf' : 'csv',
      smart:         !opts.value.forceAll,
    }
    const res = await pipelineRun(apiKey.value, payload)
    activeJob.value = res.data
    logContent.value = ''
    startPolling(res.data.job_id)
  } catch (e) {
    authError.value = `Avvio fallito: ${e.response?.data?.detail || e.message}`
  } finally {
    starting.value = false
  }
}

function startPolling(jobId) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await pipelineJobDetail(apiKey.value, jobId)
      activeJob.value = { ...activeJob.value, ...res.data }
      logContent.value = res.data.logs || ''
      scrollLog()
      if (res.data.status !== 'running') stopPolling()
    } catch {
      stopPolling()
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

async function resetAndAnalyze() {
  activeJob.value = null
  logContent.value = ''
  await analyzeFiles()
}

function scrollLog() {
  nextTick(() => {
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  })
}

function formatDate(iso) {
  if (!iso) return '–'
  return new Date(iso).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'medium' })
}

onUnmounted(stopPolling)

// Auto-analizza se la chiave è già salvata
if (apiKey.value) analyzeFiles()
</script>
