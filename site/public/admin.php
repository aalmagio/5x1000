<?php
/**
 * admin.php — Pannello di controllo pipeline 5×1000
 *
 * Accesso protetto da password (ADMIN_PASSWORD= in .env).
 * Prima visita senza ADMIN_PASSWORD → wizard di setup.
 *
 * Tab:  Panoramica · Pipeline · File & Log · Impostazioni
 */
declare(strict_types=1);
header('X-Robots-Tag: noindex, nofollow');

// ═══════════════════════════════════════════════════════════════════════════
//  PERCORSI E COSTANTI
// ═══════════════════════════════════════════════════════════════════════════

define('PROJECT_ROOT', (string) realpath(__DIR__ . '/../..'));
define('DATI_DIR',     PROJECT_ROOT . '/Dati');
define('LOG_DIR',      PROJECT_ROOT . '/log');
define('ENV_FILE',     __DIR__ . '/.env');
define('PID_FILE',     LOG_DIR . '/.pipeline.pid');
define('ANNI_MIN',     2006);
define('ANNI_MAX',     (int) date('Y'));
define('STEPS_ALL',    ['download', 'categorie', 'etl', 'report', 'gsheets']);
define('STEP_LABELS',  [
    'download'  => 'Download AdE',
    'categorie' => 'Categorie',
    'etl'       => 'ETL / Normalizza',
    'report'    => 'Report Excel',
    'gsheets'   => 'Google Sheets',
]);

// ═══════════════════════════════════════════════════════════════════════════
//  CARICA .ENV
// ═══════════════════════════════════════════════════════════════════════════

function adm_load_env(string $path): void {
    if (!is_file($path)) return;
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if (!$line || $line[0] === '#' || !str_contains($line, '=')) continue;
        [$k, $v] = explode('=', $line, 2);
        $k = trim($k); $v = trim($v, " \t\"'");
        if ($k === '') continue;
        putenv("$k=$v");
        $_ENV[$k] = $v;
    }
}
adm_load_env(ENV_FILE);

$admin_pw_hash = (string)(getenv('ADMIN_PASSWORD') ?: '');

// ═══════════════════════════════════════════════════════════════════════════
//  SESSIONE & AUTH
// ═══════════════════════════════════════════════════════════════════════════

session_name('adm5x1000');
session_start();
$csrf      = $_SESSION['csrf'] ??= bin2hex(random_bytes(16));
$logged_in = ($_SESSION['auth'] ?? false) === true;
$tab       = $_GET['tab'] ?? 'overview';
$flash     = null;       // ['type'=>'ok'|'err', 'msg'=>'...']

// ─── AJAX: get_log ───────────────────────────────────────────────────────────
if (($ga = $_GET['action'] ?? '') === 'get_log' && $logged_in) {
    header('Content-Type: application/json');
    $file    = (string)($_GET['file'] ?? '');
    $real    = $file ? @realpath($file) : false;
    $log_dir = is_dir(LOG_DIR) ? realpath(LOG_DIR) : null;
    if ($real && $log_dir && str_starts_with($real, $log_dir . '/')) {
        $off  = max(0, (int)($_GET['offset'] ?? 0));
        $fh   = fopen($real, 'r');
        fseek($fh, $off);
        $buf  = fread($fh, 131072);
        $noff = ftell($fh);
        fclose($fh);
        echo json_encode(['content' => $buf, 'offset' => $noff, 'running' => adm_is_running()]);
    } else {
        echo json_encode(['error' => 'path non valido']);
    }
    exit;
}

// ─── AJAX: get_status ────────────────────────────────────────────────────────
if ($ga === 'get_status' && $logged_in) {
    header('Content-Type: application/json');
    echo json_encode(['running' => adm_is_running(), 'pid' => (int)@file_get_contents(PID_FILE)]);
    exit;
}

// ═══════════════════════════════════════════════════════════════════════════
//  GESTIONE POST
// ═══════════════════════════════════════════════════════════════════════════

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $pa = $_POST['action'] ?? '';
    $pc = $_POST['csrf']   ?? '';

    // -- setup (prima password) --
    if ($pa === 'setup' && !$admin_pw_hash) {
        $pw = $_POST['password'] ?? ''; $pw2 = $_POST['password2'] ?? '';
        if (strlen($pw) < 8 || $pw !== $pw2) {
            $flash = ['err', 'Le password non corrispondono o sono troppo corte (min. 8 caratteri).'];
        } else {
            $hash = password_hash($pw, PASSWORD_BCRYPT);
            adm_update_env_key(ENV_FILE, 'ADMIN_PASSWORD', $hash);
            $admin_pw_hash = $hash;
            $_SESSION['auth'] = true;
            header('Location: admin.php'); exit;
        }
    }

    // -- login --
    if ($pa === 'login') {
        $pw = $_POST['password'] ?? '';
        if ($admin_pw_hash && password_verify($pw, $admin_pw_hash)) {
            session_regenerate_id(true);
            $_SESSION['auth'] = true;
            header('Location: admin.php'); exit;
        }
        $flash = ['err', 'Password non corretta.'];
    }

    // -- logout --
    if ($pa === 'logout') { session_destroy(); header('Location: admin.php'); exit; }

    // Tutte le azioni seguenti richiedono autenticazione
    if (!$logged_in || !hash_equals($pc, $csrf)) {
        if (!$logged_in) { header('Location: admin.php'); exit; }
        http_response_code(403); exit('CSRF error');
    }

    // -- launch pipeline --
    if ($pa === 'launch') {
        if (adm_is_running()) {
            $flash = ['err', 'Una pipeline è già in esecuzione (PID: ' . (int)@file_get_contents(PID_FILE) . '). Attendi o termina il processo.'];
            $tab   = 'pipeline';
        } else {
            [$ok, $msg, $log_file] = adm_launch_pipeline($_POST, $python_cmd);
            if ($ok) { header('Location: admin.php?tab=log&logfile=' . urlencode($log_file)); exit; }
            $flash = ['err', $msg]; $tab = 'pipeline';
        }
    }

    // -- launch db_updater --
    if ($pa === 'launch_db') {
        if (adm_is_running()) {
            $flash = ['err', 'Un processo è già in esecuzione.'];
        } else {
            [$ok, $msg, $log_file] = adm_launch_db($_POST, $python_cmd);
            if ($ok) { header('Location: admin.php?tab=log&logfile=' . urlencode($log_file)); exit; }
            $flash = ['err', $msg];
        }
        $tab = 'log';
    }

    // -- kill --
    if ($pa === 'kill') {
        adm_kill();
        $flash = ['ok', 'Segnale di terminazione inviato al processo.'];
        $tab   = 'log';
    }

    // -- reset --
    if ($pa === 'reset') {
        if (adm_is_running()) {
            $flash = ['err', 'Impossibile fare il reset mentre la pipeline è in esecuzione.'];
        } elseif (empty($_POST['confirm_reset'])) {
            $flash = ['err', 'Spunta la casella di conferma prima di eseguire il reset.'];
            $tab   = 'pipeline';
        } else {
            [$ok, $msg, $log_file] = adm_launch_reset($_POST, $python_cmd);
            if ($ok) { header('Location: admin.php?tab=log&logfile=' . urlencode($log_file)); exit; }
            $flash = ['err', $msg]; $tab = 'pipeline';
        }
    }

    // -- change password --
    if ($pa === 'change_pw') {
        $pw = $_POST['password'] ?? ''; $pw2 = $_POST['password2'] ?? '';
        if (strlen($pw) < 8 || $pw !== $pw2) {
            $flash = ['err', 'Le password non corrispondono o sono troppo corte.'];
        } else {
            adm_update_env_key(ENV_FILE, 'ADMIN_PASSWORD', password_hash($pw, PASSWORD_BCRYPT));
            $flash = ['ok', 'Password aggiornata con successo.'];
        }
        $tab = 'settings';
    }

    // -- setup venv --
    if ($pa === 'setup_venv') {
        if (adm_is_running()) {
            $flash = ['err', 'Un processo è già in esecuzione. Attendi prima di creare il venv.'];
        } else {
            [$ok, $msg, $log_file] = adm_run_venv_setup();
            if ($ok) { header('Location: admin.php?tab=log&logfile=' . urlencode($log_file)); exit; }
            $flash = ['err', $msg];
        }
        $tab = 'settings';
    }

    // -- set venv path --
    if ($pa === 'set_venv_path') {
        $vp = trim($_POST['venv_path'] ?? '');
        if ($vp === '' || is_dir($vp)) {
            adm_update_env_key(ENV_FILE, 'VENV_PATH', $vp);
            adm_load_env(ENV_FILE);   // ricarica per aggiornare getenv in questa request
            $flash = ['ok', $vp ? "VENV_PATH impostato su: $vp" : 'VENV_PATH rimosso (auto-detect).'];
        } else {
            $flash = ['err', "Cartella non trovata: $vp"];
        }
        $tab = 'settings';
    }
}

