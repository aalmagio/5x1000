-- ============================================================
-- Migrazione: fusione categoria_ripartizioni → categoria_ammissioni
--
-- Aggiunge 2 colonne a categoria_ammissioni,
-- copia i dati da categoria_ripartizioni (se esiste),
-- poi elimina categoria_ripartizioni.
--
-- Idempotente: i CHECK IF NOT EXISTS / IF EXISTS proteggono da
-- esecuzioni multiple.
--
-- Eseguire su: cinque_per_mille (o nome del DB in uso)
-- ============================================================

USE `cinque_per_mille`;

-- 1. Aggiungi le 2 nuove colonne a categoria_ammissioni (se non esistono)
ALTER TABLE `categoria_ammissioni`
  ADD COLUMN IF NOT EXISTS `importo_ripartizione_sotto_soglia` DECIMAL(15,2) DEFAULT NULL
    COMMENT 'quota redistribuita agli enti sotto-soglia (dal 2019)',
  ADD COLUMN IF NOT EXISTS `importo_totale_erogabile`          DECIMAL(15,2) DEFAULT NULL
    COMMENT 'importo effettivamente erogabile inclusa redistribuzione (dal 2019)';

-- 2. Copia i dati da categoria_ripartizioni → categoria_ammissioni
--    Match su (anno, categoria, cod_fiscale, stato).
--    COALESCE: non sovrascrive valori già presenti.
UPDATE `categoria_ammissioni` ca
  JOIN `categoria_ripartizioni` cr
    ON  cr.anno          = ca.anno
    AND cr.categoria     = ca.categoria
    AND cr.cod_fiscale   = ca.cod_fiscale
    AND cr.stato_categoria = ca.stato
SET
  ca.importo_ripartizione_sotto_soglia = COALESCE(
      ca.importo_ripartizione_sotto_soglia,
      NULLIF(cr.importo_ripartizione_sotto_soglia, 0)
  ),
  ca.importo_totale_erogabile = COALESCE(
      ca.importo_totale_erogabile,
      NULLIF(cr.importo_totale_erogabile, 0)
  );

-- 3. Elimina la tabella ora ridondante
DROP TABLE IF EXISTS `categoria_ripartizioni`;

-- 4. Verifica rapida
SELECT
  COUNT(*)                                                        AS n_righe,
  COUNT(importo_ripartizione_sotto_soglia)                        AS con_sotto_soglia,
  COUNT(importo_totale_erogabile)                                 AS con_erogabile,
  ROUND(SUM(importo_totale_erogabile) / 1e6, 2)                  AS totale_erogabile_mln
FROM `categoria_ammissioni`
WHERE stato = 'ammesso';
