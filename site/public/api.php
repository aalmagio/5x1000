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

    json_out([
        'anni_disponibili'   => array_map('intval', $anni),
        'righe_totali'       => $totale,
        'ultimo_aggiornamento' => $ultimo,
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
        'ABRUZZO'                            => 'Abruzzo',
        'BASILICATA'                         => 'Basilicata',
        'CALABRIA'                           => 'Calabria',
        'CAMPANIA'                           => 'Campania',
        'EMILIA-ROMAGNA'                     => 'Emilia-Romagna',
        'EMILIA ROMAGNA'                     => 'Emilia-Romagna',
        'FRIULI-VENEZIA GIULIA'              => 'Friuli-Venezia Giulia',
        'FRIULI VENEZIA GIULIA'              => 'Friuli-Venezia Giulia',
        'LAZIO'                              => 'Lazio',
        'LIGURIA'                            => 'Liguria',
        'LOMBARDIA'                          => 'Lombardia',
        'MARCHE'                             => 'Marche',
        'MOLISE'                             => 'Molise',
        'PIEMONTE'                           => 'Piemonte',
        'PUGLIA'                             => 'Puglia',
        'SARDEGNA'                           => 'Sardegna',
        'SICILIA'                            => 'Sicilia',
        'TOSCANA'                            => 'Toscana',
        'UMBRIA'                             => 'Umbria',
        "VALLE D'AOSTA"                      => "Valle d'Aosta",
        "VALLE D'AOSTA/VALLEE D'AOSTE"       => "Valle d'Aosta",
        'VENETO'                             => 'Veneto',
        // Province autonome → raggruppate sotto la regione ufficiale
        'TRENTO'                             => 'Trentino-Alto Adige',
        'BOLZANO'                            => 'Trentino-Alto Adige',
        'TRENTINO-ALTO ADIGE'                => 'Trentino-Alto Adige',
        'TRENTINO ALTO ADIGE'                => 'Trentino-Alto Adige',
        'PROVINCIA AUTONOMA DI TRENTO'       => 'Trentino-Alto Adige',
        'PROVINCIA AUTONOMA DI BOLZANO'      => 'Trentino-Alto Adige',
        'PROVINCIA AUTONOMA TRENTO'          => 'Trentino-Alto Adige',
        'PROVINCIA AUTONOMA BOLZANO'         => 'Trentino-Alto Adige',
        'ALTO ADIGE'                         => 'Trentino-Alto Adige',
        'P.A. TRENTO'                        => 'Trentino-Alto Adige',
        'P.A. BOLZANO'                       => 'Trentino-Alto Adige',
    ];
    $key = strtoupper(trim($raw));
    return $map[$key] ?? ucwords(strtolower($raw));
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
        "SELECT anno, categoria_principale,
                COUNT(*) AS n_enti,
                SUM(n_scelte) AS totale_scelte,
                SUM(importo_totale) AS totale_importo
         FROM enti
         WHERE anno = ? AND categoria_principale IS NOT NULL
         GROUP BY anno, categoria_principale
         ORDER BY totale_importo DESC"
    );
    $stmt->execute([$anno]);
    $rows = $stmt->fetchAll();

    foreach ($rows as &$r) {
        $r['n_enti']         = (int)$r['n_enti'];
        $r['totale_scelte']  = (int)$r['totale_scelte'];
        $r['totale_importo'] = (float)$r['totale_importo'];
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
        // Cerca anche nel nome canonico RUNTS (già unito via LEFT JOIN)
        $where[] = '(e.denominazione LIKE ? OR e.cod_fiscale LIKE ? OR r.denominazione LIKE ?)';
        $params[] = '%' . $q . '%';
        $params[] = '%' . $q . '%';
        $params[] = '%' . $q . '%';
    }
    if ($runts_only) {
        $where[] = 'e.runts_5x1000 = 1';
    } elseif ($non_runts) {
        $where[] = '(e.runts_5x1000 = 0 OR e.runts_5x1000 IS NULL)';
    }

    $sql_where = $where ? ('WHERE ' . implode(' AND ', $where)) : '';

    // Conteggio totale
    $count_stmt = $pdo->prepare(
        "SELECT COUNT(*) FROM enti e LEFT JOIN runts r ON r.cod_fiscale = e.cod_fiscale $sql_where"
    );
    $count_stmt->execute($params);
    $totale = (int)$count_stmt->fetchColumn();

    $pagine = max(1, (int)ceil($totale / $per_pagina));
    $offset = ($pagina - 1) * $per_pagina;

    // Dati — denominazione canonica: RUNTS se disponibile, altrimenti anno corrente
    $data_stmt = $pdo->prepare(
        "SELECT e.anno, e.cod_fiscale,
                COALESCE(NULLIF(r.denominazione,''), e.denominazione) AS denominazione,
                e.regione, e.provincia, e.comune,
                e.categoria_principale,
                e.n_scelte, e.importo_espresso, e.importo_generico, e.importo_totale,
                e.runts_5x1000
         FROM enti e
         LEFT JOIN runts r ON r.cod_fiscale = e.cod_fiscale
         $sql_where
         ORDER BY e.$sort $dir
         LIMIT $per_pagina OFFSET $offset"
    );
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

    // Mappa flag → nome categoria
    $cat_map = [
        'cat_volontariato' => 'Volontariato',
        'cat_asd'          => 'ASD',
        'cat_ets_onlus'    => 'ETS/ONLUS',
        'cat_ricerca_sci'  => 'Ricerca Scientifica',
        'cat_ricerca_san'  => 'Ricerca Sanitaria',
        'cat_comuni'       => 'Comuni',
        'cat_beni_cult'    => 'Beni Culturali',
        'cat_aree_prot'    => 'Aree Protette',
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

    $storico = [];
    foreach ($per_anno as $anno => $anno_rows) {
        $r0          = $anno_rows[0];
        $tot_scelte  = array_sum(array_column($anno_rows, 'n_scelte'));
        $tot_esp     = array_sum(array_column($anno_rows, 'importo_espresso'));
        $tot_gen     = array_sum(array_column($anno_rows, 'importo_generico'));
        $tot_tot     = array_sum(array_column($anno_rows, 'importo_totale'));

        // Breakdown per categoria (solo se ci sono più righe nello stesso anno)
        $cat_breakdown = null;
        if (count($anno_rows) > 1) {
            $cat_breakdown = array_map(fn($r) => [
                'categoria'        => $r['categoria_principale'],
                'n_scelte'         => (int)$r['n_scelte'],
                'importo_espresso' => (float)$r['importo_espresso'],
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

    // Statistiche per categoria per anno
    $stmt = $pdo->prepare(
        "SELECT anno, categoria_principale,
                COUNT(*) AS n_enti,
                SUM(n_scelte) AS totale_scelte,
                SUM(importo_totale) AS totale_importo,
                AVG(importo_totale) AS media_importo,
                MAX(importo_totale) AS max_importo
         FROM enti
         $anni_sql
         WHERE categoria_principale IS NOT NULL
         GROUP BY anno, categoria_principale
         ORDER BY anno ASC, totale_importo DESC"
    );

    // Riscrive la WHERE se anno è specificato (tabella ha già anno nella condizione)
    if ($anno) {
        $stmt = $pdo->prepare(
            "SELECT anno, categoria_principale,
                    COUNT(*) AS n_enti,
                    SUM(n_scelte) AS totale_scelte,
                    SUM(importo_totale) AS totale_importo,
                    AVG(importo_totale) AS media_importo,
                    MAX(importo_totale) AS max_importo
             FROM enti
             WHERE anno = ? AND categoria_principale IS NOT NULL
             GROUP BY anno, categoria_principale
             ORDER BY anno ASC, totale_importo DESC"
        );
        $stmt->execute([$anno]);
    } else {
        $stmt = $pdo->query(
            "SELECT anno, categoria_principale,
                    COUNT(*) AS n_enti,
                    SUM(n_scelte) AS totale_scelte,
                    SUM(importo_totale) AS totale_importo,
                    AVG(importo_totale) AS media_importo,
                    MAX(importo_totale) AS max_importo
             FROM enti
             WHERE categoria_principale IS NOT NULL
             GROUP BY anno, categoria_principale
             ORDER BY anno ASC, totale_importo DESC"
        );
    }

    $rows = $stmt->fetchAll();

    // Struttura: { anni: [...], categorie: [...], per_anno: { anno: { cat: {...} } } }
    $anni_set = [];
    $cat_set  = [];
    $per_anno = [];

    foreach ($rows as $r) {
        $a = (int)$r['anno'];
        $c = $r['categoria_principale'];
        $anni_set[$a] = true;
        $cat_set[$c]  = true;
        $per_anno[$a][$c] = [
            'n_enti'         => (int)$r['n_enti'],
            'totale_scelte'  => (int)$r['totale_scelte'],
            'totale_importo' => (float)$r['totale_importo'],
            'media_importo'  => round((float)$r['media_importo'], 2),
            'max_importo'    => (float)$r['max_importo'],
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

    $like = '%' . $q . '%';
    $pdo  = db();
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

    $tipo = str_param('tipo');  // csv | xlsx | report
    $anno = str_param('anno');  // anno numerico oppure 'completo'

    if (!in_array($tipo, ['csv', 'xlsx', 'report'], true)) {
        err('Tipo non valido', 400);
    }

    $pdo = db();

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
        header('X-Accel-Buffering: no');  // disabilita buffering nginx per lo streaming

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
    if (!file_exists($path) || !is_readable($path)) {
        err('File non disponibile sul server', 404);
    }

    $ext  = pathinfo($path, PATHINFO_EXTENSION);
    $mime = $ext === 'csv'
        ? 'text/csv; charset=utf-8'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

    header('Content-Type: ' . $mime);
    header('Content-Disposition: attachment; filename="' . basename($path) . '"');
    header('Content-Length: ' . filesize($path));
    header('Cache-Control: no-store');
    readfile($path);
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
        default                => err("Azione '$action' non trovata. Azioni disponibili: status, anni, categorie, regioni, statistiche, enti, ente, confronta, analisi_categorie, categoria_dettaglio, files, download, inoptato, salva_lead, forecast, ripartizioni", 404),
    };
} catch (PDOException $e) {
    error_log('[api.php] DB error: ' . $e->getMessage());
    err('Errore database: ' . $e->getMessage(), 500);
} catch (Throwable $e) {
    error_log('[api.php] Error: ' . $e->getMessage());
    err('Errore interno del server', 500);
}