// ═══════════════════════════════════════════════════════════════════════════
//  FUNZIONI HELPER
// ═══════════════════════════════════════════════════════════════════════════

function adm_is_running(): bool {
    $pid = (int)@file_get_contents(PID_FILE);
    if ($pid <= 0) return false;
    if (!function_exists('posix_kill')) return false;
    return posix_kill($pid, 0);
}

function adm_kill(): void {
    $pid = (int)@file_get_contents(PID_FILE);
    if ($pid > 0 && function_exists('posix_kill')) {
        posix_kill($pid, SIGTERM);
        sleep(1);
        if (posix_kill($pid, 0)) posix_kill($pid, SIGKILL);
    }
    @unlink(PID_FILE);
}

// ─── Rilevamento Python / venv ───────────────────────────────────────────────

/**
 * Restituisce info sul venv: ['path'=>..., 'python'=>..., 'exists'=>bool, 'source'=>'...'].
 * Priorità: PYTHON_CMD > VENV_PATH > PROJECT_ROOT/venv > PROJECT_ROOT/.venv > python3
 */
function adm_venv_info(): array {
    // Override esplicito comando python
    $explicit = getenv('PYTHON_CMD') ?: '';
    if ($explicit && (file_exists($explicit) || strpos($explicit, '/') === false)) {
        return ['path' => '', 'python' => $explicit, 'exists' => true, 'source' => 'PYTHON_CMD'];
    }

    // Cartella venv esplicita
    $venv_path_env = rtrim(getenv('VENV_PATH') ?: '', '/');
    if ($venv_path_env) {
        $py = $venv_path_env . '/bin/python3';
        if (is_executable($py)) {
            return ['path' => $venv_path_env, 'python' => $py, 'exists' => true, 'source' => 'VENV_PATH'];
        }
        return ['path' => $venv_path_env, 'python' => $py, 'exists' => false, 'source' => 'VENV_PATH (non trovato)'];
    }

    // Auto-detect: cartella venv o .venv nella PROJECT_ROOT
    foreach (['venv', '.venv'] as $dir) {
        $base = PROJECT_ROOT . '/' . $dir;
        $py   = $base . '/bin/python3';
        if (is_executable($py)) {
            return ['path' => $base, 'python' => $py, 'exists' => true, 'source' => "auto ($dir)"];
        }
    }

    // Fallback: python3 di sistema
    return ['path' => '', 'python' => 'python3', 'exists' => false, 'source' => 'sistema (nessun venv)'];
}

/** Restituisce il comando python da usare per lanciare gli script. */
function adm_python_cmd(): string {
    return adm_venv_info()['python'];
}

/** Crea il venv e installa requirements.txt in background. */
function adm_run_venv_setup(): array {
    @mkdir(LOG_DIR, 0755, true);
    $ts       = date('Ymd_His');
    $log_file = LOG_DIR . "/venv_setup_{$ts}.log";
    $venv     = PROJECT_ROOT . '/venv';
    $req      = PROJECT_ROOT . '/requirements.txt';
    $pip_step = is_file($req)
        ? ' && ' . escapeshellarg("$venv/bin/pip") . ' install -r ' . escapeshellarg($req)
        : '';
    $cmd = sprintf(
        'nohup bash -c "cd %s && python3 -m venv %s%s" > %s 2>&1 & echo $!',
        escapeshellarg(PROJECT_ROOT),
        escapeshellarg($venv),
        $pip_step,
        escapeshellarg($log_file)
    );
    $pid = (int)@shell_exec($cmd);
    if ($pid <= 0) return [false, 'Impossibile avviare la creazione del venv. Verifica che shell_exec() e bash siano disponibili.', ''];
    file_put_contents(PID_FILE, $pid);
    return [true, "PID $pid", $log_file];
}

// ─────────────────────────────────────────────────────────────────────────────

function adm_run_bg(string $script, array $args, string $log_prefix): array {
    @mkdir(LOG_DIR, 0755, true);
    $ts       = date('Ymd_His');
    $log_file = LOG_DIR . "/{$log_prefix}_{$ts}.log";
    if (!file_exists($script)) return [false, "Script non trovato: $script", ''];

    $python = adm_python_cmd();
    $cmd = sprintf(
        'cd %s && nohup %s %s %s > %s 2>&1 & echo $!',
        escapeshellarg(PROJECT_ROOT),
        escapeshellarg($python),
        escapeshellarg($script),
        implode(' ', $args),
        escapeshellarg($log_file)
    );
    $pid = (int)@shell_exec($cmd);
    if ($pid <= 0) return [false, 'Impossibile avviare il processo. Verifica che shell_exec() sia abilitato in PHP.', ''];
    @mkdir(LOG_DIR, 0755, true);
    file_put_contents(PID_FILE, $pid);
    return [true, "PID $pid", $log_file];
}

