# Verifica della prima versione

## Pannello Django riservato — 21 ottobre 2026

- Suite completa di **68 test backend su PostgreSQL superata**, inclusi 6 test
  dedicati al pannello Django e i test dei privilegi applicativi.
- Accesso `/admin/` consentito solo agli account attivi con ruolo `superadmin`;
  login diretto e sessioni esistenti verificati. Staff, superuser Django e
  permessi sui modelli non aggirano il controllo per admin e operatori.
- Verificati revoca dopo declassamento/disattivazione, protezione CSRF e divieto
  server di aggiunte, modifiche ed eliminazioni dei dati dal pannello.
- Build backend, controlli Django, coerenza migrazioni, Ruff e configurazione
  Nginx superati. Tutti i servizi locali risultano healthy.
- Test browser `scripts/browser-django-admin.cjs` superato: login reale,
  caricamento CSS tramite Nginx, elenco e scheda utenti in consultazione,
  assenza comandi di modifica, logout condiviso con la piattaforma e protezione
  delle pagine dopo il logout. Anteprima `.local/qa/django-admin-desktop.png`
  verificata. Superato anche lo smoke HTTP di sessioni, API, CSRF e routing.
- Migrazioni Django admin applicate dopo backup in
  `backups/hotel-20261021-102832.dump`. Nessuna password o dato gestionale
  modificato durante le prove nel browser.

## Aggiornamento ruoli e superadmin — 21 ottobre 2026

- Suite completa di 60 test backend su PostgreSQL superata; dopo gli ultimi
  perfezionamenti del ripristino, superata anche la suite mirata di 9 test
  superadmin (incluso un nuovo test della matrice operatore/cataloghi).
- Verificati: separazione privilegi, blocco delle promozioni non autorizzate,
  protezione del proprio account, licenza inclusiva nel fuso della struttura,
  riattivazione, rifiuto di backup alterati o di altra installazione, password e
  conferma del ripristino, limitazione dei tentativi.
- Ripristino e ritorno alla copia di sicurezza provati su tutti i dati demo,
  con confronto dei campi, precisione completa dei timestamp e conservazione di
  account, licenza e audit. In caso di errore verificato il rollback. Gli ID
  generati dopo il ripristino non riutilizzano gli ID già emessi.
- 10 test frontend, TypeScript, ESLint, Ruff, build Angular e immagini Docker
  superati; migrazioni coerenti, controlli Django e Nginx superati.
- Test HTTP reale di routing, sessioni e CSRF superato. Smoke browser su 11
  sezioni esistenti superato; test aggiuntivo `scripts/browser-superadmin.cjs`
  su pagina superadmin, tre opzioni ruolo, download firmato, pulsante ripristino
  disabilitato senza conferme, desktop e mobile senza overflow superato.
  Schermate in `.local/qa/superadmin-desktop.png` e `superadmin-mobile.png`.
- Migrazione 0007 applicata all'installazione locale dopo backup PostgreSQL in
  `backups/hotel-20261021-093718.dump`. Il precedente superutente è ora
  superadmin; password conservata. Nessun ripristino o modifica della scadenza
  è stato eseguito sul database operativo durante la verifica nel browser.

I ripristini sono stati provati nel database di test separato. Il test browser
usa la licenza attiva senza scadenza dell'installazione locale e non simula
guasti hardware o perdita dei segreti. Limiti e formati in
[Ruoli e superadmin](RUOLI-E-SUPERADMIN.md).

Data: 19 ottobre 2026. Ambiente: Windows, Docker Desktop con container Linux; browser Chrome in modalita headless; applicazione raggiunta attraverso Nginx.

## Verifiche superate

