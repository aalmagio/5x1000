<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-8">
      <h1 class="mb-1">Download dataset</h1>
      <p class="text-gray-500">
        Tutti i file sono liberamente scaricabili senza registrazione.
        Licenza dati:
        <a href="https://creativecommons.org/licenses/by/4.0/" class="text-brand-600 hover:underline" target="_blank" rel="noopener">CC BY 4.0</a>.
      </p>
    </div>

    <!-- Dataset completo -->
    <section class="mb-10">
      <h2 class="mb-4">Dataset completo</h2>

      <div v-if="loadingFiles" class="card animate-pulse">
        <div class="flex items-center gap-4">
          <div class="w-14 h-14 bg-gray-200 rounded-xl flex-shrink-0"></div>
          <div class="flex-1 space-y-2">
            <div class="h-5 bg-gray-200 rounded w-56"></div>
            <div class="h-4 bg-gray-100 rounded w-80"></div>
            <div class="h-3 bg-gray-100 rounded w-40"></div>
          </div>
          <div class="w-28 h-9 bg-gray-200 rounded-lg flex-shrink-0"></div>
        </div>
      </div>

      <div v-else class="card">
        <div class="flex flex-col sm:flex-row sm:items-center gap-5">
          <div class="flex-shrink-0 w-14 h-14 bg-emerald-50 rounded-xl flex items-center justify-center border border-emerald-100">
            <svg class="w-7 h-7 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex flex-wrap items-center gap-2 mb-1">
              <p class="font-semibold text-gray-800 font-mono text-sm">enti_5x1000_norm.csv</p>
              <span class="badge bg-emerald-100 text-emerald-700">CSV</span>
              <span class="badge bg-gray-100 text-gray-600">~210 MB</span>
              <span class="badge bg-brand-100 text-brand-700">~1M righe</span>
            </div>
            <p class="text-sm text-gray-500">Tutti gli anni normalizzati in un unico file. Include dati RUNTS dove disponibili.</p>
            <p v-if="completo" class="text-xs text-gray-400 mt-1">
              {{ completo.dimensione_mb }} MB &bull; Aggiornato il {{ formatDate(completo.aggiornato_il) }}
            </p>
          </div>
          <a href="/download/csv/completo" class="btn-primary whitespace-nowrap flex-shrink-0 inline-flex items-center gap-2" download>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
            Scarica CSV
          </a>
        </div>
      </div>
    </section>

    <!-- Per anno -->
    <section class="mb-10">
      <h2 class="mb-4">Download per anno</h2>

      <div v-if="loadingFiles" class="grid grid-cols-1 sm:grid-cols-2 gap-3 animate-pulse">
        <div v-for="n in 6" :key="n" class="card py-4">
          <div class="flex items-center justify-between gap-4">
            <div class="space-y-1.5">
              <div class="h-5 bg-gray-200 rounded w-24"></div>
              <div class="h-3 bg-gray-100 rounded w-16"></div>
            </div>
            <div class="flex gap-2">
              <div class="h-8 w-14 bg-gray-200 rounded-lg"></div>
              <div class="h-8 w-16 bg-gray-200 rounded-lg"></div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="errorFiles" class="card border-red-200 bg-red-50 flex items-center gap-3 py-4">
        <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
        <span class="text-sm text-red-700">Impossibile caricare il catalogo dei file. Riprova più tardi.</span>
      </div>

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div
          v-for="item in filesPerAnno"
          :key="item.anno"
          class="card py-4 flex items-center justify-between gap-4"
        >
          <div>
            <p class="font-semibold text-gray-800">Anno {{ item.anno }}</p>
            <p class="text-xs text-gray-400 mt-0.5">
              {{ item.normalizzato?.dimensione_mb ?? '–' }} MB
            </p>
          </div>
          <div class="flex gap-2 flex-shrink-0">
            <a
              :href="`/download/csv/${item.anno}`"
              class="btn-secondary text-xs px-3 py-1.5 inline-flex items-center gap-1"
              download
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              CSV
            </a>
            <a
              v-if="item.normalizzato"
              :href="`/download/xlsx/${item.anno}`"
              class="btn-secondary text-xs px-3 py-1.5 inline-flex items-center gap-1"
              download
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              Excel
            </a>
            <a
              v-if="item.report"
              :href="`/download/report/${item.anno}`"
              class="btn-primary text-xs px-3 py-1.5 inline-flex items-center gap-1"
              download
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
              </svg>
              Report
            </a>
          </div>
        </div>
      </div>
    </section>

    <!-- Schema dati -->
    <section class="card">
      <div class="flex items-center gap-3 mb-5">
        <div class="w-9 h-9 bg-brand-50 rounded-lg flex items-center justify-center flex-shrink-0">
          <svg class="w-5 h-5 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18M10 3v18"/>
          </svg>
        </div>
        <div>
          <h2>Schema del dataset</h2>
          <p class="text-xs text-gray-400 mt-0.5">{{ schema.length }} colonne nel file normalizzato</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Colonna</th>
              <th>Tipo</th>
              <th>Descrizione</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="col in schema" :key="col.name">
              <td class="font-mono text-xs text-brand-700 whitespace-nowrap">{{ col.name }}</td>
              <td class="whitespace-nowrap">
                <span class="badge text-xs" :class="typeColor(col.type)">{{ col.type }}</span>
              </td>
              <td class="text-gray-600 text-sm whitespace-normal">{{ col.desc }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchFiles } from '@/api/client'

