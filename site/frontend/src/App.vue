<template>
  <div class="min-h-screen flex flex-col">
    <!-- Navbar -->
    <header class="sticky top-0 z-50 bg-brand-700/95 backdrop-blur-sm text-white shadow-lg">
      <nav class="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between h-16">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center gap-2.5 font-bold text-lg tracking-tight group">
          <span class="flex items-center justify-center w-9 h-9 bg-yellow-400 text-brand-900 font-extrabold rounded-lg text-sm group-hover:bg-yellow-300 transition-colors">5‰</span>
          <span class="hidden sm:block">Dati 5×1000</span>
        </RouterLink>

        <!-- Desktop nav -->
        <ul class="hidden md:flex items-center gap-1 text-sm font-medium">
          <li v-for="link in navLinks" :key="link.to">
            <RouterLink
              :to="link.to"
              class="px-3 py-2 rounded-md hover:bg-white/10 transition-colors"
              active-class="bg-white/20"
            >{{ link.label }}</RouterLink>
          </li>
        </ul>

        <!-- Mobile hamburger -->
        <button
          class="md:hidden p-2 rounded-md hover:bg-white/10 transition-colors"
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
      <div v-show="menuOpen" class="md:hidden border-t border-white/10 px-4 py-2 pb-4 space-y-1">
        <RouterLink
          v-for="link in navLinks"
          :key="link.to"
          :to="link.to"
          class="block px-3 py-2 rounded-md text-sm font-medium hover:bg-white/10 transition-colors"
          active-class="bg-white/20"
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
          <div>
            <div class="flex items-center gap-2 mb-3">
              <span class="flex items-center justify-center w-8 h-8 bg-yellow-400 text-brand-900 font-extrabold rounded text-xs">5‰</span>
              <p class="font-semibold text-white">Dati 5×1000</p>
            </div>
            <p class="text-gray-400 text-xs leading-relaxed">
              Dataset open data sui beneficiari del cinque per mille italiano.<br>
              Fonte: Agenzia delle Entrate &bull; RUNTS
            </p>
          </div>
          <div>
            <p class="font-semibold text-white mb-3">Esplora</p>
            <ul class="space-y-2">
              <li><RouterLink to="/dati"      class="hover:text-white transition-colors">Ricerca enti</RouterLink></li>
              <li><RouterLink to="/confronto" class="hover:text-white transition-colors">Confronto enti</RouterLink></li>
              <li><RouterLink to="/categorie" class="hover:text-white transition-colors">Analisi categorie</RouterLink></li>
              <li><RouterLink to="/classifica" class="hover:text-white transition-colors">Classifica</RouterLink></li>
              <li><RouterLink to="/inoptato"  class="hover:text-white transition-colors">Inoptato</RouterLink></li>
              <li><RouterLink to="/forecast"  class="hover:text-white transition-colors">Proiezioni trend</RouterLink></li>
              <li><RouterLink to="/download"  class="hover:text-white transition-colors">Download dataset</RouterLink></li>
              <li><RouterLink to="/about"     class="hover:text-white transition-colors">Crediti &amp; licenza</RouterLink></li>
            </ul>
          </div>
          <div>
            <p class="font-semibold text-white mb-3">Progetto</p>
            <ul class="space-y-2">
              <li><a href="https://github.com/aalmagio/5x1000" class="hover:text-white transition-colors" target="_blank" rel="noopener">GitHub</a></li>
              <li><span class="text-gray-500 text-xs">Fonte: Agenzia delle Entrate &amp; RUNTS</span></li>
            </ul>
          </div>
        </div>
        <div class="mt-8 pt-6 border-t border-white/10 flex flex-col sm:flex-row justify-between gap-2 text-xs text-gray-500">
          <span>Dati: Agenzia delle Entrate &bull; Licenza: <span class="text-gray-400">CC BY 4.0</span></span>
          <span>Codice: MIT License</span>
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
  { to: '/inoptato',   label: 'Inoptato' },
  { to: '/forecast',   label: 'Proiezioni' },
  { to: '/download',   label: 'Download' },
  { to: '/api',        label: 'API' },
  { to: '/about',      label: 'Info' },
]
</script>
