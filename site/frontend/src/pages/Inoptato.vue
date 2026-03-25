<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="mb-1">Contribuenti che non scelgono</h1>
        <p class="text-gray-500">
          Analisi della quota di 5×1000 distribuita come <strong>scelta generica</strong>: contribuenti che hanno
          destinato il 5×1000 senza indicare un ente specifico.
        </p>
      </div>
      <!-- Toggle metrica -->
      <div class="flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 p-0.5 text-xs flex-shrink-0">
        <button
          @click="metrica = 'importo'"
          class="px-3 py-1.5 rounded-md transition-colors font-medium"
          :class="metrica === 'importo' ? 'bg-white shadow text-gray-800' : 'text-gray-500 hover:text-gray-700'"
        >€ Importo</button>
        <button
          @click="metrica = 'scelte'"
          class="px-3 py-1.5 rounded-md transition-colors font-medium"
          :class="metrica === 'scelte' ? 'bg-white shadow text-emerald-700' : 'text-gray-500 hover:text-gray-700'"
        ># Firme</button>
      </div>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="space-y-5 animate-pulse">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div v-for="n in 3" :key="n" class="card h-24 bg-gray-50"></div>
      </div>
      <div class="card h-80 bg-gray-50"></div>
      <div class="card h-48 bg-gray-50"></div>
    </div>

    <!-- Errore -->
    <div v-else-if="error" class="card border-red-200 bg-red-50 text-center py-12">
      <p class="text-red-700 font-medium mb-1">Errore nel caricamento</p>
      <p class="text-sm text-red-500">{{ error }}</p>
      <button class="btn-primary mt-4 inline-flex" @click="load">Riprova</button>
    </div>

    <template v-else-if="dati">
      <!-- KPI Cards — riga 1 -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
        <div class="card bg-gradient-to-br from-amber-50 to-white border-amber-100">
          <p class="text-xs font-medium text-amber-600 uppercase tracking-wide mb-1">
            {{ metrica === 'importo' ? '% Importo generico' : 'Firme espresse' }} ({{ ultimoAnno }})
          </p>
          <p class="text-2xl font-bold text-amber-700">
            {{ metrica === 'importo' ? ultimaPercDisplay : formatNum(ultimoScelte) }}
          </p>
          <p class="text-xs text-gray-400 mt-1">{{ metrica === 'importo' ? 'del totale distribuito' : 'designazioni esplicite' }}</p>
        </div>
        <div class="card bg-gradient-to-br from-brand-50 to-white border-brand-100">
          <p class="text-xs font-medium text-brand-500 uppercase tracking-wide mb-1">
            {{ metrica === 'importo' ? 'Importo generico' : 'Valore medio / firma' }} ({{ ultimoAnno }})
          </p>
          <p class="text-2xl font-bold text-brand-700">
            {{ metrica === 'importo' ? formatEur(ultimoGenerico) : formatEur(ultimoValoreMedio) }}
          </p>
          <p class="text-xs text-gray-400 mt-1">{{ metrica === 'importo' ? 'scelte generiche' : '€ espresso / nr. firme' }}</p>
        </div>
        <div
          class="card bg-gradient-to-br border"
          :class="variazioneDisplay !== null && variazioneDisplay < 0
            ? 'from-green-50 to-white border-green-100'
            : 'from-orange-50 to-white border-orange-100'"
        >
          <p
            class="text-xs font-medium uppercase tracking-wide mb-1"
            :class="variazioneDisplay !== null && variazioneDisplay < 0 ? 'text-green-600' : 'text-orange-600'"
          >Variazione YoY</p>
          <p
            class="text-2xl font-bold"
            :class="variazioneDisplay !== null && variazioneDisplay < 0 ? 'text-green-700' : 'text-orange-700'"
          >
            <template v-if="variazioneDisplay !== null">
              {{ variazioneDisplay > 0 ? '+' : '' }}{{ variazioneDisplay.toFixed(2) }}{{ metrica === 'importo' ? ' pp' : '%' }}
            </template>
            <template v-else>–</template>
          </p>
          <p class="text-xs text-gray-400 mt-1">rispetto a {{ penultimoAnno }}</p>
        </div>
      </div>

      <!-- KPI Cards — riga 2: nr scelte e valore medio -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <div class="card bg-gradient-to-br from-emerald-50 to-white border-emerald-100">
          <p class="text-xs font-medium text-emerald-600 uppercase tracking-wide mb-1">Nr. scelte espresse ({{ ultimoAnno }})</p>
          <p class="text-2xl font-bold text-emerald-700">{{ formatNum(ultimoScelte) }}</p>
          <p class="text-xs text-gray-400 mt-1">designazioni esplicite ai beneficiari</p>
        </div>
        <div class="card bg-gradient-to-br from-violet-50 to-white border-violet-100">
          <p class="text-xs font-medium text-violet-600 uppercase tracking-wide mb-1">Valore medio scelta espressa ({{ ultimoAnno }})</p>
          <p class="text-2xl font-bold text-violet-700">{{ formatEur(ultimoValoreMedio) }}</p>
          <p class="text-xs text-gray-400 mt-1">€ espresso / nr. scelte espresse</p>
        </div>
      </div>

      <!-- Grafico storico % generica / firme generiche -->
      <div class="card mb-6">
        <div class="flex items-center justify-between mb-5">
          <div>
            <h2 class="text-gray-900">
              {{ metrica === 'importo' ? 'Trend storico: % scelta generica' : 'Trend storico: firme espresse' }}
            </h2>
            <p class="text-sm text-gray-400 mt-0.5">
              {{ metrica === 'importo' ? 'Quota del totale distribuita come generica, per anno' : 'Numero di firme (designazioni esplicite) per anno' }}
            </p>
          </div>
          <span class="text-xs text-gray-400">{{ dati.per_anno.length }} anni</span>
        </div>

        <!-- Importo mode -->
        <div v-if="metrica === 'importo'" class="space-y-2">
          <div
            v-for="r in dati.per_anno"
            :key="r.anno"
            class="flex items-center gap-3"
          >
            <div class="w-12 text-right flex-shrink-0">
              <span
                class="text-sm font-medium"
                :class="r.anno === ultimoAnno ? 'text-brand-700' : 'text-gray-500'"
              >{{ r.anno }}</span>
            </div>
            <div class="flex-1 relative h-7 bg-gray-100 rounded overflow-hidden">
              <div
                class="absolute inset-y-0 left-0 rounded transition-all duration-500"
                :style="{ width: (r.perc_generico ?? 0) + '%', background: 'rgba(245,158,11,0.55)' }"
              ></div>
            </div>
            <div class="w-32 flex-shrink-0 text-right">
              <span class="text-sm font-semibold tabular-nums" :class="r.anno === ultimoAnno ? 'text-brand-700' : 'text-gray-700'">
                {{ r.perc_generico !== null ? r.perc_generico.toFixed(1) + '%' : '–' }}
              </span>
              <span class="text-xs text-gray-400 ml-1">{{ formatEurShort(r.tot_generico) }}</span>
            </div>
          </div>
        </div>

        <!-- Firme mode: mostra tot_scelte (firme espresse) per anno -->
        <div v-else class="space-y-2">
          <div
            v-for="r in dati.per_anno"
            :key="r.anno"
            class="flex items-center gap-3"
          >
            <div class="w-12 text-right flex-shrink-0">
              <span
                class="text-sm font-medium"
                :class="r.anno === ultimoAnno ? 'text-emerald-700' : 'text-gray-500'"
              >{{ r.anno }}</span>
            </div>
            <div class="flex-1 relative h-7 bg-gray-100 rounded overflow-hidden">
              <div
                class="absolute inset-y-0 left-0 rounded transition-all duration-500 bg-emerald-400"
                :style="{ width: maxScelte > 0 ? ((r.tot_scelte ?? 0) / maxScelte * 100).toFixed(1) + '%' : '0%' }"
              ></div>
            </div>
            <div class="w-36 flex-shrink-0 text-right">
              <span class="text-sm font-semibold tabular-nums" :class="r.anno === ultimoAnno ? 'text-emerald-700' : 'text-gray-700'">
                {{ formatNum(r.tot_scelte) }}
              </span>
              <span class="text-xs text-gray-400 ml-1">firme</span>
            </div>
          </div>
        </div>

        <!-- Legenda -->
        <div class="flex gap-4 mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
          <span v-if="metrica === 'importo'" class="flex items-center gap-1.5">
            <span class="inline-block w-3 h-3 rounded" style="background:rgba(245,158,11,0.55)"></span>
            Generica (inoptato)
          </span>
          <span v-else class="flex items-center gap-1.5">
            <span class="inline-block w-3 h-3 rounded bg-emerald-400"></span>
            Firme generiche
          </span>
        </div>
      </div>

      <!-- Grafico importi assoluti: espresso vs generico -->
      <div class="card mb-6">
        <div class="mb-5">
          <h2 class="text-gray-900">Importi: espresso vs generico</h2>
          <p class="text-sm text-gray-400 mt-0.5">Valori assoluti per anno</p>
        </div>
        <div class="space-y-2">
          <div
            v-for="r in dati.per_anno"
            :key="r.anno"
            class="flex items-center gap-3"
          >
            <div class="w-12 text-right flex-shrink-0">
              <span class="text-sm font-medium text-gray-500">{{ r.anno }}</span>
            </div>
            <div class="flex-1 flex gap-0.5 h-5">
              <div
                class="h-full rounded-l transition-all duration-500 bg-brand-400"
                :style="{ width: percEspresso(r) + '%' }"
                :title="'Espresso: ' + formatEur(r.tot_espresso)"
              ></div>
              <div
                class="h-full rounded-r transition-all duration-500 bg-amber-300"
                :style="{ width: percGenerica(r) + '%' }"
                :title="'Generico: ' + formatEur(r.tot_generico)"
              ></div>
            </div>
            <div class="w-28 flex-shrink-0 text-right text-xs text-gray-500 tabular-nums">
              {{ formatEurShort(r.tot_totale) }}
            </div>
          </div>
        </div>
        <div class="flex gap-4 mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
          <span class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded bg-brand-400"></span>Espresso</span>
          <span class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded bg-amber-300"></span>Generico</span>
        </div>
      </div>

      <!-- Grafico nr scelte espresse e valore medio per anno -->
      <div class="card mb-6">
        <div class="mb-5">
          <h2 class="text-gray-900">Nr. scelte espresse e valore medio</h2>
          <p class="text-sm text-gray-400 mt-0.5">Numero di designazioni esplicite e valore medio per scelta, per anno</p>
        </div>
        <div class="space-y-2">
          <div
            v-for="r in dati.per_anno"
            :key="r.anno"
            class="flex items-center gap-3"
          >
            <div class="w-12 text-right flex-shrink-0">
              <span class="text-sm font-medium text-gray-500">{{ r.anno }}</span>
            </div>
            <div class="flex-1 h-6 bg-gray-100 rounded overflow-hidden">
              <div
                class="h-full rounded transition-all duration-500 bg-emerald-400"
                :style="{ width: maxScelte > 0 ? ((r.tot_scelte / maxScelte) * 100).toFixed(1) + '%' : '0%' }"
              ></div>
            </div>
            <div class="w-28 flex-shrink-0 text-right text-xs tabular-nums text-gray-600">
              {{ formatNum(r.tot_scelte) }} scelte
            </div>
            <div class="w-24 flex-shrink-0 text-right text-xs tabular-nums text-violet-600 font-medium">
              {{ r.valore_medio_espressa != null ? formatEur(r.valore_medio_espressa) : '–' }}
            </div>
          </div>
        </div>
        <div class="flex gap-4 mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
          <span class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded bg-emerald-400"></span>Nr. scelte espresse</span>
          <span class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded bg-violet-300"></span>Valore medio (€/scelta)</span>
        </div>
      </div>

      <!-- Breakdown -->
      <div class="card mb-6">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
          <div>
            <h2 class="text-gray-900">Breakdown</h2>
            <p class="text-sm text-gray-400 mt-0.5">
              Distribuzione scelte generiche nell'ultimo anno disponibile ({{ breakdownAnno }})
            </p>
          </div>
          <div class="flex gap-2">
            <button
              v-for="tab in ['categoria', 'regione']"
              :key="tab"
              @click="loadBreakdown(tab)"
              class="px-3 py-1.5 rounded-full text-xs font-medium border transition-colors capitalize"
              :class="breakdownTab === tab
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400 hover:text-brand-700'"
            >{{ tab === 'categoria' ? 'Per categoria' : 'Per regione' }}</button>
          </div>
        </div>

        <div v-if="loadingBreakdown" class="animate-pulse space-y-2">
          <div v-for="n in 5" :key="n" class="h-7 bg-gray-100 rounded"></div>
        </div>

        <div v-else-if="breakdownRows.length" class="space-y-2">
          <div
            v-for="row in breakdownRows"
            :key="row.label"
            class="flex items-center gap-3"
          >
            <div class="w-40 flex-shrink-0 text-sm text-gray-700 truncate" :title="row.label">{{ row.label }}</div>
            <div class="flex-1 relative h-6 bg-gray-100 rounded overflow-hidden">
              <div
                class="absolute inset-y-0 left-0 rounded transition-all duration-500"
                :style="{ width: row.percBar + '%', background: 'rgba(245,158,11,0.5)' }"
              ></div>
            </div>
            <div class="w-20 flex-shrink-0 text-right text-sm font-semibold tabular-nums text-amber-700">
              {{ row.perc !== null ? row.perc.toFixed(1) + '%' : '–' }}
            </div>
            <div class="w-28 flex-shrink-0 text-right text-xs text-gray-400 tabular-nums">
              {{ formatEurShort(row.generico) }}
            </div>
          </div>
        </div>

        <p v-else class="text-sm text-gray-400 text-center py-6">
          Seleziona un breakdown per visualizzare i dati.
        </p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchInoptato } from '../api/client.js'

