<template>
  <div class="min-h-screen flex flex-col">
    <!-- Navbar -->
    <header class="sticky top-0 z-50 bg-white border-b border-gray-200 shadow-sm">
      <nav class="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between h-16">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-3 group">
          <img
            src="https://5x1000.assif.it/wp-content/uploads/2026/05/ASSIF_logo-1.png"
            alt="ASSIF"
            class="h-8 w-auto"
          />
          <span class="hidden sm:block text-sm font-semibold text-gray-700 border-l border-gray-300 pl-3 leading-tight">
            Osservatorio ASSIF<br><span class="text-brand-500 font-bold">sul 5, 2 e 8 per mille</span>
          </span>
        </RouterLink>

        <!-- Desktop nav -->
        <ul class="hidden md:flex items-center gap-0.5 text-sm font-medium">
          <li v-for="link in navLinks" :key="link.to">
            <RouterLink
              :to="link.to"
              class="px-3 py-2 rounded-md text-gray-600 hover:text-brand-500 hover:bg-gray-50 transition-colors"
              active-class="text-brand-500 font-semibold"
            >{{ link.label }}</RouterLink>
          </li>
        </ul>

        <!-- Mobile hamburger -->
        <button
          class="md:hidden p-2 rounded-md text-gray-600 hover:bg-gray-100 transition-colors"
          @click="menuOpen = !menuOpen"
          aria-label="Menu"
        >
          <svg v-if="!menuOpen" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
          </svg>
          <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </nav>

      <!-- Mobile menu -->
      <div v-show="menuOpen" class="md:hidden border-t border-gray-100 px-4 py-2 pb-4 space-y-1 bg-white">
        <RouterLink
          v-for="link in navLinks"
          :key="link.to"
          :to="link.to"
          class="block px-3 py-2 rounded-md text-sm font-medium text-gray-600 hover:text-brand-500 hover:bg-gray-50 transition-colors"
          active-class="text-brand-500 bg-red-50"
          @click="menuOpen = false"
        >{{ link.label }}</RouterLink>
      </div>
    </header>

    <!-- Main content -->
    <main class="flex-1">
      <RouterView />
    </main>

    <!-- Footer -->
    <footer class="bg-brand-900 text-gray-400 text-sm mt-12">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 py-10">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-8">
          <!-- Brand -->
          <div>
            <img
              src="https://5x1000.assif.it/wp-content/uploads/2026/05/ASSIF_logo-1.png"
              alt="ASSIF"
              class="h-8 w-auto mb-3 brightness-0 invert"
            />
            <p class="text-gray-400 text-xs leading-relaxed">
              Osservatorio ASSIF sul 5, 2 e 8 per mille<br>
              Associazione Italiana Fundraiser
            </p>
            <!-- Social -->
            <div class="flex gap-3 mt-4">
              <a href="https://www.facebook.com/ASSIF.Associazione.Italiana.Fundraiser/" target="_blank" rel="noopener" class="hover:text-white transition-colors" aria-label="Facebook">
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M22 12c0-5.523-4.477-10-10-10S2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.878v-6.987h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.988C18.343 21.128 22 16.991 22 12z"/></svg>
              </a>
              <a href="https://www.instagram.com/ass_italiana_fundraiser/" target="_blank" rel="noopener" class="hover:text-white transition-colors" aria-label="Instagram">
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12.315 2c2.43 0 2.784.013 3.808.06 1.064.049 1.791.218 2.427.465a4.902 4.902 0 011.772 1.153 4.902 4.902 0 011.153 1.772c.247.636.416 1.363.465 2.427.048 1.067.06 1.407.06 4.123v.08c0 2.643-.012 2.987-.06 4.043-.049 1.064-.218 1.791-.465 2.427a4.902 4.902 0 01-1.153 1.772 4.902 4.902 0 01-1.772 1.153c-.636.247-1.363.416-2.427.465-1.067.048-1.407.06-4.123.06h-.08c-2.643 0-2.987-.012-4.043-.06-1.064-.049-1.791-.218-2.427-.465a4.902 4.902 0 01-1.772-1.153 4.902 4.902 0 01-1.153-1.772c-.247-.636-.416-1.363-.465-2.427-.047-1.024-.06-1.379-.06-3.808v-.63c0-2.43.013-2.784.06-3.808.049-1.064.218-1.791.465-2.427a4.902 4.902 0 011.153-1.772A4.902 4.902 0 015.45 2.525c.636-.247 1.363-.416 2.427-.465C8.901 2.013 9.256 2 11.685 2h.63zm-.081 1.802h-.468c-2.456 0-2.784.011-3.807.058-.975.045-1.504.207-1.857.344-.467.182-.8.398-1.15.748-.35.35-.566.683-.748 1.15-.137.353-.3.882-.344 1.857-.047 1.023-.058 1.351-.058 3.807v.468c0 2.456.011 2.784.058 3.807.045.975.207 1.504.344 1.857.182.466.399.8.748 1.15.35.35.683.566 1.15.748.353.137.882.3 1.857.344 1.054.048 1.37.058 4.041.058h.08c2.597 0 2.917-.01 3.96-.058.976-.045 1.505-.207 1.858-.344.466-.182.8-.398 1.15-.748.35-.35.566-.683.748-1.15.137-.353.3-.882.344-1.857.048-1.055.058-1.37.058-4.041v-.08c0-2.597-.01-2.917-.058-3.96-.045-.976-.207-1.505-.344-1.858a3.097 3.097 0 00-.748-1.15 3.098 3.098 0 00-1.15-.748c-.353-.137-.882-.3-1.857-.344-1.023-.047-1.351-.058-3.807-.058zM12 6.865a5.135 5.135 0 110 10.27 5.135 5.135 0 010-10.27zm0 1.802a3.333 3.333 0 100 6.666 3.333 3.333 0 000-6.666zm5.338-3.205a1.2 1.2 0 110 2.4 1.2 1.2 0 010-2.4z"/></svg>
              </a>
              <a href="https://www.linkedin.com/company/assif-associazione-italiana-fundraiser/" target="_blank" rel="noopener" class="hover:text-white transition-colors" aria-label="LinkedIn">
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
              </a>
              <a href="https://www.youtube.com/c/AssifItalia" target="_blank" rel="noopener" class="hover:text-white transition-colors" aria-label="YouTube">
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
              </a>
            </div>
          </div>
          <!-- Esplora -->
          <div>
            <p class="font-semibold text-white mb-3">Esplora</p>
            <ul class="space-y-2">
              <li><RouterLink to="/dati"       class="hover:text-white transition-colors">Ricerca enti</RouterLink></li>
              <li><RouterLink to="/confronto"  class="hover:text-white transition-colors">Confronto enti</RouterLink></li>
              <li><RouterLink to="/categorie"  class="hover:text-white transition-colors">Analisi categorie</RouterLink></li>
              <li><RouterLink to="/classifica" class="hover:text-white transition-colors">Classifica</RouterLink></li>
              <li><RouterLink to="/geo"        class="hover:text-white transition-colors">Mappa geografica</RouterLink></li>
              <li><RouterLink to="/inoptato"   class="hover:text-white transition-colors">Inoptato</RouterLink></li>
              <li><RouterLink to="/forecast"   class="hover:text-white transition-colors">Proiezioni trend</RouterLink></li>
              <li><RouterLink to="/download"   class="hover:text-white transition-colors">Download dataset</RouterLink></li>
            </ul>
          </div>
          <!-- ASSIF -->
          <div>
            <p class="font-semibold text-white mb-3">ASSIF</p>
            <ul class="space-y-2">
              <li><a href="https://www.assif.it" target="_blank" rel="noopener" class="hover:text-white transition-colors">Sito ASSIF</a></li>
              <li><a href="https://5x1000.assif.it" target="_blank" rel="noopener" class="hover:text-white transition-colors">Osservatorio ASSIF sul 5, 2 e 8 per mille</a></li>
              <li><a href="https://www.assif.it/soci/modulo-iscrizione/" target="_blank" rel="noopener" class="hover:text-white transition-colors">Diventa socio</a></li>
              <li><a href="https://www.assif.it/contatti/" target="_blank" rel="noopener" class="hover:text-white transition-colors">Contatti</a></li>
              <li><RouterLink to="/about" class="hover:text-white transition-colors">Crediti &amp; licenza</RouterLink></li>
            </ul>
          </div>
        </div>
        <div class="mt-8 pt-6 border-t border-white/10 flex flex-col sm:flex-row justify-between gap-2 text-xs text-gray-500">
          <span>ASSIF – Associazione Italiana Fundraiser &bull; Via della Chiusa, 2 – 20123 Milano &bull; C.F. 92047140402</span>
          <span>Dati: Agenzia delle Entrate &bull; Licenza <span class="text-gray-400">CC BY 4.0</span></span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'

const menuOpen = ref(false)

const navLinks = [
  { to: '/',           label: 'Home' },
  { to: '/dati',       label: 'Esplora' },
  { to: '/confronto',  label: 'Confronto' },
  { to: '/categorie',  label: 'Categorie' },
  { to: '/classifica', label: 'Classifica' },
  { to: '/geo',        label: 'Mappa' },
  { to: '/inoptato',   label: 'Inoptato' },
  { to: '/forecast',   label: 'Proiezioni' },
  { to: '/download',   label: 'Download' },
  { to: '/api',        label: 'API' },
  { to: '/about',      label: 'Info' },
]
</script>
