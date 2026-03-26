<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 py-10">

    <!-- Titolo + filtri -->
    <div class="flex flex-col sm:flex-row sm:items-end gap-4 mb-8">
      <div class="flex-1">
        <h1 class="text-2xl font-bold text-gray-900">Distribuzione geografica</h1>
        <p class="text-gray-500 mt-1 text-sm">Importo erogato per regione, provincia e comune</p>
      </div>
      <div class="flex items-center gap-3">
        <select v-model="annoSel" class="input-field" @change="loadRegioni">
          <option v-for="a in anni" :key="a" :value="a">{{ a }}</option>
        </select>
        <select v-model="categoriaSel" class="input-field" @change="loadRegioni">
          <option value="">Tutte le categorie</option>
          <option v-for="c in categorie" :key="c.slug" :value="c.slug">{{ c.label }}</option>
        </select>
      </div>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="animate-pulse space-y-6">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div v-for="n in 3" :key="n" class="card h-24 bg-gray-50"></div>
      </div>
      <div class="card h-64 bg-gray-50"></div>
    </div>

    <template v-else-if="data">

      <!-- KPI nazionali -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div class="card bg-gradient-to-br from-brand-50 to-white border-brand-100">
          <p class="text-xs font-medium text-brand-500 uppercase tracking-wide mb-1">Enti beneficiari</p>
          <p class="text-2xl font-bold text-brand-700">{{ formatNum(data.totale.n_enti) }}</p>
        </div>
        <div class="card bg-gradient-to-br from-emerald-50 to-white border-emerald-100">
          <p class="text-xs font-medium text-emerald-500 uppercase tracking-wide mb-1">Scelte totali</p>
          <p class="text-2xl font-bold text-emerald-700">{{ formatNum(data.totale.n_scelte) }}</p>
        </div>
        <div class="card bg-gradient-to-br from-violet-50 to-white border-violet-100">
          <p class="text-xs font-medium text-violet-500 uppercase tracking-wide mb-1">Importo totale erogato</p>
          <p class="text-2xl font-bold text-violet-700">{{ formatEur(data.totale.importo_totale) }}</p>
        </div>
      </div>

      <!-- Tile map + ranking regioni affiancati su desktop -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">

        <!-- Tile cartogram -->
        <div class="card">
          <RegionTileMap
            :data="tileData"
            title="Importo erogato per regione"
            :subtitle="`Anno ${annoSel}`"
            color-low="#dbeafe"
            color-high="#1e40af"
            label-low="minore"
            label-high="maggiore"
            :format-fn="formatEurShort"
          />
        </div>

        <!-- Ranking regioni con bar chart -->
        <div class="card overflow-y-auto max-h-[360px]">
          <h2 class="text-sm font-semibold text-gray-700 mb-4">Classifica regioni</h2>
          <div class="space-y-2">
            <button
              v-for="r in data.per_regione"
              :key="r.regione"
              class="w-full flex items-center gap-3 text-left rounded-lg px-2 py-1 transition-colors hover:bg-gray-50"
              :class="{ 'bg-brand-50 ring-1 ring-brand-200': regioneSel === r.regione }"
              @click="selectRegione(r.regione)"
            >
              <div class="w-32 flex-shrink-0 text-right">
                <p class="text-sm font-medium text-gray-700 truncate">{{ r.regione ?? 'N/D' }}</p>
                <p class="text-xs text-gray-400">{{ formatNum(r.n_enti) }} enti · {{ r.perc_importo?.toFixed(1) }}%</p>
              </div>
              <div class="flex-1 h-8 bg-gray-100 rounded-lg overflow-hidden">
                <div
                  class="h-full rounded-lg bg-brand-500 flex items-center justify-end pr-2 transition-all duration-500"
                  :style="{ width: barWidth(r.importo_totale) }"
                >
                  <span class="text-[10px] font-semibold text-white whitespace-nowrap">
                    {{ formatEurShort(r.importo_totale) }}
                  </span>
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>

      <!-- Drill-down province (se una regione è selezionata) -->
      <transition name="slide-down">
        <div v-if="regioneSel" class="mb-8">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-base font-semibold text-gray-800">
              Province — <span class="text-brand-600">{{ regioneSel }}</span>
            </h2>
            <button class="text-sm text-gray-400 hover:text-gray-600" @click="clearRegione">
              × Chiudi
            </button>
          </div>

          <div v-if="loadingProv" class="card animate-pulse h-32 bg-gray-50"></div>

          <div v-else-if="province.length" class="card overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-xs text-gray-500 uppercase border-b border-gray-100">
                  <th class="text-left py-2 pr-4 font-medium">Provincia</th>
                  <th class="text-right py-2 pr-4 font-medium">Enti</th>
                  <th class="text-right py-2 pr-4 font-medium">Scelte</th>
                  <th class="text-right py-2 font-medium">Erogato</th>
                  <th class="w-4"></th>
                </tr>
              </thead>
              <tbody>
                <template v-for="p in province" :key="p.provincia">
                  <tr
                    class="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
                    :class="{ 'bg-emerald-50': provinciaSel === p.provincia }"
                    @click="selectProvincia(p.provincia)"
                  >
                    <td class="py-2 pr-4 font-semibold text-gray-700">{{ p.provincia }}</td>
                    <td class="py-2 pr-4 text-right text-gray-600">{{ formatNum(p.n_enti) }}</td>
                    <td class="py-2 pr-4 text-right text-gray-600">{{ formatNum(p.n_scelte) }}</td>
                    <td class="py-2 text-right font-medium text-gray-800">{{ formatEur(p.importo_totale) }}</td>
                    <td class="py-2 pl-2 text-gray-300 text-xs">{{ provinciaSel === p.provincia ? '▲' : '▼' }}</td>
                  </tr>
                  <!-- Comuni inline sotto la provincia selezionata -->
                  <tr v-if="provinciaSel === p.provincia" class="bg-emerald-50/50">
                    <td colspan="5" class="px-4 py-3">
                      <div v-if="loadingComuni" class="animate-pulse h-16 bg-gray-100 rounded"></div>
                      <div v-else-if="comuni.length" class="overflow-x-auto">
                        <table class="w-full text-xs">
                          <thead>
                            <tr class="text-gray-400 uppercase border-b border-emerald-100">
                              <th class="text-left py-1 pr-3 font-medium">Comune</th>
                              <th class="text-right py-1 pr-3 font-medium">Enti</th>
                              <th class="text-right py-1 pr-3 font-medium">Scelte</th>
                              <th class="text-right py-1 font-medium">Erogato</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr
                              v-for="c in comuni"
                              :key="c.comune"
                              class="border-b border-emerald-50"
                            >
                              <td class="py-1 pr-3 text-gray-700">{{ c.comune }}</td>
                              <td class="py-1 pr-3 text-right text-gray-500">{{ formatNum(c.n_enti) }}</td>
                              <td class="py-1 pr-3 text-right text-gray-500">{{ formatNum(c.n_scelte) }}</td>
                              <td class="py-1 text-right font-medium text-gray-700">{{ formatEur(c.importo_totale) }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <p v-else class="text-xs text-gray-400 italic">Nessun dato comune disponibile.</p>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <p v-else class="text-sm text-gray-400 italic card">Nessuna provincia disponibile per {{ regioneSel }}.</p>
        </div>
      </transition>

    </template>

    <div v-else-if="error" class="card border-red-200 bg-red-50 text-center py-10">
      <p class="text-red-700 font-medium">Errore nel caricamento dei dati geografici.</p>
      <button class="btn-primary mt-4" @click="loadRegioni">Riprova</button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchAnni, fetchCategorie, fetchGeo } from '@/api/client'
