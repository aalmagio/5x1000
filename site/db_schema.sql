-- ============================================================
-- Schema MySQL per il sito dati 5x1000
-- Compatibile con MySQL 5.7+ / 8.0+
-- ============================================================

CREATE DATABASE IF NOT EXISTS `cinque_per_mille`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `cinque_per_mille`;

-- ------------------------------------------------------------
-- 1. Tracciamento esecuzioni pipeline
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `pipeline_runs` (
  `id`                INT          NOT NULL AUTO_INCREMENT,
  `run_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `anni_processati`   JSON                  DEFAULT NULL COMMENT 'es. [2024, 2025]',
  `steps_eseguiti`    JSON                  DEFAULT NULL COMMENT 'es. ["download","etl","report"]',
  `righe_totali`      INT          NOT NULL DEFAULT 0    COMMENT 'righe nel CSV normalizzato',
  `status`            ENUM('ok','error','parziale') NOT NULL DEFAULT 'ok',
  `note`              TEXT                  DEFAULT NULL,
  `durata_secondi`    INT                   DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_run_at` (`run_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 2. File disponibili per il download
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `dataset_files` (
  `id`               INT           NOT NULL AUTO_INCREMENT,
  `anno`             SMALLINT               DEFAULT NULL COMMENT 'NULL = file multi-anno (es. dataset completo)',
  `tipo`             ENUM('completo','normalizzato','report','categoria') NOT NULL,
  `categoria`        VARCHAR(50)            DEFAULT NULL COMMENT 'NULL se tipo != categoria',
  `formato`          ENUM('csv','xlsx')     NOT NULL,
  `percorso`         VARCHAR(500)  NOT NULL COMMENT 'path assoluto sul server',
  `nome_file`        VARCHAR(255)  NOT NULL,
  `dimensione_mb`    DECIMAL(8,2)           DEFAULT 0,
  `sha256`           CHAR(64)               DEFAULT NULL COMMENT 'hash integrità file',
  `aggiornato_il`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_file` (`anno`, `tipo`, `categoria`, `formato`),
  KEY `idx_anno` (`anno`),
  KEY `idx_tipo` (`tipo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 3. Dati normalizzati per ricerca via API
--    (mirror della tabella CSV, popolata dalla pipeline)
--    ~1M righe, indicizzata per le query più comuni
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `enti` (
  `id`                     INT           NOT NULL AUTO_INCREMENT,
  `anno`                   SMALLINT      NOT NULL,
  `cod_fiscale`            VARCHAR(20)            DEFAULT NULL,
  `denominazione`          VARCHAR(500)           DEFAULT NULL,
  `regione`                VARCHAR(100)           DEFAULT NULL,
  `provincia`              CHAR(3)                DEFAULT NULL,
  `comune`                 VARCHAR(200)           DEFAULT NULL,
  -- Flag categorie (0/1)
  `cat_volontariato`       TINYINT(1)             DEFAULT 0,
  `cat_asd`                TINYINT(1)             DEFAULT 0,
  `cat_ets_onlus`          TINYINT(1)             DEFAULT 0,
  `cat_ricerca_sci`        TINYINT(1)             DEFAULT 0,
  `cat_ricerca_san`        TINYINT(1)             DEFAULT 0,
  `cat_comuni`             TINYINT(1)             DEFAULT 0,
  `cat_beni_cult`          TINYINT(1)             DEFAULT 0,
  `cat_aree_prot`          TINYINT(1)             DEFAULT 0,
  `categoria_principale`   VARCHAR(50)            DEFAULT NULL,
  -- Valori
  `n_scelte`               INT                    DEFAULT 0,
  `importo_espresso`       DECIMAL(15,2)          DEFAULT NULL,
  `importo_generico`       DECIMAL(15,2)          DEFAULT NULL,
  `importo_totale`         DECIMAL(15,2)          DEFAULT NULL,
  -- Dati RUNTS
  `runts_denominazione`    VARCHAR(500)           DEFAULT NULL,
  `runts_sezione`          VARCHAR(100)           DEFAULT NULL,
  `runts_sede_comune`      VARCHAR(200)           DEFAULT NULL,
  `runts_sede_prov`        CHAR(3)                DEFAULT NULL,
  `runts_5x1000`           TINYINT(1)             DEFAULT 0,
  `runts_data_iscrizione`  DATE                   DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_anno`           (`anno`),
  KEY `idx_cf`             (`cod_fiscale`),
  KEY `idx_anno_cat`       (`anno`, `categoria_principale`),
  KEY `idx_regione`        (`anno`, `regione`),
  KEY `idx_denominazione`  (`denominazione`(100)),
  KEY `idx_importo`        (`anno`, `importo_totale`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Vista: ultimo aggiornamento per anno
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW `v_ultimo_aggiornamento` AS
SELECT
  e.anno,
  COUNT(*)              AS n_enti,
  SUM(e.n_scelte)       AS totale_scelte,
  SUM(e.importo_totale) AS totale_importo,
  MAX(r.run_at)         AS ultimo_aggiornamento
FROM `enti` e
JOIN `pipeline_runs` r ON r.status = 'ok'
GROUP BY e.anno
ORDER BY e.anno DESC;

-- ------------------------------------------------------------
-- Vista: statistiche per categoria (anno corrente)
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW `v_statistiche_categorie` AS
SELECT
  anno,
  categoria_principale,
  COUNT(*)              AS n_enti,
  SUM(n_scelte)         AS totale_scelte,
  SUM(importo_totale)   AS totale_importo
FROM `enti`
WHERE categoria_principale IS NOT NULL
GROUP BY anno, categoria_principale
ORDER BY anno DESC, totale_importo DESC;
