<template>
  <div class="max-w-4xl mx-auto px-4 py-8 space-y-6">

    <!-- Intestazione -->
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Gestione Pipeline</h1>
      <p class="mt-1 text-gray-500">
        Scarica e aggiorna i dati 5×1000 dall'Agenzia delle Entrate, step by step.
      </p>
    </div>

    <!-- ── STEP 1: ACCESSO ─────────────────────────────────────── -->
    <section class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <h2 class="font-semibold text-gray-800 mb-3">🔑 Accesso</h2>
      <div class="flex gap-3 items-center">
        <input
          v-model="apiKey"
          type="password"
          placeholder="Inserisci la API key..."
          class="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          @keyup.enter="analyzeFiles"
        />
        <button
          @click="analyzeFiles"
          :disabled="!apiKey || loadingAnalysis"
          class="px-5 py-2 bg-brand-700 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {{ loadingAnalysis ? 'Analisi…' : 'Analizza' }}
        </button>
      </div>
      <p v-if="authError" class="mt-2 text-sm text-red-600">{{ authError }}</p>
      <p class="mt-2 text-xs text-gray-400">La chiave non viene memorizzata permanentemente.</p>
    </section>

    <!-- ── STEP 2: STATO FILE ──────────────────────────────────── -->
    <section v-if="analysis" class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-gray-800">📂 Stato file</h2>
        <button
          @click="analyzeFiles"
          :disabled="loadingAnalysis"
          class="text-xs text-brand-700 hover:underline disabled:opacity-40"
        >
          {{ loadingAnalysis ? 'Aggiornamento…' : '↻ Aggiorna' }}
        </button>
      </div>

      <!-- Riepilogo badge -->
      <div class="flex flex-wrap gap-3 mb-5">
        <div class="flex items-center gap-1.5 bg-green-50 text-green-700 px-3 py-1.5 rounded-full text-sm font-medium">
          <span class="w-2 h-2 rounded-full bg-green-500 inline-block"></span>
          Download: {{ analysis.riepilogo.download }}
        </div>
        <div class="flex items-center gap-1.5 bg-blue-50 text-blue-700 px-3 py-1.5 rounded-full text-sm font-medium">
          <span class="w-2 h-2 rounded-full bg-blue-500 inline-block"></span>
          Categorie: {{ analysis.riepilogo.categorie }}
        </div>
        <div
          :class="etlBadgeClass"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium"
        >
          <span :class="etlDotClass" class="w-2 h-2 rounded-full inline-block"></span>
          ETL: {{ analysis.riepilogo.etl }}
        </div>
      </div>

      <!-- Griglia anni -->
      <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Anni disponibili ({{ totalAnniOk }} / {{ totalAnni }})</p>
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
      <div class="flex gap-4 mt-3 text-xs text-gray-400">
        <span><span class="inline-block w-2.5 h-2.5 rounded-sm bg-green-100 border border-green-400 mr-1"></span>presente</span>
        <span><span class="inline-block w-2.5 h-2.5 rounded-sm bg-red-100 border border-red-400 mr-1"></span>mancante</span>
      </div>
    </section>

    <!-- ── STEP 3: CONFIGURAZIONE ──────────────────────────────── -->
    <section v-if="analysis && !activeJob" class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <h2 class="font-semibold text-gray-800 mb-4">⚙️ Cosa vuoi aggiornare?</h2>

      <!-- Selezione anni -->
      <div class="mb-5">
        <div class="flex items-center justify-between mb-2">
          <label class="text-sm font-medium text-gray-700">Anni da elaborare</label>
          <div class="flex gap-3 text-xs">
            <button @click="selectMissing" class="text-brand-700 hover:underline">Solo mancanti</button>
            <button @click="selectAll" class="text-brand-700 hover:underline">Tutti</button>
            <button @click="selectedAnni = []" class="text-gray-400 hover:underline">Nessuno</button>
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <label
            v-for="(stato, anno) in analysis.download"
            :key="anno"
            class="flex items-center gap-1.5 cursor-pointer select-none"
          >
            <input
              type="checkbox"
              :value="parseInt(anno)"
              v-model="selectedAnni"
              class="rounded border-gray-300 text-brand-700 focus:ring-brand-500"
            />
            <span class="text-sm font-mono" :class="stato.status === 'ok' ? 'text-gray-600' : 'text-red-600 font-semibold'">
              {{ anno }}
            </span>
          </label>
        </div>
        <p v-if="selectedAnni.length === 0" class="mt-2 text-xs text-amber-600">
          Seleziona almeno un anno per avviare la pipeline.
        </p>
      </div>

      <!-- Step da eseguire -->
      <div class="mb-5">
        <label class="text-sm font-medium text-gray-700 block mb-2">Step da eseguire</label>
        <div class="flex flex-wrap gap-4">
          <label v-for="s in availableSteps" :key="s.id" class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              :value="s.id"
              v-model="selectedSteps"
              :disabled="s.required"
              class="rounded border-gray-300 text-brand-700 focus:ring-brand-500"
            />
            <span class="text-sm text-gray-700">{{ s.label }}</span>
            <span v-if="s.badge" class="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{{ s.badge }}</span>
          </label>
        </div>
      </div>

      <!-- Opzioni -->
      <div class="mb-6">
        <button
          @click="showAdvanced = !showAdvanced"
          class="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
        >
          <span>{{ showAdvanced ? '▾' : '▸' }}</span> Opzioni avanzate
        </button>
        <div v-if="showAdvanced" class="mt-3 space-y-3 pl-4 border-l-2 border-gray-100">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="opts.forceAll" class="rounded border-gray-300 text-brand-700" />
            <span class="text-sm text-gray-700">Forza ri-download anche degli anni già presenti</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="opts.noRunts" class="rounded border-gray-300 text-brand-700" />
            <span class="text-sm text-gray-700">Salta il merge con RUNTS (registro ETS)</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="opts.sourcePdf" class="rounded border-gray-300 text-brand-700" />
            <span class="text-sm text-gray-700">Usa PDF come fonte (default: CSV)</span>
          </label>
        </div>
      </div>

      <!-- Pulsante avvio -->
      <button
        @click="startPipeline"
        :disabled="selectedAnni.length === 0 || selectedSteps.length === 0 || starting"
        class="w-full sm:w-auto px-8 py-3 bg-brand-700 text-white font-semibold rounded-lg hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {{ starting ? 'Avvio in corso…' : '▶ Avvia Pipeline' }}
      </button>
    </section>

    <!-- ── STEP 4: ESECUZIONE / LOG ────────────────────────────── -->
    <section v-if="activeJob" class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-gray-800">🚀 Esecuzione</h2>
        <span :class="jobStatusClass" class="px-3 py-1 rounded-full text-xs font-semibold">
          {{ jobStatusLabel }}
        </span>
      </div>

      <!-- Metadati job -->
      <div class="text-xs text-gray-400 mb-4 flex flex-wrap gap-x-4 gap-y-1">
        <span>Avviato: {{ formatDate(activeJob.started_at) }}</span>
        <span v-if="activeJob.finished_at">Terminato: {{ formatDate(activeJob.finished_at) }}</span>
        <span>Anni: {{ activeJob.anni || 'tutti' }}</span>
        <span>Step: {{ activeJob.steps.join(', ') }}</span>
      </div>

      <!-- Log viewer -->
      <div
        ref="logBox"
        class="bg-gray-950 text-green-400 text-xs font-mono rounded-lg p-4 h-80 overflow-y-auto whitespace-pre-wrap leading-relaxed"
      >{{ logContent || 'In attesa dei log…' }}</div>

      <!-- Azioni post-job -->
      <div v-if="activeJob.status !== 'running'" class="mt-4 flex flex-wrap gap-3">
        <button
          @click="resetAndAnalyze"
          class="px-5 py-2 bg-brand-700 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
        >
          ↻ Nuova analisi
        </button>
        <button
          @click="activeJob = null"
          class="px-5 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
        >
          Configura altra esecuzione
        </button>
      </div>
    </section>

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