import RegionTileMap from '@/components/RegionTileMap.vue'

// ── Stato filtri ──────────────────────────────────────────────────────────────
const anni      = ref([])
const categorie = ref([])
const annoSel      = ref(null)
const categoriaSel = ref('')

// ── Stato dati ────────────────────────────────────────────────────────────────
const data    = ref(null)
const loading = ref(false)
const error   = ref(false)

// ── Drill-down ────────────────────────────────────────────────────────────────
const regioneSel   = ref(null)
const province     = ref([])
const loadingProv  = ref(false)

const provinciaSel  = ref(null)
const comuni        = ref([])
const loadingComuni = ref(false)

// ── Fetch regioni (top level) ─────────────────────────────────────────────────
async function loadRegioni() {
  regioneSel.value  = null
  provinciaSel.value = null
  province.value    = []
  comuni.value      = []
  loading.value = true
  error.value   = false
  try {
    const params = { anno: annoSel.value }
    if (categoriaSel.value) params.categoria = categoriaSel.value
    const res = await fetchGeo(params)
    data.value = res.data
  } catch {
    error.value = true
    data.value  = null
  } finally {
    loading.value = false
  }
}

// ── Selezione regione → carica province ───────────────────────────────────────
async function selectRegione(regione) {
  if (regioneSel.value === regione) {
    clearRegione()
    return
  }
  regioneSel.value   = regione
  provinciaSel.value = null
  comuni.value       = []
  loadingProv.value  = true
  try {
    const params = { anno: annoSel.value, regione }
    if (categoriaSel.value) params.categoria = categoriaSel.value
    const res = await fetchGeo(params)
    province.value = res.data.per_provincia ?? []
  } catch {
    province.value = []
  } finally {
    loadingProv.value = false
  }
}

