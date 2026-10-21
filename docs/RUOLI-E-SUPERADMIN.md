# Ruoli, licenza e ripristino

| Funzione | Operatore | Admin | Superadmin |
| --- | --- | --- | --- |
| Planning, soggiorni, gruppi, extra, incassi, cassa, magazzino e report | Sì | Sì | Sì |
| Lettura camere, struttura, listini e causali per il lavoro operativo | Sì | Sì | Sì |
| Modifica struttura, camere, listini, categorie e causali | No | Sì | Sì |
| Gestione account operatore e admin, registro attività | No | Sì | Sì |
| Archivio amministrativo ZIP completo (sola esportazione) | No | Sì | Sì |
| Creazione e modifica di account superadmin | No | No | Sì |
| Esportazione e ripristino backup applicativo | No | No | Sì |
| Abilitazione e scadenza licenza | No | No | Sì |
| Accesso al pannello Django `/admin/` | No | No | Sì, consultazione |

I controlli vengono applicati alle API, oltre a menu e rotte frontend. Nessun
utente può disattivare il proprio account o cambiare il proprio ruolo. Un admin
non può cambiare neppure la password di un superadmin. Quando un superadmin
declassa un altro account, gli eventuali privilegi Django `is_superuser` e
`is_staff` vengono rimossi.

Il primo account creato da `bootstrap` è superadmin. La migrazione 0007 assegna
il ruolo superadmin agli account che avevano già `is_superuser=True`, senza
cambiare password. Gli admin ordinari restano admin.

## Pannello Django

Il pannello è disponibile su `/admin/` e richiede un account attivo con ruolo
esatto `superadmin`, anche quando l'utente è già autenticato nella piattaforma.
Il login diretto applica lo stesso controllo. I flag Django `is_staff`,
`is_superuser` e i permessi assegnati individualmente non permettono a un admin
ordinario o a un operatore di aggirare il controllo. Un superadmin creato dalla
piattaforma può accedere anche senza quei flag. Declassamento e disattivazione
revocano l'accesso già alla richiesta successiva.

Il pannello espone i modelli del gestionale in sola consultazione: aggiunte,
modifiche, eliminazioni e azioni massive sono disabilitate anche sul server.
Le modifiche si eseguono attraverso i flussi della piattaforma, per conservare
lock, audit e controlli gestionali. Hash delle password e contenuti firmati delle
copie di ripristino sono esclusi dalle schede Django. Accessi e uscite vengono
tracciati nel registro attività. Login e operazioni mantengono la protezione CSRF;
il gateway limita i tentativi di login.

Gli asset statici Django vengono raccolti all'avvio del backend nel volume
`django_static` e serviti da Nginx, con mount di sola lettura sul gateway.

## Licenza

La pagina **Superadmin** permette di abilitare/disabilitare la licenza e indicare
una data di scadenza. La data include l'intera giornata nel fuso orario della
struttura. Una scadenza vuota indica validità senza limite di data. Le
installazioni esistenti partono con licenza abilitata e senza scadenza.

A licenza scaduta o disabilitata, le API operative di operatori e admin
rispondono 403 con codice `license_inactive`; il frontend mostra una pagina
dedicata. Login, logout, sessione e lettura dello stato licenza restano
disponibili. Il superadmin mantiene accesso per poter rinnovare la licenza,
esportare e ripristinare i dati. Le modifiche della licenza sono registrate nel
registro attività. Non sono previsti server di attivazione o chiavi commerciali:
la licenza è gestita localmente nell'installazione.

## Backup e ripristino dall'interfaccia

1. Aprire **Superadmin → Scarica backup** e conservare il file `.hotel-backup.json`.
2. Per ripristinare, selezionare il file, inserire la propria password e scrivere
   `RIPRISTINA` nel campo di conferma.
3. Il ripristino sostituisce configurazione e dati operativi: struttura, gruppi,
   camere, tariffe, categorie, extra, soggiorni, addebiti, turni, pagamenti,
   allocazioni, movimenti di cassa, magazzino e chiavi di idempotenza.
4. Account, password, ruoli, licenza, sessioni e registro attività non vengono
   ripristinati. Gli account del backup devono ancora corrispondere per ID/email.
5. Prima di ogni ripristino viene salvata nel database una copia dello stato
   corrente, scaricabile da **Copie di sicurezza prima dei ripristini**. Scaricare
   la copia e caricarla nel medesimo form permette di tornare a quello stato.

Il formato è firmato con il segreto dell'installazione. File alterati o firmati
da un'altra installazione vengono rifiutati. Il segreto Django va conservato
insieme ai backup infrastrutturali; cambiarlo rende inutilizzabili le firme
precedenti. I backup contengono dati personali e contabili in chiaro: conservarli
su supporti protetti. Il limite del file è 20 MB. Le copie di sicurezza restano
nel database e l'interfaccia elenca le 100 più recenti.

Esportazione e ripristino acquisiscono lo stesso mutex delle scritture operative.
Il ripristino usa una transazione e verifica i vincoli del database: in caso di
errore, anche la sostituzione dei dati viene annullata. Dopo un ripristino gli
operatori devono ricaricare le schermate prima di proseguire il lavoro.

I file PostgreSQL `.dump` prodotti da `scripts/backup.ps1` mantengono il loro
flusso amministrativo da server e non sono caricabili nel form. Il backup
applicativo non sostituisce il backup completo di database, configurazione e
segreti per il recupero da un guasto dell'installazione.

## Endpoint aggiunti

- `GET /api/v1/license/`: stato licenza, disponibile a ogni utente autenticato.
- `GET/PATCH /api/v1/superadmin/license/`: gestione di `enabled` e `expires_on`.
- `GET /api/v1/superadmin/backup/`: download del backup applicativo firmato.
- `POST /api/v1/superadmin/restore/`: multipart con `file`, `password`,
  `confirmation=RIPRISTINA`; limite 5 tentativi/minuto per utente.
- `GET /api/v1/superadmin/recovery-backups/`: ultime copie di sicurezza.
- `GET /api/v1/superadmin/recovery-backups/<id>/`: download di una copia.

Tutti gli endpoint `superadmin/` richiedono il ruolo superadmin. Le richieste
mutanti mantengono la protezione CSRF della sessione.
