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
 *   ?action=enti[&q=...][&anno=...][&categoria=...][&regione=...][&runts_only=1]
 *              [&pagina=1][&per_pagina=50][&sort=importo_totale][&asc=0]
 *   ?action=ente&cf=CODICE_FISCALE
 *   ?action=confronta&cf[]=CF1&cf[]=CF2[&cf[]=CF3...]   (max 5)
 *   ?action=analisi_categorie[&anno=YYYY]
 */

declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// ─── Config ────────────────────────────────────────────────────────────────

function load_env(string $dir): void {
    $f = $dir . '/.env';
    if (!is_file($f)) {
        error_log("[api.php] .env non trovato in: $f");
        return;
    }
    error_log("[api.php] .env caricato da: $f");
    $loaded = [];
    foreach (file($f, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') continue;
        if (!str_contains($line, '=')) continue;
        [$k, $v] = explode('=', $line, 2);
        $k = trim($k); $v = trim($v, " \t\n\r\0\x0B\"'");
        if ($k !== '' && empty($_ENV[$k])) {
            $_ENV[$k] = $v;
            putenv("$k=$v");
            $loaded[$k] = empty($v) ? '(VUOTO)' : '(set,len=' . strlen($v) . ')';
        } elseif ($k !== '') {
            $loaded[$k] = '(saltato,ENV già set)';
        }
    }
    error_log("[api.php] .env keys: " . json_encode($loaded));
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
    error_log("[api.php] DB connect: host=$host db=$name user=" . (empty($user) ? '(VUOTO!)' : '(set,len=' . strlen($user) . ')'));
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
    return isset($_GET[$key]) ? trim((string)$_GET[$key]) : $default;
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
    $runts_only = int_param('runts_only');
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
        $where[] = 'anno = ?';
        $params[] = $anno;
    }
    if ($categoria) {
        $where[] = 'categoria_principale = ?';
        $params[] = $categoria;
    }
    if ($regione) {
        $where[] = 'regione LIKE ?';
        $params[] = '%' . $regione . '%';
    }
    if ($q) {
        $where[] = '(denominazione LIKE ? OR cod_fiscale LIKE ?)';
        $params[] = '%' . $q . '%';
        $params[] = '%' . $q . '%';
    }
    if ($runts_only) {
        $where[] = 'runts_5x1000 = 1';
    }

    $sql_where = $where ? ('WHERE ' . implode(' AND ', $where)) : '';

    // Conteggio totale
    $count_stmt = $pdo->prepare("SELECT COUNT(*) FROM enti $sql_where");
    $count_stmt->execute($params);
    $totale = (int)$count_stmt->fetchColumn();

    $pagine = max(1, (int)ceil($totale / $per_pagina));
    $offset = ($pagina - 1) * $per_pagina;

    // Dati
    $data_stmt = $pdo->prepare(
        "SELECT anno, cod_fiscale, denominazione, regione, provincia, comune,
                categoria_principale, n_scelte, importo_espresso, importo_generico, importo_totale,
                runts_5x1000
         FROM enti
         $sql_where
         ORDER BY $sort $dir
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
    $storico = [];
    foreach ($rows as $r) {
        $storico[] = [
            'anno'             => (int)$r['anno'],
            'n_scelte'         => $r['n_scelte'] !== null ? (int)$r['n_scelte'] : null,
            'importo_espresso' => $r['importo_espresso'] !== null ? (float)$r['importo_espresso'] : null,
            'importo_generico' => $r['importo_generico'] !== null ? (float)$r['importo_generico'] : null,
            'importo_totale'   => $r['importo_totale']   !== null ? (float)$r['importo_totale']   : null,
            'runts_sezione'    => $r['runts_sezione'],
            'runts_sede_comune' => $r['runts_sede_comune'],
            'runts_sede_prov'  => $r['runts_sede_prov'],
            'runts_data_iscrizione' => $r['runts_data_iscrizione'],
        ];
    }

    json_out([
        'cod_fiscale'       => $first['cod_fiscale'],
        'denominazione'     => $first['denominazione'],
        'regione'           => $first['regione'],
        'provincia'         => $first['provincia'],
        'comune'            => $first['comune'],
        'categoria'         => $first['categoria_principale'],
        'runts_denominazione' => $first['runts_denominazione'],
        'runts_5x1000'      => (bool)$first['runts_5x1000'],
        'anni_presenti'     => array_column($storico, 'anno'),
        'storico'           => $storico,
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
        'analisi_categorie'  => action_analisi_categorie(),
        'files'              => action_files(),
        'download'           => action_download(),
        default              => err("Azione '$action' non trovata. Azioni disponibili: status, anni, categorie, statistiche, enti, ente, confronta, analisi_categorie, files, download", 404),
    };
} catch (PDOException $e) {
    error_log('[api.php] DB error: ' . $e->getMessage());
    err('Errore database: ' . $e->getMessage(), 500);
} catch (Throwable $e) {
    error_log('[api.php] Error: ' . $e->getMessage());
    err('Errore interno del server', 500);
}