const loading         = ref(true)
const error           = ref(null)
const dati            = ref(null)
const loadingBreakdown = ref(false)
const breakdownTab    = ref('categoria')
const breakdownRaw    = ref(null)
const metrica         = ref('importo') // 'importo' | 'scelte'

async function load() {
  loading.value = true
  error.value   = null
  try {
    const res = await fetchInoptato()
    dati.value = res.data
  } catch (e) {
    error.value = e?.response?.data?.error ?? e.message ?? 'Errore sconosciuto'
  } finally {
    loading.value = false
    if (!error.value) loadBreakdown('categoria')
  }
}

async function loadBreakdown(tab) {
  breakdownTab.value    = tab
  loadingBreakdown.value = true
  breakdownRaw.value    = null
  try {
    const res = await fetchInoptato({ breakdown: tab })
    breakdownRaw.value = res.data
  } catch {
    // ignora errori breakdown
  } finally {
    loadingBreakdown.value = false
  }
}

onMounted(load)

// ─── Computed ────────────────────────────────────────────────────────────────

const ultimoAnno = computed(() => {
  if (!dati.value?.per_anno?.length) return null
  return dati.value.per_anno.at(-1).anno
})

const penultimoAnno = computed(() => {
  if (!dati.value?.per_anno || dati.value.per_anno.length < 2) return null
  return dati.value.per_anno.at(-2).anno
})

