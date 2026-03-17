import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

// Lazy-loaded pages
const Home        = () => import('./pages/Home.vue')
const Dati        = () => import('./pages/Dati.vue')
const Download    = () => import('./pages/Download.vue')
const ApiDocs     = () => import('./pages/ApiDocs.vue')
const About       = () => import('./pages/About.vue')
const EnteDetail  = () => import('./pages/EnteDetail.vue')
const Pipeline    = () => import('./pages/Pipeline.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',             component: Home,       name: 'home' },
    { path: '/dati',         component: Dati,       name: 'dati' },
    { path: '/download',     component: Download,   name: 'download' },
    { path: '/api',          component: ApiDocs,    name: 'api' },
    { path: '/about',        component: About,      name: 'about' },
    { path: '/ente/:cf',     component: EnteDetail, name: 'ente' },
    { path: '/pipeline',     component: Pipeline,   name: 'pipeline' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

createApp(App).use(router).mount('#app')
