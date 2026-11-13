-- ============================================================================
-- Utente MySQL in sola lettura per la ricerca in linguaggio naturale (NLQ)
-- ============================================================================
--
-- DA COMPLETARE PRIMA DELL'ESECUZIONE (due valori, evidenziati con <<< >>>):
--   1. il nome del database del sito (valore di SITE_DB_NAME nel .env);
--   2. una password robusta (es. `openssl rand -base64 24` sul server).
--
-- Va eseguito con un utente amministratore MySQL, perché l'utente del database
-- creato da Plesk di solito non ha GRANT OPTION. Via SSH sul server:
--     plesk db < nlq_utente_sola_lettura.sql
-- oppure da phpMyAdmin aperto come amministratore.
--
-- Eseguirlo una volta per ciascun database: produzione e sviluppo.
-- NON usare il ruolo "Sola lettura" del pannello Plesk: concede SELECT su tutto
-- il database, compresa la tabella `leads`, e api.php in quel caso disattiva NLQ.
--
-- Poi aggiungere al .env del sito (site/public/.env):
--     NLQ_DB_USER=nlq_ro
--     NLQ_DB_PASSWORD=<la stessa password>
--
-- api.php controlla a ogni richiesta NLQ (SHOW GRANTS) che l'utente abbia
-- solo SELECT su queste quattro tabelle; altrimenti risponde 503.
-- ============================================================================

CREATE USER IF NOT EXISTS 'nlq_ro'@'localhost' IDENTIFIED BY '<<<PASSWORD>>>';

GRANT SELECT ON `<<<NOME_DB>>>`.`enti`                 TO 'nlq_ro'@'localhost';
GRANT SELECT ON `<<<NOME_DB>>>`.`categoria_ammissioni` TO 'nlq_ro'@'localhost';
GRANT SELECT ON `<<<NOME_DB>>>`.`runts`                TO 'nlq_ro'@'localhost';
GRANT SELECT ON `<<<NOME_DB>>>`.`ripartizioni`         TO 'nlq_ro'@'localhost';

-- Limiti di risorse (facoltativi, supportati da MySQL e MariaDB)
ALTER USER 'nlq_ro'@'localhost' WITH MAX_USER_CONNECTIONS 5;

FLUSH PRIVILEGES;

-- Verifica: devono comparire solo USAGE su *.* e i quattro SELECT.
SHOW GRANTS FOR 'nlq_ro'@'localhost';

-- ----------------------------------------------------------------------------
-- Controllo a posteriori (facoltativo): la cache NLQ conserva l'SQL generato.
-- Se compaiono query su tabelle diverse dalle quattro ammesse, l'esposizione
-- è già avvenuta e va valutata come possibile data breach (GDPR).
--
-- SELECT created_at, query_text, sql_generated
-- FROM `<<<NOME_DB>>>`.nlq_cache
-- WHERE sql_generated REGEXP 'leads|information_schema|nlq_|pipeline_runs|dataset_files|LOAD_FILE'
-- ORDER BY created_at DESC;
-- ----------------------------------------------------------------------------
