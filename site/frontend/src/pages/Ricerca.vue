<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-6">
      <h1 class="mb-1">Interroga i dati in linguaggio naturale</h1>
      <p class="text-gray-500">
        Scrivi una domanda in italiano sui dati 5×1000. Il sistema la traduce automaticamente
        in una query sul database e restituisce i risultati.
      </p>
    </div>

    <!-- Disclaimer -->
    <div class="flex gap-3 items-start bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 mb-6 text-sm text-blue-800">
      <svg class="w-5 h-5 flex-shrink-0 mt-0.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <p class="leading-relaxed">
        <span class="font-semibold">Motore AI autonomo.</span>
        Questa funzione utilizza un modello di intelligenza artificiale ospitato direttamente
        sui nostri server, senza dipendenze da servizi esterni a pagamento.
        Questo ci permette di offrire la ricerca in linguaggio naturale in modo sostenibile
        e gratuito per tutti gli utenti. I tempi di risposta possono essere di qualche decina
        di secondi: ti chiediamo un momento di pazienza.
      </p>
    </div>

    <!-- Form ricerca -->
    <div class="card mb-6">
      <label class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block">
        La tua domanda
      </label>
      <div class="flex gap-2">
        <input
          v-model="domanda"
          type="text"
          class="input-field flex-1"
          placeholder="es: top 10 enti per importo nel 2024"
          @keydown.enter="cerca"
          :disabled="loading || !token"
          maxlength="500"
        />
        <button
          class="btn-primary px-5 flex items-center gap-2 flex-shrink-0"
          :disabled="loading || !domanda.trim() || !token"
          @click="cerca"
        >
          <svg v-if="!loading" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>
          </svg>
          <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          {{ loading ? 'Elaboro…' : 'Cerca' }}
        </button>
      </div>

      <!-- Esempi -->
      <div class="mt-3 flex flex-wrap gap-2">
        <span class="text-xs text-gray-400 self-center">Prova:</span>
        <button
          v-for="ex in esempi"
          :key="ex"
          class="text-xs px-2.5 py-1 rounded-full border border-gray-200 text-gray-600
                 hover:border-brand-400 hover:text-brand-700 transition-colors"
          @click="domanda = ex; cerca()"
        >{{ ex }}</button>
      </div>

      <!-- Stato token -->
      <p v-if="!token && !tokenError" class="text-xs text-gray-400 mt-2">
        Caricamento sistema di ricerca…
      </p>
      <p v-if="tokenError" class="text-xs text-red-500 mt-2">
        {{ tokenError }}
      </p>
    </div>

    <!-- Errore query -->
    <div v-if="error" class="card border-red-200 bg-red-50 mb-6">
      <p class="text-red-700 text-sm font-medium">{{ error }}</p>
    </div>

    <!-- Risultato -->
    <template v-if="result">
      <!-- Header risultato -->
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2 text-sm text-gray-500">
          <span class="font-medium text-gray-800">{{ result.n_righe }} risultati</span>
          <span v-if="result.from_cache"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 text-xs">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003
                   8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            dalla cache
          </span>
        </div>
        <!-- Toggle SQL -->
        <button
          class="text-xs text-brand-600 hover:text-brand-800 font-medium"
          @click="showSql = !showSql"
        >
          {{ showSql ? 'Nascondi SQL' : 'Mostra SQL generato' }}
        </button>
      </div>

      <!-- SQL generato -->
      <div v-if="showSql" class="card bg-gray-900 text-gray-100 mb-4 overflow-x-auto">
        <pre class="text-xs font-mono whitespace-pre-wrap">{{ result.sql }}</pre>
      </div>

      <!-- Tabella risultati -->
      <div v-if="result.data.length > 0" class="card overflow-x-auto p-0">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-100">
              <th
                v-for="col in result.colonne"
                :key="col"
                class="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap"
              >{{ col.replace(/_/g, ' ') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in result.data"
              :key="i"
              class="border-b border-gray-50 hover:bg-gray-50 transition-colors"
            >
              <td
                v-for="col in result.colonne"
                :key="col"
                class="px-4 py-2.5 text-gray-700 whitespace-nowrap"
              >
                <template v-if="isImporto(col) && row[col] !== null">
                  <span class="font-medium">{{ formatEuro(row[col]) }}</span>
                </template>
                <template v-else-if="isConteggio(col) && row[col] !== null">
                  {{ formatNum(row[col]) }}
                </template>
                <template v-else-if="row[col] === null || row[col] === ''">
                  <span class="text-gray-300">—</span>
                </template>
                <template v-else>{{ row[col] }}</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="card text-center py-10 text-gray-400 text-sm">
        Nessun risultato per questa domanda.
      </div>
    </template>

    <!-- Storico sessione -->
    <div v-if="storico.length > 1" class="mt-8">
      <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Domande precedenti</h2>
      <div class="flex flex-col gap-2">
        <button
          v-for="(s, i) in storico.slice(1)"
          :key="i"
          class="text-left px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-600
                 hover:border-brand-400 hover:text-brand-700 transition-colors"
          @click="domanda = s; cerca()"
        >{{ s }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { nlqToken, nlqQuery } from '../api/client.js'

const domanda    = ref('')
const token      = ref('')
const tokenError = ref('')
const loading    = ref(false)
const error      = ref('')
const result     = ref(null)
const showSql    = ref(false)
const storico    = ref([])

const esempi = [
  'top 10 enti per importo nel 2024',
  'quante ASD ci sono in Lombardia nel 2023?',
  'totale erogato per categoria nel 2024',
  'enti di ricerca sanitaria con più di 10000 scelte nel 2024',
  'quanti enti sono iscritti al RUNTS?',
]

onMounted(async () => {
  try {
    const { data } = await nlqToken()
    token.value = data.token
  } catch {
    tokenError.value = 'Ricerca AI non disponibile al momento. Contattare l\'amministratore.'
  }
})

async function cerca() {
  const q = domanda.value.trim()
  if (!q || !token.value) return

  loading.value = true
  error.value   = ''
  result.value  = null
  showSql.value = false

  try {
    const { data } = await nlqQuery(token.value, q)
    result.value = data
    storico.value = [q, ...storico.value.filter(s => s !== q)].slice(0, 10)
  } catch (e) {
    const msg = e.response?.data?.error
    if (e.response?.status === 429) {
      error.value = 'Hai raggiunto il limite di query per ora. Riprova tra poco.'
    } else if (e.response?.status === 503) {
      error.value = msg || 'Il servizio AI non è disponibile. Assicurarsi che Ollama sia avviato sul server.'
    } else if (e.response?.status === 422) {
      error.value = msg || 'Non è stato possibile rispondere a questa domanda. Prova a riformularla.'
    } else {
      error.value = msg || 'Errore durante l\'elaborazione della domanda.'
    }
  } finally {
    loading.value = false
  }
}

const importoKeywords = ['importo','totale','espresso','generico','eur','euro','erogato','valore']
const conteggiKeywords = ['n_enti','n_scelte','scelte','conteggio','count','enti','occorrenze']

function isImporto(col) {
  const c = col.toLowerCase()
  return importoKeywords.some(k => c.includes(k))
}

function isConteggio(col) {
  const c = col.toLowerCase()
  return conteggiKeywords.some(k => c.includes(k)) && !isImporto(col)
}

function formatEuro(v) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(v)
}

function formatNum(v) {
  return new Intl.NumberFormat('it-IT').format(v)
}
</script>
