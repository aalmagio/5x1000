/**
 * stores/meta.js — Pinia store per dati "meta" condivisi.
 *
 * Evita che ogni pagina ri-fetchi anni, categorie e regioni
 * indipendentemente. I dati vengono caricati una volta sola
 * al primo utilizzo (lazy, via ensure()) e poi cachati in
 * memoria per tutta la sessione.
 *
 * Uso in un componente Vue:
 *
 *   import { useMetaStore } from '@/stores/meta'
 *
 *   const meta = useMetaStore()
 *   await meta.ensure()
 *   // meta.anni, meta.categorie, meta.regioni ora disponibili
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchAnni, fetchCategorie, fetchRegioni } from '@/api/client'

export const useMetaStore = defineStore('meta', () => {
  // ── State ────────────────────────────────────────────────────────────────
  const anni      = ref([])
  const categorie = ref([])
  const regioni   = ref([])
  const loaded    = ref(false)
  const loading   = ref(false)
  const error     = ref(null)

  // ── Computed ─────────────────────────────────────────────────────────────
  const annoCorrente = computed(() => anni.value[0] ?? null)
  const annoMin      = computed(() => anni.value.length ? Math.min(...anni.value) : null)
  const annoMax      = computed(() => anni.value.length ? Math.max(...anni.value) : null)

  // ── Actions ──────────────────────────────────────────────────────────────

  /**
   * Carica anni, categorie e regioni in parallelo.
   * Idempotente: se già caricati non fa nulla.
   * Se un caricamento è già in corso, attende che finisca.
   */
  async function ensure() {
    if (loaded.value) return
    if (loading.value) {
      // Attende il caricamento già in corso
      await new Promise((resolve) => {
        const stop = setInterval(() => {
          if (!loading.value) { clearInterval(stop); resolve() }
        }, 50)
      })
      return
    }

    loading.value = true
    error.value   = null

    try {
      const [aRes, cRes, rRes] = await Promise.all([
        fetchAnni(),
        fetchCategorie(),
        fetchRegioni(),
      ])

      anni.value      = aRes.data?.anni      ?? aRes.data ?? []
      categorie.value = cRes.data?.categorie ?? cRes.data ?? []
      regioni.value   = rRes.data?.regioni   ?? rRes.data ?? []
      loaded.value    = true
    } catch (e) {
      error.value = e?.response?.data?.error ?? e?.message ?? 'Errore caricamento metadati'
    } finally {
      loading.value = false
    }
  }

  /** Forza un ricaricamento (utile dopo aggiornamento pipeline). */
  function refresh() {
    loaded.value = false
    return ensure()
  }

  return { anni, categorie, regioni, loaded, loading, error, annoCorrente, annoMin, annoMax, ensure, refresh }
})
