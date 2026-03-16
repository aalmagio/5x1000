<template>
  <div>
    <!-- Hero -->
    <section class="bg-brand-700 text-white py-16 px-4">
      <div class="max-w-4xl mx-auto text-center">
        <h1 class="text-4xl sm:text-5xl font-extrabold mb-4">
          Dati aperti sul <span class="text-yellow-300">5×1000</span>
        </h1>
        <p class="text-brand-100 text-lg mb-8 max-w-2xl mx-auto">
          20 anni di dati sui beneficiari del cinque per mille italiano.
          Scarica il dataset completo o interroga l'API pubblica.
        </p>
        <div class="flex flex-wrap justify-center gap-3">
          <RouterLink to="/dati"     class="btn-primary bg-yellow-400 text-brand-900 hover:bg-yellow-300">Esplora i dati</RouterLink>
          <RouterLink to="/download" class="btn-secondary border-white text-white hover:bg-white/10">Scarica dataset</RouterLink>
          <RouterLink to="/api"      class="btn-secondary border-white text-white hover:bg-white/10">Documentazione API</RouterLink>
        </div>
      </div>
    </section>

    <!-- Status bar -->
    <div v-if="status" class="bg-green-50 border-b border-green-200 px-4 py-2 text-sm text-center text-green-700">
      Ultimo aggiornamento:
      <strong>{{ formatDate(status.ultimo_aggiornamento) }}</strong>
      &bull;
      <strong>{{ formatNum(status.righe_totali) }}</strong> record •
      anni {{ status.anni_disponibili?.at(-1) }}–{{ status.anni_disponibili?.[0] }}
    </div>

    <!-- Stats cards -->
    <section class="max-w-7xl mx-auto px-4 sm:px-6 py-12">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-12">
        <div class="card text-center">
          <p class="text-4xl font-bold text-brand-600">{{ status?.anni_disponibili?.length ?? '…' }}</p>
          <p class="text-gray-500 mt-1">Anni di dati</p>
        </div>
        <div class="card text-center">
          <p class="text-4xl font-bold text-brand-600">{{ formatNum(status?.righe_totali) }}</p>
          <p class="text-gray-500 mt-1">Record totali</p>
        </div>
        <div class="card text-center">
          <p class="text-4xl font-bold text-brand-600">7</p>
          <p class="text-gray-500 mt-1">Categorie di enti</p>
        </div>
      </div>

      <!-- Statistiche ultimo anno -->
      <div v-if="stats" class="mb-12">
        <h2 class="mb-4">Riepilogo {{ stats.anno ?? 'ultimo anno disponibile' }}</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div v-for="cat in stats.per_categoria" :key="cat.categoria_principale" class="card">
            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
              {{ cat.categoria_principale }}
            </p>
            <p class="text-2xl font-bold text-gray-800">{{ formatNum(cat.n_enti) }}</p>
            <p class="text-sm text-gray-500">enti • {{ formatEur(cat.totale_importo) }}</p>
          </div>
        </div>
      </div>

      <!-- CTA bottom -->
      <div class="card bg-brand-50 border-brand-200 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h3 class="text-brand-800">Vuoi integrare questi dati nel tuo progetto?</h3>
          <p class="text-sm text-brand-600 mt-1">L'API pubblica è gratuita, senza chiave di accesso, con paginazione e filtri.</p>
        </div>
        <RouterLink to="/api" class="btn-primary whitespace-nowrap">Vai all'API</RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchStatus, fetchStatistiche } from '@/api/client'

const status = ref(null)
const stats  = ref(null)

const formatNum = (n) => n != null ? Number(n).toLocaleString('it-IT') : '…'
const formatEur = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '…'
const formatDate = (d) => d ? new Date(d).toLocaleDateString('it-IT', { day: '2-digit', month: 'long', year: 'numeric' }) : '…'

onMounted(async () => {
  try {
    const [sRes, stRes] = await Promise.all([
      fetchStatus(),
      fetchStatistiche(),
    ])
    status.value = sRes.data
    stats.value  = stRes.data
  } catch {
    // silenzioso: status rimane null
  }
})
</script>
