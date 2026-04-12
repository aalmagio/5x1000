import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia } from 'pinia'
import App from './App.vue'
import './style.css'

// Lazy-loaded pages
const Home              = () => import('./pages/Home.vue')
const Dati              = () => import('./pages/Dati.vue')
const Confronto         = () => import('./pages/Confronto.vue')
const AnalisiCategorie  = () => import('./pages/AnalisiCategorie.vue')
const Download          = () => import('./pages/Download.vue')
const About             = () => import('./pages/About.vue')
const EnteDetail        = () => import('./pages/EnteDetail.vue')
const ApiDocs            = () => import('./pages/ApiDocs.vue')
const CategoriaDettaglio = () => import('./pages/CategoriaDettaglio.vue')
const Inoptato           = () => import('./pages/Inoptato.vue')
const Forecast           = () => import('./pages/Forecast.vue')
const Classifica         = () => import('./pages/Classifica.vue')
const Geo                = () => import('./pages/Geo.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',                              component: Home,             name: 'home' },
    { path: '/dati',                          component: Dati,             name: 'dati' },
    { path: '/confronto',                     component: Confronto,        name: 'confronto' },
    { path: '/categorie',                     component: AnalisiCategorie, name: 'categorie' },
    { path: '/categorie/:categoria/:anno',    component: CategoriaDettaglio, name: 'categoria_dettaglio' },
    { path: '/inoptato',                      component: Inoptato,         name: 'inoptato' },
    { path: '/forecast',                      component: Forecast,         name: 'forecast' },
    { path: '/download',                      component: Download,         name: 'download' },
    { path: '/about',                         component: About,            name: 'about' },
    { path: '/api',                           component: ApiDocs,          name: 'api' },
    { path: '/classifica',                    component: Classifica,       name: 'classifica' },
    { path: '/ente/:cf',                      component: EnteDetail,       name: 'ente' },
    { path: '/geo',                           component: Geo,              name: 'geo' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

createApp(App).use(createPinia()).use(router).mount('#app')
