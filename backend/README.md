# Backend Hotel

Python 3.12, Django 5.2 LTS, Django REST Framework. API class-based `APIView`,
sessioni e CSRF sullo stesso dominio del frontend. Tutte le funzioni applicative
richiedono autenticazione; operatori, admin e superadmin hanno privilegi distinti.
Gli operatori gestiscono l'operatività, gli admin anche configurazione e account
ordinari, i superadmin anche backup, ripristino e licenza. Dettagli in
`docs/RUOLI-E-SUPERADMIN.md` alla root.
Le credenziali di bootstrap sono obbligatorie al primo avvio e non sono nel codice.

```sh
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Configurare `DJANGO_SECRET_KEY`, `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`,
`DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`,
`BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`.
In HTTPS impostare `DJANGO_SECURE_COOKIES=1` e
`DJANGO_SECURE_SSL_REDIRECT=1` dietro un proxy fidato.
`DJANGO_TEST_SQLITE=1` abilita esclusivamente smoke test locali: non verifica i lock
e i vincoli PostgreSQL e non va impostato in distribuzione.

```sh
python manage.py check
python manage.py test hotel.tests --verbosity=2
ruff check .
```

`GET /api/v1/health/` esegue un controllo connessione DB. Contratto in
`docs/API-CONTRACT.md` alla root. Liste paginate (100 default, massimo 500);
planning massimo 93 giorni, report massimo 366, `end` esclusivo.
Login: acquisire cookie con `auth/csrf/`, inviare `X-CSRFToken` anche sul login;
dopo login il token ruota, quindi leggere nuovamente il cookie.

Le camere, capienze, tipologie, gruppi e stagioni sono configurabili senza dati
dimostrativi. Le tariffe sono congelate in addebiti giornalieri alla prenotazione.
Gli override sono per camera/giorno, anche se il listino è per persona; day use
richiede un override esplicito o usa una giornata di listino.
La proroga mantiene lo storico e aggiunge giorni; il trasferimento conserva
la tariffa pattuita. Il check-out consente debiti e libera la camera, mantenendo
gli addebiti concordati: non applica riduzioni automatiche per partenza anticipata.
Le correzioni di addebiti incassati richiedono prima il rimborso.

I gruppi hanno un unico referente e conto: i pagamenti vanno al gruppo, allocati
alle righe aperte in ordine data/ID, con filtro camera/extra/tutto. Non si incassano
crediti superiori agli addebiti: gli acconti coprono addebiti già generati. Ogni POST
pagamento/rimborso richiede `Idempotency-Key`, legata ad autore e payload.
Rimborsi sullo stesso metodo originale, con allocazioni negative e movimento
di uscita, senza cancellare lo storico. Extra e soggiorno condividono il referente.

Una singola cassa fisica ha un turno aperto; contanti richiedono quel turno.
Il previsto è fondo iniziale + entrate contanti − uscite contanti; il conteggio
alla chiusura conserva la differenza senza creare incassi artificiali.
Ogni modifica operativa genera audit. Quantità e importi usano Decimal.

Un lock transazionale sulla singola struttura serializza le scritture operative
anche quando le tabelle sono vuote. PostgreSQL aggiunge esclusioni GiST sulle
sovrapposizioni camera e sui listini stagionali. La migrazione richiede il diritto
di creare `btree_gist` (previsto nel container PostgreSQL del progetto).
Test concorrenti verificano prenotazioni, pagamenti e retry effettivi sul DB.

Report: incassi e uscite effettivi per periodo/metodo/operatore, crediti globali
attuali separati dai flussi. Occupazione misurata sui secondi dei segmenti camera
nel periodo; include prenotazioni attive. Non equivale a un report fiscale o ISTAT.
CSV contiene tutti i movimenti filtrati, JSON restituisce al massimo 1000 righe
con contatore totale. Nessuna integrazione fiscale, documentale, email o esterna
è simulata.

`by_operator_shift` nei report offre la quadratura per autore effettivo,
turno (anche nullo per operazioni non in contanti fuori turno) e giorno locale
della struttura. Le entrate sono ripartite tra camera ed extra dalle allocazioni,
senza moltiplicare il totale per il numero di righe; rimborsi e spese contano
solo nelle uscite. I filtri `shift` (ID) e `direction=in|out` si applicano a
report, elenco movimenti ed esportazione CSV. Le email degli account vengono
normalizzate in minuscolo e sono univoche anche senza distinzione maiuscole.
