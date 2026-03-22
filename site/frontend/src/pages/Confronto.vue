<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-6">
      <h1 class="mb-1">Confronto enti</h1>
      <p class="text-gray-500">Confronta fino a 5 enti inserendo i loro codici fiscali.</p>
    </div>

    <!-- Ricerca per nome -->
    <div class="card mb-4">
      <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Cerca ente per nome</p>
      <div class="relative">
        <input
          v-model="searchNome"
          placeholder="Es. Croce Rossa, Caritas…"
          class="input-field pr-8"
          @input="onSearchNome"
        />
        <svg class="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
      </div>
      <!-- Risultati dropdown -->
      <div v-if="searchResults.length" class="mt-2 border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
        <button
          v-for="r in searchResults"
          :key="r.cod_fiscale"
          @click="addFromSearch(r)"
          class="w-full flex items-center gap-3 px-3 py-2 hover:bg-brand-50 text-left transition-colors"
        >
          <span class="font-mono text-xs text-gray-400 w-32 flex-shrink-0">{{ r.cod_fiscale }}</span>
          <span class="text-sm font-medium text-gray-800 flex-1 truncate">{{ r.denominazione }}</span>
          <span class="text-xs text-gray-400 flex-shrink-0">{{ r.regione }}</span>
          <svg class="w-4 h-4 text-brand-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
        </button>
      </div>
      <p v-if="searchNome.length >= 2 && !searchResults.length && !searchLoading" class="text-xs text-gray-400 mt-2">Nessun ente trovato.</p>
    </div>

    <!-- Input CF -->
    <div class="card mb-6">
      <div class="space-y-3 mb-4">
        <div
          v-for="(cf, i) in cfList"
          :key="i"
          class="flex items-center gap-2"
        >
          <span class="w-6 h-6 flex-shrink-0 flex items-center justify-center rounded-full text-xs font-bold text-white"
            :style="{ backgroundColor: COLORS[i] }">
            {{ i + 1 }}
          </span>
          <input
            v-model="cfList[i]"
            :placeholder="`Codice fiscale ${i + 1}${i === 0 ? ' (obbligatorio)' : ' (opzionale)'}`"
            class="input-field font-mono text-sm flex-1"
            @keyup.enter="compare"
            maxlength="20"
          />
          <button
            v-if="cfList.length > 1"
            @click="removeCf(i)"
            class="p-2 text-gray-400 hover:text-red-500 transition-colors flex-shrink-0"
            title="Rimuovi"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <button
          v-if="cfList.length < 5"
          @click="addCf"
          class="btn-secondary text-sm"
        >
          + Aggiungi ente
        </button>
        <button
          class="btn-primary gap-2 inline-flex items-center"
          :disabled="loading || !cfList[0]"
          @click="compare"
        >
          <svg v-if="!loading" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
          </svg>
          <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
          </svg>
          <span>{{ loading ? 'Caricamento…' : 'Confronta' }}</span>
        </button>
        <button v-if="result" class="btn-secondary text-sm" @click="reset">Reset</button>
      </div>
    </div>

    <!-- Errore -->
    <div v-if="error" class="card border-red-200 bg-red-50 flex items-center gap-3 mb-6 p-4">
      <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
      </svg>
      <span class="text-sm text-red-700">{{ error }}</span>
    </div>

    <template v-if="result">
      <!-- Card riassuntive per ente -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-8">
        <div
          v-for="(ente, i) in entiTrovati"
          :key="ente.cf"
          class="card"
          :style="{ borderTopColor: COLORS[i], borderTopWidth: '3px' }"
        >
          <div class="flex items-start gap-2 mb-3">
            <span class="w-6 h-6 flex-shrink-0 flex items-center justify-center rounded-full text-xs font-bold text-white mt-0.5"
              :style="{ backgroundColor: COLORS[i] }">
              {{ i + 1 }}
            </span>
            <div class="min-w-0">
              <p class="font-semibold text-gray-900 text-sm leading-snug">{{ ente.denominazione }}</p>
              <p class="font-mono text-xs text-gray-400 mt-0.5">{{ ente.cf }}</p>
            </div>
          </div>
          <div class="space-y-1.5 text-xs">
            <div class="flex justify-between">
              <span class="text-gray-400">Categoria</span>
              <span class="font-medium text-gray-700 capitalize">{{ ente.categoria?.replace(/_/g, ' ') ?? '–' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-400">Anni presenti</span>
              <span class="font-medium text-gray-700">{{ ente.anni_presenti }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-400">Totale cumulato</span>
              <span class="font-semibold text-brand-700">{{ formatEur(ente.totale_cumulato) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-400">Anno migliore</span>
              <span class="font-medium text-gray-700">{{ ente.anno_migliore }}</span>
            </div>
          </div>
          <div class="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2">
            <span v-if="ente.runts" class="badge bg-green-100 text-green-700 text-xs">✓ RUNTS</span>
            <span class="badge bg-gray-100 text-gray-500 text-xs">{{ ente.regione }}</span>
          </div>
        </div>
      </div>

      <!-- Tabella confronto per anno -->
      <div class="card mb-8">
        <h2 class="mb-4">Importo totale per anno</h2>

        <!-- Barre per anno -->
        <div class="space-y-6">
          <div v-for="anno in anniConDati" :key="anno">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-sm font-semibold text-gray-600 w-12 text-right flex-shrink-0">{{ anno }}</span>
              <div class="flex-1 space-y-1.5">
                <div
                  v-for="(ente, i) in entiTrovati"
                  :key="ente.cf"
                  class="flex items-center gap-2"
                >
                  <div class="w-3 h-3 rounded-full flex-shrink-0" :style="{ backgroundColor: COLORS[i] }"></div>
                  <div class="flex-1 h-7 bg-gray-100 rounded-md overflow-hidden">
                    <div
                      class="h-full rounded-md transition-all duration-700 ease-out flex items-center justify-end pr-2"
                      :style="{
                        width: animated ? barWidth(ente, anno) : '0%',
                        backgroundColor: COLORS[i],
                        opacity: ente.storico[anno] ? '1' : '0.15',
                        minWidth: ente.storico[anno]?.importo_totale > 0 ? '4px' : '0',
                      }"
                    >
                      <span v-if="barWidthNum(ente, anno) > 30" class="text-xs font-medium text-white whitespace-nowrap">
                        {{ formatEur(ente.storico[anno]?.importo_totale) }}
                      </span>
                    </div>
                  </div>
                  <span class="w-28 text-xs text-gray-600 font-medium text-right flex-shrink-0">
                    <span v-if="barWidthNum(ente, anno) <= 30 && ente.storico[anno]">
                      {{ formatEur(ente.storico[anno]?.importo_totale) }}
                    </span>
                    <span v-else-if="!ente.storico[anno]" class="text-gray-300">n.d.</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Tabella numerica dettagliata -->
      <div class="card p-0 overflow-hidden mb-8">
        <div class="px-6 py-4 border-b border-gray-100">
          <h2>Dettaglio numerico</h2>
        </div>
        <div class="table-wrap rounded-none border-0">
          <table>
            <thead>
              <tr>
                <th>Anno</th>
                <th
                  v-for="(ente, i) in entiTrovati"
                  :key="ente.cf"
                  class="text-right"
                >
                  <span class="inline-flex items-center gap-1.5">
                    <span class="w-2.5 h-2.5 rounded-full flex-shrink-0" :style="{ backgroundColor: COLORS[i] }"></span>
                    <span class="truncate max-w-[120px]" :title="ente.denominazione">
                      {{ ente.denominazione?.split(' ').slice(0,3).join(' ') ?? ente.cf }}
                    </span>
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="anno in [...anniConDati].reverse()" :key="anno">
                <td class="font-medium text-gray-500 tabular-nums">{{ anno }}</td>
                <td
                  v-for="ente in entiTrovati"
                  :key="ente.cf"
                  class="text-right tabular-nums"
                  :class="ente.storico[anno] ? 'text-brand-700 font-semibold' : 'text-gray-300'"
                >
                  {{ ente.storico[anno] ? formatEur(ente.storico[anno].importo_totale) : '–' }}
                </td>
              </tr>
              <!-- Totale riga -->
              <tr class="bg-gray-50 font-semibold border-t-2 border-gray-200">
                <td class="text-gray-700">Totale</td>
                <td
                  v-for="ente in entiTrovati"
                  :key="ente.cf"
                  class="text-right tabular-nums text-brand-700"
                >
                  {{ formatEur(ente.totale_cumulato) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Scelte per anno -->
      <div class="card p-0 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-100">
          <h2>Numero di scelte per anno</h2>
        </div>
        <div class="table-wrap rounded-none border-0">
          <table>
            <thead>
              <tr>
                <th>Anno</th>
                <th
                  v-for="(ente, i) in entiTrovati"
                  :key="ente.cf"
                  class="text-right"
                >
                  <span class="inline-flex items-center gap-1.5">
                    <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: COLORS[i] }"></span>
                    {{ ente.denominazione?.split(' ').slice(0,3).join(' ') ?? ente.cf }}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="anno in [...anniConDati].reverse()" :key="anno">
                <td class="font-medium text-gray-500 tabular-nums">{{ anno }}</td>
                <td
                  v-for="ente in entiTrovati"
                  :key="ente.cf"
                  class="text-right tabular-nums"
                  :class="ente.storico[anno] ? 'text-gray-800' : 'text-gray-300'"
                >
                  {{ ente.storico[anno] ? formatNum(ente.storico[anno].n_scelte) : '–' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { fetchConfronta, fetchCercaCf } from '@/api/client'

const COLORS = ['#3b82f6', '#10b981', '#ef4444', '#f59e0b', '#8b5cf6']

const cfList       = ref(['', ''])
const result       = ref(null)
const loading      = ref(false)
const error        = ref('')
const animated     = ref(false)
const searchNome   = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
let   searchTimer  = null

async function onSearchNome() {
  clearTimeout(searchTimer)
  searchResults.value = []
  if (searchNome.value.length < 2) return
  searchTimer = setTimeout(async () => {
    searchLoading.value = true
    try {
      const res = await fetchCercaCf(searchNome.value)
      searchResults.value = res.data
    } catch { /* ignora */ } finally {
      searchLoading.value = false
    }
  }, 300)
}

function addFromSearch(r) {
  // Trova il primo slot vuoto o aggiunge
  const emptyIdx = cfList.value.findIndex(v => !v.trim())
  if (emptyIdx !== -1) {
    cfList.value[emptyIdx] = r.cod_fiscale
  } else if (cfList.value.length < 5) {
    cfList.value.push(r.cod_fiscale)
  }
  searchNome.value   = ''
  searchResults.value = []
}

const entiTrovati = computed(() => result.value?.enti.filter(e => e.trovato) ?? [])

const anniConDati = computed(() => {
  if (!result.value) return []
  const anni = result.value.anni_disponibili
  // Tieni solo anni in cui almeno un ente ha dati
  return anni.filter(a => entiTrovati.value.some(e => e.storico[a]))
})

const maxImportoPerAnno = computed(() => {
  const m = {}
  for (const anno of anniConDati.value) {
    m[anno] = Math.max(...entiTrovati.value.map(e => e.storico[anno]?.importo_totale ?? 0), 1)
  }
  return m
})

function barWidthNum(ente, anno) {
  const imp = ente.storico[anno]?.importo_totale ?? 0
  const max = maxImportoPerAnno.value[anno] ?? 1
  return (imp / max) * 100
}

function barWidth(ente, anno) {
  return barWidthNum(ente, anno).toFixed(1) + '%'
}

const formatNum = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'

function addCf() {
  if (cfList.value.length < 5) cfList.value.push('')
}

function removeCf(i) {
  cfList.value.splice(i, 1)
}

function reset() {
  cfList.value = ['', '']
  result.value = null
  error.value  = ''
  animated.value = false
}

async function compare() {
  const cfs = cfList.value.map(s => s.trim().toUpperCase()).filter(Boolean)
  if (!cfs.length) return

  loading.value  = true
  error.value    = ''
  result.value   = null
  animated.value = false

  try {
    const res = await fetchConfronta(cfs)
    result.value = res.data

    const nonTrovati = res.data.enti.filter(e => !e.trovato).map(e => e.cf)
    if (nonTrovati.length) {
      error.value = `Codici fiscali non trovati: ${nonTrovati.join(', ')}`
    }

    setTimeout(() => { animated.value = true }, 100)
  } catch {
    error.value = 'Errore nel caricamento. Verifica i codici fiscali e riprova.'
  } finally {
    loading.value = false
  }
}
</script>
