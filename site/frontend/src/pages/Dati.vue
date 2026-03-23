<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-6">
      <h1 class="mb-1">Esplora i dati</h1>
      <p class="text-gray-500">Ricerca tra i beneficiari del 5×1000 con filtri multipli.</p>
    </div>

    <!-- Filtri -->
    <div class="card mb-6">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Anno</label>
          <select v-model="filters.anno" class="input-field">
            <option :value="null">Tutti gli anni</option>
            <option v-for="a in anni" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Categoria</label>
          <select v-model="filters.categoria" class="input-field">
            <option :value="null">Tutte le categorie</option>
            <option v-for="c in categorie" :key="c" :value="c">{{ c.replace(/_/g, ' ') }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Regione</label>
          <select v-model="filters.regione" class="input-field">
            <option value="">Tutte le regioni</option>
            <option v-for="r in regioni" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Nome / Codice fiscale</label>
          <input v-model="filters.q" class="input-field" placeholder="Cerca ente…" @keyup.enter="search()" />
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <button class="btn-primary gap-2 inline-flex items-center" :disabled="loading" @click="search()">
          <svg v-if="!loading" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
          </svg>
          <span>{{ loading ? 'Caricamento…' : 'Cerca' }}</span>
        </button>
        <button class="btn-secondary" @click="reset" :disabled="loading">Reset</button>
        <!-- Filtro RUNTS tri-state -->
        <div class="ml-auto flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 p-0.5 text-xs">
          <button
            @click="filters.runts_filter = 'all'"
            class="px-2.5 py-1 rounded-md transition-colors font-medium"
            :class="filters.runts_filter === 'all' ? 'bg-white shadow text-gray-800' : 'text-gray-500 hover:text-gray-700'"
          >Tutti</button>
          <button
            @click="filters.runts_filter = 'runts'"
            class="px-2.5 py-1 rounded-md transition-colors font-medium"
            :class="filters.runts_filter === 'runts' ? 'bg-white shadow text-green-700' : 'text-gray-500 hover:text-gray-700'"
          >✓ RUNTS</button>
          <button
            @click="filters.runts_filter = 'non_runts'"
            class="px-2.5 py-1 rounded-md transition-colors font-medium"
            :class="filters.runts_filter === 'non_runts' ? 'bg-white shadow text-orange-700' : 'text-gray-500 hover:text-gray-700'"
          >Non RUNTS</button>
        </div>
      </div>
    </div>

    <!-- Errore -->
    <div v-if="error" class="card border-red-200 bg-red-50 flex items-center gap-3 mb-4 p-4">
      <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
      </svg>
      <span class="text-sm text-red-700">Errore nel caricamento dati. Verifica la connessione e riprova.</span>
    </div>

    <!-- Info risultati -->
    <div v-if="result" class="mb-3 flex items-center justify-between text-sm text-gray-500">
      <span>
        <strong class="text-gray-800">{{ formatNum(result.totale) }}</strong> risultati
        <span v-if="hasActiveFilters" class="ml-1 text-brand-600">con filtri attivi</span>
      </span>
      <span>Pagina {{ result.pagina }} di {{ result.pagine }}</span>
    </div>

    <!-- Tabella risultati -->
    <div v-if="result?.data?.length" class="card p-0 overflow-hidden mb-4">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="cursor-pointer select-none" @click="toggleSort('anno')">
                <span class="inline-flex items-center gap-1">
                  Anno
                  <svg class="w-3.5 h-3.5 transition-colors" :class="sortBy === 'anno' ? 'text-brand-600' : 'text-gray-300'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="sortBy === 'anno' && sortAsc ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'" />
                  </svg>
                </span>
              </th>
              <th>Denominazione</th>
              <th class="hidden md:table-cell">CF</th>
              <th class="hidden lg:table-cell">Categoria</th>
              <th class="hidden sm:table-cell">Regione</th>
              <th class="text-right cursor-pointer select-none" @click="toggleSort('n_scelte')">
                <span class="inline-flex items-center justify-end gap-1">
                  Scelte
                  <svg class="w-3.5 h-3.5 transition-colors" :class="sortBy === 'n_scelte' ? 'text-brand-600' : 'text-gray-300'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="sortBy === 'n_scelte' && sortAsc ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'" />
                  </svg>
                </span>
              </th>
              <th class="text-right cursor-pointer select-none" @click="toggleSort('importo_totale')">
                <span class="inline-flex items-center justify-end gap-1">
                  Importo
                  <svg class="w-3.5 h-3.5 transition-colors" :class="sortBy === 'importo_totale' ? 'text-brand-600' : 'text-gray-300'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="sortBy === 'importo_totale' && sortAsc ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'" />
                  </svg>
                </span>
              </th>
              <th class="w-16"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="e in sortedData"
              :key="`${e.anno}-${e.cod_fiscale}`"
              class="group hover:bg-brand-50/50 transition-colors"
            >
              <td class="font-medium tabular-nums text-gray-500">{{ e.anno }}</td>
              <td class="max-w-xs">
                <RouterLink
                  v-if="e.cod_fiscale"
                  :to="`/ente/${e.cod_fiscale}`"
                  class="font-medium text-gray-900 hover:text-brand-700 truncate block"
                  :title="e.denominazione"
                >
                  {{ e.denominazione }}
                </RouterLink>
                <span v-else class="font-medium text-gray-900 truncate block">{{ e.denominazione }}</span>
              </td>
              <td class="font-mono text-xs text-gray-400 hidden md:table-cell">{{ e.cod_fiscale }}</td>
              <td class="hidden lg:table-cell">
                <span class="badge capitalize" :class="catColor(e.categoria_principale)">
                  {{ e.categoria_principale?.replace(/_/g, ' ') ?? '–' }}
                </span>
              </td>
              <td class="text-gray-500 hidden sm:table-cell">{{ e.regione ?? '–' }}</td>
              <td class="text-right tabular-nums text-gray-700">{{ formatNum(e.n_scelte) }}</td>
              <td class="text-right tabular-nums font-semibold text-brand-700">{{ formatEur(e.importo_totale) }}</td>
              <td>
                <RouterLink
                  v-if="e.cod_fiscale"
                  :to="`/ente/${e.cod_fiscale}`"
                  class="text-xs text-brand-600 hover:text-brand-700 font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap"
                >
                  storico →
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="result && !result.data.length" class="card text-center py-16">
      <svg class="w-12 h-12 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <p class="text-gray-500 font-medium mb-1">Nessun risultato</p>
      <p class="text-sm text-gray-400 mb-4">Prova a modificare i filtri di ricerca.</p>
      <button class="btn-secondary" @click="reset">Cancella filtri</button>
    </div>

    <!-- Skeleton primo caricamento -->
    <div v-else-if="loading && !result" class="card p-0 overflow-hidden mb-4 animate-pulse">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th v-for="n in 7" :key="n"><div class="h-4 bg-gray-200 rounded w-16"></div></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="n in 10" :key="n">
              <td><div class="h-4 bg-gray-100 rounded w-12"></div></td>
              <td><div class="h-4 bg-gray-100 rounded w-48"></div></td>
              <td class="hidden md:table-cell"><div class="h-4 bg-gray-100 rounded w-28"></div></td>
              <td class="hidden lg:table-cell"><div class="h-5 bg-gray-100 rounded-full w-20"></div></td>
              <td class="hidden sm:table-cell"><div class="h-4 bg-gray-100 rounded w-20"></div></td>
              <td><div class="h-4 bg-gray-100 rounded w-16 ml-auto"></div></td>
              <td><div class="h-4 bg-gray-100 rounded w-20 ml-auto"></div></td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Paginazione -->
    <div v-if="result?.pagine > 1" class="flex items-center justify-center gap-3 mt-2">
      <button class="btn-secondary px-3" :disabled="page <= 1" @click="goPage(1)" title="Prima pagina">«</button>
      <button class="btn-secondary" :disabled="page <= 1" @click="goPage(page - 1)">← Precedente</button>
      <span class="text-sm text-gray-600 px-2">{{ page }} / {{ result.pagine }}</span>
      <button class="btn-secondary" :disabled="page >= result.pagine" @click="goPage(page + 1)">Successiva →</button>
      <button class="btn-secondary px-3" :disabled="page >= result.pagine" @click="goPage(result.pagine)" title="Ultima pagina">»</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchEnti, fetchAnni, fetchCategorie, fetchRegioni } from '@/api/client'

