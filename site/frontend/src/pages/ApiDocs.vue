<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-10">
    <div class="mb-8">
      <h1 class="mb-1">Documentazione API</h1>
      <p class="text-gray-500">API REST pubblica e gratuita. Nessuna registrazione o chiave di accesso richiesta.</p>
    </div>

    <!-- CTA Swagger + Base URL -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-10">
      <div class="card bg-brand-50 border-brand-200 flex items-start gap-4">
        <div class="w-10 h-10 bg-brand-600 rounded-xl flex items-center justify-center flex-shrink-0">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
        </div>
        <div class="flex-1">
          <p class="font-semibold text-brand-800 text-sm">Swagger UI interattivo</p>
          <p class="text-xs text-brand-600 mt-0.5 mb-3">Prova gli endpoint direttamente nel browser</p>
          <a href="/api/docs" target="_blank" class="btn-primary text-xs px-3 py-1.5 inline-flex items-center gap-1.5">
            Apri Swagger
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
            </svg>
          </a>
        </div>
      </div>

      <div class="card">
        <p class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Base URL</p>
        <div class="relative group">
          <pre class="bg-gray-900 text-emerald-400 rounded-lg px-4 py-3 text-sm font-mono overflow-x-auto">https://tuodominio.it/api/v1</pre>
        </div>
        <p class="text-xs text-gray-400 mt-2">Risposte JSON, encoding UTF-8, CORS aperto.</p>
      </div>
    </div>

    <!-- Indice endpoints -->
    <div class="card mb-8 bg-gray-50 border-gray-100">
      <p class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3">Endpoint disponibili</p>
      <div class="flex flex-wrap gap-2">
        <a
          v-for="ep in endpoints"
          :key="ep.path"
          :href="`#ep-${ep.id}`"
          class="inline-flex items-center gap-1.5 text-xs font-mono bg-white border border-gray-200 hover:border-brand-300 hover:text-brand-700 text-gray-600 px-2.5 py-1 rounded-lg transition-colors"
        >
          <span class="text-emerald-600 font-semibold">GET</span>
          {{ ep.path }}
        </a>
      </div>
    </div>

    <!-- Endpoint cards -->
    <div class="space-y-6">
      <div
        v-for="ep in endpoints"
        :key="ep.path"
        :id="`ep-${ep.id}`"
        class="card scroll-mt-20"
      >
        <!-- Header endpoint -->
        <div class="flex items-start gap-3 mb-3">
          <span class="badge bg-emerald-100 text-emerald-700 font-mono font-bold text-xs px-2.5 py-1 flex-shrink-0 mt-0.5">GET</span>
          <div class="min-w-0">
            <code class="font-mono text-brand-700 text-sm font-semibold break-all">{{ ep.path }}</code>
            <p class="text-gray-600 text-sm mt-1.5 leading-relaxed">{{ ep.desc }}</p>
          </div>
        </div>

        <!-- Parametri -->
        <div v-if="ep.params?.length" class="mb-4">
          <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Parametri query</p>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Tipo</th>
                  <th>Descrizione</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in ep.params" :key="p.name">
                  <td class="font-mono text-xs text-brand-600 whitespace-nowrap">{{ p.name }}</td>
                  <td class="whitespace-nowrap">
                    <span class="badge text-xs" :class="p.required ? 'bg-red-50 text-red-600' : 'bg-gray-100 text-gray-500'">
                      {{ p.type }}
                    </span>
                  </td>
                  <td class="text-gray-600 text-xs whitespace-normal">{{ p.desc }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Esempio -->
        <div v-if="ep.example">
          <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">Esempio</p>
          <div class="relative group">
            <pre class="bg-gray-900 text-emerald-300 rounded-lg px-4 py-3 text-xs font-mono overflow-x-auto leading-relaxed">{{ ep.example }}</pre>
            <button
              class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs px-2 py-1 rounded"
              @click="copy(ep.example, ep.id)"
            >
              {{ copied === ep.id ? '✓ Copiato' : 'Copia' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Note utilizzo -->
    <div class="card mt-8 bg-amber-50 border-amber-200">
      <div class="flex items-start gap-3">
        <svg class="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <div>
          <h3 class="text-amber-800 font-semibold mb-2">Note sull'utilizzo</h3>
          <ul class="text-sm text-amber-700 space-y-1 list-disc pl-4">
            <li>Nessun rate limit per uso normale (i dati sono statici).</li>
            <li>Massimo <strong>1000 righe per pagina</strong> (parametro <code class="font-mono text-xs bg-amber-100 px-1 rounded">per_pagina</code>).</li>
            <li>I dati vengono aggiornati con cadenza periodica (tipicamente annuale).</li>
            <li>Per bulk download preferire gli endpoint <code class="font-mono text-xs bg-amber-100 px-1 rounded">/download/csv/*</code>.</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const copied = ref(null)

function copy(text, id) {
  navigator.clipboard?.writeText(text).then(() => {
    copied.value = id
    setTimeout(() => { copied.value = null }, 2000)
  })
}

const endpoints = [
  {
    id: 'status',
    path: '/api/v1/status',
    desc: 'Stato generale del dataset: ultimo aggiornamento, anni disponibili, numero totale di record.',
    example: 'GET /api/v1/status',
  },
  {
    id: 'anni',
    path: '/api/v1/anni',
    desc: 'Lista degli anni disponibili nel dataset, in ordine decrescente.',
    example: 'GET /api/v1/anni',
  },
  {
    id: 'categorie',
    path: '/api/v1/categorie',
    desc: 'Lista delle categorie di enti beneficiari disponibili.',
    example: 'GET /api/v1/categorie',
  },
  {
    id: 'statistiche',
    path: '/api/v1/statistiche',
    desc: 'Aggregazioni per anno: totali, ripartizione per categoria e per regione.',
    params: [
      { name: 'anno', type: 'int', desc: 'Filtra per anno specifico. Omettere per tutti gli anni.' },
    ],
    example: 'GET /api/v1/statistiche?anno=2024',
  },
  {
    id: 'enti',
    path: '/api/v1/enti',
    desc: 'Ricerca paginata degli enti con filtri multipli. Risultati ordinati per importo decrescente.',
    params: [
      { name: 'anno',       type: 'int',    desc: 'Anno di riferimento' },
      { name: 'categoria',  type: 'string', desc: 'Categoria principale (es. volontariato)' },
      { name: 'regione',    type: 'string', desc: 'Regione in maiuscolo (es. LOMBARDIA)' },
      { name: 'provincia',  type: 'string', desc: 'Sigla provincia (es. MI)' },
      { name: 'cf',         type: 'string', desc: 'Codice fiscale esatto' },
      { name: 'q',          type: 'string', desc: 'Ricerca nel nome (LIKE %q%)' },
      { name: 'runts_only', type: 'bool',   desc: 'Solo enti iscritti al RUNTS con flag 5x1000' },
      { name: 'pagina',     type: 'int',    desc: 'Numero pagina (default: 1)' },
      { name: 'per_pagina', type: 'int',    desc: 'Righe per pagina (default: 50, max: 1000)' },
    ],
    example: 'GET /api/v1/enti?anno=2024&categoria=volontariato&regione=LOMBARDIA&pagina=1&per_pagina=50',
  },
  {
    id: 'ente-storico',
    path: '/api/v1/enti/{codice_fiscale}',
    desc: 'Storico completo di un singolo ente per tutti gli anni disponibili, identificato dal codice fiscale.',
    example: 'GET /api/v1/enti/12345678901',
  },
  {
    id: 'download-files',
    path: '/download/files',
    desc: 'Catalogo di tutti i file scaricabili con metadati (dimensione, hash, data aggiornamento).',
    params: [
      { name: 'anno', type: 'int',    desc: 'Filtra per anno' },
      { name: 'tipo', type: 'string', desc: 'Tipo file: completo | normalizzato | report | categoria' },
    ],
    example: 'GET /download/files?anno=2024',
  },
  {
    id: 'download-csv-completo',
    path: '/download/csv/completo',
    desc: 'Scarica il dataset CSV completo di tutti gli anni (~210 MB, ~1M righe). Stream diretto senza buffering.',
    example: 'GET /download/csv/completo',
  },
  {
    id: 'download-csv-anno',
    path: '/download/csv/{anno}',
    desc: 'Scarica un CSV filtrato per il singolo anno, generato al volo dallo stream del dataset completo.',
    example: 'GET /download/csv/2024',
  },
]
</script>