function adm_launch_pipeline(array $post, string $python): array {
    $args = [];

    // Modalità Solo Report: ignora tutti gli altri step
    if (!empty($post['report_only'])) {
        $args[] = '--report-only';
        $anni = trim($post['anni'] ?? '');
        if ($anni !== '' && preg_match('/^[\d,\s]+$/', $anni)) {
            $ys = array_filter(array_map('intval', explode(',', $anni)));
            $ys = array_filter($ys, fn($y) => $y >= ANNI_MIN && $y <= ANNI_MAX + 1);
            if ($ys) $args[] = '--anni ' . escapeshellarg(implode(',', $ys));
        }
        $ac = (int)($post['anno_confronto'] ?? 0);
        if ($ac >= ANNI_MIN && $ac <= ANNI_MAX) $args[] = '--anno-confronto ' . $ac;
        if (!empty($post['no_confronto'])) $args[] = '--no-confronto';
        return adm_run_bg(PROJECT_ROOT . '/pipeline.py', $args, 'report');
    }

    $anni = trim($post['anni'] ?? '');
    if ($anni !== '' && preg_match('/^[\d,\s]+$/', $anni)) {
        $ys = array_filter(array_map('intval', explode(',', $anni)));
        $ys = array_filter($ys, fn($y) => $y >= ANNI_MIN && $y <= ANNI_MAX + 1);
        if ($ys) $args[] = '--anni ' . escapeshellarg(implode(',', $ys));
    }
    $src = $post['source'] ?? 'csv';
    if (in_array($src, ['csv', 'pdf'], true)) $args[] = '--source ' . $src;

    // Steps selezionati
    $steps = is_array($post['steps'] ?? null) ? $post['steps'] : [];
    $valid = array_intersect($steps, STEPS_ALL);
    if ($valid && count($valid) < count(STEPS_ALL))
        $args[] = '--only ' . escapeshellarg(implode(',', $valid));

    if (!empty($post['smart']))         $args[] = '--smart';
    if (!empty($post['no_runts']))      $args[] = '--no-runts';
    if (!empty($post['no_excel_etl'])) $args[] = '--no-excel-etl';
    if (!empty($post['no_confronto'])) $args[] = '--no-confronto';
    if (!empty($post['skip_gsheets'])) $args[] = '--skip-gsheets';
    $ac = (int)($post['anno_confronto'] ?? 0);
    if ($ac >= ANNI_MIN && $ac <= ANNI_MAX) $args[] = '--anno-confronto ' . $ac;

    return adm_run_bg(PROJECT_ROOT . '/pipeline.py', $args, 'pipeline');
}

function adm_launch_db(array $post, string $python): array {
    $args = [];
    $anni = trim($post['db_anni'] ?? '');
    if ($anni !== '' && preg_match('/^[\d,\s]+$/', $anni)) {
        $ys = array_filter(array_map('intval', explode(',', $anni)));
        if ($ys) $args[] = '--anni ' . escapeshellarg(implode(',', $ys));
    }
    return adm_run_bg(PROJECT_ROOT . '/db_updater.py', $args, 'db_update');
}

function adm_launch_reset(array $post, string $python): array {
    $args = ['--reset', '--force'];
    if (!empty($post['solo_db'])) $args[] = '--reset-db';
    // Rimuovi --reset se solo_db (pipeline.py gestisce --reset-db separatamente)
    if (!empty($post['solo_db'])) $args = ['--reset-db', '--force'];
    return adm_run_bg(PROJECT_ROOT . '/pipeline.py', $args, 'reset');
}

function adm_update_env_key(string $env_file, string $key, string $value): void {
    $content = is_file($env_file) ? file_get_contents($env_file) : '';
    $line    = "$key=$value";
    if (preg_match('/^' . preg_quote($key, '/') . '=/m', $content))
        $content = preg_replace('/^' . preg_quote($key, '/') . '=.*/m', $line, $content);
    else
        $content .= "\n$line\n";
    file_put_contents($env_file, $content, LOCK_EX);
}

function adm_db(): ?PDO {
    static $pdo = null;
    if ($pdo) return $pdo;
    $h = getenv('SITE_DB_HOST') ?: 'localhost';
    $p = getenv('SITE_DB_PORT') ?: '3306';
    $n = getenv('SITE_DB_NAME') ?: '';
    $u = getenv('SITE_DB_USER') ?: '';
    $w = getenv('SITE_DB_PASSWORD') ?: '';
    if (!$u || !$n) return null;
    try {
        $pdo = new PDO("mysql:host=$h;port=$p;dbname=$n;charset=utf8mb4", $u, $w, [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]);
    } catch (PDOException) { return null; }
    return $pdo;
}

function adm_q(string $sql, array $p = []): array {
    $pdo = adm_db();
    if (!$pdo) return [];
    try { $st = $pdo->prepare($sql); $st->execute($p); return $st->fetchAll(); }
    catch (PDOException) { return []; }
}

function adm_scalar(string $sql, array $p = []): mixed {
    $pdo = adm_db();
    if (!$pdo) return null;
    try { $st = $pdo->prepare($sql); $st->execute($p); return $st->fetchColumn(); }
    catch (PDOException) { return null; }
}

function adm_fmt_bytes(int $b): string {
    if ($b < 1024)       return $b . ' B';
    if ($b < 1048576)    return round($b / 1024, 1) . ' KB';
    if ($b < 1073741824) return round($b / 1048576, 1) . ' MB';
    return round($b / 1073741824, 1) . ' GB';
}

function adm_fmt_date(?string $d): string {
    if (!$d) return '–';
    $ts = strtotime($d);
    return $ts ? date('d/m/Y H:i', $ts) : $d;
}

function adm_dati_tree(string $dir): array {
    if (!is_dir($dir)) return [];
    $items = [];
    foreach (new DirectoryIterator($dir) as $f) {
        if ($f->isDot()) continue;
        $item = ['name' => $f->getFilename(), 'is_dir' => $f->isDir(), 'size' => 0, 'mtime' => $f->getMTime(), 'ext' => ''];
        if ($f->isFile()) { $item['size'] = $f->getSize(); $item['ext'] = strtolower($f->getExtension()); }
        elseif ($f->isDir()) {
            $sub = glob($f->getPathname() . '/*') ?: [];
            $item['sub_count'] = count($sub);
            $item['sub_size']  = (int) array_sum(array_map('filesize', array_filter($sub, 'is_file')));
        }
        $items[] = $item;
    }
    usort($items, fn($a, $b) => ($b['is_dir'] <=> $a['is_dir']) ?: strcmp($a['name'], $b['name']));
    return $items;
}