function clearRegione() {
  regioneSel.value   = null
  provinciaSel.value = null
  province.value     = []
  comuni.value       = []
}

// ── Selezione provincia → carica comuni ──────────────────────────────────────
async function selectProvincia(prov) {
  if (provinciaSel.value === prov) {
    provinciaSel.value = null
    comuni.value = []
    return
  }
  provinciaSel.value  = prov
  loadingComuni.value = true
  comuni.value        = []
  try {
    const params = { anno: annoSel.value, provincia: prov }
    if (categoriaSel.value) params.categoria = categoriaSel.value
    const res = await fetchGeo(params)
    comuni.value = res.data.per_comune ?? []
  } catch {
    comuni.value = []
  } finally {
    loadingComuni.value = false
  }
}

// ── Computed ──────────────────────────────────────────────────────────────────
const tileData = computed(() =>
  (data.value?.per_regione ?? []).map(r => ({ regione: r.regione, value: r.importo_totale }))
)

const maxImporto = computed(() => {
  if (!data.value?.per_regione?.length) return 1
  return Math.max(...data.value.per_regione.map(r => r.importo_totale))
})

function barWidth(v) {
  const pct = maxImporto.value > 0 ? (v / maxImporto.value) * 100 : 0
  return `${Math.max(pct, 2)}%`
}

// ── Formattazione ─────────────────────────────────────────────────────────────
const fmtNum = new Intl.NumberFormat('it-IT')
const fmtEur = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })

function formatNum(v) {
  return v != null ? fmtNum.format(v) : '–'
}
function formatEur(v) {
  return v != null ? fmtEur.format(v) : '–'
}
function formatEurShort(v) {
  if (v == null) return '–'
  if (v >= 1e9) return '€' + (v / 1e9).toFixed(1) + 'Mrd'
  if (v >= 1e6) return '€' + (v / 1e6).toFixed(1) + 'M'
  if (v >= 1e3) return '€' + (v / 1e3).toFixed(0) + 'k'
  return formatEur(v)
}

// ── Inizializzazione ──────────────────────────────────────────────────────────
onMounted(async () => {
  const [resAnni, resCat] = await Promise.all([fetchAnni(), fetchCategorie()])
  anni.value = (resAnni.data ?? []).slice().reverse()
  categorie.value = resCat.data ?? []
  annoSel.value = anni.value[0] ?? new Date().getFullYear() - 1
  await loadRegioni()
})
</script>

<style scoped>
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.25s ease;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
