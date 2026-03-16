<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-10">
    <RouterLink to="/dati" class="text-sm text-brand-600 hover:underline mb-6 block">&larr; Torna alla ricerca</RouterLink>

    <div v-if="loading" class="text-gray-400 py-16 text-center">Caricamento…</div>

    <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-700 p-6 rounded-lg">
      Ente non trovato per il codice fiscale <strong>{{ cf }}</strong>.
    </div>

    <template v-else-if="ente">
      <!-- Header ente -->
      <div class="card mb-6">
        <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">{{ ente.denominazione }}</h1>
            <p class="font-mono text-gray-400 text-sm mt-1">{{ ente.cod_fiscale }}</p>
            <div class="flex flex-wrap gap-2 mt-3">
              <span class="badge bg-brand-100 text-brand-700">{{ ente.categoria }}</span>
              <span v-if="ente.runts_denominazione" class="badge bg-green-100 text-green-700">RUNTS</span>
            </div>
          </div>
          <div class="text-sm text-gray-500">
            <p>Presente in <strong>{{ ente.anni_presenti?.length }}</strong> anni</p>
            <p class="mt-1">{{ ente.anni_presenti?.at(-1) }}–{{ ente.anni_presenti?.[0] }}</p>
          </div>
        </div>
      </div>

      <!-- Storico importi -->
      <div class="card mb-6">
        <h2 class="mb-4">Storico importi e scelte</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Anno</th>
                <th class="text-right">Scelte</th>
                <th class="text-right">Importo espresso</th>
                <th class="text-right">Importo generico</th>
                <th class="text-right">Totale</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in [...ente.storico].reverse()" :key="r.anno">
                <td class="font-medium">{{ r.anno }}</td>
                <td class="text-right">{{ formatNum(r.n_scelte) }}</td>
                <td class="text-right">{{ formatEur(r.importo_espresso) }}</td>
                <td class="text-right">{{ formatEur(r.importo_generico) }}</td>
                <td class="text-right font-semibold text-brand-700">{{ formatEur(r.importo_totale) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Dati RUNTS -->
      <div v-if="ente.runts_denominazione" class="card">
        <h2 class="mb-4">Dati RUNTS</h2>
        <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3 text-sm">
          <div>
            <dt class="text-gray-400 font-medium">Denominazione</dt>
            <dd>{{ ente.runts_denominazione ?? '–' }}</dd>
          </div>
          <div>
            <dt class="text-gray-400 font-medium">Sezione</dt>
            <dd>{{ ente.storico?.at(-1)?.runts_sezione ?? '–' }}</dd>
          </div>
          <div>
            <dt class="text-gray-400 font-medium">Sede</dt>
            <dd>{{ ente.storico?.at(-1)?.runts_sede_comune }} ({{ ente.storico?.at(-1)?.runts_sede_prov }})</dd>
          </div>
          <div>
            <dt class="text-gray-400 font-medium">Data iscrizione</dt>
            <dd>{{ ente.storico?.at(-1)?.runts_data_iscrizione ?? '–' }}</dd>
          </div>
        </dl>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { fetchEnteStorico } from '@/api/client'

const route   = useRoute()
const cf      = route.params.cf
const ente    = ref(null)
const loading = ref(true)
const error   = ref(false)

const formatNum = (n) => n != null ? Number(n).toLocaleString('it-IT') : '–'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '–'

onMounted(async () => {
  try {
    const res = await fetchEnteStorico(cf)
    ente.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>