const ultimaPerc = computed(() => {
  if (!dati.value?.per_anno?.length) return null
  return dati.value.per_anno.at(-1).perc_generico
})

const ultimoGenerico = computed(() => {
  if (!dati.value?.per_anno?.length) return null
  return dati.value.per_anno.at(-1).tot_generico
})

const ultimoScelte = computed(() => {
  if (!dati.value?.per_anno?.length) return null
  return dati.value.per_anno.at(-1).tot_scelte
})

const ultimoValoreMedio = computed(() => {
  if (!dati.value?.per_anno?.length) return null
  return dati.value.per_anno.at(-1).valore_medio_espressa ?? null
})

const maxScelte = computed(() => {
  if (!dati.value?.per_anno?.length) return 1
  return Math.max(...dati.value.per_anno.map(r => r.tot_scelte ?? 0), 1)
})

const variazionePerc = computed(() => {
  const rows = dati.value?.per_anno
  if (!rows || rows.length < 2) return null
  const last = rows.at(-1).perc_generico
  const prev = rows.at(-2).perc_generico
  if (last === null || prev === null) return null
  return +(last - prev).toFixed(2)
})

// Computed adattivi al metrica corrente
const ultimaPercDisplay = computed(() =>
  ultimaPerc.value !== null ? ultimaPerc.value.toFixed(1) + '%' : '–'
)

