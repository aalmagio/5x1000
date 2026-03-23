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

function action_regioni(): void {
    $regioni = db()->query(
        "SELECT DISTINCT regione FROM enti WHERE regione IS NOT NULL ORDER BY regione"
    )->fetchAll(PDO::FETCH_COLUMN);
    json_out($regioni);
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
        $where[] = 'e.categoria_principale = ?';
        $params[] = $categoria;
    }
    if ($regione) {
        $where[] = 'e.regione = ?';
        $params[] = $regione;
    }
    if ($provincia) {
        $where[] = 'e.provincia = ?';
        $params[] = $provincia;
    }
    if ($q) {
        $where[] = '(e.denominazione LIKE ? OR e.cod_fiscale LIKE ?)';
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

    // Categorie attive nell'anno più recente
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
    $categorie = [];
    foreach ($cat_map as $col => $label) {
        if ($first[$col]) $categorie[] = $label;
    }

    $storico = [];
    foreach ($rows as $r) {
        $storico[] = [
            'anno'             => (int)$r['anno'],
            'denominazione'    => $r['denominazione'],
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
        'cod_fiscale'         => $first['cod_fiscale'],
        'denominazione'       => $denom_canonica,
        'regione'             => $first['regione'],
        'provincia'           => $first['provincia'],
        'comune'              => $first['comune'],
        'categoria'           => $first['categoria_principale'],
        'categorie'           => $categorie,
        'runts_denominazione' => $first['runts_denominazione'] ?: null,
        'runts_5x1000'        => (bool)$first['runts_5x1000'],
        'anni_presenti'       => array_column($storico, 'anno'),
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

    $pdo  = db();
    $stmt = $pdo->prepare(
        "SELECT DISTINCT cod_fiscale, denominazione, regione, categoria_principale
         FROM enti
         WHERE denominazione LIKE ? OR cod_fiscale LIKE ?
         ORDER BY denominazione
         LIMIT 20"
    );
    $stmt->execute(['%' . $q . '%', '%' . $q . '%']);
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
        default                => err("Azione '$action' non trovata. Azioni disponibili: status, anni, categorie, regioni, statistiche, enti, ente, confronta, analisi_categorie, categoria_dettaglio, files, download, inoptato, salva_lead, forecast", 404),
    };
} catch (PDOException $e) {
    error_log('[api.php] DB error: ' . $e->getMessage());
    err('Errore database: ' . $e->getMessage(), 500);
} catch (Throwable $e) {
    error_log('[api.php] Error: ' . $e->getMessage());
    err('Errore interno del server', 500);
}