const anni      = ref([])
const categorie = ref([])
const regioni   = ref([])
const result    = ref(null)
const loading   = ref(false)
const error     = ref(false)
const page      = ref(1)
const sortBy    = ref('importo_totale')
const sortAsc   = ref(false)

const filters = ref({
  anno:         null,
  categoria:    null,
  regione:      '',
  q:            '',
  runts_filter: 'all',  // 'all' | 'runts' | 'non_runts'
})

const hasActiveFilters = computed(() =>
  filters.value.anno || filters.value.categoria || filters.value.regione || filters.value.q || filters.value.runts_filter !== 'all'
)

const sortedData = computed(() => {
  if (!result.value?.data) return []
  const col = sortBy.value
  return [...result.value.data].sort((a, b) => {
    const av = a[col] ?? 0
    const bv = b[col] ?? 0
    return sortAsc.value ? av - bv : bv - av
  })
})

const formatNum = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'

const CAT_COLORS = {
  'volontariato':         'bg-green-100 text-green-700',
  'volontariato_/_ets':   'bg-green-100 text-green-700',
  'ets/onlus':            'bg-green-100 text-green-700',
  'asd':                  'bg-blue-100 text-blue-700',
  'ricerca_scientifica':  'bg-yellow-100 text-yellow-700',
  'ricerca_sanitaria':    'bg-red-100 text-red-700',
  'comuni':               'bg-orange-100 text-orange-700',
  'beni_culturali':       'bg-pink-100 text-pink-700',
  'enti_gestori_aree_protette': 'bg-teal-100 text-teal-700',
  'non_specificata':      'bg-gray-100 text-gray-500',
}
const catColor = (c) => {
  const key = (c ?? '').toLowerCase().replace(/[\s/]+/g, '_')
  return CAT_COLORS[key] ?? 'bg-gray-100 text-gray-600'
}

function toggleSort(col) {
  if (sortBy.value === col) {
    sortAsc.value = !sortAsc.value
  } else {
    sortBy.value = col
    sortAsc.value = false
  }
}

async function search(p = 1) {
  loading.value = true
  error.value   = false
  page.value    = p
  try {
    const params = { pagina: p, per_pagina: 50 }
    if (filters.value.anno)       params.anno      = filters.value.anno
    if (filters.value.categoria)  params.categoria = filters.value.categoria
    if (filters.value.regione)    params.regione   = filters.value.regione
    if (filters.value.q)          params.q         = filters.value.q
    if (filters.value.runts_filter === 'runts')     params.runts_only = 1
    if (filters.value.runts_filter === 'non_runts') params.non_runts  = 1

    const res = await fetchEnti(params)
    result.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function reset() {
  filters.value = { anno: null, categoria: null, regione: '', q: '', runts_filter: 'all' }
  province.value = []
  search()
}

function goPage(p) { search(p) }

onMounted(async () => {
  const [aRes, cRes, rRes] = await Promise.all([fetchAnni(), fetchCategorie(), fetchRegioni()])
  anni.value      = aRes.data
  categorie.value = cRes.data
  regioni.value   = rRes.data
  await search()
})
</script>
