# Hotel Tempio V2

Gestionale per una struttura alla volta, con frontend Angular e backend Django REST separati. I prototipi originali sono conservati in `mockup/` e `wireframes/`.

## Avvio locale Windows

Prerequisito: Docker Desktop avviato con container Linux e Docker Compose. Node e Python sul sistema non sono necessari per avviare le immagini.

Da PowerShell nella cartella del progetto:

```powershell
./scripts/start.ps1
```

Lo script crea `.env` se assente, genera segreti casuali, costruisce le immagini, avvia PostgreSQL, applica le migrazioni, crea il primo account e avvia tutti i servizi. Se `.env` esiste, lo conserva. L'inizializzazione dell'account non deve resettare la password degli utenti già presenti.

Aprire [Hotel Tempio locale](http://localhost:18080). Email e password iniziali sono nei campi `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD` del file locale `.env`. Non esiste una password universale di demo. La porta 18080 evita le porte 80/8080 già usate da un'altra applicazione sul computer.

Per personalizzare primo account e porta prima dell'inizializzazione:

```powershell
./scripts/start.ps1 -AdminEmail reception@example.it -Port 18080
```

Al primo accesso configurare la struttura, creare gruppi con referente se necessari, camere e capienze, tariffe stagionali per trattamento, voci extra e causali. Aprire un turno di cassa prima di registrare movimenti contanti. Nessuna camera e nessun soggiorno dimostrativo sono inseriti automaticamente.

Per esplorare il gestionale con dati completi senza cancellare quelli già presenti, eseguire una sola volta:

```powershell
docker compose run --rm --no-deps backend python manage.py seed_demo
```

Il comando aggiunge camere, listino, gruppi, soggiorni in più stati, extra, incassi, cassa e magazzino. A un secondo avvio riconosce il set demo e non crea duplicati.

Se PowerShell blocca gli script, si può invocare il singolo script con `powershell -ExecutionPolicy Bypass -File ./scripts/start.ps1`; non è necessario cambiare permanentemente la policy del computer.

## Infrastruttura

| Container | Compito | Accesso |
| --- | --- | --- |
| gateway | Nginx reverse proxy, compressione, limiti login e header | Solo ingresso su localhost:18080 |
| frontend | Angular compilato, servito da Nginx senza processo Node in produzione | Rete Docker applicativa |
| backend | Django, APIView DRF, Gunicorn | Rete applicativa e rete dati |
| database | PostgreSQL 17 con volume persistente | Rete dati interna Docker |

Nginx inoltra `/api/` al backend e le altre rotte al frontend con fallback SPA. Il frontend usa URL relativi: cookie e API condividono lo stesso dominio, con sessione HttpOnly e protezione CSRF. Le immagini di base sono fissate a digest; le dipendenze applicative a versioni e lockfile.

Frontend standalone, TypeScript strict, Signals, form reattivi, servizi API tipizzati, componenti UI riutilizzabili e rotte lazy. Tailwind viene compilato, senza CDN. Backend con modelli ORM, serializer, APIView e servizi transazionali espliciti; calcoli Decimal eseguiti sul server. Gli operatori gestiscono le attività quotidiane; gli admin anche configurazione e account ordinari; i superadmin anche backup, ripristino e scadenza della licenza. [Guida ai privilegi e al ripristino](docs/RUOLI-E-SUPERADMIN.md).

## Flussi gestionali

- Struttura e camere configurabili, tipologie/capienze e gruppo predefinito della camera.
- Gruppi con colore, etichetta e referente unico; conto aggregato di camere ed extra.
- Planning per intervallo, prenotazioni, check-in, check-out, cancellazioni, no-show, proroghe, day use e trasferimenti camera tramite segmenti temporali.
- Listino stagionale per trattamento e tipologia, tariffa per camera o persona; preventivo e override della tariffa al check-in.
- Addebiti camera ed extra con prezzo storico, quantità, data e autore; gli aggiornamenti del listino non cambiano i conti già registrati.
- Data e ora consumazione degli extra, modificabili all'inserimento e distinte dall'ora di registrazione; estratto PDF per camera o gruppo con raggruppamento per giorno, subtotali e totale senza storni, nel fuso della struttura. Dal conto usare **Scarica PDF extra**.
- Incassi contanti/carta/bonifico, parziali e misti tramite registrazioni distinte, allocazione a camera/extra/intero conto, rimborsi e credito residuo dopo la partenza.
- Turni di cassa con fondo iniziale, entrate/uscite manuali, saldo atteso, conteggio di chiusura e differenza; carte e bonifici non incrementano il contante fisico. In chiusura si inserisce il totale di banconote e monete nel cassetto, non la differenza.
- Magazzino con unità configurabili, carichi/scarichi tracciati, quantità decimali e alert soglia; scorte negative impedite.
- Dashboard, report e CSV; gestione utenti, causali e listini.

## Regole da conoscere

Una sola cassa fisica/turno aperto per struttura. L'operatore del movimento è sempre quello autenticato; più operatori possono lavorare nel turno. Il contante atteso è fondo iniziale più entrate in contanti meno uscite in contanti: alla chiusura si conta il denaro fisico e il gestionale mostra automaticamente quadratura, eccedenza o ammanco. Le entrate manuali (per esempio un reintegro del fondo) richiedono una causale di entrata e restano separate dagli incassi dei soggiorni. Gli acconti sono pagamenti sul debito del soggiorno già generato: non si registrano importi superiori al saldo dovuto. Per un soggiorno di gruppo, gli incassi vengono registrati sul conto del referente.

I pagamenti si allocano alle voci ancora scoperte secondo data e ID, con filtro camera/extra/tutto. La chiusura del soggiorno e il suo saldo sono indipendenti: il check-out può lasciare un credito senza bloccare la camera. I crediti non riscossi sono esclusi dagli incassi di cassa.

Gli addebiti restano storicizzati; le rettifiche vengono tracciate. Una variazione economica su voci già pagate richiede prima il rimborso/rettifica per evitare di alterare implicitamente le allocazioni. Non si tratta di fatturazione fiscale: IVA analitica, tassa di soggiorno e trasmissioni esterne richiedono specifiche ancora da ricevere.

Le operazioni mutanti sono serializzate per struttura nel database per garantire la coerenza di disponibilità, incassi e scorte. È una scelta adeguata al gestionale di una singola struttura; il carico atteso resta da quantificare. Il mutex applicativo non protegge modifiche SQL manuali esterne al gestionale.

## Verifiche

La versione corrente ha superato 42 test backend su PostgreSQL, 10 test frontend, build/lint/tipizzazione, controlli HTTP, navigazione desktop/mobile, flusso gestionale completo nel browser (inclusi data/ora extra e download PDF) e ripristino backup in un database distinto. Dettagli e limiti: [rapporto di verifica](docs/VERIFICA.md).

Con lo stack avviato:

```powershell
./scripts/verify.ps1
```

Il comando verifica configurazione Compose, controlli Django, corrispondenza migrazioni, suite backend su un database di test PostgreSQL separato e configurazioni Nginx. Il database operativo non viene svuotato dai test Django. La build frontend avviene anche durante la costruzione dell'immagine.

Smoke test HTTP senza modifiche ai dati operativi, con Python 3.12 o successivo:

```powershell
python ./scripts/verify_http.py
```

Verifica routing SPA, risorse API, accesso autenticato, protezione CSRF, sessione e logout attraverso Nginx. Legge le credenziali iniziali da `.env`; dopo averle cambiate usare un account di verifica configurato tramite variabili di ambiente.

Con Node e Chrome installati, gli script browser verificano anche l'interfaccia compilata:

```powershell
npm install --prefix .local/ui --no-save @playwright/test
node ./scripts/browser-smoke.cjs
./scripts/run-browser-workflow.ps1
```

Il primo test accede e naviga dieci sezioni, controlla gli stili Tailwind con CSP, layout mobile e logout, senza creare dati gestionali. Il secondo crea un progetto Docker distinto sulla porta18081 e un database nuovo: configura camera e tariffa tramite interfaccia, apre un turno, esegue check-in, extra libero, pagamenti parziali, check-out con debito, saldo successivo, rimborso, uscita e conteggio. Rimuove soltanto il proprio progetto temporaneo e volume al termine; i dati su18080 restano intatti. Le schermate di verifica sono in `.local/qa/`.

## Sviluppo

Gli endpoint sono documentati in `docs/API-CONTRACT.md`. Le regole ricevute e le assunzioni sono in `docs/DECISIONI.md`.

Per esporre backend e PostgreSQL esclusivamente sul loopback locale:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d
```

Backend: localhost:18000. PostgreSQL: localhost:15432; credenziali in `.env`. Per sviluppo Angular usare Node compatibile con Angular 22, la versione pnpm dichiarata in `frontend/package.json`, `pnpm install --frozen-lockfile` e `pnpm start` dentro `frontend/`. Le origini di sviluppo devono essere incluse esplicitamente in `DJANGO_CSRF_TRUSTED_ORIGINS` se si usa la sessione da localhost:4200.

## Arresto e backup

```powershell
./scripts/backup.ps1
./scripts/verify-backup.ps1
./scripts/stop.ps1
```

`backup` e `verify-backup` richiedono il database avviato. `stop` arresta i servizi e conserva il volume. `backup` crea un dump PostgreSQL consistente in `backups/` senza far transitare output binario nella pipeline PowerShell. La cartella è esclusa dal repository. I backup vanno copiati anche su un supporto separato; frequenza e conservazione dipendono dalle esigenze della struttura.

`verify-backup` crea un dump corrente e lo ripristina in un nuovo database temporaneo con nome casuale, verifica le migrazioni e rimuove esclusivamente quel database di prova. Non modifica il database operativo.

Per un ripristino, verificare prima il dump con `pg_restore --list`, fermare le scritture e ripristinare in un database separato, verificando i dati prima di sostituire il database operativo. Non eseguire `docker compose down -v` sui dati da conservare.

## Punti ancora aperti

Sono ancora da definire dati e documenti ospiti, integrazioni Alloggiati/ISTAT/fatturazione/booking/POS, importazioni reali, stampe specifiche, recupero password/SMTP/2FA, hosting/dominio e politica backup. Queste funzionalità non vengono simulate. La configurazione consegnata è per verifica locale; l'esposizione pubblica richiede dominio, TLS e cookie Secure coerenti con l'ambiente finale.
