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

    <!-- ── Vista YoY singolo ente ── -->
    <template v-if="result && isSingleMode">
      <!-- Scheda ente (printable/card) -->
      <div id="entity-card" class="card mb-6 print:shadow-none print:border-0">
        <div class="flex flex-wrap items-start justify-between gap-4 mb-4">
          <div class="flex items-start gap-3">
            <div class="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
              :style="{ backgroundColor: COLORS[0] }">
              {{ initials(entiTrovati[0]?.denominazione) }}
            </div>
            <div>
              <h2 class="font-bold text-gray-900 text-lg leading-snug">{{ entiTrovati[0]?.denominazione }}</h2>
              <p class="font-mono text-xs text-gray-400 mt-0.5">{{ entiTrovati[0]?.cf }}</p>
              <div class="flex flex-wrap gap-1.5 mt-1.5">
                <span class="badge bg-gray-100 text-gray-600 text-xs capitalize">
                  {{ entiTrovati[0]?.categoria?.replace(/_/g,' ') ?? '–' }}
                </span>
                <span class="badge bg-gray-100 text-gray-600 text-xs">{{ entiTrovati[0]?.regione }}</span>
                <span v-if="entiTrovati[0]?.runts" class="badge bg-green-100 text-green-700 text-xs">✓ RUNTS</span>
              </div>
            </div>
          </div>
          <div class="flex gap-2 print:hidden">
            <button class="btn-secondary text-xs inline-flex items-center gap-1.5" @click="downloadCard">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              Scarica scheda
            </button>
            <button class="btn-secondary text-xs inline-flex items-center gap-1.5" @click="printCard">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/>
              </svg>
              Stampa
            </button>
          </div>
        </div>

        <!-- KPI highlights -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          <div class="bg-brand-50 rounded-lg p-3">
            <p class="text-xs text-brand-500 font-medium uppercase tracking-wide mb-0.5">Anni presenti</p>
            <p class="text-xl font-bold text-brand-700">{{ entiTrovati[0]?.anni_presenti }}</p>
          </div>
          <div class="bg-emerald-50 rounded-lg p-3">
            <p class="text-xs text-emerald-500 font-medium uppercase tracking-wide mb-0.5">Totale cumulato</p>
            <p class="text-xl font-bold text-emerald-700">{{ formatEur(entiTrovati[0]?.totale_cumulato) }}</p>
          </div>
          <div class="bg-violet-50 rounded-lg p-3">
            <p class="text-xs text-violet-500 font-medium uppercase tracking-wide mb-0.5">Anno migliore</p>
            <p class="text-xl font-bold text-violet-700">{{ entiTrovati[0]?.anno_migliore }}</p>
          </div>
          <div
            class="rounded-lg p-3"
            :class="lastYoY !== null && lastYoY >= 0 ? 'bg-green-50' : 'bg-red-50'"
          >
            <p class="text-xs font-medium uppercase tracking-wide mb-0.5"
              :class="lastYoY !== null && lastYoY >= 0 ? 'text-green-500' : 'text-red-500'">
              YoY ultimo anno
            </p>
            <p class="text-xl font-bold"
              :class="lastYoY !== null && lastYoY >= 0 ? 'text-green-700' : 'text-red-700'">
              {{ lastYoY !== null ? (lastYoY >= 0 ? '+' : '') + lastYoY.toFixed(1) + '%' : '–' }}
            </p>
          </div>
        </div>

        <!-- Grafico YoY -->
        <h3 class="text-sm font-semibold text-gray-700 mb-3">Confronto anno su anno (YoY)</h3>
        <div class="space-y-2 mb-2">
          <div
            v-for="(row, idx) in yoyRows"
            :key="row.anno"
            class="flex items-center gap-3"
          >
            <div class="w-12 text-right text-sm font-medium text-gray-500 flex-shrink-0">{{ row.anno }}</div>
            <!-- Barra importo -->
            <div class="flex-1 h-7 bg-gray-100 rounded-lg overflow-hidden">
              <div
                class="h-full rounded-lg transition-all duration-700 ease-out flex items-center justify-end pr-2"
                :style="{
                  width: animated ? ((row.importo / maxImporto) * 100).toFixed(1) + '%' : '0%',
                  backgroundColor: COLORS[0],
                  minWidth: row.importo > 0 ? '4px' : '0',
                }"
              >
                <span v-if="(row.importo / maxImporto) > 0.3" class="text-xs font-semibold text-white whitespace-nowrap">
                  {{ formatEur(row.importo) }}
                </span>
              </div>
            </div>
            <!-- Importo se barra corta -->
            <div class="w-24 flex-shrink-0 text-right text-xs font-semibold tabular-nums text-gray-700">
              <span v-if="(row.importo / maxImporto) <= 0.3">{{ formatEur(row.importo) }}</span>
            </div>
            <!-- Badge YoY -->
            <div class="w-16 flex-shrink-0 text-right">
              <span
                v-if="idx > 0 && row.yoy !== null"
                class="inline-block text-xs font-bold px-1.5 py-0.5 rounded-full"
                :class="row.yoy >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
              >
                {{ row.yoy >= 0 ? '▲' : '▼' }} {{ Math.abs(row.yoy).toFixed(1) }}%
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tabella numerica singolo ente -->
      <div class="card p-0 overflow-hidden mb-8">
        <div class="px-6 py-4 border-b border-gray-100">
          <h2>Storico completo</h2>
        </div>
        <div class="table-wrap rounded-none border-0">
          <table>
            <thead>
              <tr>
                <th>Anno</th>
                <th class="text-right">Importo</th>
                <th class="text-right">Scelte</th>
                <th class="text-right">YoY importo</th>
                <th class="text-right">YoY scelte</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in yoyRows" :key="row.anno">
                <td class="font-medium text-gray-500 tabular-nums">{{ row.anno }}</td>
                <td class="text-right tabular-nums font-semibold text-brand-700">{{ formatEur(row.importo) }}</td>
                <td class="text-right tabular-nums text-gray-700">{{ formatNum(row.scelte) }}</td>
                <td class="text-right tabular-nums">
                  <span v-if="idx > 0 && row.yoy !== null"
                    class="inline-block text-xs font-bold px-1.5 py-0.5 rounded-full"
                    :class="row.yoy >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
                    {{ row.yoy >= 0 ? '+' : '' }}{{ row.yoy.toFixed(1) }}%
                  </span>
                  <span v-else class="text-gray-300 text-xs">–</span>
                </td>
                <td class="text-right tabular-nums">
                  <span v-if="idx > 0 && row.yoyScelte !== null"
                    class="inline-block text-xs font-bold px-1.5 py-0.5 rounded-full"
                    :class="row.yoyScelte >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
                    {{ row.yoyScelte >= 0 ? '+' : '' }}{{ row.yoyScelte.toFixed(1) }}%
                  </span>
                  <span v-else class="text-gray-300 text-xs">–</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ── Vista confronto multi-ente ── -->
    <template v-if="result && !isSingleMode">
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
    </template><!-- end multi-ente -->

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { fetchConfronta, fetchCercaCf } from '@/api/client'

