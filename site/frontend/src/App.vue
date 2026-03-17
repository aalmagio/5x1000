<template>
  <div class="min-h-screen flex flex-col">
    <!-- Navbar -->
    <header class="bg-brand-700 text-white shadow-md">
      <nav class="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between h-16">
        <RouterLink to="/" class="flex items-center gap-2 font-bold text-lg tracking-tight">
          <span class="text-2xl">5‰</span>
          <span class="hidden sm:block">Dati 5×1000</span>
        </RouterLink>
        <ul class="flex items-center gap-1 text-sm font-medium">
          <li v-for="link in navLinks" :key="link.to">
            <RouterLink
              :to="link.to"
              class="px-3 py-2 rounded-md hover:bg-white/10 transition-colors"
              active-class="bg-white/20"
            >
              {{ link.label }}
            </RouterLink>
          </li>
        </ul>
      </nav>
    </header>

    <!-- Main content -->
    <main class="flex-1">
      <RouterView />
    </main>

    <!-- Footer -->
    <footer class="bg-gray-800 text-gray-400 text-sm mt-8">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row justify-between gap-4">
        <div>
          <p class="font-semibold text-white mb-1">Dati 5×1000 – Open Data</p>
          <p>Fonte: Agenzia delle Entrate • Licenza dati: CC BY 4.0</p>
        </div>
        <div class="flex flex-col gap-1">
          <RouterLink to="/api"   class="hover:text-white transition-colors">Documentazione API</RouterLink>
          <RouterLink to="/about" class="hover:text-white transition-colors">Crediti &amp; licenza</RouterLink>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { RouterLink, RouterView } from 'vue-router'

const navLinks = [
  { to: '/',          label: 'Home' },
  { to: '/dati',      label: 'Esplora' },
  { to: '/download',  label: 'Download' },
  { to: '/api',       label: 'API' },
  { to: '/about',     label: 'Info' },
  { to: '/pipeline',  label: '⚙ Pipeline' },
]
</script>
