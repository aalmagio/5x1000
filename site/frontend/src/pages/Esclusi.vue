<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-8">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Enti esclusi dai riparti</h1>
      <p class="text-gray-500 mt-1 text-sm">
        Enti esclusi da almeno una categoria di riparto in un dato anno.
        Clicca su una riga per vedere il dettaglio storico per categoria.
      </p>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-4 mb-6">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <!-- Nome / CF -->
        <div class="lg:col-span-2">
          <label class="block text-xs text-gray-500 mb-1">Nome / Codice Fiscale</label>
          <input
            v-model="filters.q"
            type="text"
            placeholder="Cerca ente..."
            class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            autocomplete="off"
            @input="debouncedSearch"
          />
        </div>
        <!-- Anno -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">Anno</label>
          <select
            v-model="filters.anno"
            class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            @change="search"
          >
            <option :value="null">Tutti gli anni</option>
            <option v-for="a in meta.anni" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <!-- Regione -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">Regione</label>
          <select
            v-model="filters.regione"
            class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            @change="search"
          >
            <option :value="null">Tutte le regioni</option>
            <option v-for="r in meta.regioni" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>
        <!-- Categoria -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">Categoria riparto</label>
          <select
            v-model="filters.categoria"
            class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            @change="search"
          >
            <option :value="null">Tutte le categorie</option>
            <option v-for="c in categorieRiparto" :key="c" :value="c">{{ slugLabel(c) }}</option>
          </select>
        </div>
      </div>

      <!-- Reset -->
      <div class="mt-3 flex items-center justify-between">
        <span class="text-xs text-gray-400">
          <template v-if="!loading && result">
            {{ result.totale.toLocaleString('it-IT') }} enti esclusi trovati
          </template>
        </span>
        <button
          class="text-xs text-brand-500 hover:underline"
          @click="resetFilters"
        >Azzera filtri</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-16 text-gray-400">
      <svg class="animate-spin w-6 h-6 mr-2" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
      Caricamento...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="bg-red-50 text-red-700 rounded-xl p-4 text-sm">{{ error }}</div>

    <!-- Empty -->
    <div v-else-if="result && result.data.length === 0" class="text-center py-16 text-gray-400">
      Nessun ente trovato con i filtri selezionati.
    </div>

    <!-- Table -->
    <template v-else-if="result">
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="bg-gray-50 border-b border-gray-200 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                <th class="px-4 py-3 w-16">Anno</th>
                <th class="px-4 py-3">Denominazione / CF</th>
                <th class="px-4 py-3 hidden md:table-cell">Regione</th>
                <th class="px-4 py-3">Escluso da</th>
                <th class="px-4 py-3 hidden lg:table-cell">Ammesso in</th>
                <th class="px-4 py-3 text-right hidden lg:table-cell">Scelte escluse</th>
                <th class="px-4 py-3 text-right hidden xl:table-cell">Importo escluso</th>
                <th class="px-4 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="row in result.data" :key="`${row.anno}-${row.cod_fiscale}`">
                <!-- Main row -->
                <tr
                  class="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
                  :class="expandedKey === rowKey(row) ? 'bg-brand-50' : ''"
                  @click="toggleDetail(row)"
                >
                  <td class="px-4 py-3 font-mono text-gray-600">{{ row.anno }}</td>
                  <td class="px-4 py-3">
                    <div class="font-medium text-gray-900 leading-snug">{{ row.denominazione }}</div>
                    <div class="text-xs text-gray-400 font-mono">{{ row.cod_fiscale }}</div>
                  </td>
                  <td class="px-4 py-3 hidden md:table-cell text-gray-500 text-xs">{{ row.regione ?? '—' }}</td>
                  <td class="px-4 py-3">
                    <div class="flex flex-wrap gap-1">
                      <span
                        v-for="c in row.categorie_escluse" :key="c"
                        class="inline-block bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full font-medium"
                      >{{ slugLabel(c) }}</span>
                    </div>
                  </td>
                  <td class="px-4 py-3 hidden lg:table-cell">
                    <div class="flex flex-wrap gap-1">
                      <span
                        v-for="c in row.categorie_ammesse" :key="c"
                        class="inline-block bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full font-medium"
                      >{{ slugLabel(c) }}</span>
                      <span v-if="row.categorie_ammesse.length === 0" class="text-gray-300 text-xs">—</span>
                    </div>
                  </td>
                  <td class="px-4 py-3 text-right hidden lg:table-cell text-gray-600 tabular-nums">
                    {{ row.n_scelte_escluse != null ? row.n_scelte_escluse.toLocaleString('it-IT') : '—' }}
                  </td>
                  <td class="px-4 py-3 text-right hidden xl:table-cell text-gray-600 tabular-nums">
                    {{ row.importo_escluse != null ? fmtEur(row.importo_escluse) : '—' }}
                  </td>
                  <td class="px-4 py-3 text-gray-400">
                    <svg class="w-4 h-4 transition-transform" :class="expandedKey === rowKey(row) ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                    </svg>
                  </td>
                </tr>

                <!-- Expanded detail row -->
                <tr v-if="expandedKey === rowKey(row)" :key="`detail-${row.anno}-${row.cod_fiscale}`">
                  <td colspan="8" class="bg-brand-50 px-6 pb-5 pt-2">
                    <!-- Loading detail -->
                    <div v-if="detailLoading" class="text-xs text-gray-400 py-2 flex items-center gap-2">
                      <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                      </svg>
                      Caricamento storico...
                    </div>
                    <!-- Detail content -->
                    <div v-else-if="detail">
                      <div class="font-semibold text-gray-700 mb-3 text-sm">
                        Storico completo — {{ detail.denominazione }}
                        <span class="font-mono text-gray-400 font-normal ml-2 text-xs">{{ detail.cod_fiscale }}</span>
                      </div>
                      <div class="space-y-3">
                        <div v-for="anno in detail.storico" :key="anno.anno" class="bg-white rounded-lg border border-gray-200 p-3">
                          <div class="font-semibold text-gray-600 text-sm mb-2">{{ anno.anno }}</div>
                          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <!-- Escluse -->
                            <div v-if="anno.escluse.length">
                              <div class="text-xs font-semibold text-red-600 mb-1.5 uppercase tracking-wide">Escluso</div>
                              <div v-for="cat in anno.escluse" :key="cat.categoria" class="flex items-start gap-2 mb-1.5">
                                <span class="inline-block bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full font-medium shrink-0">{{ slugLabel(cat.categoria) }}</span>
                                <span class="text-xs text-gray-500">
                                  <template v-if="cat.n_scelte != null">{{ cat.n_scelte.toLocaleString('it-IT') }} scelte</template>
                                  <template v-if="cat.n_scelte != null && cat.importo_totale != null"> · </template>
                                  <template v-if="cat.importo_totale != null">{{ fmtEur(cat.importo_totale) }}</template>
                                </span>
                              </div>
                            </div>
                            <!-- Ammesse -->
                            <div v-if="anno.ammesse.length">
                              <div class="text-xs font-semibold text-green-600 mb-1.5 uppercase tracking-wide">Ammesso</div>
                              <div v-for="cat in anno.ammesse" :key="cat.categoria" class="flex items-start gap-2 mb-1.5">
                                <span class="inline-block bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full font-medium shrink-0">{{ slugLabel(cat.categoria) }}</span>
                                <span class="text-xs text-gray-500">
                                  <template v-if="cat.n_scelte != null">{{ cat.n_scelte.toLocaleString('it-IT') }} scelte</template>
                                  <template v-if="cat.n_scelte != null && cat.importo_totale != null"> · </template>
                                  <template v-if="cat.importo_totale != null">{{ fmtEur(cat.importo_totale) }}</template>
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div v-else class="text-xs text-gray-400 py-2">Nessun dettaglio disponibile.</div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="result.pagine > 1" class="mt-4 flex items-center justify-between text-sm text-gray-600">
        <span>Pagina {{ result.pagina }} di {{ result.pagine }}</span>
        <div class="flex gap-2">
          <button
            :disabled="result.pagina <= 1"
            class="px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            @click="goPage(result.pagina - 1)"
          >← Prec</button>
          <button
            :disabled="result.pagina >= result.pagine"
            class="px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            @click="goPage(result.pagina + 1)"
          >Succ →</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMetaStore } from '@/stores/meta'
