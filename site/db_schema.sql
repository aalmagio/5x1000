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
  `anni_processati`   JSON                  DEFAULT NULL COMMENT 'es. [2023, 2024]',
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
-- 4. Registro RUNTS (una riga per codice fiscale)
--    Denominazione canonica: RUNTS se disponibile, altrimenti
--    quella dell'anno più recente nella tabella enti.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `runts` (
  `cod_fiscale`      VARCHAR(20)   NOT NULL,
  `denominazione`    VARCHAR(500)  DEFAULT NULL COMMENT 'Nome canonico (RUNTS o anno più recente)',
  `sezione`          VARCHAR(100)  DEFAULT NULL,
  `sede_comune`      VARCHAR(200)  DEFAULT NULL,
  `sede_prov`        CHAR(3)       DEFAULT NULL,
  `attivo_5x1000`    TINYINT(1)    DEFAULT 0,
  `data_iscrizione`  DATE          DEFAULT NULL,
  `aggiornato_il`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`cod_fiscale`),
  KEY `idx_runts_denominazione` (`denominazione`(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 5. Ripartizioni aggregate (precalcolate da _aggiorna_ripartizioni)
--    Una riga per (anno, categoria, regione).
--    regione = NULL → totale nazionale.
--    Popolata da db_updater.py dopo ogni aggiornamento ETL.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `ripartizioni` (
  `id`               INT           NOT NULL AUTO_INCREMENT,
  `anno`             SMALLINT      NOT NULL,
  `categoria`        VARCHAR(50)   NOT NULL,
  `regione`          VARCHAR(100)           DEFAULT NULL
                     COMMENT 'NULL = totale nazionale',
  `n_enti`           INT           NOT NULL DEFAULT 0
                     COMMENT 'nr. enti beneficiari',
  `n_contribuenti`   INT           NOT NULL DEFAULT 0
                     COMMENT 'firme (scelte espresse)',
  `importo_espresso` DECIMAL(15,2)          DEFAULT NULL,
  `importo_generico` DECIMAL(15,2)          DEFAULT NULL,
  `importo_totale`   DECIMAL(15,2)          DEFAULT NULL,
  `aggiornato_il`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                     ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rip`    (`anno`, `categoria`, `regione`),
  KEY `idx_rip_anno`     (`anno`),
  KEY `idx_rip_cat`      (`anno`, `categoria`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 6. Lead generation (email raccolta prima del download)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `leads` (
  `id`         INT          NOT NULL AUTO_INCREMENT,
  `email`      VARCHAR(255) NOT NULL,
  `nome`       VARCHAR(200)          DEFAULT NULL,
  `fonte`      VARCHAR(100)          DEFAULT 'download' COMMENT 'contesto: download, newsletter, …',
  `file_tipo`  VARCHAR(50)           DEFAULT NULL COMMENT 'csv | xlsx | report',
  `file_anno`  SMALLINT              DEFAULT NULL COMMENT 'NULL = dataset completo',
  `ip_hash`          CHAR(64)              DEFAULT NULL COMMENT 'SHA-256 IP anonimizzato (privacy)',
  `vuole_newsletter` TINYINT(1)  NOT NULL DEFAULT 0   COMMENT '1 se l''utente ha accettato aggiornamenti via email',
  `creato_il`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_email`   (`email`),
  KEY `idx_creato`  (`creato_il`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 7. Ammissioni per categoria (dati dai file per-categoria)
--    Una riga per (anno, categoria, cod_fiscale).
--    stato='ammesso' → ente nel file *_ammessi.xlsx
--    stato='escluso' → ente nel file *_esclusi.xlsx
--    Permette di rilevare: enti in più categorie, enti
--    ammessi da una categoria ma esclusi da un'altra.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `categoria_ammissioni` (
  `id`            INT           NOT NULL AUTO_INCREMENT,
  `anno`          SMALLINT      NOT NULL,
  `categoria`     VARCHAR(50)   NOT NULL  COMMENT 'slug: asd, ets_onlus, ricerca_scientifica, …',
  `cod_fiscale`   VARCHAR(20)   NOT NULL,
  `denominazione` VARCHAR(500)           DEFAULT NULL,
  `stato`         ENUM('ammesso','escluso') NOT NULL,
  `aggiornato_il` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cat_amm`       (`anno`, `categoria`, `cod_fiscale`),
  KEY `idx_ca_cf`               (`cod_fiscale`),
  KEY `idx_ca_anno_cat_stato`   (`anno`, `categoria`, `stato`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Vista: enti in più categorie per anno
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW `v_multi_categoria` AS
SELECT
  anno,
  cod_fiscale,
  MAX(denominazione)                      AS denominazione,
  COUNT(DISTINCT categoria)               AS n_categorie,
  GROUP_CONCAT(DISTINCT categoria
               ORDER BY categoria
               SEPARATOR ', ')            AS categorie
FROM `categoria_ammissioni`
WHERE stato = 'ammesso'
GROUP BY anno, cod_fiscale
HAVING COUNT(DISTINCT categoria) >= 2
ORDER BY anno DESC, n_categorie DESC;

-- ------------------------------------------------------------
-- Vista: enti ammessi in almeno una cat ed esclusi in un'altra
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW `v_conflitti_categoria` AS
SELECT
  a.anno,
  a.cod_fiscale,
  MAX(a.denominazione)                         AS denominazione,
  GROUP_CONCAT(DISTINCT a.categoria
               ORDER BY a.categoria SEPARATOR ', ') AS categorie_ammesse,
  GROUP_CONCAT(DISTINCT e.categoria
               ORDER BY e.categoria SEPARATOR ', ') AS categorie_escluse
FROM `categoria_ammissioni` a
JOIN `categoria_ammissioni` e
  ON  e.cod_fiscale = a.cod_fiscale
  AND e.anno        = a.anno
  AND e.stato       = 'escluso'
WHERE a.stato = 'ammesso'
GROUP BY a.anno, a.cod_fiscale
ORDER BY a.anno DESC, a.cod_fiscale;

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
