<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-10">
    <RouterLink to="/esclusi" class="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700 mb-6">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
      </svg>
      Torna agli esclusi
    </RouterLink>

    <!-- Skeleton -->
    <div v-if="loading" class="animate-pulse space-y-6">
      <div class="card">
        <div class="h-7 bg-gray-200 rounded w-2/3 mb-3"></div>
        <div class="h-4 bg-gray-200 rounded w-40"></div>
      </div>
      <div class="card space-y-3 p-5">
        <div v-for="n in 4" :key="n" class="h-12 bg-gray-100 rounded"></div>
      </div>
    </div>

    <!-- Errore -->
    <div v-else-if="error" class="card border-red-200 bg-red-50 text-center py-12">
      <p class="text-red-700 font-medium mb-1">Ente non trovato</p>
      <p class="text-sm text-red-500">Nessun dato per il codice fiscale <code class="font-mono">{{ cf }}</code></p>
      <RouterLink to="/esclusi" class="btn-primary mt-6 inline-flex">Torna agli esclusi</RouterLink>
    </div>

    <template v-else-if="ente">
      <!-- Header -->
      <div class="card mb-6">
        <div class="flex items-start gap-3">
          <div class="flex-shrink-0 w-9 h-9 rounded-full bg-red-100 flex items-center justify-center mt-0.5">
            <svg class="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <h1 class="text-2xl font-bold text-gray-900 leading-tight">{{ ente.denominazione }}</h1>
            <p class="font-mono text-gray-400 text-sm mt-1 select-all">{{ ente.cod_fiscale }}</p>
            <p class="text-sm text-gray-500 mt-2">
              Presente negli elenchi di esclusione/ammissione per
              <strong>{{ ente.anni_presenti?.length }}</strong> anno/i
              ({{ ente.anni_presenti?.at(-1) }}–{{ ente.anni_presenti?.[0] }}).
              Fonte: elenchi AdE per categoria.
            </p>
          </div>
        </div>
      </div>

      <!-- Storico per anno -->
      <div class="space-y-4">
        <div
          v-for="r in ente.storico"
          :key="r.anno"
          class="card"
        >
          <!-- Intestazione anno -->
          <div class="flex items-center gap-2 mb-4">
            <span class="inline-block px-2.5 py-1 rounded text-sm font-bold bg-gray-100 text-gray-600 tabular-nums">
              {{ r.anno }}
            </span>
            <span
              v-if="r.escluse.length && r.ammesse.length"
              class="text-xs text-amber-600 font-medium bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200"
            >Escluso in alcune categorie, ammesso in altre</span>
            <span
              v-else-if="r.escluse.length"
              class="text-xs text-red-600 font-medium bg-red-50 px-2 py-0.5 rounded-full border border-red-200"
            >Solo escluso</span>
          </div>

          <!-- Categorie escluse -->
          <div v-if="r.escluse.length" class="mb-4">
            <p class="text-xs font-semibold text-red-600 uppercase tracking-wide mb-2">Escluso</p>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-xs text-gray-400 uppercase tracking-wide border-b border-gray-100">
                    <th class="text-left pb-1.5 font-medium">Categoria</th>
                    <th class="text-right pb-1.5 font-medium">Scelte</th>
                    <th class="text-right pb-1.5 font-medium hidden sm:table-cell">Imp. espresso</th>
                    <th class="text-right pb-1.5 font-medium hidden sm:table-cell">Imp. generico</th>
                    <th class="text-right pb-1.5 font-medium">Totale</th>
                    <th class="text-right pb-1.5 font-medium hidden lg:table-cell">Erogabile</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-red-50">
                  <tr v-for="c in r.escluse" :key="c.categoria" class="hover:bg-red-50/40">
                    <td class="py-2 pr-4">
                      <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                        ✗ {{ slugLabel(c.categoria) }}
                      </span>
                    </td>
                    <td class="py-2 text-right tabular-nums text-gray-700">{{ fmt(c.n_scelte) }}</td>
                    <td class="py-2 text-right tabular-nums text-gray-500 hidden sm:table-cell">{{ fmtEur(c.importo_espresso) }}</td>
                    <td class="py-2 text-right tabular-nums text-gray-500 hidden sm:table-cell">{{ fmtEur(c.importo_generico) }}</td>
                    <td class="py-2 text-right tabular-nums font-semibold text-red-700">{{ fmtEur(c.importo_totale) }}</td>
                    <td class="py-2 text-right tabular-nums text-gray-400 hidden lg:table-cell">{{ fmtEur(c.importo_totale_erogabile) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Categorie ammesse -->
          <div v-if="r.ammesse.length">
            <p class="text-xs font-semibold text-green-600 uppercase tracking-wide mb-2">Ammesso</p>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-xs text-gray-400 uppercase tracking-wide border-b border-gray-100">
                    <th class="text-left pb-1.5 font-medium">Categoria</th>
                    <th class="text-right pb-1.5 font-medium">Scelte</th>
                    <th class="text-right pb-1.5 font-medium hidden sm:table-cell">Imp. espresso</th>
                    <th class="text-right pb-1.5 font-medium hidden sm:table-cell">Imp. generico</th>
                    <th class="text-right pb-1.5 font-medium">Totale</th>
                    <th class="text-right pb-1.5 font-medium hidden lg:table-cell">Erogabile</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-green-50">
                  <tr v-for="c in r.ammesse" :key="c.categoria" class="hover:bg-green-50/40">
                    <td class="py-2 pr-4">
                      <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                        ✓ {{ slugLabel(c.categoria) }}
                      </span>
                    </td>
                    <td class="py-2 text-right tabular-nums text-gray-700">{{ fmt(c.n_scelte) }}</td>
                    <td class="py-2 text-right tabular-nums text-gray-500 hidden sm:table-cell">{{ fmtEur(c.importo_espresso) }}</td>
                    <td class="py-2 text-right tabular-nums text-gray-500 hidden sm:table-cell">{{ fmtEur(c.importo_generico) }}</td>
                    <td class="py-2 text-right tabular-nums font-semibold text-green-700">{{ fmtEur(c.importo_totale) }}</td>
                    <td class="py-2 text-right tabular-nums text-gray-400 hidden lg:table-cell">{{ fmtEur(c.importo_totale_erogabile) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { fetchEsclusiDetail } from '@/api/client'

const route   = useRoute()
const cf      = route.params.cf
const ente    = ref(null)
const loading = ref(true)
const error   = ref(false)

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

const fmt    = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const fmtEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'

onMounted(async () => {
  try {
    const res = await fetchEsclusiDetail(cf)
    ente.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>
