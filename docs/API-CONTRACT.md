# Contratto di integrazione iniziale

Le scelte ricevute il 19/10/2026 prevalgono sui prototipi: singola struttura configurabile, tutti i flussi planning, listino stagionale/trattamento con override al check-in, referente unico gruppo, pagamenti e rettifiche interni, accesso completo dell'operatore alle funzioni operative, turni di cassa con conteggio contanti.

Base URL `/api/v1/`. Autenticazione sessione Django con CSRF. API JSON snake_case; date ISO, timestamp ISO con offset, denaro stringa decimale; ID interi. Liste `{count, results}`; frontend supporta questa struttura. Errori `{detail, code?, fields?}` oppure errori serializer DRF per campo. Cookie CSRF `csrftoken`, header `X-CSRFToken`.

## Risorse condivise

- GET `auth/csrf/`, POST `auth/login/` `{email,password}`, POST `auth/logout/`, GET `auth/me/`: utente `{id,email,first_name,last_name,role}`.
- GET/PATCH `settings/`: singola struttura `{name,address,phone,email,check_in_time,check_out_time,currency,timezone}`. Creata al primo avvio, camere create dall'utente senza 38 camere arbitrarie.
- `rooms/`, `rooms/{id}/`: GET/POST/PATCH, `{id,number,floor,room_type,capacity,is_active,default_group}`; default_group è ID gruppo nullable, proposta modificabile per ciascun soggiorno. Disattivazione con controlli su prenotazioni future.
- `groups/`, `groups/{id}/`: `{id,name,label,color,reference_name,reference_email,reference_phone,is_active}`; GET `groups/{id}/statement/`: `{group,stays,total,paid,balance,charges,payments}`.
- `rates/`: `{id,name,room_type,board,start_date,end_date,amount,basis,is_active}`; basis `room`/`person`, board `RO`/`BB`/`HB`/`FB`; periodi inclusivi nel listino e priorità non ambigua. POST `stays/quote/` con gli stessi dati di creazione restituisce `{total,nights,lines}`.
- `extra-categories/`: categorie configurabili del listino: `{id,name,is_active}`. DELETE
  `extra-categories/{id}/` è riservato agli amministratori e richiede che la categoria non abbia extra collegati.
- `price-items/`: `{id,description,category,category_name,unit,price,is_active}`. L'identificativo
  tecnico `id` è generato dal database; il catalogo si può filtrare con `?category=<id>`. DELETE
  `price-items/{id}/` è riservato agli amministratori e conserva lo storico degli addebiti già registrati.
