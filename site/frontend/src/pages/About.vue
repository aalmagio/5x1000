<template>
  <div class="max-w-3xl mx-auto px-4 sm:px-6 py-10">
    <h1 class="mb-2">Info &amp; crediti</h1>
    <p class="text-gray-500 mb-8">Informazioni sul progetto, le fonti dati e la licenza.</p>

    <div class="space-y-6">
      <div class="card">
        <h2 class="mb-3">Il progetto</h2>
        <p class="text-gray-600 text-sm leading-relaxed">
          Questo sito mette a disposizione in forma aperta i dati sui beneficiari del
          <strong>5 per mille</strong> dell'IRPEF pubblicati annualmente dall'Agenzia delle Entrate.
          I dati coprono il periodo 2006–2025 e vengono normalizzati e arricchiti con
          informazioni dal RUNTS (Registro Unico Nazionale del Terzo Settore).
        </p>
      </div>

      <div class="card">
        <h2 class="mb-3">Fonti dati</h2>
        <ul class="text-sm text-gray-600 space-y-3">
          <li class="flex items-start gap-2">
            <span class="text-brand-500 mt-0.5">•</span>
            <div>
              <strong>Agenzia delle Entrate</strong> – elenchi dei beneficiari del 5x1000<br />
              <a href="https://www.agenziaentrate.gov.it/portale/web/guest/archivio/5-per-mille"
                 class="text-brand-600 hover:underline text-xs" target="_blank">
                agenziaentrate.gov.it
              </a>
            </div>
          </li>
          <li class="flex items-start gap-2">
            <span class="text-brand-500 mt-0.5">•</span>
            <div>
              <strong>RUNTS</strong> – Registro Unico Nazionale del Terzo Settore<br />
              <a href="https://registroterzosettore.it"
                 class="text-brand-600 hover:underline text-xs" target="_blank">
                registroterzosettore.it
              </a>
            </div>
          </li>
        </ul>
      </div>

      <div class="card">
        <h2 class="mb-3">Licenza</h2>
        <p class="text-sm text-gray-600">
          Il codice sorgente è rilasciato con licenza
          <a href="https://opensource.org/licenses/MIT" class="text-brand-600 hover:underline" target="_blank">MIT</a>.
          I dati originali sono pubblicati dalla Pubblica Amministrazione e sono
          disponibili sotto licenza
          <a href="https://creativecommons.org/licenses/by/4.0/deed.it" class="text-brand-600 hover:underline" target="_blank">CC BY 4.0</a>.
          Si prega di citare la fonte (Agenzia delle Entrate) in caso di riutilizzo.
        </p>
      </div>

      <div class="card">
        <h2 class="mb-3">Tecnologie</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm text-gray-600">
          <div v-for="tech in techs" :key="tech.name" class="flex items-center gap-2">
            <span class="text-brand-400">▸</span>
            <span>{{ tech.name }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const techs = [
  { name: 'Python 3 (pipeline)' },
  { name: 'FastAPI (backend)' },
  { name: 'MySQL (database)' },
  { name: 'Vue 3 + Vite (frontend)' },
  { name: 'Tailwind CSS (stili)' },
  { name: 'Pandas (ETL)' },
  { name: 'pdfplumber (PDF)' },
  { name: 'Plesk (hosting)' },
]
</script>
