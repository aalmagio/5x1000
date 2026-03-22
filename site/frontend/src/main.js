import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
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
const ApiDocs           = () => import('./pages/ApiDocs.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',            component: Home,             name: 'home' },
    { path: '/dati',        component: Dati,             name: 'dati' },
    { path: '/confronto',   component: Confronto,        name: 'confronto' },
    { path: '/categorie',   component: AnalisiCategorie, name: 'categorie' },
    { path: '/download',    component: Download,         name: 'download' },
    { path: '/about',       component: About,            name: 'about' },
    { path: '/api',         component: ApiDocs,          name: 'api' },
    { path: '/ente/:cf',    component: EnteDetail,       name: 'ente' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

createApp(App).use(router).mount('#app')
