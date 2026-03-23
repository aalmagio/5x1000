<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 py-10">
    <!-- Back -->
    <RouterLink to="/categorie" class="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700 mb-6">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
      </svg>
      Analisi per categoria
    </RouterLink>

    <!-- Skeleton loading -->
    <div v-if="loading" class="animate-pulse space-y-6">
      <div class="h-8 bg-gray-200 rounded w-2/3 mb-2"></div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div v-for="n in 3" :key="n" class="card h-24 bg-gray-50"></div>
      </div>
      <div class="card h-64 bg-gray-50"></div>
    </div>

    <!-- Errore -->
    <div v-else-if="error" class="card border-red-200 bg-red-50 text-center py-12">
      <p class="text-red-700 font-medium mb-1">Dati non disponibili</p>
      <p class="text-sm text-red-500">Categoria: <code class="font-mono">{{ categoria }}</code> — Anno: {{ anno }}</p>
      <RouterLink to="/categorie" class="btn-primary mt-6 inline-flex">Torna alle categorie</RouterLink>
    </div>

    <template v-else-if="data">
      <!-- Title -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900 capitalize">
          {{ categoria.replace(/_/g, ' ') }}
        </h1>
        <p class="text-gray-500 mt-1">Anno {{ anno }}</p>
      </div>

      <!-- KPI cards — riga 1: metriche principali -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
        <div class="card bg-gradient-to-br from-brand-50 to-white border-brand-100">
          <p class="text-xs font-medium text-brand-500 uppercase tracking-wide mb-1">Enti beneficiari</p>
          <p class="text-2xl font-bold text-brand-700">{{ formatNum(data.totali.n_enti) }}</p>
          <p class="text-xs text-gray-400 mt-1">
            <span class="text-red-500">{{ formatNum(data.totali.nr_enti_0_scelte) }}</span> senza scelte ·
            <span class="text-orange-500">{{ formatNum(data.totali.nr_enti_0_importo) }}</span> senza importo
          </p>
        </div>
        <div class="card bg-gradient-to-br from-emerald-50 to-white border-emerald-100">
          <p class="text-xs font-medium text-emerald-500 uppercase tracking-wide mb-1">Scelte totali</p>
          <p class="text-2xl font-bold text-emerald-700">{{ formatNum(data.totali.totale_scelte) }}</p>
          <p class="text-xs text-gray-400 mt-1">
            {{ data.totali.perc_scelte_sul_totale != null ? data.totali.perc_scelte_sul_totale.toFixed(1) + '% del totale 5×mille' : '' }}
          </p>
        </div>
        <div class="card bg-gradient-to-br from-violet-50 to-white border-violet-100">
          <p class="text-xs font-medium text-violet-500 uppercase tracking-wide mb-1">Importo totale</p>
          <p class="text-2xl font-bold text-violet-700">{{ formatEur(data.totali.totale_importo) }}</p>
          <p class="text-xs text-gray-400 mt-1">
            {{ data.totali.perc_importo_sul_totale != null ? data.totali.perc_importo_sul_totale.toFixed(1) + '% del totale 5×mille' : '' }}
          </p>
        </div>
      </div>

      <!-- KPI cards — riga 2: valore medio e generica -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div class="card bg-gradient-to-br from-sky-50 to-white border-sky-100">
          <p class="text-xs font-medium text-sky-500 uppercase tracking-wide mb-1">Valore medio scelta espressa</p>
          <p class="text-2xl font-bold text-sky-700">
            {{ data.totali.valore_medio_espressa != null ? formatEur(data.totali.valore_medio_espressa) : '–' }}
          </p>
          <p class="text-xs text-gray-400 mt-1">espresso / nr. scelte</p>
        </div>
        <div class="card bg-gradient-to-br from-amber-50 to-white border-amber-100">
          <p class="text-xs font-medium text-amber-500 uppercase tracking-wide mb-1">Valore medio redistribuito</p>
          <p class="text-2xl font-bold text-amber-700">
            {{ data.totali.valore_medio_redistribuito != null ? formatEur(data.totali.valore_medio_redistribuito) : '–' }}
          </p>
          <p class="text-xs text-gray-400 mt-1">generico / nr. enti</p>
        </div>
        <div class="card bg-gradient-to-br from-orange-50 to-white border-orange-100">
          <p class="text-xs font-medium text-orange-500 uppercase tracking-wide mb-1">Incidenza generica</p>
          <p class="text-2xl font-bold text-orange-700">
            {{ data.totali.perc_incidenza_generica != null ? data.totali.perc_incidenza_generica.toFixed(1) + '%' : '–' }}
          </p>
          <p class="text-xs text-gray-400 mt-1">{{ formatEur(data.totali.totale_generico) }} su totale erogato</p>
        </div>
      </div>

      <!-- Tile Map + Bar chart: affiancati su desktop -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">

      <!-- Tile cartogram -->
      <div class="card">
        <RegionTileMap
          :data="regioneTileData"
          title="Mappa importo per regione"
          :subtitle="`Anno ${anno}`"
          color-low="#dbeafe"
          color-high="#1e40af"
          label-low="minore"
          label-high="maggiore"
          :format-fn="formatEurShort"
        />
      </div>

      <!-- Bar chart per regione -->
      <div class="card">
        <h2 class="mb-5">Distribuzione per regione</h2>
        <div class="space-y-2.5">
          <div
            v-for="r in data.per_regione"
            :key="r.regione"
            class="flex items-center gap-3"
          >
            <div class="w-36 text-right flex-shrink-0">
              <p class="text-sm font-medium text-gray-700 truncate">{{ r.regione ?? 'N/D' }}</p>
              <p class="text-xs text-gray-400">{{ formatNum(r.n_enti) }} enti</p>
            </div>
            <div class="flex-1 h-9 bg-gray-100 rounded-lg overflow-hidden">
              <div
                class="h-full rounded-lg transition-all duration-700 ease-out flex items-center justify-end pr-3"
                :style="{
                  width: animated ? `${((r.totale_importo / maxRegione) * 100).toFixed(1)}%` : '0%',
                  backgroundColor: '#3b82f6',
                  minWidth: r.totale_importo > 0 ? '4px' : '0',
                }"
              >
                <span
                  v-if="r.totale_importo / maxRegione > 0.25"
                  class="text-xs font-semibold text-white whitespace-nowrap"
                >
                  {{ formatEur(r.totale_importo) }}
                </span>
              </div>
            </div>
            <div class="w-28 flex-shrink-0 text-xs font-semibold text-gray-700 text-right">
              <span v-if="r.totale_importo / maxRegione <= 0.25">{{ formatEur(r.totale_importo) }}</span>
            </div>
          </div>
        </div>
      </div>

      </div><!-- end grid -->

      <!-- Tabella enti paginata -->
      <div class="card p-0 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2>Enti beneficiari — {{ formatNum(data.totali.n_enti) }} totali</h2>
          <span class="text-sm text-gray-400">Pagina {{ data.pagina }} / {{ data.pagine }}</span>
        </div>
        <div class="table-wrap rounded-none border-0">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Ente</th>
                <th class="hidden sm:table-cell">Regione</th>
                <th class="text-right">Scelte</th>
                <th class="text-right">Importo</th>
                <th class="hidden sm:table-cell text-center">RUNTS</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(e, i) in data.enti"
                :key="e.cod_fiscale"
                class="cursor-pointer"
                @click="$router.push({ name: 'ente', params: { cf: e.cod_fiscale } })"
              >
                <td class="text-gray-400 text-xs tabular-nums">
                  {{ (data.pagina - 1) * data.per_pagina + i + 1 }}
                </td>
                <td>
                  <p class="font-medium text-gray-900 text-sm">{{ e.denominazione }}</p>
                  <p class="font-mono text-xs text-gray-400">{{ e.cod_fiscale }}</p>
                </td>
                <td class="hidden sm:table-cell text-gray-500 text-sm">{{ e.regione ?? '–' }}</td>
                <td class="text-right tabular-nums text-sm">{{ formatNum(e.n_scelte) }}</td>
                <td class="text-right tabular-nums font-semibold text-brand-700 text-sm">{{ formatEur(e.importo_totale) }}</td>
                <td class="hidden sm:table-cell text-center">
                  <span v-if="e.runts_5x1000" class="badge bg-green-100 text-green-700 text-xs">✓</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Paginazione -->
        <div v-if="data.pagine > 1" class="px-6 py-4 border-t border-gray-100 flex items-center justify-between gap-4">
          <button
            class="btn-secondary text-sm py-1.5 px-3"
            :disabled="data.pagina <= 1"
            @click="changePage(data.pagina - 1)"
          >
            ← Precedente
          </button>
          <div class="flex gap-1">
            <button
              v-for="p in pageRange"
              :key="p"
              class="w-8 h-8 rounded text-sm font-medium transition-colors"
              :class="p === data.pagina
                ? 'bg-brand-600 text-white'
                : 'hover:bg-gray-100 text-gray-600'"
              @click="changePage(p)"
            >
              {{ p }}
            </button>
          </div>
          <button
            class="btn-secondary text-sm py-1.5 px-3"
            :disabled="data.pagina >= data.pagine"
            @click="changePage(data.pagina + 1)"
          >
            Successiva →
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { fetchCategoriaDettaglio } from '@/api/client'
import RegionTileMap from '@/components/RegionTileMap.vue'

