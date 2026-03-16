<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-10">
    <h1 class="mb-2">Esplora i dati</h1>
    <p class="text-gray-500 mb-6">Ricerca tra i beneficiari del 5×1000 con filtri multipli.</p>

    <!-- Filtri -->
    <div class="card mb-6">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1 block">Anno</label>
          <select v-model="filters.anno" class="input-field">
            <option :value="null">Tutti gli anni</option>
            <option v-for="a in anni" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1 block">Categoria</label>
          <select v-model="filters.categoria" class="input-field">
            <option :value="null">Tutte le categorie</option>
            <option v-for="c in categorie" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1 block">Regione</label>
          <input v-model="filters.regione" class="input-field" placeholder="es. LOMBARDIA" @keyup.enter="search" />
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 mb-1 block">Cerca per nome / CF</label>
          <input v-model="filters.q" class="input-field" placeholder="Nome ente o codice fiscale" @keyup.enter="search" />
        </div>
      </div>
      <div class="flex items-center gap-3 mt-4">
        <button class="btn-primary" :disabled="loading" @click="search">
          <span v-if="loading">Caricamento…</span>
          <span v-else>Cerca</span>
        </button>
        <button class="btn-secondary" @click="reset">Reset</button>
        <label class="flex items-center gap-2 text-sm text-gray-600 ml-auto cursor-pointer">
          <input type="checkbox" v-model="filters.runts_only" class="rounded" />
          Solo enti RUNTS
        </label>
      </div>
    </div>

    <!-- Risultati -->
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-4">
      Errore nel caricamento dati. Riprova.
    </div>

    <div v-if="result" class="mb-3 flex items-center justify-between text-sm text-gray-500">
      <span><strong class="text-gray-800">{{ formatNum(result.totale) }}</strong> risultati</span>
      <span>Pagina {{ result.pagina }} di {{ result.pagine }}</span>
    </div>

    <div class="table-wrap mb-4" v-if="result?.data?.length">
      <table>
        <thead>
          <tr>
            <th>Anno</th>
            <th>Denominazione</th>
            <th>CF</th>
            <th>Categoria</th>
            <th>Regione</th>
            <th class="text-right">Scelte</th>
            <th class="text-right">Importo totale</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in result.data" :key="`${e.anno}-${e.cod_fiscale}`">
            <td>{{ e.anno }}</td>
            <td class="max-w-xs truncate font-medium">{{ e.denominazione }}</td>
            <td class="font-mono text-xs text-gray-500">{{ e.cod_fiscale }}</td>
            <td>
              <span class="badge" :class="catColor(e.categoria_principale)">
                {{ e.categoria_principale ?? '–' }}
              </span>
            </td>
            <td>{{ e.regione }}</td>
            <td class="text-right">{{ formatNum(e.n_scelte) }}</td>
            <td class="text-right font-medium">{{ formatEur(e.importo_totale) }}</td>
            <td>
              <RouterLink
                v-if="e.cod_fiscale"
                :to="`/ente/${e.cod_fiscale}`"
                class="text-brand-600 hover:underline text-xs"
              >storico</RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else-if="result && !result.data.length" class="text-gray-400 text-center py-12">
      Nessun risultato per i filtri selezionati.
    </div>

    <!-- Paginazione -->
    <div v-if="result?.pagine > 1" class="flex items-center justify-center gap-2">
      <button
        class="btn-secondary"
        :disabled="page <= 1"
        @click="goPage(page - 1)"
      >&larr;</button>
      <span class="text-sm text-gray-600">{{ page }} / {{ result.pagine }}</span>
      <button
        class="btn-secondary"
        :disabled="page >= result.pagine"
        @click="goPage(page + 1)"
      >&rarr;</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchEnti, fetchAnni, fetchCategorie } from '@/api/client'

const anni      = ref([])
const categorie = ref([])
const result    = ref(null)
const loading   = ref(false)
const error     = ref(false)
const page      = ref(1)

const filters = ref({
  anno:       null,
  categoria:  null,
  regione:    '',
  q:          '',
  runts_only: false,
})

const formatNum = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'

const CAT_COLORS = {
  volontariato:         'bg-green-100 text-green-700',
  asd:                  'bg-blue-100 text-blue-700',
  ets_onlus:            'bg-purple-100 text-purple-700',
  ricerca_scientifica:  'bg-yellow-100 text-yellow-700',
  ricerca_sanitaria:    'bg-red-100 text-red-700',
  comuni:               'bg-orange-100 text-orange-700',
  beni_culturali:       'bg-pink-100 text-pink-700',
  aree_protette:        'bg-teal-100 text-teal-700',
}
const catColor = (c) => CAT_COLORS[c] ?? 'bg-gray-100 text-gray-600'

async function search(p = 1) {
  loading.value = true
  error.value   = false
  page.value    = p
  try {
    const params = {
      pagina:     p,
      per_pagina: 50,
    }
    if (filters.value.anno)       params.anno       = filters.value.anno
    if (filters.value.categoria)  params.categoria  = filters.value.categoria
    if (filters.value.regione)    params.regione    = filters.value.regione
    if (filters.value.q)          params.q          = filters.value.q
    if (filters.value.runts_only) params.runts_only = true

    const res = await fetchEnti(params)
    result.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function reset() {
  filters.value = { anno: null, categoria: null, regione: '', q: '', runts_only: false }
  result.value  = null
}

function goPage(p) { search(p) }

onMounted(async () => {
  const [aRes, cRes] = await Promise.all([fetchAnni(), fetchCategorie()])
  anni.value      = aRes.data
  categorie.value = cRes.data
  await search()
})
</script>
