<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-8">
      <h1 class="mb-1">Download dataset</h1>
      <p class="text-gray-500">
        Lascia la tua email per accedere ai file. Licenza dati:
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
          <button
            class="btn-primary whitespace-nowrap flex-shrink-0 inline-flex items-center gap-2"
            @click="requestDownload({ tipo: 'csv', anno: 'completo', href: '/download/csv/completo' })"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
            Scarica CSV
          </button>
        </div>
      </div>
    </section>

    <!-- Pivot scelte per categoria -->
    <section class="mb-10">
      <h2 class="mb-4">Scelte per categoria</h2>

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

      <div v-else-if="scelteFile" class="card">
        <div class="flex flex-col sm:flex-row sm:items-center gap-5">
          <div class="flex-shrink-0 w-14 h-14 bg-violet-50 rounded-xl flex items-center justify-center border border-violet-100">
            <svg class="w-7 h-7 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M3 10h18M3 14h18M10 3v18"/>
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex flex-wrap items-center gap-2 mb-1">
              <p class="font-semibold text-gray-800 font-mono text-sm">scelte_categorie.xlsx</p>
              <span class="badge bg-violet-100 text-violet-700">Excel</span>
              <span class="badge bg-gray-100 text-gray-600">pivot</span>
            </div>
            <p class="text-sm text-gray-500">Scelte espresse e generiche per categoria e anno (dal 2019). Formato pivot multi-foglio.</p>
            <p v-if="scelteFile" class="text-xs text-gray-400 mt-1">
              {{ scelteFile.dimensione_mb }} MB &bull; Aggiornato il {{ formatDate(scelteFile.aggiornato_il) }}
            </p>
          </div>
          <button
            class="btn-primary whitespace-nowrap flex-shrink-0 inline-flex items-center gap-2"
            @click="requestDownload({ tipo: 'scelte', anno: 'completo', href: '/download/scelte/completo' })"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
            Scarica Excel
          </button>
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
            <button
              class="btn-secondary text-xs px-3 py-1.5 inline-flex items-center gap-1"
              @click="requestDownload({ tipo: 'csv', anno: item.anno, href: `/download/csv/${item.anno}` })"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              CSV
            </button>
            <button
              v-if="item.normalizzato"
              class="btn-secondary text-xs px-3 py-1.5 inline-flex items-center gap-1"
              @click="requestDownload({ tipo: 'xlsx', anno: item.anno, href: `/download/xlsx/${item.anno}` })"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              Excel
            </button>
            <button
              v-if="item.report"
              class="btn-primary text-xs px-3 py-1.5 inline-flex items-center gap-1"
              @click="requestDownload({ tipo: 'report', anno: item.anno, href: `/download/report/${item.anno}` })"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
              </svg>
              Report
            </button>
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

  <!-- ── Modal email gate ──────────────────────────────────────────────────── -->
  <Teleport to="body">
    <div
      v-if="modal.open"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <!-- Backdrop: click chiude il modal -->
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="skipAndDownload"></div>

      <!-- Card -->
      <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 z-10" @click.stop>
        <!-- Icona -->
        <div class="w-12 h-12 bg-brand-50 rounded-xl flex items-center justify-center mb-5 mx-auto">
          <svg class="w-6 h-6 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
          </svg>
        </div>

        <h3 class="text-lg font-bold text-gray-900 text-center mb-1">Scarica il dataset</h3>
        <p class="text-sm text-gray-500 text-center mb-6">
          Lascia la tua email per ricevere aggiornamenti sui dati 5×1000. Il download è gratuito anche senza registrazione.
        </p>

        <form @submit.prevent="submitLead" class="space-y-4">
          <div>
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Nome (opzionale)</label>
            <input
              v-model="modal.nome"
              type="text"
              class="input-field"
              placeholder="Il tuo nome"
              autocomplete="name"
            />
          </div>
          <div>
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5 block">Email (opzionale)</label>
            <input
              v-model="modal.email"
              type="email"
              class="input-field"
              :class="modal.emailError ? 'border-red-400' : ''"
              placeholder="tuamail@esempio.it"
              autocomplete="email"
            />
            <p v-if="modal.emailError" class="text-xs text-red-500 mt-1">{{ modal.emailError }}</p>
          </div>

          <!-- Newsletter checkbox -->
          <label class="flex items-start gap-3 cursor-pointer group">
            <input
              v-model="modal.vuole_newsletter"
              type="checkbox"
              class="mt-0.5 w-4 h-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500 flex-shrink-0"
            />
            <span class="text-xs text-gray-500 group-hover:text-gray-700 transition-colors leading-relaxed">
              Voglio ricevere aggiornamenti via email quando vengono pubblicati nuovi dati 5×1000.
              Niente spam, disiscrizione in un click.
            </span>
          </label>

          <div class="flex gap-3 pt-1">
            <button
              type="button"
              class="btn-secondary flex-1 text-sm"
              @click="skipAndDownload"
            >
              Scarica senza email
            </button>
            <button
              type="submit"
              class="btn-primary flex-1 inline-flex items-center justify-center gap-2"
              :disabled="modal.saving"
            >
              <svg v-if="modal.saving" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              {{ modal.saving ? 'Un momento…' : 'Scarica' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { fetchFiles, salvaLead } from '@/api/client'

const files        = ref([])
const loadingFiles = ref(true)
const errorFiles   = ref(false)

// ── Lead modal ────────────────────────────────────────────────────────────────
const STORAGE_KEY    = '5x1000_lead_v2'
const EXPIRY_DAYS    = 90

function leadDone() {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return false
  try {
    const { ts } = JSON.parse(raw)
    return Date.now() - ts < EXPIRY_DAYS * 86_400_000
  } catch {
    return false
  }
}

function markLeadDone() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ts: Date.now() }))
}