const files        = ref([])
const loadingFiles = ref(true)
const errorFiles   = ref(false)

const completo = computed(() =>
  files.value.find(f => f.tipo === 'completo' && f.formato === 'csv')
)

const filesPerAnno = computed(() => {
  const byAnno = {}
  for (const f of files.value) {
    if (!f.anno) continue
    if (!byAnno[f.anno]) byAnno[f.anno] = { anno: f.anno }
    if (f.tipo === 'normalizzato') byAnno[f.anno].normalizzato = f
    if (f.tipo === 'report')       byAnno[f.anno].report       = f
  }
  return Object.values(byAnno).sort((a, b) => b.anno - a.anno)
})

const formatDate = (d) => d
  ? new Date(d).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })
  : '–'

const typeColor = (t) => ({
  int:     'bg-blue-100 text-blue-700',
  string:  'bg-gray-100 text-gray-600',
  decimal: 'bg-emerald-100 text-emerald-700',
  bool:    'bg-orange-100 text-orange-700',
  date:    'bg-violet-100 text-violet-700',
}[t] ?? 'bg-gray-100 text-gray-600')

onMounted(async () => {
  try {
    const res = await fetchFiles()
    files.value = res.data
  } catch {
    errorFiles.value = true
  } finally {
    loadingFiles.value = false
  }
})

const schema = [
  { name: 'ANNO',                  type: 'int',     desc: 'Anno fiscale di riferimento' },
  { name: 'COD_FISCALE',           type: 'string',  desc: 'Codice fiscale dell\'ente' },
  { name: 'DENOMINAZIONE',         type: 'string',  desc: 'Nome dell\'ente beneficiario' },
  { name: 'REGIONE',               type: 'string',  desc: 'Regione della sede legale' },
  { name: 'PROVINCIA',             type: 'string',  desc: 'Sigla provincia (2-3 char)' },
  { name: 'COMUNE',                type: 'string',  desc: 'Comune della sede legale' },
  { name: 'CAT_VOLONTARIATO',      type: 'bool',    desc: 'Flag: ente di volontariato' },
  { name: 'CAT_ASD',               type: 'bool',    desc: 'Flag: associazione sportiva dilettantistica' },
  { name: 'CAT_ETS_ONLUS',         type: 'bool',    desc: 'Flag: ETS / ONLUS / APS' },
  { name: 'CAT_RICERCA_SCI',       type: 'bool',    desc: 'Flag: ricerca scientifica' },
  { name: 'CAT_RICERCA_SAN',       type: 'bool',    desc: 'Flag: ricerca sanitaria' },
  { name: 'CAT_COMUNI',            type: 'bool',    desc: 'Flag: comune' },
  { name: 'CAT_BENI_CULT',         type: 'bool',    desc: 'Flag: beni culturali' },
  { name: 'CAT_AREE_PROT',         type: 'bool',    desc: 'Flag: aree naturali protette' },
  { name: 'CATEGORIA_PRINCIPALE',  type: 'string',  desc: 'Categoria primaria derivata' },
  { name: 'N_SCELTE',              type: 'int',     desc: 'Numero di scelte ricevute' },
  { name: 'IMPORTO_ESPRESSO',      type: 'decimal', desc: 'Importo da scelte esplicite (€)' },
  { name: 'IMPORTO_GENERICO',      type: 'decimal', desc: 'Importo da scelte generiche (€)' },
  { name: 'IMPORTO_TOTALE',        type: 'decimal', desc: 'Importo totale percepito (€)' },
  { name: 'RUNTS_DENOMINAZIONE',   type: 'string',  desc: 'Denominazione nel registro RUNTS' },
  { name: 'RUNTS_SEZIONE',         type: 'string',  desc: 'Sezione RUNTS di iscrizione' },
  { name: 'RUNTS_SEDE_COMUNE',     type: 'string',  desc: 'Comune sede RUNTS' },
  { name: 'RUNTS_SEDE_PROV',       type: 'string',  desc: 'Provincia sede RUNTS' },
  { name: 'RUNTS_5X1000',          type: 'bool',    desc: 'Ente ammesso al 5x1000 secondo RUNTS' },
  { name: 'RUNTS_DATA_ISCRIZIONE', type: 'date',    desc: 'Data iscrizione al RUNTS' },
]
</script>
