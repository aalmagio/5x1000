# Procedura di aggiornamento dati 5x1000

Due attività ricorrenti: **aggiunta di un nuovo anno** e **aggiornamento di anni già pubblicati**. Entrambe seguono lo stesso schema: tutto il lavoro si fa su **dev5x1000** (sviluppo) e solo alla fine i dati verificati passano su **5x1000** (produzione) con una sincronizzazione. Durante il lavoro il sito di produzione non viene toccato; il passaggio finale è uno scambio atomico di tabelle, con fermo dell'ordine di millisecondi e rollback disponibile.

## Siti e cartelle

| | Sviluppo | Produzione |
|---|---|---|
| Sito | dev5x1000.almagioni.com | 5x1000.almagioni.com (alias dati5x1000.assif.it) |
| Root progetto (script, `Dati/`, `.env`) | `<home>/dev5x1000.almagioni.com` | `<home>/5x1000.almagioni.com` |
| Webroot | `.../dev5x1000.almagioni.com/site/public` | `.../5x1000.almagioni.com/site/public` |
| File scaricabili | `Dati/` di sviluppo | `Dati/_release/<data_ora>/` di produzione |

`<home>` è la cartella home della sottoscrizione Plesk che contiene i due siti. Tutto si esegue **via SSH sul server, dalla root di sviluppo**. Le due root sono cartelle sorelle, perciò in `config.yaml` i percorsi della sezione `sync:` sono relativi, ad esempio `../5x1000.almagioni.com/...`. La cartella delle release sta dentro `Dati/` di produzione perché `api.php` serve solo file che si trovano sotto quella cartella.

> **Da verificare alla prima esecuzione**
>
> 1. **Codice aggiornato in sviluppo**: `guida.py`, `verifica.py`, `sync.py`, `db_updater.py` e `config.yaml` (sezione `sync:`) devono essere presenti nella root di sviluppo. Al momento non sono ancora committati.
> 2. **`Dati/` di sviluppo completo**: la Guida aggiorna un anno alla volta dentro `Dati/enti_5x1000_norm.csv`, che contiene tutti gli anni. Se la cartella di sviluppo non ha i dati di tutti gli anni, va copiata una volta da produzione (`cp -a ../5x1000.almagioni.com/Dati ./Dati`, se `Dati/` di sviluppo è vuota).
> 3. **DB di sviluppo allineato a produzione**: `python sync.py --stato` deve mostrare gli stessi conteggi. Se in sviluppo manca un anno presente in produzione, la sync si blocca; in quel caso serve una copia iniziale del DB di produzione in sviluppo (export/import da Plesk).
> 4. **Uscita verso AdE dal server**: download e controllo novità girano sul server. _Si presume che il server raggiunga agenzia entrate e i siti di categoria_, ma non è stato verificato.
> 5. **Prima sync reale**: `sync.py` è stato provato solo su un MySQL 8.4 locale. La prima volta va eseguito in un orario tranquillo, partendo da `--stato`.

---

## 0. Preparazione

### Una volta sola: `.env` della root di sviluppo

- `SITE_DB_*` puntate al **database di dev5x1000**. La Guida pubblica sempre su `SITE_DB_*`: se puntassero alla produzione, si scavalcherebbe tutto il processo.
- `PROD_DB_HOST`, `PROD_DB_PORT`, `PROD_DB_USER`, `PROD_DB_PASSWORD`, `PROD_DB_NAME`: gli stessi valori delle `SITE_DB_*` nel `.env` della root di produzione. L'utente deve avere i privilegi CREATE, INSERT, ALTER e DROP; `sync.py` li verifica prima di iniziare.

Il `.env` di produzione resta com'è: serve al sito di produzione.

Regola fissa: **non pubblicare mai direttamente in produzione** (niente `db_updater.py`, `pipeline.py` o Guida lanciati dalla root di produzione). Se la produzione viene modificata fuori da `sync.py`, la sync successiva sovrascrive quelle modifiche con i dati di sviluppo.

### A ogni sessione

Collegarsi in SSH al server Plesk, poi:

```
cd ~/dev5x1000.almagioni.com
python sync.py --stato
```

Se la pipeline sul server usa un venv, va attivato prima di eseguire i comandi.

`--stato` mostra le righe di ogni tabella in sviluppo e in produzione, quando è stata fatta l'ultima sync e se il rollback è disponibile. Prima di iniziare le due colonne dovrebbero coincidere. Se non coincidono, la sessione precedente non è stata sincronizzata: va chiarito prima di procedere.