// Variazione YoY firme espresse (in punti percentuali rispetto al totale)
const variazioneDisplay = computed(() => {
  if (metrica.value === 'scelte') {
    // YoY assoluto del numero di firme espresse
    const rows = dati.value?.per_anno
    if (!rows || rows.length < 2) return null
    const last = rows.at(-1).tot_scelte
    const prev = rows.at(-2).tot_scelte
    if (!prev) return null
    return +((last - prev) / prev * 100).toFixed(2)
  }
  return variazionePerc.value
})

const breakdownAnno = computed(() => breakdownRaw.value?.anno_riferimento ?? ultimoAnno.value ?? '–')

const maxPercBreakdown = computed(() => {
  if (!breakdownRows.value.length) return 1
  return Math.max(...breakdownRows.value.map(r => r.perc ?? 0), 1)
})

const breakdownRows = computed(() => {
  if (!breakdownRaw.value) return []
  const arr = breakdownTab.value === 'regione'
    ? (breakdownRaw.value.per_regione ?? [])
    : (breakdownRaw.value.per_categoria ?? [])
  const maxP = Math.max(...arr.map(r => r.perc_generico ?? 0), 1)
  return arr.map(r => ({
    label:   r.regione ?? r.categoria ?? '–',
    perc:    r.perc_generico,
    percBar: maxP > 0 ? ((r.perc_generico ?? 0) / maxP * 100) : 0,
    generico: r.tot_generico,
  }))
})

// max per barra importo assoluto
const maxTotale = computed(() => {
  if (!dati.value?.per_anno?.length) return 1
  return Math.max(...dati.value.per_anno.map(r => r.tot_totale ?? 0), 1)
})

function percEspresso(r) {
  return maxTotale.value > 0 ? ((r.tot_espresso ?? 0) / maxTotale.value * 100) : 0
}
function percGenerica(r) {
  return maxTotale.value > 0 ? ((r.tot_generico ?? 0) / maxTotale.value * 100) : 0
}

// ─── Formatters ──────────────────────────────────────────────────────────────

function formatNum(v) {
  if (v === null || v === undefined) return '–'
  return Number(v).toLocaleString('it-IT')
}

function formatEur(v) {
  if (v === null || v === undefined) return '–'
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(v)
}

function formatEurShort(v) {
  if (v === null || v === undefined) return '–'
  if (v >= 1e9) return (v / 1e9).toFixed(2) + ' Mrd €'
  if (v >= 1e6) return (v / 1e6).toFixed(1) + ' M€'
  if (v >= 1e3) return (v / 1e3).toFixed(0) + ' k€'
  return v.toFixed(0) + ' €'
}
</script>