const route    = useRoute()
const categoria = route.params.categoria
const anno      = Number(route.params.anno)

const data     = ref(null)
const loading  = ref(true)
const error    = ref(false)
const animated = ref(false)

const formatNum = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'
function formatEurShort(v) {
  if (v == null) return '–'
  if (v >= 1e9) return (v / 1e9).toFixed(1) + 'Mrd'
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M'
  if (v >= 1e3) return (v / 1e3).toFixed(0) + 'k'
  return v.toFixed(0) + '€'
}

const regioneTileData = computed(() =>
  (data.value?.per_regione ?? []).map(r => ({
    regione: r.regione,
    value:   r.totale_importo ?? 0,
  }))
)

const maxRegione = computed(() =>
  data.value?.per_regione?.length
    ? Math.max(...data.value.per_regione.map(r => r.totale_importo ?? 0), 1)
    : 1
)

const pageRange = computed(() => {
  if (!data.value) return []
  const total = data.value.pagine
  const cur   = data.value.pagina
  const delta = 2
  const pages = new Set([1, total])
  for (let p = Math.max(1, cur - delta); p <= Math.min(total, cur + delta); p++) pages.add(p)
  return [...pages].sort((a, b) => a - b)
})

async function loadPage(pagina = 1) {
  loading.value  = true
  error.value    = false
  animated.value = false
  try {
    const res  = await fetchCategoriaDettaglio(categoria, anno, pagina)
    data.value = res.data
    setTimeout(() => { animated.value = true }, 100)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function changePage(p) {
  if (p < 1 || p > data.value?.pagine) return
  loadPage(p)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => loadPage())
</script>
