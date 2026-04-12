<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-6">
      <h1 class="mb-1">Classifica enti</h1>
      <p class="text-gray-500">Top enti, maggiori crescite, cali e nuovi entranti per anno.</p>
    </div>

    <!-- Filtri -->
    <div class="card mb-6">
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <div>
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Anno</label>
          <select v-model="anno" class="input-field" @change="load">
            <option v-for="a in anni" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Categoria</label>
          <select v-model="categoria" class="input-field" @change="load">
            <option value="">Tutte</option>
            <option v-for="c in categorie" :key="c" :value="c">{{ c.replace(/_/g,' ') }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Regione</label>
          <select v-model="regione" class="input-field" @change="load">
            <option value="">Tutte</option>
            <option v-for="r in regioni" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Metrica</label>
          <div class="flex rounded-lg border border-gray-200 overflow-hidden text-xs">
            <button
              v-for="m in metriche"
              :key="m.val"
              class="flex-1 py-2 font-medium transition-colors"
              :class="metrica === m.val ? 'bg-brand-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
              @click="metrica = m.val; load()"
            >{{ m.label }}</button>
          </div>
        </div>
      </div>

      <!-- Tipo tabs -->
      <div class="flex flex-wrap gap-2">
        <button
          v-for="t in tipi"
          :key="t.val"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
          :class="tipo === t.val
            ? 'bg-brand-600 text-white border-brand-600'
            : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400 hover:text-brand-700'"
          @click="tipo = t.val; load()"
        >
          <span>{{ t.icon }}</span>{{ t.label }}
        </button>
      </div>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="card animate-pulse space-y-3">
      <div v-for="n in 8" :key="n" class="flex items-center gap-4">
        <div class="w-8 h-8 bg-gray-200 rounded-full flex-shrink-0"></div>
        <div class="flex-1 h-5 bg-gray-100 rounded"></div>
        <div class="w-24 h-5 bg-gray-100 rounded"></div>
        <div class="w-20 h-5 bg-gray-200 rounded"></div>
      </div>
    </div>

    <!-- Errore -->
    <div v-else-if="error" class="card border-red-200 bg-red-50 text-center py-10">
      <p class="text-red-700">{{ error }}</p>
      <button class="btn-primary mt-4 inline-flex" @click="load">Riprova</button>
    </div>

    <!-- Risultati -->
    <div v-else-if="result">
      <!-- Intestazione risultati -->
      <div class="flex items-center justify-between mb-3 text-sm text-gray-500">
        <span>
          <strong class="text-gray-800">{{ result.enti.length }}</strong> enti
          <span v-if="tipo === 'crescita' || tipo === 'calo'">
            — variazione {{ result.anno_prec }}→{{ result.anno }}
          </span>
          <span v-else-if="tipo === 'newcomer'">
            — nuovi nel {{ result.anno }} (non presenti nel {{ result.anno_prec }})
          </span>
          <span v-else>
            — anno {{ result.anno }}
          </span>
        </span>
      </div>

      <!-- Lista -->
      <div class="card p-0 overflow-hidden divide-y divide-gray-100">
        <div
          v-for="e in result.enti"
          :key="e.cod_fiscale"
          class="flex items-center gap-3 px-5 py-3.5 hover:bg-brand-50/40 transition-colors group"
        >
          <!-- Rank badge -->
          <div
            class="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
            :class="rankClass(e.rank)"
          >{{ e.rank }}</div>

          <!-- Nome + info -->
          <div class="flex-1 min-w-0">
            <RouterLink
              :to="`/ente/${e.cod_fiscale}`"
              class="font-medium text-gray-900 hover:text-brand-700 truncate block text-sm"
            >{{ e.denominazione }}</RouterLink>
            <div class="flex items-center gap-2 mt-0.5">
              <span
                class="badge text-xs capitalize"
                :class="catColor(e.categoria_principale)"
              >{{ (e.categoria_principale ?? '–').replace(/_/g,' ') }}</span>
              <span class="text-xs text-gray-400">{{ e.regione ?? '' }}</span>
            </div>
          </div>

          <!-- Valore principale -->
          <div class="flex-shrink-0 text-right">
            <template v-if="tipo === 'crescita' || tipo === 'calo'">
              <p class="text-sm font-semibold text-gray-900 tabular-nums">
                {{ metrica === 'importo' ? formatEur(e.importo_cur) : formatNum(e.scelte_cur) }}
              </p>
              <p class="text-xs text-gray-400 tabular-nums">
                da {{ metrica === 'importo' ? formatEur(e.importo_prec) : formatNum(e.scelte_prec) }}
              </p>
            </template>
            <template v-else>
              <p class="text-sm font-semibold tabular-nums"
                 :class="metrica === 'importo' ? 'text-brand-700' : 'text-emerald-700'">
                {{ metrica === 'importo' ? formatEur(e.importo_totale) : formatNum(e.n_scelte) }}
              </p>
            </template>
          </div>

          <!-- Badge variazione (solo crescita/calo) -->
          <div v-if="tipo === 'crescita' || tipo === 'calo'" class="flex-shrink-0 w-20 text-right">
            <span
              class="inline-flex items-center gap-0.5 text-xs font-bold px-2 py-0.5 rounded-full tabular-nums"
              :class="(e.perc_var ?? 0) >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
            >
              {{ (e.perc_var ?? 0) >= 0 ? '▲' : '▼' }}
              {{ Math.abs(e.perc_var ?? 0).toFixed(1) }}%
            </span>
          </div>

          <!-- Badge newcomer -->
          <div v-else-if="tipo === 'newcomer'" class="flex-shrink-0">
            <span class="badge bg-yellow-100 text-yellow-700 text-xs">Nuovo</span>
          </div>

          <!-- Link storico -->
          <RouterLink
            :to="`/ente/${e.cod_fiscale}`"
            class="flex-shrink-0 text-xs text-brand-600 opacity-0 group-hover:opacity-100 transition-opacity font-medium"
          >storico →</RouterLink>
        </div>

        <!-- Empty state -->
        <div v-if="!result.enti.length" class="text-center py-12 text-gray-400">
          <p>Nessun dato disponibile con questi filtri.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchClassifica } from '@/api/client'