function adm_log_files(): array {
    if (!is_dir(LOG_DIR)) return [];
    $files = glob(LOG_DIR . '/*.log') ?: [];
    usort($files, fn($a, $b) => filemtime($b) - filemtime($a));
    return array_slice($files, 0, 50);
}

function adm_status_badge(string $status): string {
    return match($status) {
        'ok'      => '<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">ok</span>',
        'error'   => '<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">errore</span>',
        'parziale'=> '<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">parziale</span>',
        default   => '<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">' . htmlspecialchars($status) . '</span>',
    };
}

// ═══════════════════════════════════════════════════════════════════════════
//  RACCOLTA DATI (solo se loggati)
// ═══════════════════════════════════════════════════════════════════════════

$is_running  = false;
$recent_runs = $dati_tree = $log_files = [];
$enti_count = $last_anno = $files_count = $last_run = null;
$db_ok       = false;
$active_log  = null;
$venv_info   = adm_venv_info();   // rilevato prima del login check così è disponibile ovunque

if ($logged_in) {
    $is_running   = adm_is_running();
    $db_ok        = adm_db() !== null;
    $recent_runs  = adm_q("SELECT * FROM pipeline_runs ORDER BY run_at DESC LIMIT 10");
    $enti_count   = adm_scalar("SELECT COUNT(*) FROM enti");
    $last_anno    = adm_scalar("SELECT MAX(anno) FROM enti");
    $files_count  = adm_scalar("SELECT COUNT(*) FROM dataset_files");
    $last_run     = $recent_runs[0] ?? null;
    $dati_tree    = adm_dati_tree(DATI_DIR);
    $log_files    = adm_log_files();

    // Log attivo (da GET param, con validazione path)
    $log_param = $_GET['logfile'] ?? '';
    if ($log_param) {
        $log_real    = @realpath($log_param);
        $log_dir_abs = is_dir(LOG_DIR) ? realpath(LOG_DIR) : null;
        if ($log_real && $log_dir_abs && str_starts_with($log_real, $log_dir_abs . '/'))
            $active_log = $log_real;
    }
    if (!$active_log && $log_files) $active_log = $log_files[0];
}

// ─── Helper per il template HTML ────────────────────────────────────────────
$he = fn(string $s) => htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');

?><!DOCTYPE html>
<html lang="it" class="h-full">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin — 5×1000</title>
<script src="https://cdn.tailwindcss.com"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
<style>
  [x-cloak]{display:none!important}
  .tab-btn{@apply px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors cursor-pointer;}
  .tab-active{@apply border-blue-600 text-blue-700 bg-white;}
  .tab-inactive{@apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 bg-gray-50;}
  pre.log-view{font-size:0.72rem;line-height:1.5;white-space:pre-wrap;word-break:break-all;}
</style>
</head>
<body class="h-full bg-gray-100">

<?php if (!$logged_in): ?>
<!-- ═══════════════ PAGINA LOGIN / SETUP ═══════════════ -->
<div class="min-h-screen flex items-center justify-center p-4">
  <div class="w-full max-w-sm">
    <div class="text-center mb-8">
      <span class="inline-flex items-center justify-center w-12 h-12 bg-blue-600 text-white font-extrabold rounded-xl text-lg">5‰</span>
      <h1 class="mt-3 text-2xl font-bold text-gray-900">Pipeline Admin</h1>
      <p class="text-sm text-gray-500 mt-1">Pannello di controllo 5×1000</p>
    </div>

    <?php if ($flash): ?>
    <div class="mb-4 px-4 py-3 rounded-lg text-sm <?= $flash[0]==='ok' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200' ?>">
      <?= $he($flash[1]) ?>
    </div>
    <?php endif; ?>

    <?php if (!$admin_pw_hash): ?>
    <!-- Setup prima password -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h2 class="font-semibold text-gray-900 mb-1">Prima configurazione</h2>
      <p class="text-xs text-gray-500 mb-4">Imposta la password per proteggere il pannello admin.</p>
      <form method="POST">
        <input type="hidden" name="action" value="setup">
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Password (min. 8 caratteri)</label>
            <input type="password" name="password" required minlength="8" autofocus
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Conferma password</label>
            <input type="password" name="password2" required minlength="8"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>
          <button type="submit" class="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
            Imposta password e accedi
          </button>
        </div>
      </form>
    </div>
    <?php else: ?>
    <!-- Login -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <form method="POST">
        <input type="hidden" name="action" value="login">
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Password</label>
            <input type="password" name="password" required autofocus
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>
          <button type="submit" class="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
            Accedi
          </button>
        </div>
      </form>
    </div>
    <?php endif; ?>
  </div>
</div>

