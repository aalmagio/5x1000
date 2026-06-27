<?php
/**
 * api.php — Backend PHP per Dati 5×1000
 * Sostituisce FastAPI. Nativo su Plesk, zero dipendenze, solo PDO + MySQL.
 *
 * Configurazione: file .env nella stessa cartella (o variabili d'ambiente):
 *   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
 *
 * Endpoint (GET):
 *   ?action=status
 *   ?action=anni
 *   ?action=categorie
 *   ?action=statistiche[&anno=YYYY]
 *   ?action=enti[&q=...][&anno=...][&categoria=...][&regione=...][&runts_only=1][&non_runts=1]
 *              [&pagina=1][&per_pagina=50][&sort=importo_totale][&asc=0]
 *   ?action=ente&cf=CODICE_FISCALE
 *   ?action=confronta&cf[]=CF1&cf[]=CF2[&cf[]=CF3...]   (max 5)
 *   ?action=cerca_cf&q=NOME_ENTE                        (ricerca CF per nome, max 20 risultati)
 *   ?action=analisi_categorie[&anno=YYYY]
 */

declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: strict-origin-when-cross-origin');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// ─── Config ────────────────────────────────────────────────────────────────

function load_env(string $dir): void {
    $f = $dir . '/.env';
    if (!is_file($f)) return;
    foreach (file($f, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') continue;
        if (!str_contains($line, '=')) continue;
        [$k, $v] = explode('=', $line, 2);
        $k = trim($k); $v = trim($v, " \t\n\r\0\x0B\"'");
        if ($k !== '' && empty($_ENV[$k])) {
            $_ENV[$k] = $v;
            putenv("$k=$v");
        }
    }
}

load_env(__DIR__);

// ─── Manutenzione ───────────────────────────────────────────────────────────
// Se la pipeline è in corso, risponde 503 per tutte le azioni tranne 'status'.
// Il percorso del lock file è configurabile tramite PIPELINE_LOCK_PATH in .env;
// default: due livelli sopra site/public/ (cioè la root del progetto).

function _maintenance_lock_path(): string {
    $from_env = getenv('PIPELINE_LOCK_PATH') ?: '';
    if ($from_env !== '') return $from_env;
    // __DIR__ = .../site/public → root = ../../
    return dirname(dirname(__DIR__)) . '/pipeline.lock';
}

function _check_manutenzione(): void {
    $action = $_GET['action'] ?? '';
    // status è sempre raggiungibile (permette al monitoraggio di sapere lo stato)
    if ($action === 'status') return;

    $path = _maintenance_lock_path();
    if (!is_file($path)) return;

    // Ignora lock più vecchi di 12 ore (safeguard per crash della pipeline)
    $age_hours = (time() - filemtime($path)) / 3600;
    if ($age_hours > 12) return;

    // Leggi il payload del lock
    $payload = @json_decode(file_get_contents($path), true) ?? [];

    http_response_code(503);
    header('Retry-After: 300');
    echo json_encode([
        'errore'       => 'Sito in manutenzione',
        'manutenzione' => true,
        'avviato_il'   => $payload['avviato_il'] ?? null,
        'anni'         => $payload['anni']        ?? [],
        'steps'        => $payload['steps']       ?? [],
        'messaggio'    => 'La pipeline di aggiornamento dati è in corso. Riprova tra qualche minuto.',
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

_check_manutenzione();

function db(): PDO {
    static $pdo = null;
    if ($pdo) return $pdo;
    // getenv() riflette putenv() (chiamato da load_env) in modo più affidabile
    // di $_ENV che può contenere stringhe vuote pre-impostate da Apache/PHP-FPM.
    $host = (getenv('SITE_DB_HOST') ?: null) ?? ($_ENV['SITE_DB_HOST'] ?? 'localhost');
    $port = (getenv('SITE_DB_PORT') ?: null) ?? ($_ENV['SITE_DB_PORT'] ?? '3306');
    $name = (getenv('SITE_DB_NAME') ?: null) ?? ($_ENV['SITE_DB_NAME'] ?? '');
    $user = (getenv('SITE_DB_USER') ?: null) ?? ($_ENV['SITE_DB_USER'] ?? '');
    $pass = (getenv('SITE_DB_PASSWORD') ?: null) ?? ($_ENV['SITE_DB_PASSWORD'] ?? '');
    $dsn  = "mysql:host=$host;port=$port;dbname=$name;charset=utf8mb4";
    $pdo  = new PDO($dsn, $user, $pass, [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::MYSQL_ATTR_INIT_COMMAND => "SET NAMES utf8mb4",
    ]);
    return $pdo;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function json_out(mixed $data, int $code = 200): never {
    http_response_code($code);
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function err(string $msg, int $code = 400): never {
    json_out(['error' => $msg], $code);
}

function int_param(string $key, int $default = 0): int {
    return isset($_GET[$key]) ? (int)$_GET[$key] : $default;
}

function str_param(string $key, string $default = ''): string {
    $val = $_POST[$key] ?? $_GET[$key] ?? null;
    return $val !== null ? trim((string)$val) : $default;
}

// ─── Actions ────────────────────────────────────────────────────────────────

function action_status(): void {
    $pdo = db();

    $anni = $pdo->query(
        "SELECT DISTINCT anno FROM enti ORDER BY anno DESC"
    )->fetchAll(PDO::FETCH_COLUMN);

    $totale = (int)$pdo->query("SELECT COUNT(*) FROM enti")->fetchColumn();

    $ultimo = $pdo->query(
        "SELECT MAX(run_at) FROM pipeline_runs WHERE status='ok'"
    )->fetchColumn();

    // Stato manutenzione
    $lock_path    = _maintenance_lock_path();
    $manutenzione = false;
    $lock_info    = null;
    if (is_file($lock_path) && (time() - filemtime($lock_path)) / 3600 <= 12) {
        $manutenzione = true;
        $lock_info    = @json_decode(file_get_contents($lock_path), true) ?? [];
    }

    json_out([
        'anni_disponibili'     => array_map('intval', $anni),
        'righe_totali'         => $totale,
        'ultimo_aggiornamento' => $ultimo,
        'manutenzione'         => $manutenzione,
        'pipeline_attiva'      => $lock_info,
    ]);
}

function action_anni(): void {
    $anni = db()->query(
        "SELECT DISTINCT anno FROM enti ORDER BY anno DESC"
    )->fetchAll(PDO::FETCH_COLUMN);
    json_out(array_map('intval', $anni));
}

function action_categorie(): void {
    $cats = db()->query(
        "SELECT DISTINCT categoria_principale
         FROM enti
         WHERE categoria_principale IS NOT NULL
         ORDER BY categoria_principale"
    )->fetchAll(PDO::FETCH_COLUMN);
    json_out($cats);
}

// ─── Normalizzazione nomi regione ────────────────────────────────────────────
// Mappa i valori raw del DB alle 20 regioni ufficiali italiane.
// Trento e Bolzano vengono entrambi raggruppati sotto "Trentino-Alto Adige".
function normalize_regione(string $raw): string {
    static $map = [
        // ── Abruzzo ──────────────────────────────────────────────────────────
        'ABRUZZO'                                => 'Abruzzo',
        // ── Basilicata ───────────────────────────────────────────────────────
        'BASILICATA'                             => 'Basilicata',
        // ── Calabria ─────────────────────────────────────────────────────────
        'CALABRIA'                               => 'Calabria',
        // ── Campania ─────────────────────────────────────────────────────────
        'CAMPANIA'                               => 'Campania',
        // ── Emilia-Romagna ───────────────────────────────────────────────────
        'EMILIA-ROMAGNA'                         => 'Emilia-Romagna',
        'EMILIA ROMAGNA'                         => 'Emilia-Romagna',
        'EMILIAROMAGNA'                          => 'Emilia-Romagna',
        'EMILIAROMAG NA'                         => 'Emilia-Romagna',
        'EMILIAROMAG'                            => 'Emilia-Romagna',
        'EMILIAROMAGN'                           => 'Emilia-Romagna',
        'EMILIAROMA GNA'                         => 'Emilia-Romagna',
        'E M ILIA ROMAGN'                        => 'Emilia-Romagna',
        // ── Friuli-Venezia Giulia ────────────────────────────────────────────
        'FRIULI-VENEZIA GIULIA'                  => 'Friuli-Venezia Giulia',
        'FRIULI VENEZIA GIULIA'                  => 'Friuli-Venezia Giulia',
        'FRIULI VENEZIA - GIULIA'                => 'Friuli-Venezia Giulia',
        'FRIULI VENEZIA G'                       => 'Friuli-Venezia Giulia',
        'FRIULI VENEZIA'                         => 'Friuli-Venezia Giulia',
        'FRIULI V.G.'                            => 'Friuli-Venezia Giulia',
        'FRIULIVENEZIA GIULIA'                   => 'Friuli-Venezia Giulia',
        'FRIULIVENEZIAG IULIA'                   => 'Friuli-Venezia Giulia',
        'FRIULIVENEZIAGI ULIA'                   => 'Friuli-Venezia Giulia',
        'FRIULIVENEZIAGIU LIA'                   => 'Friuli-Venezia Giulia',
        'FRIULIVENEZIAGIUL IA'                   => 'Friuli-Venezia Giulia',
        'FRIULIVENEZIAGIULIA'                    => 'Friuli-Venezia Giulia',
        'FRIULIVENEZIA'                          => 'Friuli-Venezia Giulia',
        'FRIULIVENEZIAG'                         => 'Friuli-Venezia Giulia',
        // ── Lazio ────────────────────────────────────────────────────────────
        'LAZIO'                                  => 'Lazio',
        // ── Liguria ──────────────────────────────────────────────────────────
        'LIGURIA'                                => 'Liguria',
        'LIGURA'                                 => 'Liguria',
        // ── Lombardia ────────────────────────────────────────────────────────
        'LOMBARDIA'                              => 'Lombardia',
        'LOMBARIA'                               => 'Lombardia',
        // ── Marche ───────────────────────────────────────────────────────────
        'MARCHE'                                 => 'Marche',
        // ── Molise ───────────────────────────────────────────────────────────
        'MOLISE'                                 => 'Molise',
        // ── Piemonte ─────────────────────────────────────────────────────────
        'PIEMONTE'                               => 'Piemonte',
        // ── Puglia ───────────────────────────────────────────────────────────
        'PUGLIA'                                 => 'Puglia',
        'PUGLIE'                                 => 'Puglia',
        // ── Sardegna ─────────────────────────────────────────────────────────
        'SARDEGNA'                               => 'Sardegna',
        // ── Sicilia ──────────────────────────────────────────────────────────
        'SICILIA'                                => 'Sicilia',
        // ── Toscana ──────────────────────────────────────────────────────────
        'TOSCANA'                                => 'Toscana',
        // ── Trentino-Alto Adige ──────────────────────────────────────────────
        'TRENTINO-ALTO ADIGE'                    => 'Trentino-Alto Adige',
        'TRENTINO ALTO ADIGE'                    => 'Trentino-Alto Adige',
        'TRENTINO ALTO ADIGE (BOLZANO)'          => 'Trentino-Alto Adige',
        'TRENTINO ALTO ADIGE (TRENTO)'           => 'Trentino-Alto Adige',
        'TRENTO'                                 => 'Trentino-Alto Adige',
        'BOLZANO'                                => 'Trentino-Alto Adige',
        'ALTO ADIGE'                             => 'Trentino-Alto Adige',
        'TAA BOLZANO'                            => 'Trentino-Alto Adige',
        'TAA TRENTO'                             => 'Trentino-Alto Adige',
        'PROVINCIA AUTONOMA DI TRENTO'           => 'Trentino-Alto Adige',
        'PROVINCIA AUTONOMA DI BOLZANO'          => 'Trentino-Alto Adige',
        'PROVINCIA AUTONOMA TRENTO'              => 'Trentino-Alto Adige',
        'PROVINCIA AUTONOMA BOLZANO'             => 'Trentino-Alto Adige',
        'P.A. TRENTO'                            => 'Trentino-Alto Adige',
        'P.A. BOLZANO'                           => 'Trentino-Alto Adige',
        // ── Umbria ───────────────────────────────────────────────────────────
        'UMBRIA'                                 => 'Umbria',
        // ── Valle d'Aosta ────────────────────────────────────────────────────
        "VALLE D'AOSTA"                          => "Valle d'Aosta",
        "VALLE D'AOSTA/VALLEE D'AOSTE"           => "Valle d'Aosta",
        "VALLED ' AOSTA"                         => "Valle d'Aosta",
        "VALLE D ' AOSTA"                        => "Valle d'Aosta",
        'VALLE'                                  => "Valle d'Aosta",
        // ── Veneto ───────────────────────────────────────────────────────────
        'VENETO'                                 => 'Veneto',
        // ── Valori non riconoscibili ─────────────────────────────────────────
        '#RIF!'                                  => 'ND',
        'ND'                                     => 'ND',
    ];

    $key = strtoupper(trim($raw));

    // Lookup diretto
    if (isset($map[$key])) return $map[$key];

    // Rimuovi caratteri non-lettera iniziali e finali poi riprova
    // Gestisce: "=- Toscana", "‐ Calabria", "Lazio -", "Veneto -", "Lombardia -"
    $clean = preg_replace(['/^[^A-Z]+/u', '/[^A-Z\')]+$/u'], '', $key);
    $clean = preg_replace('/\s+/', ' ', trim($clean));
    if ($clean !== $key && isset($map[$clean])) return $map[$clean];

    return ucwords(strtolower(trim($raw)));
}

// Dato un nome display (es. "Trentino-Alto Adige"), restituisce tutti i valori
// raw presenti nel DB che vi corrispondono (usato per il filtro WHERE ... IN).
function regione_display_to_raws(PDO $pdo, string $display): array {
    static $cache = [];
    if (!array_key_exists($display, $cache)) {
        $all_raws = $pdo->query(
            "SELECT DISTINCT regione FROM enti WHERE regione IS NOT NULL"
        )->fetchAll(PDO::FETCH_COLUMN);
        $cache[$display] = array_values(
            array_filter($all_raws, fn($r) => normalize_regione($r) === $display)
        );
    }
    return $cache[$display] ?: [$display]; // fallback al valore stesso
}

function action_regioni(): void {
    $raws = db()->query(
        "SELECT DISTINCT regione FROM enti WHERE regione IS NOT NULL"
    )->fetchAll(PDO::FETCH_COLUMN);

    // Deduplica per nome display (es. TRENTO+BOLZANO → una sola voce "Trentino-Alto Adige")
    $displays = array_values(array_unique(array_map('normalize_regione', $raws)));
    sort($displays);
    json_out($displays);
}

function action_statistiche(): void {
    $pdo  = db();
    $anno = int_param('anno');

    // Anno più recente se non specificato
    if (!$anno) {
        $anno = (int)$pdo->query(
            "SELECT MAX(anno) FROM enti"
        )->fetchColumn();
    }

    $stmt = $pdo->prepare(
        "SELECT anno, categoria,
                SUM(stato = 'ammesso')                      AS n_enti_ammessi,
                SUM(stato = 'escluso')                      AS n_enti_esclusi,
                COUNT(*)                                    AS n_enti_iscritti,
                SUM(IF(stato='ammesso', n_scelte, 0))       AS scelte_ammessi,
                SUM(IF(stato='ammesso', importo_totale, 0)) AS importo_ammessi,
                SUM(IF(stato='escluso', importo_totale, 0)) AS importo_esclusi
         FROM categoria_ammissioni
         WHERE anno = ?
         GROUP BY anno, categoria
         ORDER BY importo_ammessi DESC"
    );
    $stmt->execute([$anno]);
    $rows = $stmt->fetchAll();

    foreach ($rows as &$r) {
        $r['n_enti_ammessi']  = (int)$r['n_enti_ammessi'];
        $r['n_enti_esclusi']  = (int)$r['n_enti_esclusi'];
        $r['n_enti_iscritti'] = (int)$r['n_enti_iscritti'];
        $r['scelte_ammessi']  = (int)$r['scelte_ammessi'];
        $r['importo_ammessi'] = (float)$r['importo_ammessi'];
        $r['importo_esclusi'] = (float)$r['importo_esclusi'];
    }

    json_out(['anno' => $anno, 'per_categoria' => $rows]);
}

function action_enti(): void {
    $pdo = db();

    $q          = str_param('q');
    $anno       = int_param('anno');
    $categoria  = str_param('categoria');
    $regione    = str_param('regione');
    $provincia  = str_param('provincia');
    $runts_only = int_param('runts_only');
    $non_runts  = int_param('non_runts');
    $pagina     = max(1, int_param('pagina', 1));
    $per_pagina = min(200, max(1, int_param('per_pagina', 50)));
    $sort       = str_param('sort', 'importo_totale');
    $asc        = int_param('asc', 0);

    $allowed_sort = ['anno','denominazione','n_scelte','importo_totale','importo_espresso','regione'];
    if (!in_array($sort, $allowed_sort, true)) $sort = 'importo_totale';
    $dir = $asc ? 'ASC' : 'DESC';

    $where  = [];
    $params = [];

    if ($anno) {
        $where[] = 'e.anno = ?';
        $params[] = $anno;
    }
    if ($categoria) {
        // Usa le colonne flag per coprire enti in più categorie (es. ASD + Volontariato)
        $cat_col_map = [
            'Volontariato'        => 'e.cat_volontariato',
            'ASD'                 => 'e.cat_asd',
            'ETS/ONLUS'           => 'e.cat_ets_onlus',
            'Ricerca Scientifica' => 'e.cat_ricerca_sci',
            'Ricerca Sanitaria'   => 'e.cat_ricerca_san',
            'Comuni'              => 'e.cat_comuni',
            'Beni Culturali'      => 'e.cat_beni_cult',
            'Aree Protette'       => 'e.cat_aree_prot',
        ];
        if (isset($cat_col_map[$categoria])) {
            $where[] = $cat_col_map[$categoria] . ' = 1';
        } else {
            $where[] = 'e.categoria_principale = ?';
            $params[] = $categoria;
        }
    }
    if ($regione) {
        // $regione è il nome display normalizzato → mappiamo ai raw values del DB
        $raws = regione_display_to_raws($pdo, $regione);
        if (count($raws) === 1) {
            $where[]  = 'e.regione = ?';
            $params[] = $raws[0];
        } else {
            $ph      = implode(',', array_fill(0, count($raws), '?'));
            $where[] = "e.regione IN ($ph)";
            foreach ($raws as $rv) $params[] = $rv;
        }
    }
    if ($provincia) {
        $where[] = 'e.provincia = ?';
        $params[] = $provincia;
    }
    if ($q) {
        $q_upper = strtoupper(trim($q));
        // CF esatto: 11 cifre (aziende/PI) o 16 alfanumerici schema persona fisica
        $is_exact_cf = preg_match('/^\d{11}$/', $q_upper)
                    || preg_match('/^[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]$/', $q_upper);
        if ($is_exact_cf) {
            // Match diretto su cod_fiscale — salta FULLTEXT
            $where[]  = 'e.cod_fiscale = ?';
            $params[] = $q_upper;
        } elseif (strlen($q) >= 3) {
            // Fulltext su denominazione + LIKE su cod_fiscale
            $ft_q = '+' . implode('* +', preg_split('/\s+/', trim($q))) . '*';
            $where[] = '(MATCH(e.denominazione) AGAINST(? IN BOOLEAN MODE)'
                     . ' OR MATCH(r.denominazione) AGAINST(? IN BOOLEAN MODE)'
                     . ' OR e.cod_fiscale LIKE ?)';
            $params[] = $ft_q;
            $params[] = $ft_q;
            $params[] = '%' . $q . '%';
        } else {
            $where[] = '(e.denominazione LIKE ? OR e.cod_fiscale LIKE ? OR r.denominazione LIKE ?)';
            $params[] = '%' . $q . '%';
            $params[] = '%' . $q . '%';
            $params[] = '%' . $q . '%';
        }
    }
    if ($runts_only) {
        $where[] = 'e.runts_5x1000 = 1';
    } elseif ($non_runts) {
        $where[] = '(e.runts_5x1000 = 0 OR e.runts_5x1000 IS NULL)';
    }

    $sql_where = $where ? ('WHERE ' . implode(' AND ', $where)) : '';

    // Helper per debug SQL leggibile (sostituisce ? con i valori reali)
    $debug_sql = function(string $sql, array $p): string {
        $i = 0;
        return preg_replace_callback('/\?/', function() use ($p, &$i) {
            $v = $p[$i++] ?? 'NULL';
            return is_numeric($v) ? (string)$v : "'" . str_replace("'", "''", (string)$v) . "'";
        }, $sql);
    };

    $count_sql = "SELECT COUNT(*) FROM enti e LEFT JOIN runts r ON r.cod_fiscale = e.cod_fiscale $sql_where";

    // Conteggio totale
    $count_stmt = $pdo->prepare($count_sql);
    $count_stmt->execute($params);
    $totale = (int)$count_stmt->fetchColumn();

    $pagine = max(1, (int)ceil($totale / $per_pagina));
    $offset = ($pagina - 1) * $per_pagina;

    $data_sql = "SELECT e.anno, e.cod_fiscale,
                COALESCE(NULLIF(r.denominazione,''), e.denominazione) AS denominazione,
                e.regione, e.provincia, e.comune,
                e.categoria_principale,
                e.n_scelte, e.importo_espresso, e.importo_generico, e.importo_totale,
                e.runts_5x1000
         FROM enti e
         LEFT JOIN runts r ON r.cod_fiscale = e.cod_fiscale
         $sql_where
         ORDER BY e.$sort $dir
         LIMIT $per_pagina OFFSET $offset";

    // Dati — denominazione canonica: RUNTS se disponibile, altrimenti anno corrente
    $data_stmt = $pdo->prepare($data_sql);
    $data_stmt->execute($params);
    $rows = $data_stmt->fetchAll();

    foreach ($rows as &$r) {
        $r['anno']             = (int)$r['anno'];
        $r['n_scelte']         = $r['n_scelte'] !== null ? (int)$r['n_scelte'] : null;
        $r['importo_espresso'] = $r['importo_espresso'] !== null ? (float)$r['importo_espresso'] : null;
        $r['importo_generico'] = $r['importo_generico'] !== null ? (float)$r['importo_generico'] : null;
        $r['importo_totale']   = $r['importo_totale']   !== null ? (float)$r['importo_totale']   : null;
        $r['runts_5x1000']     = (bool)$r['runts_5x1000'];
    }

    json_out([
        'totale'     => $totale,
        'pagina'     => $pagina,
        'pagine'     => $pagine,
        'per_pagina' => $per_pagina,
        'data'       => $rows,
        'debug_sql'  => $debug_sql($count_sql, $params) . "\n\n" . $debug_sql($data_sql, $params),
    ]);
}

function action_ente(): void {
    $cf = str_param('cf');
    if (!$cf) err('Parametro cf mancante');

    $pdo  = db();
    $stmt = $pdo->prepare(
        "SELECT anno, cod_fiscale, denominazione, regione, provincia, comune,
                categoria_principale,
                cat_volontariato, cat_asd, cat_ets_onlus, cat_ricerca_sci,
                cat_ricerca_san, cat_comuni, cat_beni_cult, cat_aree_prot,
                n_scelte, importo_espresso, importo_generico, importo_totale,
                runts_denominazione, runts_sezione, runts_sede_comune, runts_sede_prov,
                runts_5x1000, runts_data_iscrizione
         FROM enti
         WHERE cod_fiscale = ?
         ORDER BY anno DESC"
    );
    $stmt->execute([$cf]);
    $rows = $stmt->fetchAll();

    if (!$rows) err('Ente non trovato', 404);

    $first = $rows[0];

    // Denominazione canonica: RUNTS se disponibile, altrimenti anno più recente
    $denom_canonica = ($first['runts_denominazione'] ?: null) ?? $first['denominazione'];

    // Mappa flag → slug categoria (stesso formato di categoria_principale)
    $cat_map = [
        'cat_volontariato' => 'volontariato',
        'cat_asd'          => 'asd',
        'cat_ets_onlus'    => 'ets_onlus',
        'cat_ricerca_sci'  => 'ricerca_scientifica',
        'cat_ricerca_san'  => 'ricerca_sanitaria',
        'cat_comuni'       => 'comuni',
        'cat_beni_cult'    => 'beni_culturali',
        'cat_aree_prot'    => 'aree_protette',
    ];

    // Raccoglie TUTTE le categorie su TUTTE le righe (sia da categoria_principale
    // sia da flag columns) — necessario per enti come AIRC che hanno una riga
    // per categoria per anno.
    $cat_set = [];
    foreach ($rows as $r) {
        if ($r['categoria_principale']) {
            $cat_set[$r['categoria_principale']] = true;
        }
        foreach ($cat_map as $col => $label) {
            if ($r[$col]) $cat_set[$label] = true;
        }
    }
    $categorie = array_keys($cat_set);

    // Raggruppa le righe per anno (possono esserci più righe per anno se l'ente
    // è presente in più categorie nello stesso anno — es. AIRC).
    $per_anno = [];
    foreach ($rows as $r) {
        $per_anno[(int)$r['anno']][] = $r;
    }
    krsort($per_anno); // anno decrescente

    // Carica il breakdown per categoria da categoria_ammissioni
    $stmt_ca = $pdo->prepare(
        "SELECT anno, categoria, n_scelte, importo_espresso, importo_generico, importo_totale
         FROM categoria_ammissioni
         WHERE cod_fiscale = ? AND stato = 'ammesso'
         ORDER BY anno DESC, importo_totale DESC"
    );
    $stmt_ca->execute([$cf]);
    $cat_per_anno = [];
    foreach ($stmt_ca->fetchAll() as $cr) {
        $cat_per_anno[(int)$cr['anno']][] = [
            'categoria'        => $cr['categoria'],
            'n_scelte'         => (int)$cr['n_scelte'],
            'importo_espresso' => (float)$cr['importo_espresso'],
            'importo_generico' => (float)$cr['importo_generico'],
            'importo_totale'   => (float)$cr['importo_totale'],
        ];
    }

    $storico = [];
    foreach ($per_anno as $anno => $anno_rows) {
        $r0          = $anno_rows[0];
        $tot_scelte  = array_sum(array_column($anno_rows, 'n_scelte'));
        $tot_esp     = array_sum(array_column($anno_rows, 'importo_espresso'));
        $tot_gen     = array_sum(array_column($anno_rows, 'importo_generico'));
        $tot_tot     = array_sum(array_column($anno_rows, 'importo_totale'));

        // Breakdown per categoria: priorità a categoria_ammissioni (più completo),
        // fallback su più righe enti nello stesso anno
        $cat_breakdown = null;
        if (isset($cat_per_anno[$anno]) && count($cat_per_anno[$anno]) > 1) {
            $cat_breakdown = $cat_per_anno[$anno];
        } elseif (count($anno_rows) > 1) {
            $cat_breakdown = array_map(fn($r) => [
                'categoria'        => $r['categoria_principale'],
                'n_scelte'         => (int)$r['n_scelte'],
                'importo_espresso' => (float)$r['importo_espresso'],
                'importo_generico' => null,
                'importo_totale'   => (float)$r['importo_totale'],
            ], $anno_rows);
        }

        $storico[] = [
            'anno'                  => $anno,
            'denominazione'         => $r0['denominazione'],
            'categoria'             => count($anno_rows) === 1 ? $r0['categoria_principale'] : null,
            'cat_breakdown'         => $cat_breakdown,
            'n_scelte'              => $tot_scelte,
            'importo_espresso'      => $tot_esp > 0 ? round($tot_esp, 2) : null,
            'importo_generico'      => $tot_gen > 0 ? round($tot_gen, 2) : null,
            'importo_totale'        => $tot_tot > 0 ? round($tot_tot, 2) : null,
            'runts_sezione'         => $r0['runts_sezione'],
            'runts_sede_comune'     => $r0['runts_sede_comune'],
            'runts_sede_prov'       => $r0['runts_sede_prov'],
            'runts_data_iscrizione' => $r0['runts_data_iscrizione'],
        ];
    }

    json_out([
        'cod_fiscale'         => $first['cod_fiscale'],
        'denominazione'       => $denom_canonica,
        'regione'             => normalize_regione($first['regione'] ?? ''),
        'provincia'           => $first['provincia'],
        'comune'              => $first['comune'],
        'categoria'           => $first['categoria_principale'],
        'categorie'           => $categorie,
        'runts_denominazione' => $first['runts_denominazione'] ?: null,
        'runts_5x1000'        => (bool)$first['runts_5x1000'],
        'anni_presenti'       => array_keys($per_anno),
        'storico'             => $storico,
    ]);
}

function action_confronta(): void {
    $cfs = $_GET['cf'] ?? [];
    if (!is_array($cfs)) $cfs = [$cfs];
    $cfs = array_values(array_filter(array_map('trim', $cfs)));

    if (count($cfs) < 1) err('Almeno un codice fiscale richiesto');
    if (count($cfs) > 5) err('Massimo 5 codici fiscali');

    $pdo = db();

    // Recupera tutti gli anni presenti nel DB
    $anni_disponibili = array_map('intval', $pdo->query(
        "SELECT DISTINCT anno FROM enti ORDER BY anno ASC"
    )->fetchAll(PDO::FETCH_COLUMN));

    $risultati = [];
    foreach ($cfs as $cf) {
        $stmt = $pdo->prepare(
            "SELECT anno, denominazione, categoria_principale,
                    n_scelte, importo_espresso, importo_generico, importo_totale,
                    regione, runts_5x1000
             FROM enti
             WHERE cod_fiscale = ?
             ORDER BY anno ASC"
        );
        $stmt->execute([$cf]);
        $rows = $stmt->fetchAll();

        if (!$rows) {
            $risultati[] = [
                'cf'            => $cf,
                'trovato'       => false,
                'denominazione' => null,
                'categoria'     => null,
                'storico'       => [],
            ];
            continue;
        }

        $storico = [];
        foreach ($rows as $r) {
            $storico[(int)$r['anno']] = [
                'n_scelte'         => $r['n_scelte'] !== null ? (int)$r['n_scelte'] : null,
                'importo_totale'   => $r['importo_totale'] !== null ? (float)$r['importo_totale'] : null,
                'importo_espresso' => $r['importo_espresso'] !== null ? (float)$r['importo_espresso'] : null,
                'importo_generico' => $r['importo_generico'] !== null ? (float)$r['importo_generico'] : null,
            ];
        }

        $totale_cumulato = array_sum(array_column($rows, 'importo_totale'));
        $max_importo_row = array_reduce($rows, fn($c, $r) => ($r['importo_totale'] > ($c['importo_totale'] ?? 0)) ? $r : $c, $rows[0]);

        $risultati[] = [
            'cf'              => $cf,
            'trovato'         => true,
            'denominazione'   => $rows[0]['denominazione'],
            'categoria'       => $rows[0]['categoria_principale'],
            'regione'         => $rows[0]['regione'],
            'runts'           => (bool)$rows[0]['runts_5x1000'],
            'anni_presenti'   => count($rows),
            'totale_cumulato' => (float)$totale_cumulato,
            'anno_migliore'   => (int)$max_importo_row['anno'],
            'storico'         => $storico,
        ];
    }

    json_out([
        'anni_disponibili' => $anni_disponibili,
        'enti'             => $risultati,
    ]);
}

function action_files(): void {
    $pdo  = db();
    $rows = $pdo->query(
        "SELECT id, anno, tipo, categoria, formato, nome_file, dimensione_mb, aggiornato_il
         FROM dataset_files
         ORDER BY anno DESC, tipo ASC"
    )->fetchAll();

    foreach ($rows as &$r) {
        $r['anno']         = $r['anno'] !== null ? (int)$r['anno'] : null;
        $r['dimensione_mb'] = (float)$r['dimensione_mb'];
    }

    json_out($rows);
}

function action_analisi_categorie(): void {
    $pdo  = db();
    $anno = int_param('anno');

    // Se anno non specificato, prendi tutti gli anni
    $anni_sql   = '';
    $anni_param = [];
    if ($anno) {
        $anni_sql   = 'WHERE anno = ?';
        $anni_param = [$anno];
    }

    // Statistiche per categoria per anno (fonte: categoria_ammissioni, con ammessi/esclusi)
    $sql = "SELECT anno, categoria,
                   SUM(stato = 'ammesso')                      AS n_enti_ammessi,
                   SUM(stato = 'escluso')                      AS n_enti_esclusi,
                   COUNT(*)                                    AS n_enti_iscritti,
                   SUM(IF(stato='ammesso', n_scelte, 0))       AS scelte_ammessi,
                   SUM(IF(stato='ammesso', importo_totale, 0)) AS importo_ammessi,
                   SUM(IF(stato='escluso', importo_totale, 0)) AS importo_esclusi
            FROM categoria_ammissioni";

    if ($anno) {
        $stmt = $pdo->prepare($sql . " WHERE anno = ? GROUP BY anno, categoria ORDER BY anno ASC, importo_ammessi DESC");
        $stmt->execute([$anno]);
    } else {
        $stmt = $pdo->query($sql . " GROUP BY anno, categoria ORDER BY anno ASC, importo_ammessi DESC");
    }

    $rows = $stmt->fetchAll();

    // Struttura: { anni: [...], categorie: [...], per_anno: { anno: { cat: {...} } } }
    $anni_set = [];
    $cat_set  = [];
    $per_anno = [];

    foreach ($rows as $r) {
        $a = (int)$r['anno'];
        $c = $r['categoria'];
        $anni_set[$a] = true;
        $cat_set[$c]  = true;
        $per_anno[$a][$c] = [
            'n_enti_ammessi'  => (int)$r['n_enti_ammessi'],
            'n_enti_esclusi'  => (int)$r['n_enti_esclusi'],
            'n_enti_iscritti' => (int)$r['n_enti_iscritti'],
            'scelte_ammessi'  => (int)$r['scelte_ammessi'],
            'importo_ammessi' => (float)$r['importo_ammessi'],
            'importo_esclusi' => (float)$r['importo_esclusi'],
        ];
    }

    $anni_list = array_keys($anni_set);
    $cat_list  = array_keys($cat_set);
    sort($anni_list);
    sort($cat_list);

    json_out([
        'anni'      => $anni_list,
        'categorie' => $cat_list,
        'per_anno'  => $per_anno,
    ]);
}

function action_cerca_cf(): void {
    $q = str_param('q');
    if (strlen($q) < 2) err('Parametro q troppo corto (min. 2 caratteri)');

    $pdo = db();

    if (strlen($q) >= 3) {
        // FULLTEXT in boolean mode con prefix match
        $ft_q = '+' . implode('* +', preg_split('/\s+/', trim($q))) . '*';
        $stmt = $pdo->prepare(
            "SELECT e.cod_fiscale,
                    COALESCE(NULLIF(r.denominazione,''), e.denominazione) AS denominazione,
                    e.regione, e.categoria_principale
             FROM enti e
             LEFT JOIN runts r ON r.cod_fiscale = e.cod_fiscale
             WHERE MATCH(e.denominazione) AGAINST(? IN BOOLEAN MODE)
                OR MATCH(r.denominazione) AGAINST(? IN BOOLEAN MODE)
                OR e.cod_fiscale LIKE ?
             GROUP BY e.cod_fiscale
             ORDER BY denominazione
             LIMIT 20"
        );
        $stmt->execute([$ft_q, $ft_q, '%' . $q . '%']);
    } else {
        $like = '%' . $q . '%';
        $stmt = $pdo->prepare(
            "SELECT e.cod_fiscale,
                    COALESCE(NULLIF(r.denominazione,''), e.denominazione) AS denominazione,
                    e.regione, e.categoria_principale
             FROM enti e
             LEFT JOIN runts r ON r.cod_fiscale = e.cod_fiscale
             WHERE e.denominazione LIKE ? OR e.cod_fiscale LIKE ? OR r.denominazione LIKE ?
             GROUP BY e.cod_fiscale
             ORDER BY denominazione
             LIMIT 20"
        );
        $stmt->execute([$like, $like, $like]);
    }
    json_out($stmt->fetchAll());
}

function action_categoria_dettaglio(): void {
    $pdo       = db();
    $categoria = str_param('categoria');
    $anno      = int_param('anno');
    $pagina    = max(1, int_param('pagina', 1));
    $per_pagina = min(200, max(1, int_param('per_pagina', 50)));

    if (!$categoria) err('Parametro categoria mancante');
    if (!$anno)      err('Parametro anno mancante');

    // Totali + per regione
    $stmt = $pdo->prepare(
        "SELECT regione,
                COUNT(*) AS n_enti,
                SUM(n_scelte)          AS totale_scelte,
                SUM(importo_espresso)  AS totale_espresso,
                SUM(importo_generico)  AS totale_generico,
                SUM(importo_totale)    AS totale_importo
         FROM enti
         WHERE anno = ? AND categoria_principale = ?
         GROUP BY regione
         ORDER BY totale_importo DESC"
    );
    $stmt->execute([$anno, $categoria]);
    $per_regione    = $stmt->fetchAll();
    $totale_enti    = 0;
    $totale_scelte  = 0;
    $totale_esp     = 0.0;
    $totale_gen     = 0.0;
    $totale_imp     = 0.0;
    foreach ($per_regione as &$r) {
        $r['n_enti']          = (int)$r['n_enti'];
        $r['totale_scelte']   = (int)$r['totale_scelte'];
        $r['totale_espresso'] = (float)$r['totale_espresso'];
        $r['totale_generico'] = (float)$r['totale_generico'];
        $r['totale_importo']  = (float)$r['totale_importo'];
        $totale_enti   += $r['n_enti'];
        $totale_scelte += $r['totale_scelte'];
        $totale_esp    += $r['totale_espresso'];
        $totale_gen    += $r['totale_generico'];
        $totale_imp    += $r['totale_importo'];
    }

    // KPI aggiuntivi: enti con 0 scelte, 0 importo
    $kpi = $pdo->prepare(
        "SELECT
            SUM(n_scelte = 0 OR n_scelte IS NULL)          AS nr_enti_0_scelte,
            SUM(importo_totale = 0 OR importo_totale IS NULL) AS nr_enti_0_importo
         FROM enti WHERE anno = ? AND categoria_principale = ?"
    );
    $kpi->execute([$anno, $categoria]);
    $kpi_row = $kpi->fetch();

    // Totale anno (tutte le categorie) per calcolare le %
    $tot_anno = $pdo->prepare(
        "SELECT SUM(n_scelte) AS tot_scelte_anno, SUM(importo_totale) AS tot_importo_anno
         FROM enti WHERE anno = ?"
    );
    $tot_anno->execute([$anno]);
    $tot_anno_row = $tot_anno->fetch();
    $tot_s_anno = (float)($tot_anno_row['tot_scelte_anno']  ?? 1);
    $tot_i_anno = (float)($tot_anno_row['tot_importo_anno'] ?? 1);

    // Calcoli derivati
    $valore_medio_espressa = ($totale_scelte > 0) ? round($totale_esp / $totale_scelte, 2) : null;
    $valore_medio_redistribuito = ($totale_enti > 0) ? round($totale_gen / $totale_enti, 2) : null;
    $perc_incidenza_generica = ($totale_imp > 0) ? round($totale_gen / $totale_imp * 100, 2) : null;
    $perc_scelte_sul_totale  = ($tot_s_anno > 0) ? round($totale_scelte / $tot_s_anno * 100, 2) : null;
    $perc_importo_sul_totale = ($tot_i_anno > 0) ? round($totale_imp / $tot_i_anno * 100, 2) : null;

    // Lista enti paginata
    $pagine = max(1, (int)ceil($totale_enti / $per_pagina));
    $offset = ($pagina - 1) * $per_pagina;
    $stmt2 = $pdo->prepare(
        "SELECT cod_fiscale, denominazione, regione, n_scelte,
                importo_espresso, importo_generico, importo_totale, runts_5x1000
         FROM enti
         WHERE anno = ? AND categoria_principale = ?
         ORDER BY importo_totale DESC
         LIMIT $per_pagina OFFSET $offset"
    );
    $stmt2->execute([$anno, $categoria]);
    $enti = $stmt2->fetchAll();
    foreach ($enti as &$e) {
        $e['n_scelte']         = $e['n_scelte'] !== null ? (int)$e['n_scelte'] : null;
        $e['importo_espresso'] = $e['importo_espresso'] !== null ? (float)$e['importo_espresso'] : null;
        $e['importo_generico'] = $e['importo_generico'] !== null ? (float)$e['importo_generico'] : null;
        $e['importo_totale']   = $e['importo_totale'] !== null ? (float)$e['importo_totale'] : null;
        $e['runts_5x1000']     = (bool)$e['runts_5x1000'];
    }

    json_out([
        'categoria'   => $categoria,
        'anno'        => $anno,
        'totali'      => [
            'n_enti'                   => $totale_enti,
            'totale_scelte'            => $totale_scelte,
            'totale_espresso'          => $totale_esp,
            'totale_generico'          => $totale_gen,
            'totale_importo'           => $totale_imp,
            'nr_enti_0_scelte'         => (int)($kpi_row['nr_enti_0_scelte'] ?? 0),
            'nr_enti_0_importo'        => (int)($kpi_row['nr_enti_0_importo'] ?? 0),
            'valore_medio_espressa'    => $valore_medio_espressa,
            'valore_medio_redistribuito' => $valore_medio_redistribuito,
            'perc_incidenza_generica'  => $perc_incidenza_generica,
            'perc_scelte_sul_totale'   => $perc_scelte_sul_totale,
            'perc_importo_sul_totale'  => $perc_importo_sul_totale,
        ],
        'per_regione' => $per_regione,
        'pagina'      => $pagina,
        'pagine'      => $pagine,
        'per_pagina'  => $per_pagina,
        'enti'        => $enti,
    ]);
}

function action_download(): void {
    set_time_limit(0);

    $tipo = str_param('tipo');  // csv | xlsx | report | scelte
    $anno = str_param('anno');  // anno numerico oppure 'completo'

    if (!in_array($tipo, ['csv', 'xlsx', 'report', 'scelte'], true)) {
        err('Tipo non valido', 400);
    }

    $pdo = db();

    // ── Pivot scelte per categoria (file multi-anno) ────────────────────────
    if ($tipo === 'scelte') {
        $stmt = $pdo->prepare(
            "SELECT percorso, nome_file FROM dataset_files
             WHERE anno IS NULL AND tipo = 'scelte' AND formato = 'xlsx' LIMIT 1"
        );
        $stmt->execute();
        $row = $stmt->fetch();
        if (!$row) err('File scelte_categorie non disponibile nel catalogo', 404);

        $path = $row['percorso'];
        $allowed_base = realpath(__DIR__ . '/../../Dati');
        $real_path    = realpath($path);
        if ($real_path === false || $allowed_base === false ||
            strncmp($real_path, $allowed_base, strlen($allowed_base)) !== 0) {
            err('File non disponibile sul server', 404);
        }
        if (!is_readable($real_path)) err('File non leggibile sul server', 500);

        header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        header('Content-Disposition: attachment; filename="scelte_categorie.xlsx"');
        header('Content-Length: ' . filesize($real_path));
        header('Cache-Control: no-store');
        while (ob_get_level()) ob_end_clean();
        $fh = fopen($real_path, 'rb');
        fpassthru($fh);
        fclose($fh);
        exit;
    }

    // ── CSV per anno: streaming filtrato dal file completo ──────────────────
    if ($tipo === 'csv' && $anno !== 'completo') {
        $anno_int = (int)$anno;
        if ($anno_int < 2006 || $anno_int > 2030) err('Anno non valido', 400);

        $stmt = $pdo->prepare(
            "SELECT percorso FROM dataset_files
             WHERE tipo = 'completo' AND formato = 'csv' LIMIT 1"
        );
        $stmt->execute();
        $row = $stmt->fetch();
        if (!$row || !file_exists($row['percorso'])) {
            err('Dataset completo non disponibile sul server', 404);
        }

        $prefix = $anno_int . ',';
        header('Content-Type: text/csv; charset=utf-8');
        header("Content-Disposition: attachment; filename=\"dati_{$anno_int}.csv\"");
        header('Cache-Control: no-store');
        header('X-Accel-Buffering: no');
        while (ob_get_level()) ob_end_clean();

        $fh = fopen($row['percorso'], 'r');
        echo fgets($fh);  // riga intestazione
        flush();
        while (($line = fgets($fh)) !== false) {
            if (str_starts_with($line, $prefix)) {
                echo $line;
                flush();
            }
        }
        fclose($fh);
        exit;
    }

    // ── File statico (xlsx, report, csv completo) ───────────────────────────
    $anno_q  = ($anno === 'completo') ? null : (int)$anno;
    $tipo_db = match($tipo) {
        'xlsx'   => 'normalizzato',
        'report' => 'report',
        'csv'    => 'completo',
    };

    if ($anno_q !== null) {
        $stmt = $pdo->prepare(
            "SELECT percorso, nome_file FROM dataset_files
             WHERE anno = ? AND tipo = ? LIMIT 1"
        );
        $stmt->execute([$anno_q, $tipo_db]);
    } else {
        $stmt = $pdo->prepare(
            "SELECT percorso, nome_file FROM dataset_files
             WHERE anno IS NULL AND tipo = ? AND formato = ? LIMIT 1"
        );
        $stmt->execute([$tipo_db, $tipo]);
    }

    $row = $stmt->fetch();
    if (!$row) err('File non trovato nel catalogo', 404);

    $path = $row['percorso'];
    // Path traversal guard: il file deve essere dentro la directory Dati/
    $allowed_base = realpath(__DIR__ . '/../../Dati');
    $real_path    = realpath($path);
    if ($real_path === false || $allowed_base === false ||
        strncmp($real_path, $allowed_base, strlen($allowed_base)) !== 0) {
        err('File non disponibile sul server', 404);
    }
    if (!is_readable($real_path)) {
        err('File non disponibile sul server', 404);
    }

    $ext  = pathinfo($path, PATHINFO_EXTENSION);
    $mime = $ext === 'csv'
        ? 'text/csv; charset=utf-8'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

    header('Content-Type: ' . $mime);
    header('Content-Disposition: attachment; filename="' . basename($row['nome_file']) . '"');
    header('Content-Length: ' . filesize($real_path));
    header('Cache-Control: no-store');
    while (ob_get_level()) ob_end_clean();
    $fh = fopen($real_path, 'rb');
    fpassthru($fh);
    fclose($fh);
    exit;
}


// ─── Inoptato ───────────────────────────────────────────────────────────────

function action_inoptato(): void {
    $pdo       = db();
    $categoria = str_param('categoria');
    $regione   = str_param('regione');
    $breakdown = str_param('breakdown'); // 'regione' | 'categoria' | ''

    $where  = [];
    $params = [];
    if ($categoria) { $where[] = 'categoria_principale = ?'; $params[] = $categoria; }
    if ($regione)   { $where[] = 'regione LIKE ?';           $params[] = '%' . $regione . '%'; }
    $sql_where = $where ? 'WHERE ' . implode(' AND ', $where) : '';

    // Storico aggregato per anno
    $stmt = $pdo->prepare(
        "SELECT anno,
                SUM(importo_espresso) AS tot_espresso,
                SUM(importo_generico) AS tot_generico,
                SUM(importo_totale)   AS tot_totale,
                SUM(n_scelte)         AS tot_scelte
         FROM enti
         $sql_where
         GROUP BY anno
         ORDER BY anno ASC"
    );
    $stmt->execute($params);
    $per_anno = [];
    foreach ($stmt->fetchAll() as $r) {
        $gen  = (float)$r['tot_generico'];
        $esp  = (float)$r['tot_espresso'];
        $tot  = (float)$r['tot_totale'];
        $sc   = (int)$r['tot_scelte'];
        $per_anno[] = [
            'anno'                  => (int)$r['anno'],
            'tot_espresso'          => $esp,
            'tot_generico'          => $gen,
            'tot_totale'            => $tot,
            'tot_scelte'            => $sc,
            'perc_generico'         => $tot > 0 ? round($gen / $tot * 100, 2) : null,
            'valore_medio_espressa' => $sc > 0 ? round($esp / $sc, 2) : null,
        ];
    }

    $out = ['per_anno' => $per_anno];

    // Breakdown per regione (anno più recente)
    if ($breakdown === 'regione') {
        $anno_max = (int)$pdo->query("SELECT MAX(anno) FROM enti")->fetchColumn();
        $w2 = ['anno = ?'];
        $p2 = [$anno_max];
        if ($categoria) { $w2[] = 'categoria_principale = ?'; $p2[] = $categoria; }
        $stmt2 = $pdo->prepare(
            "SELECT regione,
                    SUM(importo_espresso) AS tot_espresso,
                    SUM(importo_generico) AS tot_generico,
                    SUM(importo_totale)   AS tot_totale
             FROM enti
             WHERE " . implode(' AND ', $w2) . "
             GROUP BY regione
             ORDER BY tot_totale DESC"
        );
        $stmt2->execute($p2);
        $per_regione = [];
        foreach ($stmt2->fetchAll() as $r) {
            $gen = (float)$r['tot_generico'];
            $tot = (float)$r['tot_totale'];
            $per_regione[] = [
                'regione'       => $r['regione'],
                'tot_espresso'  => (float)$r['tot_espresso'],
                'tot_generico'  => $gen,
                'tot_totale'    => $tot,
                'perc_generico' => $tot > 0 ? round($gen / $tot * 100, 2) : null,
            ];
        }
        $out['anno_riferimento'] = $anno_max;
        $out['per_regione']      = $per_regione;

    // Breakdown per categoria (anno più recente)
    } elseif ($breakdown === 'categoria') {
        $anno_max = (int)$pdo->query("SELECT MAX(anno) FROM enti")->fetchColumn();
        $stmt2    = $pdo->prepare(
            "SELECT categoria_principale,
                    SUM(importo_espresso) AS tot_espresso,
                    SUM(importo_generico) AS tot_generico,
                    SUM(importo_totale)   AS tot_totale
             FROM enti
             WHERE anno = ? AND categoria_principale IS NOT NULL
             GROUP BY categoria_principale
             ORDER BY tot_totale DESC"
        );
        $stmt2->execute([$anno_max]);
        $per_cat = [];
        foreach ($stmt2->fetchAll() as $r) {
            $gen = (float)$r['tot_generico'];
            $tot = (float)$r['tot_totale'];
            $per_cat[] = [
                'categoria'     => $r['categoria_principale'],
                'tot_espresso'  => (float)$r['tot_espresso'],
                'tot_generico'  => $gen,
                'tot_totale'    => $tot,
                'perc_generico' => $tot > 0 ? round($gen / $tot * 100, 2) : null,
            ];
        }
        $out['anno_riferimento'] = $anno_max;
        $out['per_categoria']    = $per_cat;
    }

    json_out($out);
}

// ─── Lead generation ────────────────────────────────────────────────────────

function action_salva_lead(): void {
    $email            = str_param('email');
    $nome             = str_param('nome');
    $tipo             = str_param('tipo');
    $anno             = (int)str_param('anno');
    $vuole_newsletter = (int)(bool)str_param('vuole_newsletter');

    if (!$email || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
        err('Email non valida', 400);
    }

    $ip_hash = hash('sha256', $_SERVER['REMOTE_ADDR'] ?? '');
    $pdo = db();

    try {
        $stmt = $pdo->prepare(
            "INSERT INTO leads (email, nome, fonte, file_tipo, file_anno, ip_hash, vuole_newsletter)
             VALUES (?, ?, 'download', ?, ?, ?, ?)"
        );
        $stmt->execute([
            strtolower($email),
            $nome ?: null,
            $tipo ?: null,
            $anno ?: null,
            $ip_hash,
            $vuole_newsletter,
        ]);
    } catch (\Throwable $e) {
        // Tabella non ancora creata sul server: degrada silenziosamente
        error_log('[api.php] leads insert failed: ' . $e->getMessage());
    }

    json_out(['ok' => true]);
}

// ─── Classifica ─────────────────────────────────────────────────────────────

function action_classifica(): void {
    $pdo        = db();
    $anno       = int_param('anno');
    $metrica    = str_param('metrica', 'importo'); // importo | scelte
    $tipo       = str_param('tipo',    'top');      // top | crescita | calo | newcomer
    $categoria  = str_param('categoria');
    $regione    = str_param('regione');
    $per_pagina = min(100, max(1, int_param('per_pagina', 25)));

    if (!$anno) {
        $anno = (int)$pdo->query("SELECT MAX(anno) FROM enti")->fetchColumn();
    }
    $anno_prec = $anno - 1;
    $col = $metrica === 'scelte' ? 'n_scelte' : 'importo_totale';

    // Filtri opzionali (oltre anno)
    $cond    = [];
    $cparams = [];
    if ($categoria) { $cond[] = 'e.categoria_principale = ?'; $cparams[] = $categoria; }
    if ($regione)   { $cond[] = 'e.regione = ?';              $cparams[] = $regione; }
    $extra = $cond ? 'AND ' . implode(' AND ', $cond) : '';

    if ($tipo === 'top') {
        $params = array_merge([$anno], $cparams);
        $stmt   = $pdo->prepare("
            SELECT e.cod_fiscale,
                   COALESCE(NULLIF(r.denominazione,''), e.denominazione) AS denominazione,
                   e.regione, e.categoria_principale, e.n_scelte, e.importo_totale
            FROM enti e LEFT JOIN runts r ON r.cod_fiscale = e.cod_fiscale
            WHERE e.anno = ? $extra AND e.$col > 0
            ORDER BY e.$col DESC LIMIT $per_pagina");
        $stmt->execute($params);

    } elseif ($tipo === 'crescita' || $tipo === 'calo') {
        $order  = $tipo === 'crescita' ? 'DESC' : 'ASC';
        $extra_p = str_replace('e.', 'p.', $extra);
        $params  = array_merge([$anno_prec, $anno], $cparams);
        $stmt    = $pdo->prepare("
            SELECT e.cod_fiscale,
                   COALESCE(NULLIF(r.denominazione,''), e.denominazione) AS denominazione,
                   e.regione, e.categoria_principale,
                   e.n_scelte AS scelte_cur,   e.importo_totale AS importo_cur,
                   p.n_scelte AS scelte_prec,  p.importo_totale AS importo_prec,
                   ROUND((e.$col - p.$col) / NULLIF(p.$col, 0) * 100, 1) AS perc_var,
                   (e.$col - p.$col) AS var_assoluta
            FROM enti e
            JOIN enti p ON p.cod_fiscale = e.cod_fiscale AND p.anno = ?
            LEFT JOIN runts r ON r.cod_fiscale = e.cod_fiscale
            WHERE e.anno = ? $extra AND e.$col > 0 AND p.$col > 0
            ORDER BY perc_var $order LIMIT $per_pagina");
        $stmt->execute($params);

    } elseif ($tipo === 'newcomer') {
        $params = array_merge([$anno], $cparams, [$anno_prec]);
        $stmt   = $pdo->prepare("
            SELECT e.cod_fiscale,
                   COALESCE(NULLIF(r.denominazione,''), e.denominazione) AS denominazione,
                   e.regione, e.categoria_principale, e.n_scelte, e.importo_totale
            FROM enti e LEFT JOIN runts r ON r.cod_fiscale = e.cod_fiscale
            WHERE e.anno = ? $extra AND e.n_scelte > 0
              AND NOT EXISTS (
                SELECT 1 FROM enti p WHERE p.cod_fiscale = e.cod_fiscale AND p.anno = ?
              )
            ORDER BY e.$col DESC LIMIT $per_pagina");
        $stmt->execute($params);

    } else {
        err('tipo non valido: top | crescita | calo | newcomer');
    }

    $rows = $stmt->fetchAll();
    foreach ($rows as $i => &$row) {
        $row['rank'] = $i + 1;
        // Normalizza tipi
        foreach (['n_scelte','scelte_cur','scelte_prec'] as $k) {
            if (array_key_exists($k, $row))
                $row[$k] = $row[$k] !== null ? (int)$row[$k] : null;
        }
        foreach (['importo_totale','importo_cur','importo_prec','perc_var','var_assoluta'] as $k) {
            if (array_key_exists($k, $row))
                $row[$k] = $row[$k] !== null ? (float)$row[$k] : null;
        }
    }

    json_out([
        'anno'      => $anno,
        'anno_prec' => $anno_prec,
        'tipo'      => $tipo,
        'metrica'   => $metrica,
        'enti'      => $rows,
    ]);
}

function action_province(): void {
    $regione = str_param('regione');
    $pdo     = db();
    if ($regione) {
        $stmt = $pdo->prepare(
            "SELECT DISTINCT provincia FROM enti
             WHERE regione = ? AND provincia IS NOT NULL AND provincia != ''
             ORDER BY provincia"
        );
        $stmt->execute([$regione]);
    } else {
        $stmt = $pdo->query(
            "SELECT DISTINCT provincia FROM enti
             WHERE provincia IS NOT NULL AND provincia != ''
             ORDER BY provincia"
        );
    }
    json_out($stmt->fetchAll(PDO::FETCH_COLUMN));
}

// ─── Forecast ───────────────────────────────────────────────────────────────

function action_forecast(): void {
    $path = __DIR__ . '/data/forecast.json';
    if (!file_exists($path)) {
        err('Dati forecast non disponibili. Eseguire forecast.py per generarli.', 404);
    }
    $json = file_get_contents($path);
    if ($json === false) err('Errore lettura dati forecast', 500);
    // Re-emit as JSON (avoid double encoding)
    http_response_code(200);
    echo $json;
    exit;
}

// ─── Ripartizioni ────────────────────────────────────────────────────────────
// Restituisce i dati pre-aggregati dalla tabella ripartizioni.
//
// ?action=ripartizioni
//   &anno=YYYY           filtra per anno (opzionale; default: anno più recente)
//   &categoria=NomeCAT   filtra per categoria (opzionale)
//   &regione=NomeREG     filtra per regione display (opzionale; NULL = nazionale)
//   &breakdown=regione   aggiunge dettaglio per regione
//   &breakdown=anno      serie storica (tutti gli anni)
//   &breakdown=categoria distribuzione tra categorie per l'anno scelto

function action_ripartizioni(): void {
    $pdo       = db();
    $anno      = int_param('anno');
    $categoria = str_param('categoria');
    $regione   = str_param('regione');    // nome display normalizzato
    $breakdown = str_param('breakdown');  // 'regione' | 'anno' | 'categoria' | ''

    // Anno default: il più recente disponibile
    if (!$anno && $breakdown !== 'anno') {
        $anno = (int)$pdo->query("SELECT MAX(anno) FROM ripartizioni")->fetchColumn();
        if (!$anno) {
            // Tabella vuota: fallback su enti
            $anno = (int)$pdo->query("SELECT MAX(anno) FROM enti")->fetchColumn();
        }
    }

    $where  = [];
    $params = [];

    if ($anno && $breakdown !== 'anno') {
        $where[]  = 'anno = ?';
        $params[] = $anno;
    }
    if ($categoria) {
        $where[]  = 'categoria = ?';
        $params[] = $categoria;
    }
    if ($regione !== '') {
        // '' = tutti; NULL esplicito = solo nazionali
        if ($regione === 'nazionale' || $regione === 'null') {
            $where[] = 'regione IS NULL';
        } else {
            $where[]  = 'regione = ?';
            $params[] = $regione;
        }
    }
    $sql_where = $where ? ('WHERE ' . implode(' AND ', $where)) : '';

    // ── Breakdown per regione ────────────────────────────────────────────────
    if ($breakdown === 'regione') {
        $sql = "SELECT regione, categoria, anno,
                       n_enti, n_contribuenti,
                       importo_espresso, importo_generico, importo_totale
                FROM ripartizioni
                $sql_where AND regione IS NOT NULL
                ORDER BY importo_totale DESC";
        // aggiunge AND manualmente se sql_where è vuoto
        if (!$where) {
            $sql = str_replace('$sql_where AND', 'WHERE', $sql);
            $sql = "SELECT regione, categoria, anno,
                           n_enti, n_contribuenti,
                           importo_espresso, importo_generico, importo_totale
                    FROM ripartizioni
                    WHERE regione IS NOT NULL
                    ORDER BY importo_totale DESC";
        } else {
            $sql = "SELECT regione, categoria, anno,
                           n_enti, n_contribuenti,
                           importo_espresso, importo_generico, importo_totale
                    FROM ripartizioni
                    $sql_where AND regione IS NOT NULL
                    ORDER BY importo_totale DESC";
        }
        $stmt = $pdo->prepare($sql);
        $stmt->execute($params);
        $rows = $stmt->fetchAll();
        _cast_ripartizioni($rows);
        json_out(['anno' => $anno, 'per_regione' => $rows]);
        return;
    }

    // ── Serie storica (breakdown=anno) ───────────────────────────────────────
    if ($breakdown === 'anno') {
        $where2  = ['regione IS NULL'];  // totali nazionali
        $params2 = [];
        if ($categoria) { $where2[] = 'categoria = ?'; $params2[] = $categoria; }
        $sql2 = "SELECT anno, categoria,
                        n_enti, n_contribuenti,
                        importo_espresso, importo_generico, importo_totale
                 FROM ripartizioni
                 WHERE " . implode(' AND ', $where2) . "
                 ORDER BY anno ASC, importo_totale DESC";
        $stmt2 = $pdo->prepare($sql2);
        $stmt2->execute($params2);
        $rows2 = $stmt2->fetchAll();
        _cast_ripartizioni($rows2);
        json_out(['serie_storica' => $rows2]);
        return;
    }

    // ── Default: distribuzione per categoria (nazionali, anno scelto) ────────
    $w_naz  = array_merge($where, ['regione IS NULL']);
    $sql_d  = "SELECT categoria, anno,
                      n_enti, n_contribuenti,
                      importo_espresso, importo_generico, importo_totale
               FROM ripartizioni
               WHERE " . implode(' AND ', $w_naz) . "
               ORDER BY importo_totale DESC";
    $stmt_d = $pdo->prepare($sql_d);
    $stmt_d->execute($params);
    $rows_d = $stmt_d->fetchAll();
    _cast_ripartizioni($rows_d);

    // Totale dell'anno per calcolo percentuali
    $totale_anno = array_sum(array_column($rows_d, 'importo_totale'));
    foreach ($rows_d as &$r) {
        $r['perc_importo'] = $totale_anno > 0
            ? round($r['importo_totale'] / $totale_anno * 100, 2)
            : null;
    }

    json_out(['anno' => $anno, 'per_categoria' => $rows_d, 'totale' => $totale_anno]);
}

function _cast_ripartizioni(array &$rows): void {
    foreach ($rows as &$r) {
        $r['anno']             = (int)$r['anno'];
        $r['n_enti']           = (int)$r['n_enti'];
        $r['n_contribuenti']   = (int)$r['n_contribuenti'];
        $r['importo_espresso'] = $r['importo_espresso'] !== null ? (float)$r['importo_espresso'] : null;
        $r['importo_generico'] = $r['importo_generico'] !== null ? (float)$r['importo_generico'] : null;
        $r['importo_totale']   = $r['importo_totale']   !== null ? (float)$r['importo_totale']   : null;
    }
}

// ─── Endpoint: enti ammessi in più categorie ─────────────────────────────────
/**
 * ?action=multi_categoria[&anno=YYYY][&min_categorie=2][&pagina=1][&per_pagina=50]
 *
 * Restituisce enti presenti (come ammessi) in almeno min_categorie categorie distinte,
 * usando la tabella categoria_ammissioni.
 */
function action_multi_categoria(): void {
    $pdo           = db();
    $anno          = int_param('anno');
    $min_cat       = max(2, int_param('min_categorie', 2));
    $pagina        = max(1, int_param('pagina', 1));
    $per_pagina    = min(200, max(1, int_param('per_pagina', 50)));
    $offset        = ($pagina - 1) * $per_pagina;

    $where  = $anno ? 'AND ca.anno = ?' : '';
    $params = $anno ? [$anno] : [];

    // Totale righe
    $sql_count = "
        SELECT COUNT(*) FROM (
            SELECT ca.cod_fiscale
            FROM categoria_ammissioni ca
            WHERE ca.stato = 'ammesso' $where
            GROUP BY ca.anno, ca.cod_fiscale
            HAVING COUNT(DISTINCT ca.categoria) >= $min_cat
        ) sub";
    $totale = (int)$pdo->prepare($sql_count) ? 0 : 0;
    $stmt_c = $pdo->prepare($sql_count);
    $stmt_c->execute($params);
    $totale = (int)$stmt_c->fetchColumn();

    // Dati paginati — arricchiti con importo da enti se disponibile
    $params_pag = array_merge($params, [$per_pagina, $offset]);
    $stmt = $pdo->prepare("
        SELECT
            ca.anno,
            ca.cod_fiscale,
            MAX(ca.denominazione)                      AS denominazione,
            COUNT(DISTINCT ca.categoria)               AS n_categorie,
            GROUP_CONCAT(DISTINCT ca.categoria
                         ORDER BY ca.categoria
                         SEPARATOR ', ')               AS categorie,
            e.importo_totale,
            e.n_scelte,
            e.regione
        FROM categoria_ammissioni ca
        LEFT JOIN enti e
          ON e.cod_fiscale = ca.cod_fiscale
         AND e.anno        = ca.anno
        WHERE ca.stato = 'ammesso' $where
        GROUP BY ca.anno, ca.cod_fiscale, e.importo_totale, e.n_scelte, e.regione
        HAVING COUNT(DISTINCT ca.categoria) >= $min_cat
        ORDER BY ca.anno DESC, n_categorie DESC, e.importo_totale DESC
        LIMIT ? OFFSET ?
    ");
    $stmt->execute($params_pag);
    $rows = $stmt->fetchAll();

    foreach ($rows as &$r) {
        $r['anno']           = (int)$r['anno'];
        $r['n_categorie']    = (int)$r['n_categorie'];
        $r['importo_totale'] = $r['importo_totale'] !== null ? (float)$r['importo_totale'] : null;
        $r['n_scelte']       = $r['n_scelte'] !== null ? (int)$r['n_scelte'] : null;
    }
    unset($r);

    json_out([
        'totale'      => $totale,
        'pagina'      => $pagina,
        'per_pagina'  => $per_pagina,
        'min_categorie' => $min_cat,
        'risultati'   => $rows,
    ]);
}


// ─── Endpoint: composizione importo per categoria ────────────────────────────
/**
 * ?action=composizione_categorie[&anno=YYYY]
 *
 * Restituisce il breakdown dell'importo totale per categoria (dati dalla
 * tabella ripartizioni, regione=NULL = totale nazionale).
 * Se non ci sono dati in ripartizioni, deriva da categoria_ammissioni + enti.
 */
function action_composizione_categorie(): void {
    $pdo  = db();
    $anno = int_param('anno');

    // Prima tenta dalla tabella ripartizioni (dati precalcolati)
    if ($anno) {
        $stmt = $pdo->prepare("
            SELECT categoria, n_enti, n_contribuenti,
                   importo_espresso, importo_generico, importo_totale
            FROM ripartizioni
            WHERE anno = ? AND regione IS NULL
            ORDER BY importo_totale DESC
        ");
        $stmt->execute([$anno]);
    } else {
        $stmt = $pdo->query("
            SELECT anno, categoria, n_enti, n_contribuenti,
                   importo_espresso, importo_generico, importo_totale
            FROM ripartizioni
            WHERE regione IS NULL
            ORDER BY anno DESC, importo_totale DESC
        ");
    }
    $rows = $stmt->fetchAll();

    // Se ripartizioni è vuota, usa categoria_ammissioni + enti come fallback
    if (empty($rows)) {
        $where  = $anno ? 'WHERE ca.anno = ?' : '';
        $params = $anno ? [$anno] : [];
        $stmt2  = $pdo->prepare("
            SELECT
                ca.anno,
                ca.categoria,
                COUNT(DISTINCT ca.cod_fiscale)     AS n_enti,
                COALESCE(SUM(e.n_scelte),0)        AS n_contribuenti,
                COALESCE(SUM(e.importo_espresso),0) AS importo_espresso,
                COALESCE(SUM(e.importo_generico),0) AS importo_generico,
                COALESCE(SUM(e.importo_totale),0)   AS importo_totale
            FROM categoria_ammissioni ca
            LEFT JOIN enti e
              ON e.cod_fiscale = ca.cod_fiscale AND e.anno = ca.anno
            WHERE ca.stato = 'ammesso' $where
            GROUP BY ca.anno, ca.categoria
            ORDER BY ca.anno DESC, importo_totale DESC
        ");
        $stmt2->execute($params);
        $rows = $stmt2->fetchAll();
    }

    foreach ($rows as &$r) {
        if (isset($r['anno'])) $r['anno'] = (int)$r['anno'];
        $r['n_enti']           = (int)$r['n_enti'];
        $r['n_contribuenti']   = (int)$r['n_contribuenti'];
        $r['importo_espresso'] = (float)$r['importo_espresso'];
        $r['importo_generico'] = (float)$r['importo_generico'];
        $r['importo_totale']   = (float)$r['importo_totale'];
    }
    unset($r);

    // Se anno specificato, calcola anche la percentuale sul totale
    if ($anno && !empty($rows)) {
        $tot = array_sum(array_column($rows, 'importo_totale'));
        foreach ($rows as &$r) {
            $r['perc_importo'] = $tot > 0 ? round($r['importo_totale'] / $tot * 100, 2) : 0;
        }
        unset($r);
    }

    json_out([
        'anno'        => $anno ?: null,
        'categorie'   => $rows,
    ]);
}


// ─── Endpoint: conflitti (ammesso in una cat, escluso in un'altra) ────────────
/**
 * ?action=conflitti_categoria[&anno=YYYY][&pagina=1][&per_pagina=50]
 *
 * Restituisce enti ammessi in almeno una categoria ma esclusi in almeno
 * un'altra nello stesso anno (es. AIRC ammessa ricerca_sanitaria ma esclusa
 * da ets_onlus).
 */
function action_conflitti_categoria(): void {
    $pdo        = db();
    $anno       = int_param('anno');
    $pagina     = max(1, int_param('pagina', 1));
    $per_pagina = min(200, max(1, int_param('per_pagina', 50)));
    $offset     = ($pagina - 1) * $per_pagina;

    $where  = $anno ? 'AND a.anno = ?' : '';
    $params = $anno ? [$anno] : [];

    $sql_count = "
        SELECT COUNT(*) FROM (
            SELECT a.cod_fiscale, a.anno
            FROM categoria_ammissioni a
            JOIN categoria_ammissioni e
              ON  e.cod_fiscale = a.cod_fiscale
              AND e.anno        = a.anno
              AND e.stato       = 'escluso'
            WHERE a.stato = 'ammesso' $where
            GROUP BY a.anno, a.cod_fiscale
        ) sub";
    $stmt_c = $pdo->prepare($sql_count);
    $stmt_c->execute($params);
    $totale = (int)$stmt_c->fetchColumn();

    $params_pag = array_merge($params, [$per_pagina, $offset]);
    $stmt = $pdo->prepare("
        SELECT
            a.anno,
            a.cod_fiscale,
            MAX(a.denominazione)                           AS denominazione,
            GROUP_CONCAT(DISTINCT a.categoria
                         ORDER BY a.categoria SEPARATOR ', ') AS categorie_ammesse,
            GROUP_CONCAT(DISTINCT e.categoria
                         ORDER BY e.categoria SEPARATOR ', ') AS categorie_escluse,
            ent.importo_totale,
            ent.regione
        FROM categoria_ammissioni a
        JOIN categoria_ammissioni e
          ON  e.cod_fiscale = a.cod_fiscale
          AND e.anno        = a.anno
          AND e.stato       = 'escluso'
        LEFT JOIN enti ent
          ON  ent.cod_fiscale = a.cod_fiscale
          AND ent.anno        = a.anno
        WHERE a.stato = 'ammesso' $where
        GROUP BY a.anno, a.cod_fiscale, ent.importo_totale, ent.regione
        ORDER BY a.anno DESC, a.cod_fiscale
        LIMIT ? OFFSET ?
    ");
    $stmt->execute($params_pag);
    $rows = $stmt->fetchAll();

    foreach ($rows as &$r) {
        $r['anno']           = (int)$r['anno'];
        $r['importo_totale'] = $r['importo_totale'] !== null ? (float)$r['importo_totale'] : null;
    }
    unset($r);

    json_out([
        'totale'     => $totale,
        'pagina'     => $pagina,
        'per_pagina' => $per_pagina,
        'risultati'  => $rows,
    ]);
}


// ─── Geo: aggregati per regione / provincia / comune ─────────────────────────
/**
 * ?action=geo[&anno=YYYY][&categoria=CAT]
 *   → { anno, totale: {n_enti,n_scelte,importo_totale}, per_regione: [...] }
 *
 * ?action=geo&regione=NOME_DISPLAY[&anno=YYYY][&categoria=CAT]
 *   → { anno, regione, per_provincia: [{provincia, n_enti, n_scelte, importo_totale}] }
 *
 * ?action=geo&provincia=SIGLA[&anno=YYYY][&categoria=CAT]
 *   → { anno, provincia, per_comune: [{comune, n_enti, n_scelte, importo_totale}] }
 */
function action_geo(): void {
    $pdo       = db();
    $anno      = int_param('anno');
    $regione   = str_param('regione');   // nome display normalizzato
    $provincia = str_param('provincia'); // sigla 2/3 char
    $categoria = str_param('categoria');

    if (!$anno) {
        $anno = (int)$pdo->query("SELECT MAX(anno) FROM enti")->fetchColumn();
    }

    $cond   = ['e.anno = ?'];
    $params = [$anno];
    if ($categoria) {
        $cond[]   = 'e.categoria_principale = ?';
        $params[] = $categoria;
    }

    // ── Livello comune ───────────────────────────────────────────────────────
    if ($provincia) {
        $cond[]   = 'e.provincia = ?';
        $params[] = strtoupper($provincia);
        $stmt = $pdo->prepare(
            "SELECT e.comune,
                    COUNT(*) AS n_enti,
                    SUM(e.n_scelte) AS n_scelte,
                    SUM(e.importo_totale) AS importo_totale
             FROM enti e
             WHERE " . implode(' AND ', $cond) . "
               AND e.comune IS NOT NULL AND e.comune != ''
             GROUP BY e.comune
             ORDER BY importo_totale DESC"
        );
        $stmt->execute($params);
        $rows = $stmt->fetchAll();
        foreach ($rows as &$r) {
            $r['n_enti']         = (int)$r['n_enti'];
            $r['n_scelte']       = (int)($r['n_scelte'] ?? 0);
            $r['importo_totale'] = (float)($r['importo_totale'] ?? 0);
        }
        json_out(['anno' => $anno, 'provincia' => strtoupper($provincia), 'per_comune' => $rows]);
        return;
    }

    // ── Livello provincia ────────────────────────────────────────────────────
    if ($regione) {
        $raw_regioni = regione_display_to_raws($pdo, $regione);
        if (!$raw_regioni) {
            json_out(['anno' => $anno, 'regione' => $regione, 'per_provincia' => []]);
            return;
        }
        $ph      = implode(',', array_fill(0, count($raw_regioni), '?'));
        $cond[]  = "e.regione IN ($ph)";
        $params  = array_merge($params, $raw_regioni);
        $stmt = $pdo->prepare(
            "SELECT e.provincia,
                    COUNT(*) AS n_enti,
                    SUM(e.n_scelte) AS n_scelte,
                    SUM(e.importo_totale) AS importo_totale
             FROM enti e
             WHERE " . implode(' AND ', $cond) . "
               AND e.provincia IS NOT NULL AND e.provincia != ''
             GROUP BY e.provincia
             ORDER BY importo_totale DESC"
        );
        $stmt->execute($params);
        $rows = $stmt->fetchAll();
        foreach ($rows as &$r) {
            $r['n_enti']         = (int)$r['n_enti'];
            $r['n_scelte']       = (int)($r['n_scelte'] ?? 0);
            $r['importo_totale'] = (float)($r['importo_totale'] ?? 0);
        }
        json_out(['anno' => $anno, 'regione' => $regione, 'per_provincia' => $rows]);
        return;
    }

    // ── Livello regione (top level) ──────────────────────────────────────────
    $stmt = $pdo->prepare(
        "SELECT e.regione,
                COUNT(*) AS n_enti,
                SUM(e.n_scelte) AS n_scelte,
                SUM(e.importo_totale) AS importo_totale
         FROM enti e
         WHERE " . implode(' AND ', $cond) . "
         GROUP BY e.regione
         ORDER BY importo_totale DESC"
    );
    $stmt->execute($params);
    $raw_rows = $stmt->fetchAll();

    // Aggrega per nome display normalizzato (es. TRENTO+BOLZANO → Trentino-Alto Adige)
    $agg = [];
    foreach ($raw_rows as $r) {
        $disp = normalize_regione($r['regione'] ?? '');
        if (!isset($agg[$disp])) {
            $agg[$disp] = ['regione' => $disp, 'n_enti' => 0, 'n_scelte' => 0, 'importo_totale' => 0.0];
        }
        $agg[$disp]['n_enti']         += (int)$r['n_enti'];
        $agg[$disp]['n_scelte']       += (int)($r['n_scelte'] ?? 0);
        $agg[$disp]['importo_totale'] += (float)($r['importo_totale'] ?? 0);
    }
    $per_regione = array_values($agg);
    usort($per_regione, fn($a, $b) => $b['importo_totale'] <=> $a['importo_totale']);

    $totale_enti    = array_sum(array_column($per_regione, 'n_enti'));
    $totale_scelte  = array_sum(array_column($per_regione, 'n_scelte'));
    $totale_importo = array_sum(array_column($per_regione, 'importo_totale'));
    foreach ($per_regione as &$r) {
        $r['perc_importo'] = $totale_importo > 0
            ? round($r['importo_totale'] / $totale_importo * 100, 2)
            : 0.0;
    }

    json_out([
        'anno'        => $anno,
        'totale'      => [
            'n_enti'         => $totale_enti,
            'n_scelte'       => $totale_scelte,
            'importo_totale' => $totale_importo,
        ],
        'per_regione' => $per_regione,
    ]);
}


// ─── NLQ: Natural Language Query ─────────────────────────────────────────────
//
// Endpoint semi-protetto: richiede un token HMAC giornaliero (da nlq_token)
// + rate limiting per IP. La domanda in italiano viene tradotta in SQL da
// Ollama (modello locale, porta 11434) ed eseguita in sola lettura sul DB.
//
// Configurazione nel .env:
//   NLQ_SECRET=<stringa-segreta>        obbligatorio per abilitare NLQ
//   OLLAMA_URL=http://127.0.0.1:11434   default
//   OLLAMA_MODEL=qwen2.5-coder:7b       default
//   NLQ_MAX_PER_HOUR=20                 default
//   NLQ_CACHE_TTL=86400                 secondi (default 24h)

function _nlq_secret(): string {
    $s = getenv('NLQ_SECRET') ?: '';
    if ($s === '') throw new \RuntimeException('NLQ_SECRET non configurato nel .env');
    return $s;
}

function _nlq_token_today(): string {
    return hash_hmac('sha256', date('Y-m-d'), _nlq_secret());
}

function action_nlq_token(): void {
    try {
        $token = _nlq_token_today();
    } catch (\RuntimeException) {
        err('NLQ non abilitato su questo server (NLQ_SECRET mancante nel .env)', 503);
    }
    json_out([
        'token'       => $token,
        'valid_until' => date('Y-m-d') . ' 23:59:59',
    ]);
}

function _nlq_check_rate_limit(string $ip_hash): void {
    $max = (int)(getenv('NLQ_MAX_PER_HOUR') ?: 20);
    $pdo = db();

    if (mt_rand(1, 100) === 1) {
        try {
            $pdo->exec("DELETE FROM nlq_rate_limit WHERE ts < DATE_SUB(NOW(), INTERVAL 2 HOUR)");
        } catch (\Throwable) {}
    }

    $stmt = $pdo->prepare(
        "SELECT COUNT(*) FROM nlq_rate_limit
         WHERE ip_hash = ? AND ts > DATE_SUB(NOW(), INTERVAL 1 HOUR)"
    );
    $stmt->execute([$ip_hash]);
    if ((int)$stmt->fetchColumn() >= $max) {
        err("Limite raggiunto: massimo $max query/ora per IP. Riprova tra poco.", 429);
    }

    $pdo->prepare("INSERT INTO nlq_rate_limit (ip_hash) VALUES (?)")->execute([$ip_hash]);
}

function _nlq_cache_get(string $hash): ?array {
    try {
        $stmt = db()->prepare(
            "SELECT result_json FROM nlq_cache WHERE query_hash = ? AND expires_at > NOW()"
        );
        $stmt->execute([$hash]);
        $row = $stmt->fetch();
        if (!$row) return null;
        db()->prepare("UPDATE nlq_cache SET hits = hits + 1 WHERE query_hash = ?")
             ->execute([$hash]);
        return json_decode($row['result_json'], true);
    } catch (\Throwable) {
        return null;
    }
}

function _nlq_cache_set(string $hash, string $domanda, string $sql, array $result): void {
    $ttl = (int)(getenv('NLQ_CACHE_TTL') ?: 86400);
    try {
        db()->prepare(
            "INSERT INTO nlq_cache (query_hash, query_text, sql_generated, result_json, expires_at)
             VALUES (?, ?, ?, ?, DATE_ADD(NOW(), INTERVAL ? SECOND))
             ON DUPLICATE KEY UPDATE
               result_json   = VALUES(result_json),
               sql_generated = VALUES(sql_generated),
               expires_at    = VALUES(expires_at),
               hits          = hits + 1"
        )->execute([$hash, $domanda, $sql, json_encode($result, JSON_UNESCAPED_UNICODE), $ttl]);
    } catch (\Throwable) {}
}

function _nlq_call_ollama(string $domanda): string {
    $base  = rtrim(getenv('OLLAMA_URL') ?: 'http://127.0.0.1:11434', '/');
    $model = getenv('OLLAMA_MODEL') ?: 'qwen2.5-coder:7b';

    $schema = <<<'SCHEMA'
DATABASE MySQL — 5x1000 italiano (contributo 5 per mille IRPEF)

TABLE enti  (~1M righe, una riga per anno per ente)
  anno               SMALLINT         -- es: 2006 … 2025
  cod_fiscale        VARCHAR(20)      -- codice fiscale dell'ente
  denominazione      VARCHAR(500)     -- nome ente (MAIUSCOLO nel DB)
  regione            VARCHAR(100)     -- MAIUSCOLO: 'LOMBARDIA','TOSCANA','LAZIO','CAMPANIA'…
  provincia          CHAR(3)          -- sigla: 'MI','RM','TO','NA','BO'…
  comune             VARCHAR(200)
  categoria_principale VARCHAR(50)    -- 'volontariato','asd','ets_onlus','ricerca_scientifica',
                                      --  'ricerca_sanitaria','comuni','beni_culturali','aree_protette'
  cat_volontariato   TINYINT(1)       -- 1 se ente appartiene a questa categoria
  cat_asd            TINYINT(1)
  cat_ets_onlus      TINYINT(1)
  cat_ricerca_sci    TINYINT(1)
  cat_ricerca_san    TINYINT(1)
  cat_comuni         TINYINT(1)
  cat_beni_cult      TINYINT(1)
  cat_aree_prot      TINYINT(1)
  n_scelte           INT              -- scelte espresse dai contribuenti
  importo_espresso   DECIMAL(15,2)    -- importo da scelte dirette (EUR)
  importo_generico   DECIMAL(15,2)    -- importo da scelte generiche/inoptato (EUR)
  importo_totale     DECIMAL(15,2)    -- importo totale ricevuto (EUR)
  runts_5x1000       TINYINT(1)       -- 1 se iscritto al RUNTS

TABLE categoria_ammissioni  (stato ammissione per categoria per anno)
  anno               SMALLINT
  cod_fiscale        VARCHAR(20)
  denominazione      VARCHAR(500)
  categoria          VARCHAR(50)
  stato              ENUM('ammesso','escluso')
  n_scelte           INT
  importo_espresso   DECIMAL(15,2)
  importo_generico   DECIMAL(15,2)
  importo_totale     DECIMAL(15,2)

TABLE runts  (Registro Unico Terzo Settore)
  cod_fiscale        VARCHAR(20)
  denominazione      VARCHAR(500)
  sezione            VARCHAR(100)
  sede_comune        VARCHAR(200)
  sede_prov          CHAR(3)
  data_iscrizione    DATE

ESEMPI:

Domanda: top 10 enti per importo nel 2024
SQL: SELECT denominazione, categoria_principale, importo_totale, n_scelte FROM enti WHERE anno = 2024 ORDER BY importo_totale DESC LIMIT 10

Domanda: quante associazioni sportive ci sono in Lombardia nel 2023?
SQL: SELECT COUNT(*) AS n_enti FROM enti WHERE anno = 2023 AND regione = 'LOMBARDIA' AND categoria_principale = 'asd'

Domanda: totale erogato per categoria nel 2024
SQL: SELECT categoria_principale, SUM(importo_totale) AS totale_eur, COUNT(*) AS n_enti FROM enti WHERE anno = 2024 GROUP BY categoria_principale ORDER BY totale_eur DESC

Domanda: enti esclusi in almeno una categoria nel 2024
SQL: SELECT cod_fiscale, denominazione, GROUP_CONCAT(DISTINCT categoria ORDER BY categoria SEPARATOR ', ') AS categorie_escluse FROM categoria_ammissioni WHERE anno = 2024 AND stato = 'escluso' GROUP BY cod_fiscale, denominazione ORDER BY denominazione LIMIT 50

SCHEMA;

    $payload = json_encode([
        'model'   => $model,
        'system'  => 'Sei un assistente che genera SOLO query SELECT MySQL valide. Non aggiungere spiegazioni, commenti, markdown o backtick. Rispondi UNICAMENTE con la query SQL su una o più righe.',
        'prompt'  => $schema . "\nDomanda: $domanda\nSQL:",
        'stream'  => false,
        'options' => ['temperature' => 0, 'num_predict' => 500],
    ]);

    if (!function_exists('curl_init')) err('cURL non disponibile sul server', 500);

    $ch = curl_init("$base/api/generate");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $payload,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 120,
        CURLOPT_CONNECTTIMEOUT => 5,
    ]);
    $resp = curl_exec($ch);
    $cerr = curl_error($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($resp === false || $cerr) {
        err('Modello AI non raggiungibile. Assicurarsi che Ollama sia avviato sul server.', 503);
    }
    if ($code !== 200) {
        err("Ollama ha risposto con errore HTTP $code.", 503);
    }

    $data = json_decode($resp, true);
    if (!isset($data['response'])) err('Risposta Ollama non valida.', 503);

    $sql = trim($data['response']);
    $sql = preg_replace('/^```(?:sql)?\s*/i', '', $sql);
    $sql = preg_replace('/\s*```\s*$/', '', $sql);
    return trim($sql);
}

function _nlq_validate_sql(string $sql): string {
    $clean = preg_replace('/--[^\n]*/m', '', $sql);
    $clean = preg_replace('/\/\*.*?\*\//s', '', $clean);
    $clean = trim(preg_replace('/\s+/', ' ', $clean));

    if (!preg_match('/^(SELECT|WITH)\s+/i', $clean)) {
        err('Il modello ha generato una risposta non utilizzabile. Prova a riformulare la domanda.');
    }

    static $forbidden = [
        'DROP','DELETE','UPDATE','INSERT','CREATE','ALTER','TRUNCATE',
        'EXEC','EXECUTE','GRANT','REVOKE','LOAD\s+DATA','INTO\s+OUTFILE',
        'INTO\s+DUMPFILE','SLEEP\s*\(','BENCHMARK\s*\(',
    ];
    foreach ($forbidden as $kw) {
        if (preg_match('/\b' . $kw . '\b/i', $clean)) {
            err("Query non permessa (contiene '$kw').");
        }
    }

    $allowed = ['enti','categoria_ammissioni','runts','ripartizioni'];
    if (preg_match_all('/\b(?:FROM|JOIN)\s+`?(\w+)`?/i', $clean, $m)) {
        foreach ($m[1] as $tbl) {
            if (!in_array(strtolower($tbl), $allowed, true)) {
                err("Tabella '$tbl' non accessibile tramite questa interfaccia.");
            }
        }
    }

    if (!preg_match('/\bLIMIT\s+\d+/i', $clean)) {
        $clean .= ' LIMIT 50';
    }
    $clean = preg_replace_callback(
        '/\bLIMIT\s+(\d+)\b/i',
        fn($m) => 'LIMIT ' . min((int)$m[1], 100),
        $clean
    );

    return $clean;
}

function action_nlq(): void {
    set_time_limit(180); // generazione SQL su CPU può richiedere >60s
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') err('Usa POST per questa azione.', 405);

    // Supporta sia JSON body che form-encoded
    $body = [];
    $ct   = $_SERVER['CONTENT_TYPE'] ?? '';
    if (str_contains($ct, 'application/json')) {
        $body = json_decode(file_get_contents('php://input'), true) ?? [];
    }

    $token   = $body['token'] ?? str_param('token');
    $domanda = trim($body['q'] ?? str_param('q'));

    if (!$token) err('Token mancante.', 401);
    try {
        if (!hash_equals(_nlq_token_today(), $token)) err('Token non valido o scaduto.', 401);
    } catch (\RuntimeException) {
        err('NLQ non abilitato su questo server.', 503);
    }

    if (strlen($domanda) < 5)   err('Domanda troppo corta (min. 5 caratteri).');
    if (strlen($domanda) > 500) err('Domanda troppo lunga (max. 500 caratteri).');

    $ip_hash = hash('sha256', $_SERVER['REMOTE_ADDR'] ?? 'unknown');
    try {
        _nlq_check_rate_limit($ip_hash);
    } catch (\PDOException) {
        error_log('[api.php] nlq_rate_limit table missing — run migration');
    }

    $cache_key = md5(mb_strtolower($domanda));
    $cached    = _nlq_cache_get($cache_key);
    if ($cached !== null) {
        json_out(array_merge($cached, ['from_cache' => true]));
    }

    $sql_raw = _nlq_call_ollama($domanda);
    $sql     = _nlq_validate_sql($sql_raw);

    $pdo = db();
    try {
        // Impone un timeout di 25s sulla singola query MySQL (evita subquery lente su grandi tabelle)
        try { $pdo->exec("SET SESSION MAX_EXECUTION_TIME=25000"); } catch (\Throwable) {}
        $stmt = $pdo->query($sql);
        $rows = $stmt->fetchAll();
    } catch (\PDOException $e) {
        error_log('[api.php] NLQ exec error: ' . $e->getMessage() . ' | SQL: ' . $sql);
        $msg = str_contains($e->getMessage(), '3024') || str_contains($e->getMessage(), 'execution time')
            ? 'La query ha impiegato troppo tempo. Prova a riformulare la domanda in modo più semplice (es. specifica l\'anno).'
            : 'La query generata non è eseguibile sul database. Prova a riformulare la domanda.';
        err($msg, 422);
    }

    $rows = array_map(function ($row) {
        foreach ($row as &$v) {
            if ($v !== null && preg_match('/^-?\d+$/', (string)$v))       $v = (int)$v;
            elseif ($v !== null && preg_match('/^-?\d+\.\d+$/', (string)$v)) $v = (float)$v;
        }
        return $row;
    }, $rows);

    $result = [
        'domanda'    => $domanda,
        'sql'        => $sql,
        'n_righe'    => count($rows),
        'colonne'    => $rows ? array_keys($rows[0]) : [],
        'data'       => $rows,
        'from_cache' => false,
    ];

    _nlq_cache_set($cache_key, $domanda, $sql, $result);
    json_out($result);
}

// ─── Router ─────────────────────────────────────────────────────────────────

try {
    $action = str_param('action');
    match ($action) {
        'status'             => action_status(),
        'anni'               => action_anni(),
        'categorie'          => action_categorie(),
        'statistiche'        => action_statistiche(),
        'enti'               => action_enti(),
        'ente'               => action_ente(),
        'confronta'          => action_confronta(),
        'cerca_cf'           => action_cerca_cf(),
        'analisi_categorie'    => action_analisi_categorie(),
        'categoria_dettaglio'  => action_categoria_dettaglio(),
        'regioni'              => action_regioni(),
        'province'             => action_province(),
        'classifica'           => action_classifica(),
        'files'                => action_files(),
        'download'             => action_download(),
        'inoptato'             => action_inoptato(),
        'salva_lead'           => action_salva_lead(),
        'forecast'             => action_forecast(),
        'ripartizioni'         => action_ripartizioni(),
        'multi_categoria'      => action_multi_categoria(),
        'composizione_categorie' => action_composizione_categorie(),
        'conflitti_categoria'  => action_conflitti_categoria(),
        'geo'                  => action_geo(),
        'nlq_token'            => action_nlq_token(),
        'nlq'                  => action_nlq(),
        default                => err("Azione '$action' non trovata. Azioni disponibili: status, anni, categorie, regioni, statistiche, enti, ente, confronta, analisi_categorie, categoria_dettaglio, files, download, inoptato, salva_lead, forecast, ripartizioni, multi_categoria, composizione_categorie, conflitti_categoria, geo", 404),
    };
} catch (PDOException $e) {
    error_log('[api.php] DB error: ' . $e->getMessage());
    err('Errore database', 500);
} catch (Throwable $e) {
    error_log('[api.php] Error: ' . $e->getMessage());
    err('Errore interno del server', 500);
}
