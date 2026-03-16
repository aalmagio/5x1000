<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-10">
    <h1 class="mb-2">Documentazione API</h1>
    <p class="text-gray-500 mb-8">
      API REST pubblica e gratuita. Nessuna registrazione o chiave di accesso richiesta.
    </p>

    <!-- Link a Swagger -->
    <div class="card bg-brand-50 border-brand-200 mb-8 flex flex-col sm:flex-row items-center gap-4 justify-between">
      <div>
        <p class="font-semibold text-brand-800">Interfaccia interattiva (Swagger UI)</p>
        <p class="text-sm text-brand-600 mt-1">Esplora e prova tutti gli endpoint direttamente nel browser.</p>
      </div>
      <a href="/api/docs" target="_blank" class="btn-primary whitespace-nowrap">Apri Swagger</a>
    </div>

    <!-- Base URL -->
    <div class="card mb-8">
      <h2 class="mb-3">Base URL</h2>
      <code class="block bg-gray-900 text-green-400 rounded-lg px-4 py-3 text-sm">
        https://tuodominio.it/api/v1
      </code>
      <p class="text-sm text-gray-500 mt-2">Tutte le risposte sono in JSON, encoding UTF-8.</p>
    </div>

    <!-- Endpoints -->
    <div class="space-y-6">
      <div v-for="ep in endpoints" :key="ep.path" class="card">
        <div class="flex items-start gap-3 mb-3">
          <span class="badge bg-green-100 text-green-700 font-mono text-xs px-2 py-1">GET</span>
          <code class="font-mono text-brand-700 text-sm">{{ ep.path }}</code>
        </div>
        <p class="text-gray-600 text-sm mb-3">{{ ep.desc }}</p>

        <!-- Parametri -->
        <div v-if="ep.params?.length" class="mb-3">
          <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Parametri</p>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Nome</th><th>Tipo</th><th>Descrizione</th></tr></thead>
              <tbody>
                <tr v-for="p in ep.params" :key="p.name">
                  <td class="font-mono text-xs">{{ p.name }}</td>
                  <td class="text-gray-400 text-xs">{{ p.type }}</td>
                  <td class="text-gray-600 text-xs whitespace-normal">{{ p.desc }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Esempio -->
        <div v-if="ep.example">
          <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Esempio</p>
          <code class="block bg-gray-900 text-green-300 rounded-lg px-3 py-2 text-xs overflow-x-auto">{{ ep.example }}</code>
        </div>
      </div>
    </div>

    <!-- Limiti -->
    <div class="card mt-8 bg-yellow-50 border-yellow-200">
      <h3 class="text-yellow-800 mb-2">Note sull'utilizzo</h3>
      <ul class="text-sm text-yellow-700 list-disc pl-5 space-y-1">
        <li>Nessun rate limit per uso normale (dati statici).</li>
        <li>Massimo <strong>1000 righe per pagina</strong> (parametro <code>per_pagina</code>).</li>
        <li>I dati vengono aggiornati con cadenza periodica (tipicamente annuale).</li>
        <li>Per bulk download usare gli endpoint <code>/download/csv/*</code>.</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
const endpoints = [
  {
    path: '/api/v1/status',
    desc: 'Stato generale del dataset: ultimo aggiornamento, anni disponibili, numero totale di record.',
    example: 'GET /api/v1/status',
  },
  {
    path: '/api/v1/anni',
    desc: 'Lista degli anni disponibili nel dataset, in ordine decrescente.',
    example: 'GET /api/v1/anni',
  },
  {
    path: '/api/v1/categorie',
    desc: 'Lista delle categorie di enti beneficiari disponibili.',
    example: 'GET /api/v1/categorie',
  },
  {
    path: '/api/v1/statistiche',
    desc: 'Aggregazioni per anno: totali, ripartizione per categoria e per regione.',
    params: [
      { name: 'anno', type: 'int (opt)', desc: 'Filtra per anno specifico. Omettere per tutti gli anni.' },
    ],
    example: 'GET /api/v1/statistiche?anno=2024',
  },
  {
    path: '/api/v1/enti',
    desc: 'Ricerca paginata degli enti con filtri multipli.',
    params: [
      { name: 'anno',       type: 'int (opt)',    desc: 'Anno di riferimento' },
      { name: 'categoria',  type: 'string (opt)', desc: 'Categoria principale (es. volontariato)' },
      { name: 'regione',    type: 'string (opt)', desc: 'Regione in maiuscolo (es. LOMBARDIA)' },
      { name: 'provincia',  type: 'string (opt)', desc: 'Sigla provincia (es. MI)' },
      { name: 'cf',         type: 'string (opt)', desc: 'Codice fiscale esatto' },
      { name: 'q',          type: 'string (opt)', desc: 'Ricerca nel nome (LIKE %q%)' },
      { name: 'runts_only', type: 'bool (opt)',   desc: 'Solo enti iscritti al RUNTS con flag 5x1000' },
      { name: 'pagina',     type: 'int',          desc: 'Numero pagina (default: 1)' },
      { name: 'per_pagina', type: 'int',          desc: 'Righe per pagina (default: 50, max: 1000)' },
    ],
    example: 'GET /api/v1/enti?anno=2024&categoria=volontariato&regione=LOMBARDIA&pagina=1&per_pagina=50',
  },
  {
    path: '/api/v1/enti/{codice_fiscale}',
    desc: 'Storico completo di un singolo ente identificato dal codice fiscale.',
    example: 'GET /api/v1/enti/12345678901',
  },
  {
    path: '/download/files',
    desc: 'Catalogo di tutti i file scaricabili con metadati (dimensione, hash, data aggiornamento).',
    params: [
      { name: 'anno', type: 'int (opt)', desc: 'Filtra per anno' },
      { name: 'tipo', type: 'string (opt)', desc: 'Filtra per tipo: completo | normalizzato | report | categoria' },
    ],
    example: 'GET /download/files?anno=2024',
  },
  {
    path: '/download/csv/completo',
    desc: 'Scarica il dataset CSV completo di tutti gli anni (~210 MB, ~1M righe).',
    example: 'GET /download/csv/completo',
  },
  {
    path: '/download/csv/{anno}',
    desc: 'Scarica un CSV filtrato per il singolo anno, generato al volo dallo stream del dataset completo.',
    example: 'GET /download/csv/2024',
  },
]
</script>
