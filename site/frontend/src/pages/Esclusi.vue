<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-6">
      <h1 class="mb-1">Enti esclusi</h1>
      <p class="text-gray-500">Enti presenti negli elenchi degli esclusi per almeno una categoria. Chiave: codice fiscale + anno. Un ente può risultare escluso in una categoria e ammesso in un'altra nello stesso anno.</p>
    </div>

    <!-- Filtri -->
    <div class="card mb-6">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Anno</label>
          <select v-model="filters.anno" class="input-field">
            <option value="">Tutti</option>
            <option v-for="a in anni" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Escluso in categoria</label>
          <select v-model="filters.categoria" class="input-field">
            <option value="">Tutte</option>
            <option v-for="c in categorieSlug" :key="c" :value="c">{{ slugLabel(c) }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Nome / Codice fiscale</label>
          <input v-model="filters.q" class="input-field" placeholder="Cerca ente…"
                 @input="debouncedSearch" @keyup.enter="search()" />
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
      </div>
    </div>

    <!-- Errore -->
    <div v-if="error" class="card border-red-200 bg-red-50 flex items-center gap-3 mb-4 p-4">
      <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
      </svg>
      <span class="text-sm text-red-700">Errore nel caricamento dati. Verifica la connessione e riprova.</span>
    </div>

    <!-- Info risultati + toggle colonne -->
    <div v-if="result" class="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-500">
      <span>
        <strong class="text-gray-800">{{ formatNum(result.totale) }}</strong>
        {{ result.totale === 1 ? 'ente escluso' : 'enti esclusi' }}
      </span>
<span>Pagina {{ page }} di {{ result.pagine }}</span>
    </div>

    <!-- Tabella risultati -->
    <div v-if="result?.data?.length" class="card p-0 overflow-hidden mb-4">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Anno</th>
              <th>Denominazione</th>
              <th class="hidden md:table-cell">CF</th>

              <th>Cat. escluse</th>
              <th class="text-right">Scelte escluse</th>
              <th class="text-right">Importo escluse</th>
              <th class="w-16"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="e in result.data"
              :key="`${e.anno}-${e.cod_fiscale}`"
              class="group hover:bg-red-50/30 transition-colors"
            >
              <td class="font-medium tabular-nums text-gray-500">{{ e.anno }}</td>
              <td class="max-w-xs">
                <RouterLink
                  :to="`/esclusi/${e.cod_fiscale}`"
                  class="font-medium text-gray-900 hover:text-brand-700 truncate block"
                  :title="e.denominazione"
                >{{ e.denominazione || e.cod_fiscale }}</RouterLink>
              </td>
              <td class="font-mono text-xs text-gray-400 hidden md:table-cell">{{ e.cod_fiscale }}</td>

              <td>
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="cat in e.categorie_escluse" :key="cat"
                    class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700"
                  >✗ {{ slugLabel(cat) }}</span>
                </div>
              </td>
              <td class="text-right tabular-nums text-gray-700">{{ formatNum(e.n_scelte_escluse) }}</td>
              <td class="text-right tabular-nums font-semibold text-red-700">{{ formatEur(e.importo_escluse) }}</td>
              <td>
                <RouterLink
                  :to="`/esclusi/${e.cod_fiscale}`"
                  class="text-xs text-brand-600 hover:text-brand-700 font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap"
                >dettaglio →</RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="result && !result.data.length" class="card text-center py-16">
      <p class="text-gray-500 font-medium mb-1">Nessun risultato</p>
      <p class="text-sm text-gray-400 mb-4">Prova a modificare i filtri di ricerca.</p>
      <button class="btn-secondary" @click="reset">Cancella filtri</button>
    </div>

    <!-- Skeleton -->
    <div v-else-if="loading && !result" class="card p-0 overflow-hidden mb-4 animate-pulse">
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th v-for="n in 8" :key="n"><div class="h-4 bg-gray-200 rounded w-16"></div></th></tr>
          </thead>
          <tbody>
            <tr v-for="n in 10" :key="n">
              <td><div class="h-4 bg-gray-100 rounded w-12"></div></td>
              <td><div class="h-4 bg-gray-100 rounded w-48"></div></td>
              <td class="hidden md:table-cell"><div class="h-4 bg-gray-100 rounded w-28"></div></td>
              <td class="hidden sm:table-cell"><div class="h-4 bg-gray-100 rounded w-20"></div></td>
              <td><div class="h-5 bg-red-50 rounded-full w-24"></div></td>
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
import { fetchEsclusi } from '@/api/client'
import { useMetaStore } from '@/stores/meta'

const meta    = useMetaStore()
const anni    = computed(() => meta.anni.filter(a => a >= 2019))
const regioni = computed(() => meta.regioni)

const categorieSlug = [
  'volontariato', 'asd', 'ets_onlus', 'ricerca_scientifica',
  'ricerca_sanitaria', 'comuni', 'beni_culturali', 'aree_protette',
]
const SLUG_LABELS = {
  volontariato:        'Volontariato',
  asd:                 'ASD',
  ets_onlus:           'ETS/ONLUS',
  ricerca_scientifica: 'Ricerca Scientifica',
  ricerca_sanitaria:   'Ricerca Sanitaria',
  comuni:              'Comuni',
  beni_culturali:      'Beni Culturali',
  aree_protette:       'Aree Protette',
}
const slugLabel = (s) => SLUG_LABELS[s] ?? s.replace(/_/g, ' ')

const filters = ref({ anno: '', categoria: '', q: '' })
const result  = ref(null)
const loading = ref(false)
const error   = ref(false)
const page    = ref(1)

const formatNum = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'

let _debounceTimer = null
function debouncedSearch() {
  clearTimeout(_debounceTimer)
  _debounceTimer = setTimeout(() => search(1), 400)
}

async function search(p = 1) {
  loading.value = true
  error.value   = false
  page.value    = p
  try {
    const params = { pagina: p, per_pagina: 50 }
    if (filters.value.anno)      params.anno      = filters.value.anno
    if (filters.value.categoria) params.categoria = filters.value.categoria

    if (filters.value.q)         params.q         = filters.value.q
    const res = await fetchEsclusi(params)
    result.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function reset() {
  filters.value = { anno: '', categoria: '', q: '' }
  search(1)
}

function goPage(p) { search(p) }

onMounted(async () => {
  await meta.ensure()
  await search()
})
</script>
