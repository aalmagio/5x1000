-- ============================================================
-- Ottimizzazioni performance - Indici mancanti
-- Eseguire con: mysql -u USER -p cinque_per_mille < db_performance.sql
-- Sicuro su database live (InnoDB online DDL, nessun lock prolungato)
-- ============================================================

-- ------------------------------------------------------------
-- 1. categoria_ammissioni — self-join in conflitti categoria
--    Query: JOIN ca ON e.cod_fiscale = a.cod_fiscale AND e.anno = a.anno AND e.stato = 'escluso'
--    Attuale idx_ca_cf(cod_fiscale) non copre anno+stato → full scan sul join
-- ------------------------------------------------------------
ALTER TABLE categoria_ammissioni
  ADD INDEX idx_ca_cf_anno_stato (cod_fiscale, anno, stato);

-- ------------------------------------------------------------
-- 2. enti — query geografiche provincia e comune
--    idx_regione(anno, regione) esiste già. Mancano provincia e comune.
--    Query: WHERE anno = ? GROUP BY provincia / comune
-- ------------------------------------------------------------
ALTER TABLE enti
  ADD INDEX idx_enti_anno_provincia (anno, provincia),
  ADD INDEX idx_enti_anno_comune    (anno, comune);

-- ------------------------------------------------------------
-- 3. enti — ricerca ordinata per importo dentro categoria
--    Esiste idx_anno_cat(anno, categoria_principale) e idx_importo(anno, importo_totale)
--    separati. MySQL non può combinarli per ORDER BY. Un indice composto copre entrambi.
--    Query: WHERE anno=? AND categoria_principale=? ORDER BY importo_totale DESC LIMIT ?
-- ------------------------------------------------------------
ALTER TABLE enti
  ADD INDEX idx_enti_cat_importo (anno, categoria_principale, importo_totale);

-- ------------------------------------------------------------
-- 4. enti — ricerca ordinata per n_scelte
--    Query: WHERE anno=? [AND categoria=?] ORDER BY n_scelte DESC LIMIT ?
-- ------------------------------------------------------------
ALTER TABLE enti
  ADD INDEX idx_enti_anno_scelte (anno, n_scelte);

-- ------------------------------------------------------------
-- 5. FULLTEXT — ricerca denominazione (LIKE '%testo%' non usa indici B-tree)
--    Permette MATCH(denominazione) AGAINST(? IN BOOLEAN MODE) → 10-50x più veloce
--    api.php usa già MATCH...AGAINST per query ≥3 caratteri (con fallback LIKE).
--    Eseguire solo se l'indice non esiste già:
--      SELECT COUNT(*) FROM information_schema.STATISTICS
--      WHERE table_schema=DATABASE() AND table_name='enti' AND index_name='ft_enti_denom';
-- ------------------------------------------------------------
ALTER TABLE enti  ADD FULLTEXT INDEX ft_enti_denom  (denominazione);
ALTER TABLE runts ADD FULLTEXT INDEX ft_runts_denom (denominazione);

-- ============================================================
-- VERIFICA: mostra indici creati
-- ============================================================
SHOW INDEX FROM enti            WHERE Key_name LIKE 'idx_enti_%' OR Key_name LIKE 'ft_%';
SHOW INDEX FROM categoria_ammissioni WHERE Key_name = 'idx_ca_cf_anno_stato';
