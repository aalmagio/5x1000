<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <div>
        <h3 class="text-sm font-semibold text-gray-700">{{ title }}</h3>
        <p v-if="subtitle" class="text-xs text-gray-400 mt-0.5">{{ subtitle }}</p>
      </div>
      <div class="flex items-center gap-3 text-xs text-gray-400">
        <span class="flex items-center gap-1">
          <span class="inline-block w-3 h-3 rounded-sm" :style="{ background: colorLow }"></span>
          {{ labelLow }}
        </span>
        <span class="flex items-center gap-1">
          <span class="inline-block w-3 h-3 rounded-sm" :style="{ background: colorHigh }"></span>
          {{ labelHigh }}
        </span>
      </div>
    </div>

    <!-- Griglia tile cartogram 7×5 (col, row) -->
    <div
      class="grid gap-1"
      style="grid-template-columns: repeat(7, 1fr); grid-template-rows: repeat(5, 40px);"
    >
      <div
        v-for="tile in tiles"
        :key="tile.code"
        class="relative rounded flex items-center justify-center cursor-default transition-transform hover:scale-105 hover:z-10"
        :style="gridStyle(tile)"
        :title="tooltip(tile)"
      >
        <span class="text-[10px] font-bold text-white drop-shadow select-none leading-none text-center px-0.5">
          {{ tile.abbr }}
        </span>
        <!-- Valore sotto l'abbreviazione -->
        <span
          v-if="tile.value != null"
          class="absolute bottom-0.5 left-0 right-0 text-center text-[8px] text-white/80 leading-none"
        >
          {{ formatShort(tile.value) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * Mappa tile cartogram delle 20 regioni italiane.
 * Layout su griglia 7 colonne × 5 righe (col 1-7, row 1-5).
 *
 * Coordinate (col, row) — 1-based, rispecchiano la geografia approssimativa.
 */
const REGION_GRID = [
  { code: 'VDA', abbr: 'VDA', name: "Valle d'Aosta",      col: 1, row: 1 },
  { code: 'PIE', abbr: 'PIE', name: 'Piemonte',           col: 2, row: 1 },
  { code: 'LOM', abbr: 'LOM', name: 'Lombardia',          col: 3, row: 1 },
  { code: 'TAA', abbr: 'TAA', name: 'Trentino-A. A.',     col: 4, row: 1 },
  { code: 'VEN', abbr: 'VEN', name: 'Veneto',             col: 5, row: 1 },
  { code: 'FVG', abbr: 'FVG', name: 'Friuli-V. G.',       col: 6, row: 1 },
  { code: 'LIG', abbr: 'LIG', name: 'Liguria',            col: 2, row: 2 },
  { code: 'EMR', abbr: 'EMR', name: 'Emilia-Romagna',     col: 4, row: 2 },
  { code: 'TOS', abbr: 'TOS', name: 'Toscana',            col: 3, row: 3 },
  { code: 'MAR', abbr: 'MAR', name: 'Marche',             col: 5, row: 3 },
  { code: 'UMB', abbr: 'UMB', name: 'Umbria',             col: 4, row: 3 },
  { code: 'LAZ', abbr: 'LAZ', name: 'Lazio',              col: 4, row: 4 },
  { code: 'ABR', abbr: 'ABR', name: 'Abruzzo',            col: 5, row: 4 },
  { code: 'MOL', abbr: 'MOL', name: 'Molise',             col: 6, row: 4 },
  { code: 'CAM', abbr: 'CAM', name: 'Campania',           col: 4, row: 5 },
  { code: 'PUG', abbr: 'PUG', name: 'Puglia',             col: 6, row: 5 },
  { code: 'BAS', abbr: 'BAS', name: 'Basilicata',         col: 5, row: 5 },
  { code: 'CAL', abbr: 'CAL', name: 'Calabria',           col: 5, row: 6 },
  { code: 'SIC', abbr: 'SIC', name: 'Sicilia',            col: 4, row: 7 },
  { code: 'SAR', abbr: 'SAR', name: 'Sardegna',           col: 2, row: 6 },
]

const props = defineProps({
  /** Array di { regione: string, value: number } — regione è il nome completo */
  data:      { type: Array,  default: () => [] },
  title:     { type: String, default: 'Distribuzione geografica' },
  subtitle:  { type: String, default: '' },
  colorLow:  { type: String, default: '#dbeafe' },   // blue-100
  colorHigh: { type: String, default: '#1d4ed8' },   // blue-700
  labelLow:  { type: String, default: 'minore' },
  labelHigh: { type: String, default: 'maggiore' },
  formatFn:  { type: Function, default: null },
})

// Normalizza il nome regione per il match (lowercase, no accenti semplificati)
function normalize(s) {
  return (s ?? '').toLowerCase()
    .replace(/[àáâ]/g, 'a').replace(/[èéê]/g, 'e')
    .replace(/[ìíî]/g, 'i').replace(/[òóô]/g, 'o')
    .replace(/[ùúû]/g, 'u')
    .replace(/[-\s]+/g, ' ').trim()
}

// Mapping nomi regione → codice tile
const NAME_TO_CODE = {
  "valle d'aosta": 'VDA', "valle daosta": 'VDA', 'vda': 'VDA',
  'piemonte': 'PIE',
  'lombardia': 'LOM',
  'trentino-alto adige': 'TAA', 'trentino alto adige': 'TAA', 'trentino': 'TAA', 'alto adige': 'TAA',
  'veneto': 'VEN',
  'friuli-venezia giulia': 'FVG', 'friuli venezia giulia': 'FVG', 'friuli': 'FVG',
  'liguria': 'LIG',
  'emilia-romagna': 'EMR', 'emilia romagna': 'EMR', 'emilia': 'EMR',
  'toscana': 'TOS',
  'marche': 'MAR',
  'umbria': 'UMB',
  'lazio': 'LAZ',
  'abruzzo': 'ABR',
  'molise': 'MOL',
  'campania': 'CAM',
  'puglia': 'PUG',
  'basilicata': 'BAS',
  'calabria': 'CAL',
  'sicilia': 'SIC',
  'sardegna': 'SAR',
}

const valueMap = computed(() => {
  const m = {}
  for (const d of props.data) {
    const key = normalize(d.regione)
    const code = NAME_TO_CODE[key]
    if (code) m[code] = d.value
  }
  return m
})

const minVal = computed(() => {
  const vals = Object.values(valueMap.value).filter(v => v != null && v > 0)
  return vals.length ? Math.min(...vals) : 0
})
const maxVal = computed(() => {
  const vals = Object.values(valueMap.value).filter(v => v != null)
  return vals.length ? Math.max(...vals) : 1
})

function lerpColor(hexA, hexB, t) {
  const parse = h => [
    parseInt(h.slice(1, 3), 16),
    parseInt(h.slice(3, 5), 16),
    parseInt(h.slice(5, 7), 16),
  ]
  const [r1, g1, b1] = parse(hexA)
  const [r2, g2, b2] = parse(hexB)
  const r = Math.round(r1 + (r2 - r1) * t)
  const g = Math.round(g1 + (g2 - g1) * t)
  const b = Math.round(b1 + (b2 - b1) * t)
  return `rgb(${r},${g},${b})`
}

function tileColor(code) {
  const v = valueMap.value[code]
  if (v == null) return '#e5e7eb' // gray-200
  const range = maxVal.value - minVal.value
  const t = range > 0 ? (v - minVal.value) / range : 0.5
  return lerpColor(props.colorLow, props.colorHigh, t)
}

const tiles = computed(() =>
  REGION_GRID.map(r => ({
    ...r,
    value: valueMap.value[r.code] ?? null,
    color: tileColor(r.code),
  }))
)

function gridStyle(tile) {
  return {
    gridColumn: tile.col,
    gridRow:    tile.row,
    background: tile.color,
  }
}

function tooltip(tile) {
  if (tile.value == null) return `${tile.name}: n.d.`
  return `${tile.name}: ${formatShort(tile.value)}`
}

function formatShort(v) {
  if (props.formatFn) return props.formatFn(v)
  if (v == null) return '–'
  if (v >= 1e9) return (v / 1e9).toFixed(1) + 'Mrd'
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M'
  if (v >= 1e3) return (v / 1e3).toFixed(0) + 'k'
  return String(v)
}
</script>
