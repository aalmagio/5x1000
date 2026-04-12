<template>
  <div>
    <!-- Hero -->
    <section class="relative overflow-hidden bg-gradient-to-br from-brand-900 via-brand-700 to-brand-600 text-white">
      <!-- Decorative background blobs -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
        <div class="absolute -top-32 -right-32 w-96 h-96 bg-white/5 rounded-full"></div>
        <div class="absolute -bottom-40 -left-20 w-80 h-80 bg-yellow-400/10 rounded-full"></div>
        <div class="absolute top-1/2 left-1/3 w-72 h-72 bg-brand-500/20 rounded-full blur-3xl"></div>
      </div>

      <div class="relative max-w-4xl mx-auto px-4 sm:px-6 py-20 text-center">
        <!-- Live badge -->
        <div class="inline-flex items-center gap-2 bg-white/10 text-white/90 text-xs font-medium px-3 py-1.5 rounded-full mb-6 border border-white/20">
          <span class="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"></span>
          Dataset aggiornato
        </div>

        <h1 class="text-4xl sm:text-6xl font-extrabold mb-5 leading-tight tracking-tight">
          Dati aperti sul<br>
          <span class="text-yellow-300">5×1000</span> italiano
        </h1>
        <p class="text-brand-100 text-lg sm:text-xl mb-10 max-w-2xl mx-auto leading-relaxed">
          {{ status?.anni_disponibili?.length ?? '20' }} anni di storia sui beneficiari del cinque per mille.
          Scarica il dataset o interroga l'API pubblica, gratuitamente.
        </p>
        <div class="flex flex-wrap justify-center gap-3">
          <RouterLink to="/dati" class="btn-primary bg-yellow-400 text-brand-900 hover:bg-yellow-300 text-base px-6 py-3 shadow-lg">
            Esplora i dati
          </RouterLink>
          <RouterLink to="/download" class="btn-ghost text-base px-6 py-3">
            Scarica dataset
          </RouterLink>
          <RouterLink to="/api" class="btn-ghost text-base px-6 py-3">
            Documentazione API
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- Status bar -->
    <div v-if="status" class="bg-green-50 border-b border-green-200 px-4 py-2.5 text-sm text-center text-green-700">
      <span class="inline-flex items-center gap-1.5">
        <span class="w-1.5 h-1.5 bg-green-500 rounded-full inline-block"></span>
        Ultimo aggiornamento: <strong>{{ formatDate(status.ultimo_aggiornamento) }}</strong>
        &bull; <strong>{{ formatNum(status.righe_totali) }}</strong> record
        &bull; anni <strong>{{ status.anni_disponibili?.at(-1) }}–{{ status.anni_disponibili?.[0] }}</strong>
      </span>
    </div>

    <section class="max-w-7xl mx-auto px-4 sm:px-6 py-12">
      <!-- KPI Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-14">
        <div class="card flex items-center gap-5">
          <div class="flex-shrink-0 w-14 h-14 bg-brand-50 rounded-xl flex items-center justify-center">
            <svg class="w-7 h-7 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
            </svg>
          </div>
          <div>
            <p class="text-3xl font-bold text-brand-600">{{ status?.anni_disponibili?.length ?? '…' }}</p>
            <p class="text-gray-500 text-sm mt-0.5">Anni di dati</p>
          </div>
        </div>

        <div class="card flex items-center gap-5">
          <div class="flex-shrink-0 w-14 h-14 bg-emerald-50 rounded-xl flex items-center justify-center">
            <svg class="w-7 h-7 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
          </div>
          <div>
            <p class="text-3xl font-bold text-emerald-600">{{ formatNum(status?.righe_totali) }}</p>
            <p class="text-gray-500 text-sm mt-0.5">Record totali</p>
          </div>
        </div>

        <div class="card flex items-center gap-5">
          <div class="flex-shrink-0 w-14 h-14 bg-violet-50 rounded-xl flex items-center justify-center">
            <svg class="w-7 h-7 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
          </div>
          <div>
            <p class="text-3xl font-bold text-violet-600">7</p>
            <p class="text-gray-500 text-sm mt-0.5">Categorie di enti</p>
          </div>
        </div>
      </div>

      <!-- Bar chart categorie -->
      <div v-if="stats" class="card mb-14">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h2 class="text-gray-900">Importi per categoria</h2>
            <p class="text-sm text-gray-500 mt-0.5">Anno {{ stats.anno ?? 'più recente disponibile' }}</p>
          </div>
          <RouterLink to="/dati" class="text-sm text-brand-600 hover:text-brand-700 font-medium">
            Esplora tutti →
          </RouterLink>
        </div>

        <div class="space-y-3">
          <div
            v-for="(cat, i) in statsSorted"
            :key="cat.categoria"
            class="flex items-center gap-3"
          >
            <!-- Label -->
            <div class="w-40 text-right flex-shrink-0">
              <p class="text-sm font-medium text-gray-700 truncate capitalize">{{ cat.categoria?.replace(/_/g, ' ') }}</p>
              <p class="text-xs text-gray-400">{{ formatNum(cat.n_enti_ammessi) }} ammessi · {{ formatNum(cat.n_enti_esclusi) }} esclusi</p>
            </div>

            <!-- Bar track -->
            <div class="flex-1 h-9 bg-gray-100 rounded-lg overflow-hidden">
              <div
                class="h-full rounded-lg transition-all duration-700 ease-out flex items-center justify-end pr-3"
                :style="{
                  width: animated ? `${(cat.importo_ammessi / maxImporto * 100).toFixed(1)}%` : '0%',
                  backgroundColor: CAT_COLORS[i % CAT_COLORS.length],
                }"
              >
                <span v-if="cat.importo_ammessi / maxImporto > 0.15" class="text-xs font-semibold text-white whitespace-nowrap">
                  {{ formatEur(cat.importo_ammessi) }}
                </span>
              </div>
            </div>

            <!-- Importo fuori dalla barra (barre corte) -->
            <div class="w-28 flex-shrink-0 text-xs font-semibold text-gray-700">
              <span v-if="cat.importo_ammessi / maxImporto <= 0.15">
                {{ formatEur(cat.importo_ammessi) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Skeleton categorie (loading) -->
      <div v-else class="card mb-14 animate-pulse">
        <div class="h-6 bg-gray-200 rounded w-48 mb-6"></div>
        <div class="space-y-4">
          <div v-for="n in 5" :key="n" class="flex items-center gap-3">
            <div class="w-40 h-8 bg-gray-200 rounded flex-shrink-0"></div>
            <div class="flex-1 h-9 bg-gray-200 rounded-lg"></div>
            <div class="w-28 h-4 bg-gray-200 rounded flex-shrink-0"></div>
          </div>
        </div>
      </div>

      <!-- CTA API -->
      <div class="card bg-gradient-to-r from-brand-50 to-brand-100 border-brand-200">
        <div class="flex flex-col sm:flex-row items-center justify-between gap-6">
          <div class="flex items-start gap-4">
            <div class="flex-shrink-0 w-12 h-12 bg-brand-600 rounded-xl flex items-center justify-center">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
              </svg>
            </div>
            <div>
              <h3 class="text-brand-800">Integra questi dati nel tuo progetto</h3>
              <p class="text-sm text-brand-600 mt-1">API REST pubblica, gratuita, senza chiave di accesso. Paginazione e filtri inclusi.</p>
            </div>
          </div>
          <RouterLink to="/api" class="btn-primary whitespace-nowrap shadow-md">
            Vai all'API →
          </RouterLink>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchStatus, fetchStatistiche } from '@/api/client'

const status   = ref(null)
const stats    = ref(null)
const animated = ref(false)

const CAT_COLORS = ['#3b82f6', '#10b981', '#8b5cf6', '#ef4444', '#f59e0b', '#06b6d4', '#f97316']

const statsSorted = computed(() => {
  if (!stats.value?.per_categoria) return []
  return [...stats.value.per_categoria].sort((a, b) => b.importo_ammessi - a.importo_ammessi)
})

const maxImporto = computed(() =>
  statsSorted.value.length ? statsSorted.value[0].importo_ammessi : 1
)

const formatNum  = (n) => n != null ? Number(n).toLocaleString('it-IT') : '…'
const formatEur  = (n) => n != null
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n)
  : '…'
const formatDate = (d) => d
  ? new Date(d).toLocaleDateString('it-IT', { day: '2-digit', month: 'long', year: 'numeric' })
  : '…'

onMounted(async () => {
  try {
    const [sRes, stRes] = await Promise.all([fetchStatus(), fetchStatistiche()])
    status.value = sRes.data
    stats.value  = stRes.data
  } catch {
    // silenzioso
  }
  setTimeout(() => { animated.value = true }, 150)
})
</script>
