<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-6">
      <h1 class="mb-1">Proiezioni e trend</h1>
      <p class="text-gray-500">
        Stime statistiche sui trend futuri del 5×1000 basate su regressione lineare dei dati storici.
      </p>
    </div>

    <!-- Disclaimer prominente -->
    <div class="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 mb-6 flex gap-3">
      <svg class="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
      </svg>
      <div>
        <p class="text-sm font-semibold text-amber-800 mb-1">Disclaimer — stime statistiche</p>
        <p class="text-xs text-amber-700 leading-relaxed">
          {{ disclaimer }}
        </p>
      </div>
    </div>

    <!-- Forecast non disponibile -->
    <div v-if="!loading && notAvailable" class="card border-gray-200 text-center py-12">
      <svg class="w-12 h-12 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
          d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
      </svg>
      <p class="text-gray-600 font-medium mb-2">Dati di proiezione non ancora disponibili</p>
      <p class="text-sm text-gray-400 mb-4">
        Per generarli eseguire il comando:
      </p>
      <code class="text-xs bg-gray-100 text-gray-700 rounded px-3 py-1.5 font-mono">python forecast.py</code>
    </div>

    <!-- Skeleton -->
    <div v-else-if="loading" class="space-y-5 animate-pulse">
      <div class="card h-16 bg-gray-50"></div>
      <div class="card h-80 bg-gray-50"></div>
      <div class="card h-48 bg-gray-50"></div>
    </div>

    <!-- Errore generico -->
    <div v-else-if="error && !notAvailable" class="card border-red-200 bg-red-50 text-center py-10">
      <p class="text-red-700 font-medium mb-1">Errore nel caricamento</p>
      <p class="text-sm text-red-500">{{ error }}</p>
      <button class="btn-primary mt-4 inline-flex" @click="load">Riprova</button>
    </div>

    <template v-else-if="dati">
      <!-- Selettore categoria -->
      <div class="card mb-6">
        <div class="flex flex-wrap items-end gap-4">
          <div class="flex-1 min-w-48">
            <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Visualizza</label>
            <select v-model="catSelezionata" class="input-field">
              <option value="__globale__">Tutte le categorie (dato aggregato)</option>
              <option v-for="cat in categorie" :key="cat" :value="cat">{{ cat }}</option>
            </select>
          </div>
          <div class="flex-1 min-w-48">
            <label class="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wide">Metrica</label>
            <select v-model="metrica" class="input-field">
              <option value="importo">Importo totale (€)</option>
              <option value="scelte">Numero di scelte</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Grafico storico + proiezione -->
      <div v-if="serieCorrente" class="card mb-6">
        <div class="flex items-center justify-between mb-5">
          <div>
            <h2 class="text-gray-900">
              {{ catSelezionata === '__globale__' ? 'Tutte le categorie' : catSelezionata }}
            </h2>
            <p class="text-sm text-gray-400 mt-0.5">
              {{ metrica === 'importo' ? 'Importo totale (€)' : 'Numero di scelte' }} — storico e proiezione
            </p>
          </div>
          <div class="text-right">
            <span class="text-xs text-gray-400 block">R² = {{ serieCorrente.r2.toFixed(3) }}</span>
            <span class="text-xs text-gray-400">{{ serieCorrente.storico.length }} anni storici</span>
          </div>
        </div>

        <div class="space-y-2.5">
          <!-- Barre storiche -->
          <div
            v-for="r in serieCorrente.storico"
            :key="'s' + r.anno"
            class="flex items-center gap-3"
          >
            <div class="w-12 text-right flex-shrink-0">
              <span class="text-sm font-medium text-gray-600">{{ r.anno }}</span>
            </div>
            <div class="flex-1 relative h-7 bg-gray-100 rounded overflow-hidden">
              <div
                class="absolute inset-y-0 left-0 rounded transition-all duration-500 bg-brand-500"
                :style="{ width: barPct(serieCorrente, r) + '%' }"
              ></div>
            </div>
            <div class="w-32 flex-shrink-0 text-right text-sm tabular-nums text-gray-700">
              {{ metrica === 'importo' ? formatEurShort(r.tot_importo) : fmtN(r.tot_scelte) }}
            </div>
          </div>

          <!-- Separatore -->
          <div class="flex items-center gap-3 py-1">
            <div class="w-12"></div>
            <div class="flex-1 border-t border-dashed border-amber-300"></div>
            <div class="w-32 text-right text-xs text-amber-600 font-medium">↓ proiezioni</div>
          </div>

          <!-- Barre proiezione -->
          <div
            v-for="p in serieCorrente.proiezioni"
            :key="'p' + p.anno"
            class="flex items-center gap-3"
          >
            <div class="w-12 text-right flex-shrink-0">
              <span class="text-sm font-semibold text-amber-700">{{ p.anno }}</span>
            </div>
            <div class="flex-1 relative h-7 rounded overflow-hidden bg-amber-50">
              <!-- Intervallo confidenza -->
              <div
                class="absolute inset-y-0 rounded bg-amber-100 transition-all duration-500"
                :style="{
                  left: barPct(serieCorrente, { val: p.intervallo_inf }) + '%',
                  width: Math.max(barPct(serieCorrente, { val: p.intervallo_sup }) - barPct(serieCorrente, { val: p.intervallo_inf }), 2) + '%',
                }"
              ></div>
              <!-- Valore centrale -->
              <div
                class="absolute inset-y-0 left-0 rounded transition-all duration-500 bg-amber-400 opacity-70"
                :style="{ width: barPct(serieCorrente, { val: p.valore }) + '%' }"
              ></div>
            </div>
            <div class="w-32 flex-shrink-0 text-right">
              <span class="text-sm font-semibold tabular-nums text-amber-700">
                {{ metrica === 'importo' ? formatEurShort(p.valore) : fmtN(p.valore) }}
              </span>
              <span class="text-xs text-gray-400 block">
                ±{{ metrica === 'importo' ? formatEurShort(p.intervallo_sup - p.valore) : fmtN(p.intervallo_sup - p.valore) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Legenda -->
        <div class="flex gap-4 mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
          <span class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded bg-brand-500"></span>Dati storici</span>
          <span class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded bg-amber-400 opacity-70"></span>Proiezione (centrale)</span>
          <span class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded bg-amber-100"></span>Intervallo 95%</span>
        </div>
      </div>

      <!-- Tabella proiezioni per categoria -->
      <div class="card">
        <div class="mb-5">
          <h2 class="text-gray-900">Riepilogo proiezioni per categoria</h2>
          <p class="text-sm text-gray-400 mt-0.5">Valori proiettati per {{ anniProiezione.join(', ') }}</p>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-100 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                <th class="pb-3 pr-4">Categoria</th>
                <th class="pb-3 pr-4">R²</th>
                <th v-for="anno in anniProiezione" :key="anno" class="pb-3 pr-4 text-right text-amber-600">
                  {{ anno }} ({{ metrica === 'importo' ? '€' : 'scelte' }})
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr
                v-for="(cat, key) in dati.per_categoria"
                :key="key"
                class="hover:bg-gray-50 cursor-pointer transition-colors"
                @click="catSelezionata = key"
              >
                <td class="py-2.5 pr-4 font-medium text-gray-800">{{ key }}</td>
                <td class="py-2.5 pr-4 text-gray-500 tabular-nums">
                  {{ metrica === 'importo' ? cat.importo.r2.toFixed(3) : cat.scelte.r2.toFixed(3) }}
                </td>
                <td
                  v-for="p in (metrica === 'importo' ? cat.importo.proiezioni : cat.scelte.proiezioni)"
                  :key="p.anno"
                  class="py-2.5 pr-4 text-right tabular-nums text-amber-700 font-medium"
                >
                  {{ metrica === 'importo' ? formatEurShort(p.valore) : fmtN(p.valore) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Info generazione -->
      <p class="text-xs text-gray-400 text-center mt-4">
        Dati generati il {{ generatoIl }}
      </p>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchForecast } from '../api/client.js'

const loading      = ref(true)
const error        = ref(null)
const notAvailable = ref(false)
const dati         = ref(null)
const catSelezionata = ref('__globale__')
const metrica        = ref('importo')

async function load() {
  loading.value      = false
  notAvailable.value = false
  error.value        = null
  loading.value      = true
  try {
    const res = await fetchForecast()
    dati.value = res.data
  } catch (e) {
    if (e?.response?.status === 404) {
      notAvailable.value = true
    } else {
      error.value = e?.response?.data?.error ?? e.message ?? 'Errore sconosciuto'
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ─── Computed ────────────────────────────────────────────────────────────────

const disclaimer = computed(() => dati.value?.disclaimer ?? '')

const generatoIl = computed(() => {
  if (!dati.value?.generato_il) return '–'
  return new Date(dati.value.generato_il).toLocaleString('it-IT')
})

const categorie = computed(() => Object.keys(dati.value?.per_categoria ?? {}))

const anniProiezione = computed(() => {
  if (!dati.value?.globale) return []
  return dati.value.globale.importo.proiezioni.map(p => p.anno)
})

const serieCorrente = computed(() => {
  if (!dati.value) return null
  const src = catSelezionata.value === '__globale__'
    ? dati.value.globale
    : dati.value.per_categoria[catSelezionata.value]
  if (!src) return null
  const serie = metrica.value === 'importo' ? src.importo : src.scelte
  return {
    r2:         serie.r2,
    storico:    src.storico.map(r => ({
      anno:       r.anno,
      val:        metrica.value === 'importo' ? r.tot_importo : r.tot_scelte,
      tot_importo: r.tot_importo,
      tot_scelte:  r.tot_scelte,
    })),
    proiezioni: serie.proiezioni,
  }
})

function maxVal(serie) {
  const allVals = [
    ...serie.storico.map(r => r.val),
    ...serie.proiezioni.map(p => p.intervallo_sup),
  ]
  return Math.max(...allVals, 1)
}

function barPct(serie, item) {
  const v = item.val ?? item.valore ?? 0
  return Math.min((v / maxVal(serie)) * 100, 100)
}

// ─── Formatters ──────────────────────────────────────────────────────────────

function formatEurShort(v) {
  if (v === null || v === undefined) return '–'
  if (v >= 1e9) return (v / 1e9).toFixed(2) + ' Mrd €'
  if (v >= 1e6) return (v / 1e6).toFixed(1) + ' M€'
  if (v >= 1e3) return (v / 1e3).toFixed(0) + ' k€'
  return (+v).toFixed(0) + ' €'
}

function fmtN(v) {
  if (v === null || v === undefined) return '–'
  return new Intl.NumberFormat('it-IT').format(Math.round(v))
}
</script>