- `cash/reasons/`: `{id,name,direction,is_active}`; direction `in`/`out`.
- `stays/`, `stays/{id}/`: `{id,room,room_number,guest_name,guest_email,guest_phone,guest_count,board,group,group_name,group_color,group_label,arrival,departure,status,is_day_use,nightly_rate,notes,total,paid,balance,room_balance,extras_balance}`. arrival/departure sono timestamp ISO; status `reserved`/`checked_in`/`checked_out`/`cancelled`/`no_show`; nightly_rate override nullable. `{room,guest_name,guest_count,board,group,arrival,departure,is_day_use,nightly_rate,notes}` in scrittura. Se gruppo omesso usa default camera; null esplicito resta individuale.
- POST `stays/{id}/check-in/` `{nightly_rate?}`; POST `stays/{id}/check-out/`; POST `stays/{id}/cancel/`; POST `stays/{id}/no-show/`; POST `stays/{id}/move/` `{room,effective_at}`; POST `stays/{id}/extend/` `{departure}`. Le azioni sono validate e transazionali: il check-out richiede saldo zero per gli operatori; admin e superadmin possono autorizzarlo con residuo, con importo tracciato nel registro attività.
- GET `planning/?start=YYYY-MM-DD&end=YYYY-MM-DD`: `{rooms,stays,groups}`; include intervalli che intersecano periodo; eventuali segmenti dei trasferimenti documentati nel payload.
- GET `dashboard/`: KPI `{rooms_total,rooms_occupied,arrivals_today,departures_today,outstanding,income_today,low_stock_count}` e liste `arrivals`/`departures` filtrate nel giorno locale della struttura, senza caricare lo storico nel frontend. Arrivi: `reserved` e `checked_in`; partenze: `reserved`, `checked_in` e `checked_out`, coerenti con i relativi contatori.
- `stays/{id}/charges/`: GET/POST `{id,stay,kind,description,quantity,unit_price,amount,paid,balance,consumed_at,created_at,created_by}`; POST `{price_item?,description?,quantity,unit_price?,consumed_at?}` crea extra con prezzo storico e data/ora consumazione ISO con offset (default: ora server). `created_at` resta la registrazione di audit. Gli extra preesistenti usano la data di registrazione come consumazione nota; kind `room`/`extra`, consumazione null per camera. Storno POST `charges/{id}/void/` `{reason}`; non cancellare gli storici.
- GET `stays/{id}/extras/pdf/` e `groups/{id}/extras/pdf/`: download autenticato `application/pdf`, extra ordinati per consumazione e raggruppati per giorno nel fuso struttura. Data, ora, camera, descrizione, quantita, prezzo e importo; subtotali giornalieri e totale finale escludono gli storni, che restano indicati. Nessuna modifica a cassa, pagamenti o soggiorni.
- `payments/`: GET/POST `{id,stay?,group?,amount,method,reason,scope,note,created_at,operator_name,shift,reverses?}`; method `cash`/`card`/`transfer`, scope `all`/`room`/`extra`; pagamento con una sola destinazione stay o group; POST header `Idempotency-Key`. POST `payments/{id}/refund/` `{amount,reason,note}`. Allocazione deterministica alle righe scoperte per data/ID, filtro scope, riferimento unico gruppo.
- `cash/shifts/`: GET, POST apertura `{opening_cash}`; POST `cash/shifts/{id}/close/` `{counted_cash,note}`. `{id,operator_name,opened_at,closed_at,opening_cash,expected_cash,counted_cash,difference,status}`. `counted_cash` è il totale fisico di banconote e monete trovato nel cassetto, mentre `difference` viene calcolata come contato meno atteso. Singola cassa fisica/turno aperto per installazione; autore incasso resta utente effettivo. Movimenti contanti richiedono turno aperto e lock sulla sessione.
- `cash/movements/`: GET e POST uscita manuale `{amount,method,reason,description}`; `{id,direction,amount,method,reason,description,operator_name,created_at,shift}`. POST `cash/movements/income/` registra un'entrata manuale con lo stesso payload: richiede una causale attiva di direzione `in`, registra autore e turno e non modifica il saldo di un conto soggiorno/gruppo. Gli incassi dei soggiorni restano nei servizi pagamento.
- `inventory/items/`: GET/POST/PATCH `{id,code,name,unit,quantity,minimum_stock,is_active}`; quantità di sola lettura; unità base libera. `inventory/movements/`: GET/POST `{item,direction,quantity,reason}`; direction `in`/`out`, niente stock negativo. La risposta del movimento include `quantity_after`, la giacenza aggiornata dell'articolo. Rettifiche come movimenti tracciati.
- GET `reports/`: filtri `start,end,operator,method,shift,direction` (fine esclusa); `{income,expenses,balance,outstanding,occupancy,operators,by_operator_shift,movements,movements_count}`. `by_operator_shift` contiene `{operator_id,operator_name,shift,day,movements_count,room_income,extra_income,income,expenses,balance}`. Le prime1000 righe movimenti sono visualizzate; export CSV completo GET `reports/export/` con stessi filtri.
- `users/`: gestione utenti con password solo scrittura, riservata ad admin e superadmin. Ruoli `operator`, `admin`, `superadmin`; solo un superadmin può creare o modificare account superadmin. Nessuno può cambiare il proprio ruolo o disattivare il proprio account.
- GET `audit-events/`: registro riservato agli amministratori, filtrabile con `?actor=<id>` e
  `?action=<testo>`. Restituisce `{id,actor,actor_name,actor_email,action,action_label,object_type,object_id,object_label,data,created_at}` per tutte le operazioni tracciate, incluse sessioni, configurazione, soggiorni, addebiti, pagamenti, cassa e magazzino.
- GET `backup/export/`: archivio ZIP JSON riservato agli amministratori. Contiene tutti i modelli
  applicativi del gestionale, inclusi utenti, configurazione, storico e registro attività, per la
  conservazione locale. Ogni esportazione viene tracciata nel registro attività.

Le integrazioni esterne, documenti ospite, fiscalità, email e la destinazione di installazione restano da chiarire. Non implementare integrazioni simulate. Interfaccia in italiano, euro, Europe/Rome come default configurabile; prezzi lordi gestionali, nessuna fatturazione fiscale implicita.

I privilegi per configurazione, licenza e ripristino sono descritti in
[Ruoli e superadmin](RUOLI-E-SUPERADMIN.md), inclusi gli endpoint `superadmin/`
e `license/`. Gli operatori conservano la lettura dei cataloghi; le modifiche a
struttura, camere, tariffe, categorie, extra di catalogo e causali richiedono
admin o superadmin. Le operazioni su soggiorni, cassa, gruppi e magazzino restano
operative. A licenza inattiva le API gestionali rispondono 403 con codice
`license_inactive`, eccetto per i superadmin. L'archivio ZIP `backup/export/`
è un'esportazione amministrativa e non è il formato firmato del ripristino.
