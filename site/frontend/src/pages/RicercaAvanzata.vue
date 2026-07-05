<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-8">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Ricerca Avanzata</h1>
      <p class="text-gray-500 mt-1 text-sm">
        Stato degli enti nei riparti — categorie ammesse ed escluse da <em>categoria_ammissioni</em>.
        Usa il filtro "Solo conflitti" per trovare enti presenti in più categorie con stati diversi.
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
        <!-- Categoria (presenza in qualsiasi stato) -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">Categoria riparto</label>
          <select
            v-model="filters.categoria"
            class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            @change="search"
          >
            <option :value="null">Tutte le categorie</option>
            <option v-for="c in ALL_CATS" :key="c.slug" :value="c.slug">{{ c.label }}</option>
          </select>
        </div>
        <!-- Stato categoria (opzionale, attivo solo se categoria selezionata) -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">Stato in categoria</label>
          <select
            v-model="filters.stato_cat"
            :disabled="!filters.categoria"
            class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 disabled:opacity-40"
            @change="search"
          >
            <option value="">Qualsiasi</option>
            <option value="ammesso">Ammesso</option>
            <option value="escluso">Escluso</option>
          </select>
        </div>
      </div>

      <!-- Solo conflitti + reset -->
      <div class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <label class="flex items-center gap-2 cursor-pointer select-none text-sm text-gray-600">
          <input
            type="checkbox"
            v-model="filters.solo_conflitti"
            class="w-4 h-4 accent-brand-500 rounded"
            @change="search"
          />
          <span>Solo conflitti <span class="text-gray-400 font-normal">(ammesso in una cat, escluso in un'altra)</span></span>
        </label>
        <button
          v-if="hasActiveFilters"
          @click="reset"
          class="ml-auto text-xs text-gray-400 hover:text-gray-600 underline"
        >Azzera filtri</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-16">
      <div class="animate-spin w-8 h-8 border-4 border-brand-300 border-t-brand-600 rounded-full"></div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-xl p-4 text-red-600 text-sm">
      {{ error }}
    </div>

    <!-- Results -->
    <div v-else>
      <!-- Summary bar -->
      <div class="flex items-center justify-between mb-3">
        <span class="text-sm text-gray-500">
          <span class="font-semibold text-gray-800">{{ totale.toLocaleString('it-IT') }}</span> risultati
          <span v-if="pagine > 1"> — pagina {{ pagina }}/{{ pagine }}</span>
        </span>
        <!-- Legend -->
        <div class="hidden sm:flex items-center gap-3 text-xs text-gray-500">
          <span class="inline-flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-sm bg-green-100 border border-green-200"></span>
            Ammesso
          </span>
          <span class="inline-flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-sm bg-red-100 border border-red-200"></span>
            Escluso
          </span>
        </div>
      </div>

      <!-- Table -->
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-100 bg-gray-50/80">
                <th class="text-left px-4 py-3 font-semibold text-gray-600 w-16">Anno</th>
                <th class="text-left px-4 py-3 font-semibold text-gray-600">Ente</th>
                <th class="text-left px-4 py-3 font-semibold text-gray-600 hidden md:table-cell w-36">Regione</th>
                <th class="text-left px-4 py-3 font-semibold text-gray-600">Stato nei riparti</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="rows.length === 0">
                <td colspan="4" class="text-center py-12 text-gray-400">Nessun risultato</td>
              </tr>
              <tr
                v-for="r in rows"
                :key="`${r.anno}-${r.cod_fiscale}`"
                class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
                :class="r.ha_conflitti ? 'bg-amber-50/30' : ''"
              >
                <td class="px-4 py-3 text-gray-500 tabular-nums align-top">{{ r.anno }}</td>
                <td class="px-4 py-3 align-top">
                  <RouterLink
                    :to="`/ente/${r.cod_fiscale}`"
                    class="font-medium text-brand-600 hover:text-brand-700 hover:underline leading-tight block"
                  >{{ r.denominazione }}</RouterLink>
                  <span class="text-xs text-gray-400 font-mono">{{ r.cod_fiscale }}</span>
                </td>
                <td class="px-4 py-3 text-gray-500 text-xs hidden md:table-cell align-top">{{ r.regione || '–' }}</td>
                <td class="px-4 py-3 align-top">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="cat in r.categorie_ammesse"
                      :key="`amm-${cat}`"
                      class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700"
                    >
                      <span class="text-green-500 leading-none">✓</span>
                      {{ slugLabel(cat) }}
                    </span>
                    <span
                      v-for="cat in r.categorie_escluse"
                      :key="`esc-${cat}`"
                      class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-600"
                    >
                      <span class="text-red-400 leading-none">✗</span>
                      {{ slugLabel(cat) }}
                    </span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="pagine > 1" class="flex justify-center gap-2 mt-6 flex-wrap">
        <button
          v-for="p in paginationRange"
          :key="p"
          :disabled="p === '...'"
          @click="p !== '...' && goPage(p)"
          class="px-3 py-1.5 text-sm rounded-lg border transition-colors"
          :class="p === pagina
            ? 'bg-brand-500 text-white border-brand-500 font-semibold'
            : p === '...' ? 'border-transparent text-gray-400 cursor-default'
            : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
        >{{ p }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useMetaStore } from '@/stores/meta'
import { fetchRicercaAvanzata } from '@/api/client'

const meta = useMetaStore()

const loading = ref(false)
const error   = ref(null)
const rows    = ref([])
const totale  = ref(0)
const pagina  = ref(1)
const pagine  = ref(1)

const filters = ref({
  q:              '',
  anno:           null,
  categoria:      null,
  stato_cat:      '',
  regione:        null,
  solo_conflitti: false,
})

const ALL_CATS = [
  { slug: 'ets_onlus',          label: 'ETS/ONLUS' },
  { slug: 'volontariato',       label: 'Volontariato' },
  { slug: 'asd',                label: 'ASD' },
  { slug: 'ricerca_scientifica',label: 'Ricerca Scientifica' },
  { slug: 'ricerca_sanitaria',  label: 'Ricerca Sanitaria' },
  { slug: 'comuni',             label: 'Comuni' },
  { slug: 'beni_culturali',     label: 'Beni Culturali' },
  { slug: 'aree_protette',      label: 'Aree Protette' },
]

const SLUG_LABELS = {
  volontariato:        'Volontariato',
  asd:                 'ASD',
  ets_onlus:           'ETS/ONLUS',
  'ets/onlus':         'ETS/ONLUS',
  ricerca_scientifica: 'Ric. Scient.',
  ricerca_sanitaria:   'Ric. Sanit.',
  comuni:              'Comuni',
  beni_culturali:      'Beni Cult.',
  aree_protette:       'Aree Prot.',
}
const slugLabel = (s) => SLUG_LABELS[(s ?? '').toLowerCase()] ?? (s ?? '–')

const hasActiveFilters = computed(() =>
  !!filters.value.q ||
  filters.value.anno !== null ||
  filters.value.categoria !== null ||
  !!filters.value.regione ||
  filters.value.solo_conflitti
)

function buildParams(pg = 1) {
  const p = { pagina: pg }
  if (filters.value.q)              p.q             = filters.value.q
  if (filters.value.anno)           p.anno          = filters.value.anno
  if (filters.value.categoria)      p.categoria     = filters.value.categoria
  if (filters.value.categoria && filters.value.stato_cat) p.stato_cat = filters.value.stato_cat
  if (filters.value.regione)        p.regione       = filters.value.regione
  if (filters.value.solo_conflitti) p.solo_conflitti = 1
  return p
}

async function search() {
  loading.value = true
  error.value   = null
  try {
    const res    = await fetchRicercaAvanzata(buildParams(1))
    rows.value   = res.data.data    ?? []
    totale.value = res.data.totale  ?? 0
    pagine.value = res.data.pagine  ?? 1
    pagina.value = res.data.pagina  ?? 1
  } catch (e) {
    error.value = e?.response?.data?.error ?? 'Errore caricamento dati'
  } finally {
    loading.value = false
  }
}

async function goPage(p) {
  if (p === pagina.value) return
  loading.value = true
  error.value   = null
  try {
    const res    = await fetchRicercaAvanzata(buildParams(p))
    rows.value   = res.data.data    ?? []
    totale.value = res.data.totale  ?? 0
    pagine.value = res.data.pagine  ?? 1
    pagina.value = res.data.pagina  ?? 1
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e) {
    error.value = e?.response?.data?.error ?? 'Errore caricamento dati'
  } finally {
    loading.value = false
  }
}

function reset() {
  filters.value = {
    q:              '',
    anno:           meta.annoCorrente,
    categoria:      null,
    stato_cat:      '',
    regione:        null,
    solo_conflitti: false,
  }
  search()
}

let debounceTimer = null
function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(search, 400)
}

const paginationRange = computed(() => {
  const total = pagine.value
  const cur   = pagina.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = new Set([1, total, cur])
  if (cur > 1) pages.add(cur - 1)
  if (cur < total) pages.add(cur + 1)
  const sorted = [...pages].sort((a, b) => a - b)
  const result = []
  let prev = 0
  for (const p of sorted) {
    if (p - prev > 1) result.push('...')
    result.push(p)
    prev = p
  }
  return result
})

onMounted(async () => {
  await meta.ensure()
  filters.value.anno = meta.annoCorrente
  await search()
})
</script>