import { useMetaStore } from '@/stores/meta'

const meta      = useMetaStore()
const anni      = computed(() => meta.anni)
const categorie = computed(() => meta.categorie)
const regioni   = computed(() => meta.regioni)

const anno      = ref(null)
const categoria = ref('')
const regione   = ref('')
const metrica   = ref('importo')
const tipo      = ref('top')

const loading = ref(false)
const error   = ref(null)
const result  = ref(null)

const metriche = [
  { val: 'importo', label: 'Importo' },
  { val: 'scelte',  label: 'Scelte' },
]
const tipi = [
  { val: 'top',      icon: '🏆', label: 'Top 25' },
  { val: 'crescita', icon: '📈', label: 'Maggiore crescita' },
  { val: 'calo',     icon: '📉', label: 'Maggiore calo' },
  { val: 'newcomer', icon: '⭐', label: 'Nuovi entranti' },
]

async function load() {
  loading.value = true
  error.value   = null
  try {
    const res = await fetchClassifica({
      anno:       anno.value,
      metrica:    metrica.value,
      tipo:       tipo.value,
      categoria:  categoria.value || undefined,
      regione:    regione.value   || undefined,
      per_pagina: 25,
    })
    result.value = res.data
  } catch (e) {
    error.value = e?.response?.data?.error ?? 'Errore nel caricamento'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await meta.ensure()
  anno.value = anni.value[0] ?? null
  await load()
})

// ─── Helpers ────────────────────────────────────────────────────────────────

const formatNum = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'

function rankClass(rank) {
  if (rank === 1) return 'bg-yellow-400 text-yellow-900'
  if (rank === 2) return 'bg-gray-300 text-gray-700'
  if (rank === 3) return 'bg-amber-600 text-white'
  return 'bg-gray-100 text-gray-500'
}

const CAT_COLORS = {
  'volontariato':               'bg-green-100 text-green-700',
  'asd':                        'bg-blue-100 text-blue-700',
  'ricerca_scientifica':        'bg-yellow-100 text-yellow-700',
  'ricerca_sanitaria':          'bg-red-100 text-red-700',
  'comuni':                     'bg-orange-100 text-orange-700',
  'beni_culturali':             'bg-pink-100 text-pink-700',
  'enti_gestori_aree_protette': 'bg-teal-100 text-teal-700',
}
const catColor = (c) => CAT_COLORS[(c ?? '').toLowerCase()] ?? 'bg-gray-100 text-gray-600'
</script>
