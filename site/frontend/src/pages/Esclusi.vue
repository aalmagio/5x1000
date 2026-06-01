<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-6">
      <h1 class="mb-1">Enti esclusi</h1>
      <p class="text-gray-500">
        Enti presenti negli elenchi degli esclusi per almeno una categoria. Chiave: codice fiscale + anno.
        Un ente può risultare escluso in una categoria e ammesso in un'altra nello stesso anno.
      </p>
    </div>

    <!-- Filtri -->
    <div class="card mb-6">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <!-- Ricerca -->
        <div class="sm:col-span-2 lg:col-span-1">
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Nome / Cod. fiscale</label>
          <input
            v-model="q"
            type="text"
            placeholder="Cerca…"
            class="input-field"
            @input="debouncedLoad"
          />
        </div>
        <!-- Anno -->
        <div>
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Anno</label>
          <select v-model="anno" class="input-field" @change="load">
            <option value="">Tutti</option>
            <option v-for="a in anni" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <!-- Categoria esclusa -->
        <div>
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Escluso in categoria</label>
          <select v-model="categoria" class="input-field" @change="load">
            <option value="">Tutte</option>
            <option v-for="c in categorieSlug" :key="c" :value="c">{{ slugLabel(c) }}</option>
          </select>
        </div>
        <!-- Regione -->
        <div>
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Regione</label>
          <select v-model="regione" class="input-field" @change="load">
            <option value="">Tutte</option>
            <option v-for="r in regioni" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="card animate-pulse space-y-3 p-5">
      <div v-for="n in 8" :key="n" class="flex items-start gap-3">
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-2/3"></div>
          <div class="h-3 bg-gray-100 rounded w-1/2"></div>
        </div>
        <div class="h-5 w-20 bg-gray-100 rounded"></div>
      </div>
    </div>

    <!-- Errore -->
    <div v-else-if="error" class="card border-red-200 bg-red-50 text-center py-10">
      <p class="text-red-700">{{ error }}</p>
      <button class="btn-primary mt-4 inline-flex" @click="load">Riprova</button>
    </div>

    <!-- Risultati -->
    <template v-else-if="result">
      <!-- Totale + paginazione info -->
      <div class="flex items-center justify-between mb-3 text-sm text-gray-500">
        <span>
          <strong class="text-gray-800">{{ result.totale.toLocaleString('it-IT') }}</strong>
          {{ result.totale === 1 ? 'ente escluso' : 'enti esclusi' }}
          <span v-if="anno"> nel {{ anno }}</span>
          <span v-if="categoria"> – categoria {{ slugLabel(categoria) }}</span>
        </span>
        <span v-if="result.pagine > 1" class="text-xs">
          Pag. {{ result.pagina }} / {{ result.pagine }}
        </span>
      </div>

      <!-- Lista -->
      <div class="card p-0 overflow-hidden divide-y divide-gray-100">
        <div
          v-for="e in result.data"
          :key="`${e.anno}-${e.cod_fiscale}`"
          class="px-5 py-3.5 hover:bg-red-50/30 transition-colors group"
        >
          <div class="flex items-start gap-3">
            <!-- Badge anno -->
            <span class="flex-shrink-0 mt-0.5 inline-block px-2 py-0.5 rounded text-xs font-bold bg-gray-100 text-gray-500 tabular-nums">
              {{ e.anno }}
            </span>

            <!-- Nome + CF + regione -->
            <div class="flex-1 min-w-0">
              <RouterLink
                :to="`/esclusi/${e.cod_fiscale}`"
                class="font-medium text-gray-900 hover:text-brand-700 block truncate text-sm"
              >{{ e.denominazione || e.cod_fiscale }}</RouterLink>
              <div class="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-0.5 text-xs text-gray-400">
                <span class="font-mono">{{ e.cod_fiscale }}</span>
                <span v-if="e.regione">{{ e.regione }}</span>
              </div>

              <!-- Metriche -->
              <div class="flex flex-wrap items-center gap-3 mt-1.5 text-xs text-gray-500">
                <span v-if="e.n_scelte_escluse">
                  <span class="font-medium text-red-600">{{ e.n_scelte_escluse.toLocaleString('it-IT') }}</span> scelte escluse
                </span>
                <span v-if="e.importo_escluse">
                  <span class="font-medium text-red-600">{{ formatEur(e.importo_escluse) }}</span> escluse
                </span>
                <span v-if="e.n_scelte_ammesse" class="border-l border-gray-200 pl-3">
                  <span class="font-medium text-green-600">{{ e.n_scelte_ammesse.toLocaleString('it-IT') }}</span> scelte ammesse
                </span>
                <span v-if="e.importo_ammesse">
                  <span class="font-medium text-green-600">{{ formatEur(e.importo_ammesse) }}</span> ammesse
                </span>
              </div>

              <!-- Categorie -->
              <div class="flex flex-wrap gap-1.5 mt-2">
                <!-- Escluse -->
                <span
                  v-for="cat in e.categorie_escluse"
                  :key="'ex-' + cat"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 border border-red-200"
                  :title="'Escluso: ' + slugLabel(cat)"
                >
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                  </svg>
                  {{ slugLabel(cat) }}
                </span>
                <!-- Ammesse -->
                <span
                  v-for="cat in e.categorie_ammesse"
                  :key="'am-' + cat"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 border border-green-200"
                  :title="'Ammesso: ' + slugLabel(cat)"
                >
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                  {{ slugLabel(cat) }}
                </span>
              </div>
            </div>

            <!-- Link dettaglio -->
            <RouterLink
              :to="`/esclusi/${e.cod_fiscale}`"
              class="flex-shrink-0 text-xs text-brand-600 opacity-0 group-hover:opacity-100 transition-opacity font-medium mt-1"
            >dettaglio →</RouterLink>
          </div>
        </div>

        <!-- Empty state -->
        <div v-if="!result.data.length" class="text-center py-12 text-gray-400">
          <p>Nessun ente escluso con questi filtri.</p>
        </div>
      </div>

      <!-- Paginazione -->
      <div v-if="result.pagine > 1" class="flex justify-center items-center gap-2 mt-6">
        <button
          class="px-3 py-1.5 rounded border text-sm disabled:opacity-40 hover:bg-gray-50"
          :disabled="pagina <= 1"
          @click="paginaPrev"
        >← Prec</button>
        <span class="text-sm text-gray-500">{{ pagina }} / {{ result.pagine }}</span>
        <button
          class="px-3 py-1.5 rounded border text-sm disabled:opacity-40 hover:bg-gray-50"
          :disabled="pagina >= result.pagine"
          @click="paginaNext"
        >Succ →</button>
      </div>
    </template>
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

