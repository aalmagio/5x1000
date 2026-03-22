<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-6">
      <h1 class="mb-1">Analisi per categoria</h1>
      <p class="text-gray-500">Distribuzione di importi e scelte tra le categorie di enti beneficiari.</p>
    </div>

    <!-- Filtro anno -->
    <div class="card mb-6">
      <div class="flex flex-wrap items-end gap-4 mb-4">
        <div class="flex-1 min-w-48">
          <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Anno di riferimento</label>
          <select v-model="annoSelezionato" class="input-field">
            <option :value="null">Tutti gli anni (confronto storico)</option>
            <option v-for="a in anniDisponibili" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <div class="flex-1 min-w-48">
          <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Visualizza</label>
          <select v-model="metrica" class="input-field">
            <option value="totale_importo">Importo totale (€)</option>
            <option value="totale_scelte">Numero di scelte</option>
            <option value="n_enti">Numero di enti</option>
          </select>
        </div>
      </div>
      <!-- Selezione rapida categorie predefinite -->
      <div>
        <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Selezione rapida</p>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="preset in PRESETS"
            :key="preset.label"
            @click="applyPreset(preset)"
            class="px-3 py-1 rounded-full text-xs font-medium border transition-colors"
            :class="activePreset === preset.label
              ? 'bg-brand-600 text-white border-brand-600'
              : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400 hover:text-brand-700'"
          >
            {{ preset.label }}
          </button>
          <button
            @click="applyPreset(null)"
            class="px-3 py-1 rounded-full text-xs font-medium border transition-colors"
            :class="activePreset === null
              ? 'bg-gray-700 text-white border-gray-700'
              : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400'"
          >
            Tutte
          </button>
        </div>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-4 animate-pulse">
      <div class="card h-64 bg-gray-50"></div>
      <div class="card h-48 bg-gray-50"></div>
    </div>

    <!-- Errore -->
    <div v-else-if="error" class="card border-red-200 bg-red-50 flex items-center gap-3 p-4">
      <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
      </svg>
      <span class="text-sm text-red-700">Errore nel caricamento dati.</span>
    </div>

    <template v-else-if="data">
      <!-- Modalità: anno singolo -->
      <template v-if="annoSelezionato">
        <!-- Bar chart -->
        <div class="card mb-6">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h2>{{ metricaLabel }} per categoria — {{ annoSelezionato }}</h2>
              <p class="text-sm text-gray-400 mt-0.5">Tutte le categorie, ordinate per {{ metricaLabel.toLowerCase() }}</p>
            </div>
          </div>

          <div class="space-y-3">
            <div
              v-for="(row, i) in categorieOrdinate"
              :key="row.cat"
              class="flex items-center gap-3 cursor-pointer hover:opacity-80"
              @click="router.push({ name: 'categoria_dettaglio', params: { categoria: row.cat, anno: annoSelezionato } })"
            >
              <div class="w-44 text-right flex-shrink-0">
                <p class="text-sm font-medium text-gray-700 capitalize truncate">{{ row.cat.replace(/_/g, ' ') }}</p>
                <p class="text-xs text-gray-400">{{ formatNum(row.data.n_enti) }} enti</p>
              </div>
              <div class="flex-1 h-10 bg-gray-100 rounded-lg overflow-hidden">
                <div
                  class="h-full rounded-lg transition-all duration-700 ease-out flex items-center justify-end pr-3"
                  :style="{
                    width: animated ? `${((row.val / maxVal) * 100).toFixed(1)}%` : '0%',
                    backgroundColor: CAT_COLORS[i % CAT_COLORS.length],
                  }"
                >
                  <span
                    v-if="row.val / maxVal > 0.2"
                    class="text-xs font-semibold text-white whitespace-nowrap"
                  >
                    {{ formatMetrica(row.val) }}
                  </span>
                </div>
              </div>
              <div class="w-32 flex-shrink-0 text-xs font-semibold text-gray-700 text-right">
                <span v-if="row.val / maxVal <= 0.2">{{ formatMetrica(row.val) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Tabella dettaglio -->
        <div class="card p-0 overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-100">
            <h2>Dettaglio categorie — {{ annoSelezionato }}</h2>
          </div>
          <div class="table-wrap rounded-none border-0">
            <table>
              <thead>
                <tr>
                  <th>Categoria</th>
                  <th class="text-right">Enti</th>
                  <th class="text-right">Scelte</th>
                  <th class="text-right">Importo totale</th>
                  <th class="text-right hidden sm:table-cell">Media per ente</th>
                  <th class="text-right hidden lg:table-cell">Massimo</th>
                </tr>
              </thead>
              <tbody>
                <tr
                v-for="(row, i) in categorieOrdinate"
                :key="row.cat"
                class="cursor-pointer hover:bg-brand-50"
                @click="router.push({ name: 'categoria_dettaglio', params: { categoria: row.cat, anno: annoSelezionato } })"
              >
                  <td>
                    <span class="flex items-center gap-2">
                      <span class="w-3 h-3 rounded-full flex-shrink-0" :style="{ backgroundColor: CAT_COLORS[i % CAT_COLORS.length] }"></span>
                      <span class="capitalize">{{ row.cat.replace(/_/g, ' ') }}</span>
                    </span>
                  </td>
                  <td class="text-right tabular-nums">{{ formatNum(row.data.n_enti) }}</td>
                  <td class="text-right tabular-nums">{{ formatNum(row.data.totale_scelte) }}</td>
                  <td class="text-right tabular-nums font-semibold text-brand-700">{{ formatEur(row.data.totale_importo) }}</td>
                  <td class="text-right tabular-nums hidden sm:table-cell text-gray-500">{{ formatEur(row.data.media_importo) }}</td>
                  <td class="text-right tabular-nums hidden lg:table-cell text-gray-500">{{ formatEur(row.data.max_importo) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <!-- Modalità: tutti gli anni (trend storico) -->
      <template v-else>
        <!-- Trend importo per categoria nel tempo -->
        <div class="card mb-6">
          <div class="mb-6">
            <h2>{{ metricaLabel }} per categoria nel tempo</h2>
            <p class="text-sm text-gray-400 mt-0.5">Evoluzione storica per categoria — usa il filtro metrica per cambiare dato</p>
          </div>

          <!-- Legenda categorie -->
          <div class="flex flex-wrap gap-3 mb-6">
            <button
              v-for="(cat, i) in data.categorie"
              :key="cat"
              @click="toggleCat(cat)"
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-opacity border"
              :class="catAttive.has(cat) ? 'opacity-100 border-transparent' : 'opacity-40 border-gray-200 bg-white'"
              :style="catAttive.has(cat) ? { backgroundColor: CAT_COLORS[i % CAT_COLORS.length] + '22', borderColor: CAT_COLORS[i % CAT_COLORS.length], color: CAT_COLORS[i % CAT_COLORS.length] } : {}"
            >
              <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: CAT_COLORS[i % CAT_COLORS.length] }"></span>
              {{ cat.replace(/_/g, ' ') }}
            </button>
          </div>

          <!-- Mini sparklines per ogni categoria attiva -->
          <div class="space-y-8">
            <div v-for="(cat, catIdx) in data.categorie.filter(c => catAttive.has(c))" :key="cat">
              <div class="flex items-center gap-2 mb-2">
                <span class="w-3 h-3 rounded-full" :style="{ backgroundColor: CAT_COLORS[data.categorie.indexOf(cat) % CAT_COLORS.length] }"></span>
                <span class="text-sm font-semibold text-gray-700 capitalize">{{ cat.replace(/_/g, ' ') }}</span>
              </div>
              <div class="space-y-1">
                <div
                  v-for="anno in data.anni"
                  :key="anno"
                  class="flex items-center gap-3"
                >
                  <span class="w-12 text-right text-xs text-gray-400 flex-shrink-0">{{ anno }}</span>
                  <div class="flex-1 h-6 bg-gray-100 rounded overflow-hidden">
                    <div
                      class="h-full rounded transition-all duration-500 ease-out"
                      :style="{
                        width: animated ? sparkWidth(cat, anno) : '0%',
                        backgroundColor: CAT_COLORS[data.categorie.indexOf(cat) % CAT_COLORS.length],
                      }"
                    ></div>
                  </div>
                  <span class="w-32 text-xs text-gray-600 font-medium text-right flex-shrink-0">
                    {{ data.per_anno[anno]?.[cat] ? formatMetrica(getVal(cat, anno)) : '–' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tabella pivot anno × categoria -->
        <div class="card p-0 overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-100">
            <h2>Tabella pivot: {{ metricaLabel }} per anno e categoria</h2>
          </div>
          <div class="table-wrap rounded-none border-0">
            <table>
              <thead>
                <tr>
                  <th>Anno</th>
                  <th
                    v-for="(cat, i) in data.categorie"
                    :key="cat"
                    class="text-right"
                  >
                    <span class="flex items-center justify-end gap-1 capitalize">
                      <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: CAT_COLORS[i % CAT_COLORS.length] }"></span>
                      {{ cat.replace(/_/g, ' ').split(' ').slice(0,2).join(' ') }}
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="anno in [...data.anni].reverse()" :key="anno">
                  <td class="font-medium text-gray-500">{{ anno }}</td>
                  <td
                    v-for="cat in data.categorie"
                    :key="cat"
                    class="text-right tabular-nums text-xs"
                    :class="data.per_anno[anno]?.[cat] ? 'text-gray-700' : 'text-gray-200'"
                  >
                    {{ data.per_anno[anno]?.[cat] ? formatMetrica(getVal(cat, anno)) : '–' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchAnni, fetchAnalisiCategorie } from '@/api/client'

const router = useRouter()

const CAT_COLORS = ['#3b82f6','#10b981','#8b5cf6','#ef4444','#f59e0b','#06b6d4','#f97316','#ec4899']

// Parole chiave da cercare nel nome categoria (case-insensitive)
const PRESETS = [
  { label: 'Ricerca Scientifica', keywords: ['ricerca_scientifica', 'ricerca scientifica'] },
  { label: 'Sanitari',            keywords: ['sanitari', 'ricerca_sanitaria', 'ricerca sanitaria'] },
  { label: 'Volontariato / ETS',  keywords: ['volontariato', 'ets', 'onlus'] },
]

const anniDisponibili  = ref([])
const annoSelezionato  = ref(null)
const metrica          = ref('totale_importo')
const data             = ref(null)
const loading          = ref(false)
const error            = ref(false)
const animated         = ref(false)
const catAttive        = ref(new Set())
const activePreset     = ref(null)

function applyPreset(preset) {
  if (!data.value) return
  activePreset.value = preset ? preset.label : null
  if (!preset) {
    catAttive.value = new Set(data.value.categorie)
    return
  }
  const matched = data.value.categorie.filter(cat => {
    const c = cat.toLowerCase()
    return preset.keywords.some(k => c.includes(k))
  })
  catAttive.value = new Set(matched.length ? matched : data.value.categorie.slice(0, 4))
}

const metricaLabel = computed(() => ({
  totale_importo: 'Importo totale',
  totale_scelte:  'Numero di scelte',
  n_enti:         'Numero di enti',
})[metrica.value])

const categorieOrdinate = computed(() => {
  if (!data.value || !annoSelezionato.value) return []
  const perAnno = data.value.per_anno[annoSelezionato.value] ?? {}
  return data.value.categorie
    .filter(cat => catAttive.value.size === 0 || catAttive.value.has(cat))
    .map(cat => ({ cat, data: perAnno[cat] ?? null, val: perAnno[cat]?.[metrica.value] ?? 0 }))
    .filter(r => r.data)
    .sort((a, b) => b.val - a.val)
})

const maxVal = computed(() =>
  categorieOrdinate.value.length
    ? Math.max(...categorieOrdinate.value.map(r => r.val), 1)
    : 1
)

function getVal(cat, anno) {
  return data.value?.per_anno[anno]?.[cat]?.[metrica.value] ?? 0
}

function sparkWidth(cat, anno) {
  const vals = data.value.anni.map(a => getVal(cat, a))
  const max  = Math.max(...vals, 1)
  return ((getVal(cat, anno) / max) * 100).toFixed(1) + '%'
}

function toggleCat(cat) {
  const s = new Set(catAttive.value)
  s.has(cat) ? s.delete(cat) : s.add(cat)
  catAttive.value = s
}

const formatNum = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'
const formatMetrica = (v) => {
  if (v == null) return '–'
  if (metrica.value === 'totale_importo' || metrica.value === 'media_importo') return formatEur(v)
  return formatNum(v)
}

async function loadData() {
  loading.value  = true
  error.value    = false
  animated.value = false

  try {
    const res  = await fetchAnalisiCategorie(annoSelezionato.value)
    data.value = res.data
    // Mantieni il preset attivo (se applicabile) altrimenti prime 4
    if (activePreset.value) {
      applyPreset(PRESETS.find(p => p.label === activePreset.value) ?? null)
    } else {
      // Default: Ricerca sanitaria + Ricerca scientifica + Volontariato/ETS
      const defaultKw = ['ricerca', 'sanitari', 'volontariato', 'ets', 'onlus']
      const preferite = data.value.categorie.filter(cat =>
        defaultKw.some(k => cat.toLowerCase().includes(k))
      )
      catAttive.value = new Set(preferite.length ? preferite : data.value.categorie.slice(0, 4))
    }
    setTimeout(() => { animated.value = true }, 100)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

watch(annoSelezionato, loadData)

onMounted(async () => {
  const res = await fetchAnni()
  anniDisponibili.value = res.data
  await loadData()
})
</script>
