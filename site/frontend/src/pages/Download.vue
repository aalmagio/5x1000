<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-10">
    <h1 class="mb-2">Download dataset</h1>
    <p class="text-gray-500 mb-8">
      Tutti i file sono liberamente scaricabili senza registrazione.
      Licenza dati: <a href="https://creativecommons.org/licenses/by/4.0/" class="text-brand-600 hover:underline" target="_blank">CC BY 4.0</a>.
    </p>

    <!-- Dataset completo -->
    <section class="mb-10">
      <h2 class="mb-4">Dataset completo</h2>
      <div class="card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p class="font-semibold text-gray-800">enti_5x1000_norm.csv</p>
          <p class="text-sm text-gray-500 mt-1">
            Tutti gli anni normalizzati in un unico file CSV (~210 MB, ~1M righe).
            Include dati RUNTS.
          </p>
          <p v-if="completo" class="text-xs text-gray-400 mt-1">
            {{ completo.dimensione_mb }} MB •
            Aggiornato il {{ formatDate(completo.aggiornato_il) }}
          </p>
        </div>
        <a
          href="/download/csv/completo"
          class="btn-primary whitespace-nowrap"
          download
        >Scarica CSV</a>
      </div>
    </section>

    <!-- Per anno -->
    <section class="mb-10">
      <h2 class="mb-4">Download per anno</h2>
      <div v-if="loadingFiles" class="text-gray-400">Caricamento…</div>
      <div v-else>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div
            v-for="item in filesPerAnno"
            :key="item.anno"
            class="card flex items-center justify-between gap-4 py-4"
          >
            <div>
              <p class="font-semibold text-gray-800">Anno {{ item.anno }}</p>
              <p class="text-xs text-gray-400">{{ item.normalizzato?.dimensione_mb ?? '–' }} MB Excel</p>
            </div>
            <div class="flex gap-2">
              <a
                :href="`/download/csv/${item.anno}`"
                class="btn-secondary text-xs px-3 py-1.5"
                download
              >CSV</a>
              <a
                v-if="item.normalizzato"
                :href="`/download/xlsx/${item.anno}`"
                class="btn-secondary text-xs px-3 py-1.5"
                download
              >Excel</a>
              <a
                v-if="item.report"
                :href="`/download/report/${item.anno}`"
                class="btn-primary text-xs px-3 py-1.5"
                download
              >Report</a>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Schema dati -->
    <section class="card">
      <h2 class="mb-4">Schema del dataset normalizzato</h2>
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
              <td class="font-mono text-xs">{{ col.name }}</td>
              <td class="text-gray-500 text-xs">{{ col.type }}</td>
              <td class="text-gray-600 text-xs whitespace-normal">{{ col.desc }}</td>
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

onMounted(async () => {
  try {
    const res = await fetchFiles()
    files.value = res.data
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