- Build Docker frontend e backend, con dipendenze bloccate e immagini di base fissate a digest.
- Quattro servizi operativi e healthcheck positivi; unica porta pubblicata dal progetto: 127.0.0.1:18080 sul gateway. La rete dati PostgreSQL e interna.
- Script completo di avvio ripetuto su installazione gia inizializzata: `.env`, credenziali e utenti esistenti conservati; migrazioni coerenti.
- Django system check e `makemigrations --check --dry-run` senza problemi.
- **44 test backend su PostgreSQL reale**, senza skip: disponibilita concorrente, vincoli database, tariffe e prezzi storici, gruppi, pagamenti parziali, idempotenza, rimborsi, partenza con credito, cassa, entrate manuali, scorte, autenticazione/CSRF, report, email, cambio dell'ora, data/ora consumazione, migrazione storica, raggruppamento giornaliero e download PDF. Anche la rimozione del database di test termina correttamente.
- Ruff backend, ESLint frontend e TypeScript strict senza errori.
- **10 test frontend** su periodi inclusivi/esclusivi, cambio dell'ora, segmenti camera, conversione consumazioni nel fuso struttura e riutilizzo delle chiavi di pagamento dopo errori di rete.
- Build Angular produzione circa 320 kB iniziali, circa 87 kB stimati compressi; funzionalita caricate con rotte lazy. Non e una misura dei tempi di risposta sotto carico.
- Controllo HTML di build: CSS caricato senza handler inline incompatibili con CSP.
- Test HTTP del gateway: routing SPA, health, accesso alle risorse, cookie sessione, CSRF su login e logout, protezione degli endpoint e header HTTP.
- Browser desktop: login, dieci sezioni, assenza di errori JavaScript/API e stili Tailwind effettivamente applicati. Browser mobile a 390 px: dashboard senza overflow orizzontale. Logout e protezione delle rotte verificati.
- Dump PostgreSQL in formato custom e ripristino in un database temporaneo separato, con verifica delle migrazioni; database di prova rimosso.

## Test del flusso gestionale

Lo script `scripts/run-browser-workflow.ps1` usa un progetto Docker separato su localhost:18081 e un database inizialmente vuoto. Il percorso verifica configurazione camera e tariffa dall'interfaccia, apertura turno, check-in, extra libero, pagamenti misti/parziali, partenza con credito, saldo successivo, rimborso, entrata e uscita manuali, conteggio fisico e chiusura con differenza di cassa. La suite confronta i risultati con le API e il report; le schermate sono in `.local/qa/`. I dati dell'installazione su18080 non vengono usati per questi movimenti.

**Esito finale: superato.** La chiusura turno e stata verificata anche lasciando vuote le note facoltative. Sul conto da110 EUR sono stati registrati60 EUR contanti e50 EUR carta, con partenza prima del saldo, rimborso20 EUR, entrata manuale20 EUR e spesa10 EUR; il report conferma130 EUR entrate,30 EUR uscite e20 EUR di credito residuo. Fondo50 EUR: contante atteso100 EUR; conteggio fisico98 EUR: differenza-2 EUR. Il progetto temporaneo e il suo volume sono stati rimossi dopo la prova.

## Aggiornamento extra

Aggiornamento extra: il test browser inserisce una consumazione alle08:15, verifica la data/ora restituita dall'API e la colonna nel conto, scarica il PDF dal pulsante e controlla il contenuto PDF. Verificato separatamente un estratto sintetico di tre pagine, con anteprima di tutte le pagine: raggruppamenti di tre giorni, ore, caratteri accentati, euro, uno storno e totale175,00EUR corretti. La migrazione0004 conserva l'ora di registrazione degli extra preesistenti come ora consumo disponibile; un backup e stato salvato prima di applicarla ai dati operativi.

## Limiti della verifica

Non sono stati eseguiti test di carico con piu postazioni reali, una verifica su hosting pubblico o un collaudo con dati della struttura. Non sono implementate integrazioni esterne, adempimenti fiscali, invio email o recupero password automatico, per i quali mancano ancora specifiche. L'audit e la gestione degli incassi sono gestionali; non sostituiscono documenti fiscali.