// Slug delle categorie (valori usati in categoria_ammissioni.categoria)
const categorieSlug = [
  'volontariato',
  'asd',
  'ets_onlus',
  'ricerca_scientifica',
  'ricerca_sanitaria',
  'comuni',
  'beni_culturali',
  'aree_protette',
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
const formatEur = (n) => n != null && n > 0
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'

const q         = ref('')
const anno      = ref('')
const categoria = ref('')
const regione   = ref('')
const pagina    = ref(1)

const loading = ref(false)
const error   = ref(null)
const result  = ref(null)

async function load() {
  pagina.value  = 1
  loading.value = true
  error.value   = null
  try {
    const res = await fetchEsclusi({
      ...(q.value         ? { q: q.value }               : {}),
      ...(anno.value      ? { anno: anno.value }          : {}),
      ...(categoria.value ? { categoria: categoria.value }: {}),
      ...(regione.value   ? { regione: regione.value }    : {}),
      pagina:    pagina.value,
      per_pagina: 50,
    })
    result.value = res.data
  } catch (e) {
    error.value = e?.response?.data?.error ?? 'Errore nel caricamento'
  } finally {
    loading.value = false
  }
}

async function loadPage() {
  loading.value = true
  error.value   = null
  try {
    const res = await fetchEsclusi({
      ...(q.value         ? { q: q.value }               : {}),
      ...(anno.value      ? { anno: anno.value }          : {}),
      ...(categoria.value ? { categoria: categoria.value }: {}),
      ...(regione.value   ? { regione: regione.value }    : {}),
      pagina:    pagina.value,
      per_pagina: 50,
    })
    result.value = res.data
  } catch (e) {
    error.value = e?.response?.data?.error ?? 'Errore nel caricamento'
  } finally {
    loading.value = false
  }
}

// Debounce per la ricerca testuale
let debounceTimer = null
function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(load, 350)
}

// Sovrascriviamo i click di paginazione per non resettare pagina
// (i pulsanti incrementano pagina.value prima di chiamare load)
// Usiamo loadPage() separato che non resetta pagina
const paginaPrev = () => { pagina.value--; loadPage() }
const paginaNext = () => { pagina.value++; loadPage() }

onMounted(async () => {
  await meta.ensure()
  await load()
})
</script>