const router = useRouter()

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

// True se caricato un solo ente → vista YoY
const isSingleMode = computed(() => entiTrovati.value.length === 1)

const anniConDati = computed(() => {
  if (!result.value) return []
  const anni = result.value.anni_disponibili
  return anni.filter(a => entiTrovati.value.some(e => e.storico[a]))
})

// Righe YoY per singolo ente (ordinato crescente per anno)
const yoyRows = computed(() => {
  if (!isSingleMode.value) return []
  const ente = entiTrovati.value[0]
  const anni = anniConDati.value // già ordinato crescente
  return anni.map((anno, idx) => {
    const cur  = ente.storico[anno]
    const prev = idx > 0 ? ente.storico[anni[idx - 1]] : null
    const importo = cur?.importo_totale ?? 0
    const scelte  = cur?.n_scelte ?? 0
    const yoy = prev && prev.importo_totale
      ? +((importo - prev.importo_totale) / prev.importo_totale * 100).toFixed(2)
      : null
    const yoyScelte = prev && prev.n_scelte
      ? +((scelte - prev.n_scelte) / prev.n_scelte * 100).toFixed(2)
      : null
    return { anno, importo, scelte, yoy, yoyScelte }
  })
})

const maxImporto = computed(() => {
  if (!yoyRows.value.length) return 1
  return Math.max(...yoyRows.value.map(r => r.importo), 1)
})

const lastYoY = computed(() => {
  if (!yoyRows.value.length) return null
  return yoyRows.value.at(-1)?.yoy ?? null
})

function initials(name) {
  if (!name) return '?'
  return name.split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase()
}

function printCard() {
  window.print()
}

function downloadCard() {
  // Genera un mini HTML stampabile con i dati dell'ente e lo scarica
  const ente = entiTrovati.value[0]
  if (!ente) return

  const rows = yoyRows.value.map(r => `
    <tr>
      <td>${r.anno}</td>
      <td>${formatEur(r.importo)}</td>
      <td>${formatNum(r.scelte)}</td>
      <td>${r.yoy !== null ? (r.yoy >= 0 ? '+' : '') + r.yoy.toFixed(1) + '%' : '–'}</td>
    </tr>`).join('')

  const html = `<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>Scheda 5×1000 — ${ente.denominazione}</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #111; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  .sub { color: #666; font-size: 13px; margin-bottom: 24px; }
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
  .kpi { background: #f3f4f6; border-radius: 8px; padding: 12px; }
  .kpi .label { font-size: 10px; text-transform: uppercase; color: #666; margin-bottom: 4px; }
  .kpi .value { font-size: 18px; font-weight: bold; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #f3f4f6; padding: 8px 12px; text-align: left; border-bottom: 2px solid #e5e7eb; }
  td { padding: 7px 12px; border-bottom: 1px solid #f3f4f6; }
  .footer { margin-top: 24px; font-size: 11px; color: #aaa; }
</style>
</head>
<body>
<h1>${ente.denominazione}</h1>
<p class="sub">${ente.cf} &bull; ${ente.categoria?.replace(/_/g,' ') ?? ''} &bull; ${ente.regione ?? ''}</p>
<div class="kpis">
  <div class="kpi"><div class="label">Anni presenti</div><div class="value">${ente.anni_presenti}</div></div>
  <div class="kpi"><div class="label">Totale cumulato</div><div class="value">${formatEur(ente.totale_cumulato)}</div></div>
  <div class="kpi"><div class="label">Anno migliore</div><div class="value">${ente.anno_migliore}</div></div>
  <div class="kpi"><div class="label">YoY ultimo anno</div><div class="value">${lastYoY.value !== null ? (lastYoY.value >= 0 ? '+' : '') + lastYoY.value.toFixed(1) + '%' : '–'}</div></div>
</div>
<table>
  <thead><tr><th>Anno</th><th>Importo</th><th>Scelte</th><th>YoY</th></tr></thead>
  <tbody>${rows}</tbody>
</table>
<p class="footer">Fonte: Agenzia delle Entrate — dati 5×1000 &bull; Generato da 5x1000.almagioni.com il ${new Date().toLocaleDateString('it-IT')}</p>
</body>
</html>`

  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `scheda_5x1000_${ente.cf}.html`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

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

  // Un solo CF → scheda ente diretta
  if (cfs.length === 1) {
    router.push({ name: 'ente', params: { cf: cfs[0] } })
    return
  }

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