import { fetchEsclusi, fetchEsclusiDetail, fetchCategorieRiparto } from '@/api/client'

const meta = useMetaStore()

const SLUG_LABELS = {
  ets_onlus:           'ETS/ONLUS',
  asd:                 'Sport dilettantistico',
  ricerca_scientifica: 'Ricerca scientifica',
  ricerca_sanitaria:   'Ricerca sanitaria',
  comuni:              'Comuni',
  beni_culturali:      'Beni culturali',
  aree_protette:       'Aree protette',
}
const slugLabel = (s) => SLUG_LABELS[s] ?? s

const fmtEur = (v) => new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(v)

const categorieRiparto = ref([])
const filters = ref({ q: '', anno: null, regione: null, categoria: null })
const loading = ref(false)
const error   = ref(null)
const result  = ref(null)

const expandedKey  = ref(null)
const detail       = ref(null)
const detailLoading = ref(false)

const rowKey = (row) => `${row.anno}-${row.cod_fiscale}`

let debounceTimer = null
const debouncedSearch = () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(search, 350)
}

async function search(pagina = 1) {
  loading.value = true
  error.value   = null
  expandedKey.value = null
  detail.value  = null

  const params = { pagina }
  if (filters.value.q)         params.q         = filters.value.q
  if (filters.value.anno)      params.anno      = filters.value.anno
  if (filters.value.regione)   params.regione   = filters.value.regione
  if (filters.value.categoria) params.categoria = filters.value.categoria

  try {
    const res = await fetchEsclusi(params)
    result.value = res.data
  } catch (e) {
    error.value = e?.response?.data?.error ?? e?.message ?? 'Errore di caricamento'
  } finally {
    loading.value = false
  }
}

async function toggleDetail(row) {
  const k = rowKey(row)
  if (expandedKey.value === k) {
    expandedKey.value = null
    detail.value = null
    return
  }
  expandedKey.value = k
  detail.value = null
  detailLoading.value = true
  try {
    const res = await fetchEsclusiDetail(row.cod_fiscale)
    detail.value = res.data
  } catch {
    detail.value = null
  } finally {
    detailLoading.value = false
  }
}

function goPage(p) {
  search(p)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function resetFilters() {
  filters.value = { q: '', anno: null, regione: null, categoria: null }
  search()
}

onMounted(async () => {
  await meta.ensure()
  const cr = await fetchCategorieRiparto()
  categorieRiparto.value = cr.data ?? []
  await search()
})
</script>