<?php else: ?>
<!-- ═══════════════ PANNELLO PRINCIPALE ═══════════════ -->
<div x-data="{
  tab: '<?= $he($tab) ?>',
  logContent: '',
  logOffset: 0,
  logRunning: <?= $is_running ? 'true' : 'false' ?>,
  logFile: <?= $active_log ? "'" . addslashes($active_log) . "'" : 'null' ?>,
  logTimer: null,
  logAutoScroll: true,
  startLogPolling() {
    this.stopLogPolling();
    this.fetchLog(true);
    if (this.logRunning) this.logTimer = setInterval(() => this.fetchLog(false), 2000);
  },
  stopLogPolling() { if (this.logTimer) { clearInterval(this.logTimer); this.logTimer = null; } },
  fetchLog(reset) {
    if (!this.logFile) return;
    if (reset) { this.logContent = ''; this.logOffset = 0; }
    fetch('admin.php?action=get_log&file=' + encodeURIComponent(this.logFile) + '&offset=' + this.logOffset)
      .then(r => r.json()).then(d => {
        if (d.content) { this.logContent += d.content; this.logOffset = d.offset; }
        this.logRunning = d.running;
        if (!d.running) this.stopLogPolling();
        if (this.logAutoScroll) this.$nextTick(() => {
          const el = document.getElementById('log-pre'); if (el) el.scrollTop = el.scrollHeight;
        });
      }).catch(() => {});
  },
  switchLog(f) {
    this.logFile = f;
    this.startLogPolling();
  }
}" x-init="if (tab === 'log') startLogPolling()" @tab-change.window="if ($event.detail === 'log') startLogPolling()" class="min-h-screen flex flex-col">

  <!-- Topbar -->
  <header class="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-10">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between h-14">
      <div class="flex items-center gap-2.5">
        <span class="flex items-center justify-center w-8 h-8 bg-blue-600 text-white font-extrabold rounded-lg text-sm">5‰</span>
        <span class="font-semibold text-gray-900 text-sm">Pipeline Admin</span>
        <?php if ($is_running): ?>
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full animate-pulse">
          <span class="w-1.5 h-1.5 bg-green-500 rounded-full"></span>Pipeline attiva
        </span>
        <?php endif; ?>
      </div>
      <form method="POST" class="flex items-center gap-3">
        <input type="hidden" name="action" value="logout">
        <input type="hidden" name="csrf" value="<?= $he($csrf) ?>">
        <a href="/" target="_blank" class="text-xs text-gray-500 hover:text-gray-700 transition-colors">← Sito</a>
        <button type="submit" class="text-xs text-gray-500 hover:text-red-600 transition-colors">Esci</button>
      </form>
    </div>
  </header>

  <!-- Flash message -->
  <?php if ($flash): ?>
  <div class="max-w-7xl mx-auto w-full px-4 sm:px-6 pt-4">
    <div class="px-4 py-3 rounded-lg text-sm <?= $flash[0]==='ok' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200' ?>">
      <?= $he($flash[1]) ?>
    </div>
  </div>
  <?php endif; ?>

  <!-- Tab nav -->
  <div class="bg-white border-b border-gray-200 mt-3">
    <div class="max-w-7xl mx-auto px-4 sm:px-6">
      <div class="flex gap-1 -mb-px overflow-x-auto">
        <?php foreach ([
          'overview'  => 'Panoramica',
          'pipeline'  => 'Pipeline',
          'files'     => 'File',
          'log'       => 'Log',
          'settings'  => 'Impostazioni',
        ] as $t => $l): ?>
        <button @click="tab = '<?= $t ?>'; if('<?= $t ?>' === 'log') $dispatch('tab-change', 'log')"
          :class="tab === '<?= $t ?>' ? 'tab-btn tab-active' : 'tab-btn tab-inactive'">
          <?= $l ?>
        </button>
        <?php endforeach; ?>
      </div>
    </div>
  </div>

  <!-- Tab content -->
  <main class="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6 space-y-6">

    <!-- ─── Tab: Panoramica ─────────────────────────────────────────────────── -->
    <div x-show="tab === 'overview'" x-cloak>
      <!-- Stat cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-white rounded-xl border border-gray-200 p-4">
          <p class="text-xs text-gray-500 mb-1">Database</p>
          <p class="text-lg font-bold <?= $db_ok ? 'text-green-600' : 'text-red-500' ?>">
            <?= $db_ok ? '● Connessa' : '● Errore' ?>
          </p>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 p-4">
          <p class="text-xs text-gray-500 mb-1">Enti totali</p>
          <p class="text-lg font-bold text-gray-900"><?= $enti_count !== null ? number_format((int)$enti_count, 0, ',', '.') : '–' ?></p>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 p-4">
          <p class="text-xs text-gray-500 mb-1">Ultimo anno</p>
          <p class="text-lg font-bold text-gray-900"><?= $he((string)($last_anno ?? '–')) ?></p>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 p-4">
          <p class="text-xs text-gray-500 mb-1">File catalogo</p>
          <p class="text-lg font-bold text-gray-900"><?= $files_count !== null ? (int)$files_count : '–' ?></p>
        </div>
      </div>

      <?php if ($is_running): ?>
      <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between mb-6">
        <div class="flex items-center gap-2.5 text-sm text-amber-800">
          <span class="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></span>
          <strong>Pipeline in esecuzione</strong>
          <span class="text-amber-600">(PID: <?= (int)@file_get_contents(PID_FILE) ?>)</span>
        </div>
        <form method="POST" onsubmit="return confirm('Inviare segnale di terminazione al processo?')">
          <input type="hidden" name="action" value="kill">
          <input type="hidden" name="csrf" value="<?= $he($csrf) ?>">
          <button type="submit" class="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded-lg transition-colors">
            Termina processo
          </button>
        </form>
      </div>
      <?php endif; ?>

      <!-- Ultimi run -->
      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div class="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
          <h2 class="font-semibold text-gray-900 text-sm">Ultimi run pipeline</h2>
          <a href="?tab=pipeline" class="text-xs text-blue-600 hover:underline">Avvia nuova →</a>
        </div>
        <?php if ($recent_runs): ?>
        <div class="overflow-x-auto">
          <table class="min-w-full text-xs">
            <thead>
              <tr class="bg-gray-50 text-gray-500 text-left">
                <th class="px-4 py-2 font-medium">Data</th>
                <th class="px-4 py-2 font-medium">Anni</th>
                <th class="px-4 py-2 font-medium">Step</th>
                <th class="px-4 py-2 font-medium">Righe</th>
                <th class="px-4 py-2 font-medium">Durata</th>
                <th class="px-4 py-2 font-medium">Status</th>
                <th class="px-4 py-2 font-medium">Note</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <?php foreach ($recent_runs as $r): ?>
              <tr class="hover:bg-gray-50">
                <td class="px-4 py-2 whitespace-nowrap text-gray-700"><?= $he(adm_fmt_date($r['run_at'])) ?></td>
                <td class="px-4 py-2 text-gray-600">
                  <?php $anni_arr = json_decode($r['anni_processati'] ?? '[]', true) ?: []; echo $he(implode(', ', $anni_arr) ?: '–'); ?>
                </td>
                <td class="px-4 py-2 text-gray-600">
                  <?php $steps_arr = json_decode($r['steps_eseguiti'] ?? '[]', true) ?: []; echo $he(implode(', ', $steps_arr) ?: '–'); ?>
                </td>
                <td class="px-4 py-2 text-gray-600"><?= $r['righe_totali'] ? number_format((int)$r['righe_totali'], 0, ',', '.') : '–' ?></td>
                <td class="px-4 py-2 text-gray-600"><?= $r['durata_secondi'] ? $r['durata_secondi'] . 's' : '–' ?></td>
                <td class="px-4 py-2"><?= adm_status_badge($r['status'] ?? '') ?></td>
                <td class="px-4 py-2 text-gray-500 max-w-xs truncate"><?= $he($r['note'] ?? '') ?></td>
              </tr>
              <?php endforeach; ?>
            </tbody>
          </table>
        </div>
        <?php else: ?>
        <p class="px-5 py-8 text-center text-sm text-gray-400">Nessun run registrato<?= !$db_ok ? ' (DB non disponibile)' : '' ?>.</p>
        <?php endif; ?>
      </div>
    </div>

    <!-- ─── Tab: Pipeline ──────────────────────────────────────────────────── -->
    <div x-show="tab === 'pipeline'" x-cloak>

      <?php if ($is_running): ?>
      <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6 text-sm text-amber-800">
        ⚠ Una pipeline è già in esecuzione (PID <?= (int)@file_get_contents(PID_FILE) ?>). Vai al tab <a href="?tab=log" class="underline">Log</a> per monitorarla.
      </div>
      <?php endif; ?>

      <!-- Form launch pipeline -->
      <div class="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 class="font-semibold text-gray-900 mb-4 text-sm">Avvia pipeline.py</h2>
        <form method="POST" x-data="{anni: [], anniText: ''}">
          <input type="hidden" name="action" value="launch">
          <input type="hidden" name="csrf" value="<?= $he($csrf) ?>">

          <!-- Anni -->
          <div class="mb-4">
            <label class="block text-xs font-medium text-gray-700 mb-2">Anni (lascia vuoto per tutti)</label>
            <div class="flex flex-wrap gap-1.5 mb-2">
              <?php for ($y = ANNI_MAX; $y >= ANNI_MIN; $y--): ?>
              <button type="button" x-data="{ y: <?= $y ?> }"
                @click="if(anni.includes(y)) { anni = anni.filter(a=>a!==y) } else { anni.push(y); anni.sort((a,b)=>a-b) }"
                :class="anni.includes(<?= $y ?>) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'"
                class="px-2.5 py-1 text-xs rounded border font-medium transition-colors"><?= $y ?></button>
              <?php endfor; ?>
            </div>
            <input type="text" name="anni" :value="anni.join(',')"
              placeholder="oppure scrivi es. 2022,2023" @input="anni=[]"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>

          <!-- Sorgente -->
          <div class="mb-4">
            <label class="block text-xs font-medium text-gray-700 mb-2">Sorgente dati</label>
            <div class="flex gap-4">
              <label class="flex items-center gap-1.5 text-sm cursor-pointer">
                <input type="radio" name="source" value="csv" checked class="text-blue-600"> CSV (default)
              </label>
              <label class="flex items-center gap-1.5 text-sm cursor-pointer">
                <input type="radio" name="source" value="pdf" class="text-blue-600"> PDF
              </label>
            </div>
          </div>

          <!-- Step -->
          <div class="mb-4">
            <label class="block text-xs font-medium text-gray-700 mb-2">Step da eseguire</label>
            <div class="flex flex-wrap gap-3">
              <?php foreach (STEP_LABELS as $sk => $sl): ?>
              <label class="flex items-center gap-1.5 text-sm cursor-pointer">
                <input type="checkbox" name="steps[]" value="<?= $he($sk) ?>" checked class="rounded text-blue-600"> <?= $he($sl) ?>
              </label>
              <?php endforeach; ?>
            </div>
          </div>

          <!-- Opzioni -->
          <div class="mb-5 grid grid-cols-2 sm:grid-cols-3 gap-3">
            <label class="flex items-center gap-1.5 text-sm cursor-pointer">
              <input type="checkbox" name="smart" class="rounded text-blue-600"> Smart mode
            </label>
            <label class="flex items-center gap-1.5 text-sm cursor-pointer">
              <input type="checkbox" name="no_runts" class="rounded text-blue-600"> No RUNTS
            </label>
            <label class="flex items-center gap-1.5 text-sm cursor-pointer">
              <input type="checkbox" name="no_excel_etl" class="rounded text-blue-600"> Solo CSV (no xlsx ETL)
            </label>
            <label class="flex items-center gap-1.5 text-sm cursor-pointer">
              <input type="checkbox" name="no_confronto" class="rounded text-blue-600"> No confronto YoY
            </label>
            <label class="flex items-center gap-1.5 text-sm cursor-pointer">
              <input type="checkbox" name="skip_gsheets" class="rounded text-blue-600"> Skip Google Sheets
            </label>
            <div class="flex items-center gap-1.5">
              <label class="text-sm text-gray-700 whitespace-nowrap">Anno confronto:</label>
              <select name="anno_confronto" class="px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">–</option>
                <?php for ($y = ANNI_MAX; $y >= ANNI_MIN; $y--): ?>
                <option><?= $y ?></option>
                <?php endfor; ?>
              </select>
            </div>
          </div>

          <div class="flex items-center gap-3 flex-wrap">
            <button type="submit" name="report_only" value="" <?= $is_running ? 'disabled' : '' ?>
              class="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors">
              ▶ Avvia pipeline
            </button>
            <button type="submit" name="report_only" value="1" <?= $is_running ? 'disabled' : '' ?>
              class="px-4 py-2 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
              title="Esegue solo lo step 'report' (--report-only): rigenera il report Excel senza riscaricare i dati">
              📊 Solo Report
            </button>
          </div>
        </form>
      </div>

      <!-- DB Updater (collapsible) -->
      <div x-data="{open:false}" class="bg-white rounded-xl border border-gray-200 mb-5">
        <button @click="open=!open" class="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-xl transition-colors">
          <span>Aggiorna DB manualmente (db_updater.py)</span>
          <span x-text="open ? '▲' : '▼'" class="text-gray-400"></span>
        </button>
        <div x-show="open" x-collapse class="border-t border-gray-100 px-5 pb-5 pt-4">
          <form method="POST">
            <input type="hidden" name="action" value="launch_db">
            <input type="hidden" name="csrf" value="<?= $he($csrf) ?>">
            <div class="mb-3">
              <label class="block text-xs font-medium text-gray-700 mb-1">Anni (opzionale, es. 2023,2024)</label>
              <input type="text" name="db_anni" placeholder="Vuoto = tutti"
                class="w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            </div>
            <button type="submit" <?= $is_running ? 'disabled' : '' ?>
              class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors">
              Avvia db_updater
            </button>
          </form>
        </div>
      </div>

      <!-- Reset (collapsible, danger) -->
      <div x-data="{open:false, confirmed:false, solo_db:false}" class="bg-white rounded-xl border border-red-200 mb-5">
        <button @click="open=!open" class="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-red-700 hover:bg-red-50 rounded-xl transition-colors">
          <span>⚠ Reset dati</span>
          <span x-text="open ? '▲' : '▼'" class="text-gray-400"></span>
        </button>
        <div x-show="open" x-collapse class="border-t border-red-100 px-5 pb-5 pt-4 bg-red-50/50 rounded-b-xl">
          <p class="text-xs text-red-700 mb-3 leading-relaxed">
            Questa operazione cancella <strong>tutti i dati</strong>: file in <code>Dati/</code> e le tabelle
            <code>enti</code>, <code>dataset_files</code>, <code>pipeline_runs</code>. L'azione è irreversibile.
          </p>
          <form method="POST" onsubmit="return this.querySelector('[name=confirm_reset]').checked || (alert('Spunta la casella di conferma.'), false)">
            <input type="hidden" name="action" value="reset">
            <input type="hidden" name="csrf" value="<?= $he($csrf) ?>">
            <div class="flex flex-col gap-2 mb-3">
              <label class="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" name="solo_db" x-model="solo_db" class="rounded text-red-600">
                Solo reset DB (non tocca i file su disco)
              </label>
              <label class="flex items-center gap-2 text-sm font-medium text-red-800 cursor-pointer">
                <input type="checkbox" name="confirm_reset" x-model="confirmed" class="rounded text-red-600">
                Confermo di voler cancellare <span x-text="solo_db ? 'i dati DB' : 'tutto'"></span>
              </label>
            </div>
            <button type="submit" :disabled="!confirmed || <?= $is_running ? 'true' : 'false' ?>"
              class="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors">
              Esegui reset
            </button>
          </form>
        </div>
      </div>
    </div>

    <!-- ─── Tab: File ──────────────────────────────────────────────────────── -->
    <div x-show="tab === 'files'" x-cloak>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

        <!-- Dati/ tree -->
        <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div class="px-5 py-3 border-b border-gray-100 bg-gray-50">
            <h2 class="font-semibold text-gray-900 text-sm">Cartella Dati/</h2>
          </div>
          <div class="p-3">
            <?php if ($dati_tree): ?>
            <div class="divide-y divide-gray-50">
              <?php foreach ($dati_tree as $item): ?>
              <?php if ($item['is_dir']): ?>
              <details class="group">
                <summary class="flex items-center justify-between px-2 py-1.5 cursor-pointer hover:bg-gray-50 rounded text-xs select-none">
                  <span class="flex items-center gap-1.5">
                    <span class="text-gray-400 group-open:rotate-90 transition-transform inline-block">▶</span>
                    <span class="font-medium text-gray-700">📁 <?= $he($item['name']) ?></span>
                  </span>
                  <span class="text-gray-400"><?= $item['sub_count'] ?> file · <?= adm_fmt_bytes($item['sub_size']) ?></span>
                </summary>
                <div class="pl-6 py-1">
                  <?php foreach (glob(DATI_DIR . '/' . $item['name'] . '/*') ?: [] as $sf): ?>
                  <?php if (!is_file($sf)) continue; ?>
                  <div class="flex items-center justify-between px-2 py-1 text-xs text-gray-600 hover:bg-gray-50 rounded">
                    <span class="truncate max-w-xs"><?= $he(basename($sf)) ?></span>
                    <span class="text-gray-400 ml-2 whitespace-nowrap"><?= adm_fmt_bytes(filesize($sf)) ?></span>
                  </div>
                  <?php endforeach; ?>
                </div>
              </details>
              <?php else: ?>
              <div class="flex items-center justify-between px-2 py-1.5 text-xs hover:bg-gray-50 rounded">
                <div class="flex items-center gap-1.5 min-w-0">
                  <?php $ec = match($item['ext']) { 'xlsx' => 'text-green-700 bg-green-50', 'csv' => 'text-blue-700 bg-blue-50', default => 'text-gray-600 bg-gray-100' }; ?>
                  <span class="px-1.5 py-0.5 rounded text-xs font-medium <?= $ec ?>"><?= $he($item['ext'] ?: 'file') ?></span>
                  <span class="text-gray-700 truncate"><?= $he($item['name']) ?></span>
                </div>
                <div class="text-right ml-2 whitespace-nowrap text-gray-400">
                  <div><?= adm_fmt_bytes($item['size']) ?></div>
                  <div><?= date('d/m/y', $item['mtime']) ?></div>
                </div>
              </div>
              <?php endif; ?>
              <?php endforeach; ?>
            </div>
            <?php else: ?>
            <p class="text-xs text-gray-400 text-center py-6">Cartella Dati/ vuota o non trovata.</p>
            <?php endif; ?>
          </div>
        </div>

        <!-- Log files -->
        <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div class="px-5 py-3 border-b border-gray-100 bg-gray-50">
            <h2 class="font-semibold text-gray-900 text-sm">Log files (log/)</h2>
          </div>
          <div class="p-3">
            <?php if ($log_files): ?>
            <div class="divide-y divide-gray-50">
              <?php foreach ($log_files as $lf): ?>
              <?php $lname = basename($lf); $lsize = filesize($lf); $lmtime = filemtime($lf); ?>
              <div class="flex items-center justify-between px-2 py-1.5 text-xs hover:bg-gray-50 rounded">
                <span class="text-gray-700 truncate flex-1"><?= $he($lname) ?></span>
                <div class="text-right ml-3 whitespace-nowrap text-gray-400 flex items-center gap-3">
                  <span><?= adm_fmt_bytes($lsize) ?></span>
                  <span><?= date('d/m/y H:i', $lmtime) ?></span>
                  <button @click="tab='log'; logFile=<?= htmlspecialchars("'" . addslashes($lf) . "'", ENT_QUOTES) ?>; startLogPolling(); $dispatch('tab-change', 'log')"
                    class="text-blue-600 hover:underline">Apri</button>
                </div>
              </div>
              <?php endforeach; ?>
            </div>
            <?php else: ?>
            <p class="text-xs text-gray-400 text-center py-6">Nessun log file trovato.</p>
            <?php endif; ?>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── Tab: Log ───────────────────────────────────────────────────────── -->
    <div x-show="tab === 'log'" x-cloak class="flex flex-col gap-4">

      <!-- Controls -->
      <div class="bg-white rounded-xl border border-gray-200 px-4 py-3 flex flex-wrap items-center gap-3">
        <!-- Log selector -->
        <select x-model="logFile" @change="startLogPolling()"
          class="px-3 py-1.5 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 max-w-xs flex-1">
          <?php foreach ($log_files as $lf): ?>
          <option value="<?= $he($lf) ?>" <?= $lf === $active_log ? 'selected' : '' ?>><?= $he(basename($lf)) ?></option>
          <?php endforeach; ?>
          <?php if (!$log_files): ?><option value="">Nessun log disponibile</option><?php endif; ?>
        </select>

        <!-- LIVE badge -->
        <span x-show="logRunning" class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full animate-pulse">
          <span class="w-1.5 h-1.5 bg-green-500 rounded-full"></span>LIVE
        </span>
        <span x-show="!logRunning" class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-gray-100 text-gray-500 text-xs font-medium rounded-full">
          Completato
        </span>

        <!-- Auto-scroll toggle -->
        <label class="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
          <input type="checkbox" x-model="logAutoScroll" class="rounded text-blue-600"> Auto-scroll
        </label>

        <!-- Download -->
        <a :href="logFile ? 'admin.php?action=get_log&file=' + encodeURIComponent(logFile) + '&offset=0&download=1' : '#'"
          :download="logFile ? logFile.split('/').pop() : ''"
          class="px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors">
          ⬇ Scarica
        </a>

        <!-- Copy -->
        <button @click="navigator.clipboard.writeText(logContent).then(()=>alert('Copiato!'))"
          class="px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors">
          ⎘ Copia
        </button>

        <!-- Refresh -->
        <button @click="startLogPolling()"
          class="px-3 py-1.5 text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors">
          ↻ Ricarica
        </button>
      </div>

      <!-- Log viewer -->
      <div class="bg-[#0d1117] rounded-xl border border-gray-800 overflow-hidden flex flex-col" style="height:65vh">
        <pre id="log-pre" class="log-view flex-1 overflow-y-auto p-4 text-green-300" x-text="logContent || '(log vuoto o non ancora disponibile)'"></pre>
      </div>
    </div>

    <!-- ─── Tab: Impostazioni ──────────────────────────────────────────────── -->
    <div x-show="tab === 'settings'" x-cloak class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <!-- Cambia password -->
      <div class="bg-white rounded-xl border border-gray-200 p-5">
        <h2 class="font-semibold text-gray-900 text-sm mb-4">Cambia password</h2>
        <form method="POST">
          <input type="hidden" name="action" value="change_pw">
          <input type="hidden" name="csrf" value="<?= $he($csrf) ?>">
          <div class="space-y-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Nuova password (min. 8 caratteri)</label>
              <input type="password" name="password" required minlength="8"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Conferma password</label>
              <input type="password" name="password2" required minlength="8"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            </div>
            <button type="submit" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
              Aggiorna password
            </button>
          </div>
        </form>
      </div>

      <!-- Info sistema -->
      <div class="bg-white rounded-xl border border-gray-200 p-5">
        <h2 class="font-semibold text-gray-900 text-sm mb-4">Informazioni sistema</h2>
        <dl class="space-y-2 text-xs">
          <?php foreach ([
            'PROJECT_ROOT' => PROJECT_ROOT,
            'DATI_DIR'     => DATI_DIR,
            'LOG_DIR'      => LOG_DIR,
            'ENV_FILE'     => ENV_FILE,
            'Python usato' => $venv_info['python'],
            'Venv source'  => $venv_info['source'],
            'PHP version'  => phpversion(),
            'DB host'      => getenv('SITE_DB_HOST') ?: 'localhost',
            'DB name'      => getenv('SITE_DB_NAME') ?: '(non configurato)',
            'DB status'    => $db_ok ? '✓ Connessa' : '✗ Errore connessione',
            'shell_exec'   => function_exists('shell_exec') ? '✓ disponibile' : '✗ disabilitata',
            'posix_kill'   => function_exists('posix_kill') ? '✓ disponibile' : '✗ non disponibile',
          ] as $k => $v): ?>
          <div class="flex justify-between gap-3">
            <dt class="text-gray-500 font-medium shrink-0"><?= $he($k) ?></dt>
            <dd class="text-gray-700 font-mono truncate text-right"><?= $he((string)$v) ?></dd>
          </div>
          <?php endforeach; ?>
        </dl>
      </div>

      <!-- Venv card (span 2 cols on lg) -->
      <div class="bg-white rounded-xl border border-gray-200 p-5 lg:col-span-2">
        <h2 class="font-semibold text-gray-900 text-sm mb-1">Ambiente Python (venv)</h2>
        <p class="text-xs text-gray-500 mb-4">
          Il pannello cerca automaticamente un venv in <code>PROJECT_ROOT/venv</code> o <code>.venv</code>,
          oppure usa <code>VENV_PATH</code> / <code>PYTHON_CMD</code> dal file <code>.env</code>.
        </p>

        <?php
        $venv_exists = $venv_info['exists'] && $venv_info['path'];
        $venv_path   = $venv_info['path'] ?: PROJECT_ROOT . '/venv';
        $req_exists  = is_file(PROJECT_ROOT . '/requirements.txt');
        ?>

        <!-- Stato attuale -->
        <div class="flex items-center gap-3 mb-4 p-3 rounded-lg <?= $venv_exists ? 'bg-green-50 border border-green-200' : 'bg-amber-50 border border-amber-200' ?>">
          <span class="text-lg"><?= $venv_exists ? '✅' : '⚠️' ?></span>
          <div class="text-xs">
            <?php if ($venv_exists): ?>
              <p class="font-medium text-green-800">Venv trovato: <code class="font-mono"><?= $he($venv_info['path']) ?></code></p>
              <p class="text-green-700">Python: <code class="font-mono"><?= $he($venv_info['python']) ?></code> &nbsp;·&nbsp; Rilevato via: <?= $he($venv_info['source']) ?></p>
            <?php else: ?>
              <p class="font-medium text-amber-800">Nessun venv trovato — verrà usato <code class="font-mono"><?= $he($venv_info['python']) ?></code> (sistema)</p>
              <p class="text-amber-700">Se mancano dipendenze Python, crea il venv qui sotto.</p>
            <?php endif; ?>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <!-- Crea / Ricrea venv -->
          <div class="border border-gray-200 rounded-lg p-4">
            <p class="text-xs font-medium text-gray-700 mb-1">
              <?= $venv_exists ? 'Ricrea venv + reinstalla dipendenze' : 'Crea venv e installa dipendenze' ?>
            </p>
            <p class="text-xs text-gray-500 mb-3">
              Esegue <code>python3 -m venv <?= $he($venv_path) ?></code>
              <?= $req_exists ? ' e poi <code>pip install -r requirements.txt</code>' : ' (requirements.txt non trovato)' ?>.
              Il log è visibile nel tab Log.
            </p>
            <form method="POST">
              <input type="hidden" name="action" value="setup_venv">
              <input type="hidden" name="csrf" value="<?= $he($csrf) ?>">
              <?php if ($venv_exists): ?>
              <label class="flex items-center gap-1.5 text-xs text-red-700 mb-2 cursor-pointer">
                <input type="checkbox" required class="rounded text-red-600">
                Confermo di voler sovrascrivere il venv esistente
              </label>
              <?php endif; ?>
              <button type="submit" <?= $is_running ? 'disabled' : '' ?>
                class="px-4 py-2 <?= $venv_exists ? 'bg-orange-500 hover:bg-orange-600' : 'bg-blue-600 hover:bg-blue-700' ?> disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors">
                <?= $venv_exists ? '🔄 Ricrea venv' : '⚙ Crea venv' ?>
              </button>
            </form>
          </div>

          <!-- Override VENV_PATH -->
          <div class="border border-gray-200 rounded-lg p-4">
            <p class="text-xs font-medium text-gray-700 mb-1">Percorso venv personalizzato</p>
            <p class="text-xs text-gray-500 mb-3">
              Imposta <code>VENV_PATH</code> in <code>.env</code> per usare un venv in un percorso
              diverso dalla root del progetto. Lascia vuoto per auto-detect.
            </p>
            <form method="POST">
              <input type="hidden" name="action" value="set_venv_path">
              <input type="hidden" name="csrf" value="<?= $he($csrf) ?>">
              <div class="flex gap-2">
                <input type="text" name="venv_path"
                  value="<?= $he(getenv('VENV_PATH') ?: '') ?>"
                  placeholder="/percorso/assoluto/venv"
                  class="flex-1 px-2 py-1.5 border border-gray-300 rounded text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500">
                <button type="submit"
                  class="px-3 py-1.5 bg-gray-600 hover:bg-gray-700 text-white text-xs font-medium rounded transition-colors">
                  Salva
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>

  </main>
</div>

<?php endif; ?>
</body>
</html>