---

## 1. Aggiunta di un nuovo anno

### Cosa serve prima di iniziare

- Il link della pagina AdE con l'**elenco complessivo** dell'anno, cioè la pagina che elenca i file PDF/CSV, non il singolo file.
- I link delle pagine AdE per **categoria** (ETS/Volontariato, ASD, Ricerca scientifica, Ricerca sanitaria, Comuni, Beni culturali, Aree protette). Si possono inserire anche in seguito con l'aggiornamento.

### Passi su dev5x1000

1. Avviare `python guida.py`. Nell'intestazione controllare che compaia **"DB del sito: raggiungibile"** e che il DB sia quello di sviluppo.
2. Scegliere **1 - Aggiungi un nuovo anno**. La Guida propone l'anno successivo all'ultimo configurato; confermarlo o correggerlo.
3. Incollare il link dell'elenco complessivo. La Guida conta i PDF e i CSV trovati: se sono zero, il link è sbagliato e lo richiede.
4. Inserire i link delle categorie disponibili.
5. Confermare la registrazione in `config.yaml` e `categorie.xlsx`. Di entrambi viene salvata una copia in `_archivio/config`.
6. Confermare l'avvio dei 10 passi. La Guida scarica, estrae ed esegue l'ETL. Si ferma e chiede conferma solo in due casi:
   - **Controllo 1** (dati estratti): segnala anomalie nei dati estratti. Per un anno nuovo non esiste una versione precedente, quindi il confronto è solo con i CSV grezzi AdE.
   - **Controllo 2** (CSV normalizzato): blocca sempre se l'ETL ha alterato le righe di altri anni.

   Se un passo fallisce, i file vengono ripristinati automaticamente e il DB non viene toccato.
7. Alla domanda **"Pubblico l'anno sul sito?"** rispondere sì. L'anno viene scritto nel DB di sviluppo in un'unica transazione, poi vengono aggiornati ripartizioni, RUNTS, catalogo file e forecast.
8. Leggere il **riepilogo finale** e il report di verifica in `Dati/verifiche/verifica_<data>.xlsx`. Le righe gialle sono differenze da capire prima di andare avanti.

### Controllo sul sito dev5x1000

Aprire dev5x1000 e controllare a mano che:

- il nuovo anno compaia nei filtri;
- i totali (enti, scelte, importi) siano plausibili rispetto all'anno precedente;
- la scheda di qualche ente noto sia corretta;
- la pagina Download e il forecast siano aggiornati.

_Se il frontend ha liste di anni o testi legati all'anno scritti nel codice, vanno aggiornati e pubblicati separatamente: `sync.py` non sincronizza il codice._

### Passaggio in produzione

Vedi la sezione 3.

---

## 2. Aggiornamento di anni esistenti

AdE ripubblica periodicamente gli elenchi di anni passati. Si possono aggiornare più anni in sviluppo e poi fare **una sola sincronizzazione**.

### Passi su dev5x1000

1. Avviare `python guida.py` e controllare che **"DB del sito: raggiungibile"** si riferisca allo sviluppo.
2. Scegliere **2 - Aggiorna un anno esistente**.
3. Accettare il controllo delle novità su AdE. La tabella mostra, per ogni anno, i file online, quelli locali e quelli nuovi. Gli anni con file nuovi sono segnati con `<-- novità`.
4. Indicare l'anno da aggiornare. La Guida mostra i link di categoria registrati e permette di aggiungere quelli mancanti.
5. Confermare l'avvio. I passi sono gli stessi dell'aggiunta, con una differenza nel **Controllo 1**: qui il nuovo estratto viene confrontato anche con la versione precedente. Viene segnalato se il numero di enti, le scelte o gli importi cambiano di oltre il 5%, o di oltre il 10% su una singola categoria. Un aggiornamento AdE normale produce variazioni contenute: una variazione forte va capita prima di confermare.
6. Rispondere sì a **"Pubblico l'anno sul sito?"**. In sviluppo l'anno viene sostituito (DELETE+INSERT in transazione). Se il numero di enti scritti non coincide con l'atteso, viene eseguito il ROLLBACK e restano i dati precedenti.
7. Controllare il riepilogo e il report di verifica.
8. Ripetere dal passo 2 per ogni altro anno con novità.

Per un controllo complessivo prima della sync, usare la voce **3 - Verifica dati** sugli anni toccati (_stima indicata dalla Guida: 2-3 minuti per anno_). Equivale a:

```
python verifica.py --anni 2024,2023
```

### Controllo sul sito dev5x1000

Per ogni anno aggiornato, confrontare con la produzione i totali e alcune schede ente. Il report di verifica dice già se DB, CSV e file AdE coincidono; il controllo sul sito serve a vedere che le pagine mostrino i nuovi dati.

### Passaggio in produzione

Vedi la sezione 3.

---

## 3. Sincronizzazione dev5x1000 -> 5x1000

Si esegue con `python sync.py`, oppure dalla Guida con la voce **5 - Sincronizza sviluppo -> produzione**.

1. **Anteprima**: `python sync.py --stato`. Le tabelle in sviluppo devono avere i nuovi conteggi.
2. **Sync**: `python sync.py`, da eseguire nella root di sviluppo.
   - **Controlli**: la sync si blocca se i due DB coincidono, se lo schema delle tabelle differisce o se un anno presente in produzione manca in sviluppo. Le variazioni oltre il 5% per anno vengono mostrate come avvisi e chiedono conferma. Per un anno nuovo non compaiono avvisi; per un anno aggiornato sono le stesse variazioni già viste al Controllo 1.
   - **Copia**: le tabelle cambiate vengono copiate in produzione come `<tabella>__new` e verificate (conteggi e totali per anno). Il sito resta online e mostra i dati vecchi.
   - **File**: i file scaricabili vengono copiati in una nuova release, con controllo SHA-256.
   - **Conferma**: va digitato il nome del database di produzione. Qualunque altra risposta annulla e lascia la produzione invariata.
   - **Scambio**: un unico `RENAME TABLE` mette in linea tutte le tabelle insieme. Poi viene svuotata la cache `nlq_cache` e viene sostituito `forecast.json`.
   - **Controllo finale**: conteggi, totali per anno, viste.
3. **Controllo sul sito 5x1000**: ripetere gli stessi controlli fatti su dev5x1000.
4. **Se qualcosa non va**: `python sync.py --rollback`. Rimette in linea tabelle, file e forecast precedenti. Rieseguito, torna alla versione nuova.
5. **Pulizia**, quando i dati in produzione sono confermati: `python sync.py --pulisci`. Elimina le tabelle `*__old` e le release di file più vecchie. Fino alla pulizia le tabelle occupano in produzione circa il doppio dello spazio; **dopo la pulizia il rollback non è più possibile**.

Le tabelle `leads` e `nlq_rate_limit`, scritte dal sito di produzione, non vengono mai toccate.

---

## Riferimento rapido

| Attività | Sito interessato | Comando / voce (sempre via SSH dalla root di sviluppo) |
|---|---|---|
| Controllo allineamento | entrambi | `python sync.py --stato` |
| Nuovo anno | dev5x1000 | `python guida.py` -> 1 |
| Aggiornamento anni | dev5x1000 | `python guida.py` -> 2 (ripetere per ogni anno) |
| Verifica dati | dev5x1000 | `python guida.py` -> 3, oppure `python verifica.py --anni ...` |
| Ripubblicare un anno già elaborato | dev5x1000 | `python guida.py` -> 4 |
| Passaggio in produzione | dev -> prod | `python guida.py` -> 5, oppure `python sync.py` |
| Tornare indietro | produzione | `python sync.py --rollback` |
| Liberare spazio | produzione | `python sync.py --pulisci` |

## Cosa fare se...

- **La Guida si ferma prima della pubblicazione**: i file precedenti sono già ripristinati e il DB non è stato toccato. Il motivo è nel log in `log/` e l'archivio resta in `_archivio/<anno>_<data>/`.
- **La pubblicazione in sviluppo fallisce**: è stato eseguito il ROLLBACK e i dati locali sono aggiornati. Dopo aver risolto, usare la voce **4 - Ripubblica un anno**.
- **"Un'altra esecuzione risulta in corso"**: esiste `Dati/.stato/guida.lock` (di solito dopo un crash). Rispondere sì allo sblocco solo dopo aver verificato che nessuna Guida sia davvero in esecuzione.
- **La sync si ferma prima dello scambio**: la produzione è invariata e le tabelle `__new` create sono state rimosse. Il motivo è nel messaggio e nel log `sync`.
- **La sync si ferma al controllo finale**: lo scambio è già avvenuto. Controllare il sito e, se serve, eseguire `python sync.py --rollback`.
