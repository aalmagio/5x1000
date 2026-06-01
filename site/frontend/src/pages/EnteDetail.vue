<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-10">
    <RouterLink to="/dati" class="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700 mb-6">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
      </svg>
      Torna alla ricerca
    </RouterLink>

    <!-- Skeleton loading -->
    <div v-if="loading" class="animate-pulse space-y-6">
      <div class="card">
        <div class="h-7 bg-gray-200 rounded w-2/3 mb-3"></div>
        <div class="h-4 bg-gray-200 rounded w-40 mb-4"></div>
        <div class="flex gap-2">
          <div class="h-6 bg-gray-200 rounded-full w-24"></div>
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div v-for="n in 3" :key="n" class="card h-24 bg-gray-50"></div>
      </div>
      <div class="card">
        <div class="h-5 bg-gray-200 rounded w-48 mb-6"></div>
        <div class="space-y-3">
          <div v-for="n in 5" :key="n" class="flex items-center gap-3">
            <div class="w-12 h-5 bg-gray-200 rounded flex-shrink-0"></div>
            <div class="flex-1 h-8 bg-gray-200 rounded-lg"></div>
            <div class="w-28 h-4 bg-gray-200 rounded flex-shrink-0"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Errore -->
    <div v-else-if="error" class="card border-red-200 bg-red-50 text-center py-12">
      <svg class="w-12 h-12 text-red-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
      </svg>
      <p class="text-red-700 font-medium mb-1">Ente non trovato</p>
      <p class="text-sm text-red-500">Nessun dato per il codice fiscale <code class="font-mono">{{ cf }}</code></p>
      <RouterLink to="/dati" class="btn-primary mt-6 inline-flex">Torna alla ricerca</RouterLink>
    </div>

    <template v-else-if="ente">
      <!-- Header ente -->
      <div class="card mb-6">
        <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <h1 class="text-2xl font-bold text-gray-900 leading-tight">{{ ente.denominazione }}</h1>
            <p class="font-mono text-gray-400 text-sm mt-1 select-all">{{ ente.cod_fiscale }}</p>
            <div class="flex flex-wrap gap-2 mt-3">
              <span
                v-for="cat in (ente.categorie?.length ? ente.categorie : [ente.categoria])"
                :key="cat"
                class="badge"
                :class="catColor(cat)"
              >{{ slugLabel(cat) }}</span>
              <span v-if="ente.runts_denominazione" class="badge bg-green-100 text-green-700">✓ RUNTS</span>
            </div>
          </div>
          <!-- Trend rispetto anno precedente -->
          <div v-if="trend !== null" class="flex-shrink-0 text-right">
            <p class="text-xs text-gray-400 mb-1">vs anno precedente</p>
            <div
              class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-semibold"
              :class="trend >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  :d="trend >= 0 ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'"
                />
              </svg>
              {{ Math.abs(trend).toFixed(1) }}%
            </div>
            <p class="text-xs text-gray-400 mt-1">{{ annoPrecedente }} → {{ annoUltimo }}</p>
          </div>
        </div>
      </div>

      <!-- KPI Cards -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div class="card bg-gradient-to-br from-brand-50 to-white border-brand-100">
          <p class="text-xs font-medium text-brand-500 uppercase tracking-wide mb-1">Totale ricevuto</p>
          <p class="text-2xl font-bold text-brand-700">{{ formatEur(totaleCumulato) }}</p>
          <p class="text-xs text-gray-400 mt-1">su {{ ente.anni_presenti?.length }} anni</p>
        </div>
        <div class="card bg-gradient-to-br from-emerald-50 to-white border-emerald-100">
          <p class="text-xs font-medium text-emerald-500 uppercase tracking-wide mb-1">Anno migliore</p>
          <p class="text-2xl font-bold text-emerald-700">{{ annoBest?.anno ?? '–' }}</p>
          <p class="text-xs text-gray-400 mt-1">{{ formatEur(annoBest?.importo_totale) }}</p>
        </div>
        <div class="card bg-gradient-to-br from-violet-50 to-white border-violet-100">
          <p class="text-xs font-medium text-violet-500 uppercase tracking-wide mb-1">Media annua</p>
          <p class="text-2xl font-bold text-violet-700">{{ formatEur(mediaAnnua) }}</p>
          <p class="text-xs text-gray-400 mt-1">{{ ente.anni_presenti?.at(-1) }}–{{ ente.anni_presenti?.[0] }}</p>
        </div>
        <!-- Reddito medio stimato — basato su 5×1000 = 5‰ IRPEF, aliquota media 20% -->
        <div v-if="redditoStimato" class="card bg-gradient-to-br from-amber-50 to-white border-amber-100">
          <p class="text-xs font-medium text-amber-600 uppercase tracking-wide mb-1">
            Reddito medio stimato
            <span
              class="ml-1 cursor-help text-amber-400"
              title="Stima: firma media / 0,005 (5×1000 = 5‰ IRPEF) / 0,20 (aliquota media). Indicativo, non considera detrazioni."
            >ⓘ</span>
          </p>
          <p class="text-2xl font-bold text-amber-700">{{ formatEur(redditoStimato) }}</p>
          <p class="text-xs text-gray-400 mt-1">IRPEF medio {{ formatEur(irpefMedio) }}</p>
        </div>
      </div>

      <!-- Bar chart storico importi -->
      <div class="card mb-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h2 class="text-gray-900">Andamento storico</h2>
            <p class="text-sm text-gray-400 mt-0.5">Importo totale ricevuto per anno</p>
          </div>
          <span class="text-xs text-gray-400">{{ ente.anni_presenti?.length }} anni di dati</span>
        </div>

        <!-- Legenda categorie (solo per enti multi-categoria) -->
        <div v-if="hasCatBreakdown" class="flex flex-wrap gap-3 mb-4">
          <div
            v-for="cat in categorieBreakdown"
            :key="cat"
            class="flex items-center gap-1.5 text-xs text-gray-600"
          >
            <span class="w-3 h-3 rounded-sm flex-shrink-0" :style="{ backgroundColor: catHex(cat) }"></span>
            {{ slugLabel(cat) }}
          </div>
        </div>

        <div class="space-y-2.5">
          <div
            v-for="r in storicoOrdinato"
            :key="r.anno"
            class="flex items-center gap-3"
          >
            <!-- Anno -->
            <div class="w-12 text-right flex-shrink-0">
              <span class="text-sm font-medium" :class="r.anno === annoUltimo ? 'text-brand-700' : 'text-gray-500'">
                {{ r.anno }}
              </span>
            </div>
            <!-- Barra (stacked per multi-categoria, singola altrimenti) -->
            <div class="flex-1 h-8 bg-gray-100 rounded-lg overflow-hidden flex">
              <template v-if="r.cat_breakdown && animated">
                <div
                  v-for="cb in r.cat_breakdown"
                  :key="cb.categoria"
                  class="h-full transition-all duration-700 ease-out"
                  :style="{
                    width: `${((cb.importo_totale ?? 0) / maxImporto * 100).toFixed(1)}%`,
                    backgroundColor: catHex(cb.categoria),
                    minWidth: (cb.importo_totale ?? 0) > 0 ? '3px' : '0',
                  }"
                ></div>
              </template>
              <template v-else-if="r.cat_breakdown && !animated">
                <div
                  v-for="cb in r.cat_breakdown"
                  :key="cb.categoria"
                  class="h-full"
                  style="width:0%"
                ></div>
              </template>
              <div
                v-else
                class="h-full rounded-lg transition-all duration-700 ease-out flex items-center justify-end pr-3"
                :style="{
                  width: animated ? `${((r.importo_totale ?? 0) / maxImporto * 100).toFixed(1)}%` : '0%',
                  backgroundColor: r.anno === annoUltimo ? '#3b82f6' : '#93c5fd',
                  minWidth: (r.importo_totale ?? 0) > 0 ? '4px' : '0',
                }"
              >
                <span
                  v-if="(r.importo_totale ?? 0) / maxImporto > 0.3"
                  class="text-xs font-semibold text-white whitespace-nowrap"
                >
                  {{ formatEur(r.importo_totale) }}
                </span>
              </div>
            </div>
            <!-- Importo totale a destra -->
            <div class="w-28 flex-shrink-0 text-xs font-semibold text-gray-600 text-right">
              <span v-if="!r.cat_breakdown || (r.importo_totale ?? 0) / maxImporto <= 0.3">
                {{ formatEur(r.importo_totale) }}
              </span>
              <span v-else class="text-gray-400">{{ formatEur(r.importo_totale) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tabella dettaglio storico -->
      <div class="card mb-6">
        <h2 class="mb-4">Dettaglio per anno</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Anno</th>
                <th v-if="categorieMultiple" class="hidden sm:table-cell">Categoria</th>
                <th class="text-right">Scelte</th>
                <th class="text-right hidden sm:table-cell">Imp. espresso</th>
                <th class="text-right hidden sm:table-cell">Imp. generico</th>
                <th class="text-right hidden lg:table-cell">€/firma</th>
                <th class="text-right">Totale</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="r in storicoOrdinato" :key="r.anno">
                <!-- Riga anno (totale) -->
                <tr :class="r.cat_breakdown ? 'font-semibold bg-gray-50' : ''">
                  <td class="font-medium">
                    {{ r.anno }}
                    <span v-if="r.anno === annoUltimo" class="ml-1.5 text-xs text-brand-400 font-normal">ultimo</span>
                  </td>
                  <td v-if="categorieMultiple" class="hidden sm:table-cell">
                    <span v-if="r.categoria" class="badge text-xs" :class="catColor(r.categoria)">{{ slugLabel(r.categoria) }}</span>
                    <span v-else-if="r.cat_breakdown" class="text-xs text-gray-400">{{ r.cat_breakdown.length }} categorie</span>
                    <span v-else class="text-gray-300">–</span>
                  </td>
                  <td class="text-right tabular-nums">{{ formatNum(r.n_scelte) }}</td>
                  <td class="text-right tabular-nums hidden sm:table-cell">{{ formatEur(r.importo_espresso) }}</td>
                  <td class="text-right tabular-nums hidden sm:table-cell">{{ formatEur(r.importo_generico) }}</td>
                  <td class="text-right tabular-nums hidden lg:table-cell text-gray-500">{{ formatEur2(importoMedioFirma(r)) }}</td>
                  <td class="text-right font-semibold text-brand-700 tabular-nums">{{ formatEur(r.importo_totale) }}</td>
                </tr>
                <!-- Sub-righe per categoria (solo anni con più categorie) -->
                <template v-if="r.cat_breakdown">
                  <tr
                    v-for="cb in r.cat_breakdown"
                    :key="r.anno + '-' + cb.categoria"
                    class="text-xs text-gray-500 bg-white"
                  >
                    <td class="pl-6">
                      <span class="inline-flex items-center gap-1.5 text-gray-400">
                        <span class="w-2 h-2 rounded-sm flex-shrink-0" :style="{ backgroundColor: catHex(cb.categoria) }"></span>
                      </span>
                    </td>
                    <td v-if="categorieMultiple" class="hidden sm:table-cell">
                      <span class="badge text-xs" :class="catColor(cb.categoria)">{{ slugLabel(cb.categoria) }}</span>
                    </td>
                    <td class="text-right tabular-nums">{{ formatNum(cb.n_scelte) }}</td>
                    <td class="text-right tabular-nums hidden sm:table-cell">{{ formatEur(cb.importo_espresso) }}</td>
                    <td class="text-right tabular-nums hidden sm:table-cell">{{ formatEur(cb.importo_generico) }}</td>
                    <td class="text-right tabular-nums hidden lg:table-cell text-gray-500">{{ formatEur2(importoMedioFirma(cb)) }}</td>
                    <td class="text-right tabular-nums text-gray-700">{{ formatEur(cb.importo_totale) }}</td>
                  </tr>
                </template>
              </template>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Dati RUNTS -->
      <div v-if="ente.runts_denominazione" class="card">
        <div class="flex items-center gap-2 mb-4">
          <span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-100">
            <svg class="w-3.5 h-3.5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
            </svg>
          </span>
          <h2>Dati RUNTS</h2>
        </div>
        <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4 text-sm">
          <div>
            <dt class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-0.5">Denominazione</dt>
            <dd class="text-gray-800">{{ ente.runts_denominazione ?? '–' }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-0.5">Sezione</dt>
            <dd class="text-gray-800">{{ latestRow?.runts_sezione ?? '–' }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-0.5">Sede</dt>
            <dd class="text-gray-800">
              {{ latestRow?.runts_sede_comune }}
              <span v-if="latestRow?.runts_sede_prov" class="text-gray-400">({{ latestRow.runts_sede_prov }})</span>
            </dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-0.5">Data iscrizione</dt>
            <dd class="text-gray-800">{{ formatDate(latestRow?.runts_data_iscrizione) }}</dd>
          </div>
        </dl>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { fetchEnteStorico } from '@/api/client'

const route    = useRoute()
const cf       = route.params.cf
const ente     = ref(null)
const loading  = ref(true)
const error    = ref(false)
const animated = ref(false)

// ── Slug → label display ─────────────────────────────────────────────────────
const SLUG_LABELS = {
  volontariato:       'Volontariato',
  asd:                'ASD',
  ets_onlus:          'ETS/ONLUS',
  'ets/onlus':        'ETS/ONLUS',
  ricerca_scientifica:'Ricerca Scientifica',
  ricerca_sanitaria:  'Ricerca Sanitaria',
  comuni:             'Comuni',
  beni_culturali:     'Beni Culturali',
  aree_protette:      'Aree Protette',
}
const slugLabel = (s) => SLUG_LABELS[(s ?? '').toLowerCase()] ?? (s ?? '–')

// ── Colori badge (Tailwind classes) ─────────────────────────────────────────
const SLUG_BADGE = {
  volontariato:       'bg-green-100 text-green-700',
  ets_onlus:          'bg-emerald-100 text-emerald-700',
  'ets/onlus':        'bg-emerald-100 text-emerald-700',
  asd:                'bg-blue-100 text-blue-700',
  ricerca_scientifica:'bg-yellow-100 text-yellow-700',
  ricerca_sanitaria:  'bg-red-100 text-red-700',
  comuni:             'bg-orange-100 text-orange-700',
  beni_culturali:     'bg-pink-100 text-pink-700',
  aree_protette:      'bg-teal-100 text-teal-700',
}
const catColor = (c) => SLUG_BADGE[(c ?? '').toLowerCase()] ?? 'bg-brand-100 text-brand-700'

// ── Colori hex per stacked bar ───────────────────────────────────────────────
const SLUG_HEX = {
  volontariato:       '#10b981',
  ets_onlus:          '#34d399',
  'ets/onlus':        '#34d399',
  asd:                '#3b82f6',
  ricerca_scientifica:'#f59e0b',
  ricerca_sanitaria:  '#ef4444',
  comuni:             '#f97316',
  beni_culturali:     '#ec4899',
  aree_protette:      '#14b8a6',
}
const FALLBACK_HEX = ['#6366f1','#8b5cf6','#06b6d4','#84cc16']
const catHex = (c) => {
  const key = (c ?? '').toLowerCase()
  return SLUG_HEX[key] ?? FALLBACK_HEX[
    Math.abs([...key].reduce((h, ch) => (h << 5) - h + ch.charCodeAt(0), 0)) % FALLBACK_HEX.length
  ]
}

const formatNum  = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const formatDate = (d) => d
  ? new Date(d).toLocaleDateString('it-IT', { day: '2-digit', month: 'long', year: 'numeric' })
  : '–'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'

// Storico ordinato dal più recente al più vecchio
const storicoOrdinato = computed(() => {
  if (!ente.value?.storico) return []
  return [...ente.value.storico].sort((a, b) => b.anno - a.anno)
})

const latestRow      = computed(() => storicoOrdinato.value[0])
const annoUltimo     = computed(() => latestRow.value?.anno)
const annoPrecedente = computed(() => storicoOrdinato.value[1]?.anno)

const totaleCumulato = computed(() =>
  storicoOrdinato.value.reduce((acc, r) => acc + (r.importo_totale ?? 0), 0)
)

const annoBest = computed(() =>
  storicoOrdinato.value.reduce(
    (best, r) => ((r.importo_totale ?? 0) > (best?.importo_totale ?? 0) ? r : best),
    null
  )
)

const mediaAnnua = computed(() => {
  const s = storicoOrdinato.value
  return s.length ? totaleCumulato.value / s.length : 0
})

const maxImporto = computed(() =>
  Math.max(...storicoOrdinato.value.map(r => r.importo_totale ?? 0), 1)
)

const trend = computed(() => {
  const s = storicoOrdinato.value
  if (s.length < 2) return null
  const curr = s[0]?.importo_totale ?? 0
  const prev = s[1]?.importo_totale ?? 0
  if (!prev) return null
  return ((curr - prev) / prev) * 100
})

// True se almeno un anno ha il breakdown per categoria
const hasCatBreakdown = computed(() =>
  storicoOrdinato.value.some(r => r.cat_breakdown)
)

// Lista ordinata delle categorie che appaiono nei breakdown (per legenda)
const categorieBreakdown = computed(() => {
  const set = new Set()
  for (const r of storicoOrdinato.value) {
    if (r.cat_breakdown) {
      for (const cb of r.cat_breakdown) {
        if (cb.categoria) set.add(cb.categoria)
      }
    }
  }
  return [...set]
})

// True se l'ente ha più di una categoria (in qualsiasi anno)
const categorieMultiple = computed(() =>
  (ente.value?.categorie?.length ?? 0) > 1 ||
  hasCatBreakdown.value
)

// ── Importo medio per firma ───────────────────────────────────────────────────
const importoMedioFirma = (r) => {
  if (!r?.n_scelte) return null
  const base = r.importo_espresso || r.importo_totale
  return base ? base / r.n_scelte : null
}

const formatEur2 = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 }).format(n)
  : '–'

// ── Reddito medio stimato ─────────────────────────────────────────────────────
const irpefMedio = computed(() => {
  const r = latestRow.value
  if (!r?.n_scelte) return null
  const base = r.importo_espresso || r.importo_totale
  return base ? (base / r.n_scelte) / 0.005 : null
})
const redditoStimato = computed(() => {
  if (!irpefMedio.value) return null
  return irpefMedio.value / 0.20
})

onMounted(async () => {
  try {
    const res = await fetchEnteStorico(cf)
    ente.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
  setTimeout(() => { animated.value = true }, 150)
})
</script>