const modal = reactive({
  open:             false,
  email:            '',
  nome:             '',
  emailError:       '',
  saving:           false,
  vuole_newsletter: false,
  pending:          null,  // { tipo, anno, href } — download in attesa
})

function requestDownload({ tipo, anno, href }) {
  // Se l'utente ha già interagito con il modal di recente (< 90 giorni), scarica direttamente
  if (leadDone()) {
    triggerDownload(href)
    return
  }
  modal.pending          = { tipo, anno, href }
  modal.email            = ''
  modal.nome             = ''
  modal.emailError       = ''
  modal.vuole_newsletter = false
  modal.open             = true
}

// Scarica senza lasciare l'email (click su backdrop o sul bottone "Senza email")
function skipAndDownload() {
  const href = modal.pending?.href
  modal.open = false
  markLeadDone()
  if (href) triggerDownload(href)
}

async function submitLead() {
  modal.emailError = ''
  const email = modal.email.trim()

  // Email fornita ma non valida → errore
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    modal.emailError = 'Inserisci un indirizzo email valido.'
    return
  }

  // Email fornita → salva il lead
  if (email) {
    modal.saving = true
    try {
      await salvaLead({
        email,
        nome:             modal.nome,
        tipo:             modal.pending?.tipo,
        anno:             modal.pending?.anno !== 'completo' ? modal.pending?.anno : undefined,
        vuole_newsletter: modal.vuole_newsletter,
      })
      markLeadDone()
    } catch {
      // Degrada silenziosamente
    } finally {
      modal.saving = false
    }
  }

  modal.open = false
  if (modal.pending?.href) triggerDownload(modal.pending.href)
}

function triggerDownload(href) {
  const a = document.createElement('a')
  a.href     = href
  a.download = ''
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

// ── Files ─────────────────────────────────────────────────────────────────────
const completo = computed(() =>
  files.value.find(f => f.tipo === 'completo' && f.formato === 'csv')
)

const scelteFile = computed(() =>
  files.value.find(f => f.tipo === 'scelte' && f.formato === 'xlsx')
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
