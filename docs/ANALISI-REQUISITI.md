# Hotel Tempio V2 — Analisi dei requisiti

Data: 19 ottobre 2026. Stato: analisi iniziale aggiornata dalle risposte riportate in [DECISIONI.md](DECISIONI.md). La terza sezione del questionario resta aperta.

## Materiale esaminato

- `scheda-funzionalita-a4.html`: riferimento funzionale principale.
- `index.html`: hub di presentazione.
- Tutte le pagine HTML di `mockup/` e `wireframes/`, relativi CSS e script di navigazione.

Sono presenti 19 schermate per ciascuna serie di prototipi. Sono rappresentazioni statiche: il login sceglie il ruolo in sessionStorage in base al testo dell'email; non esistono autenticazione effettiva, API, database o persistenza dei dati operativi. Le schermate meno sviluppate, come alcuni form di utenti, causali e magazzino, richiedono una specifica funzionale ulteriore.

Non sono stati trovati file AGENTS.md o documenti di convenzioni di sviluppo nella cartella. I prototipi originali vengono conservati. Le convenzioni proposte sono nel documento ARCHITETTURA.md e non sostituiscono eventuali linee guida aziendali da fornire.

## Funzioni esplicite

| Area | Funzioni e dati | Permessi espliciti |
| --- | --- | --- |
| Accesso | Email, password, Admin e Operatore | Due ruoli |
| Dashboard | Occupazione, partenze, debiti, incassi, extra, scorte, arrivi e gruppi | Visibilità dei dati economici da chiarire |
| Planning | Camere × giorni; libero/occupato/gruppo; colore e etichetta gruppo; icone pagamento camera ed extra | Admin e Operatore |
| Check-in | Camera, arrivo, partenza prevista, referente, PAX, trattamento HB/BB/RO/FB, tariffa, gruppo, etichetta, note; scheda e lista recenti | Admin e Operatore |
| Soggiorno | Riepilogo conto; extra con quantità, prezzo, data e ora; incasso camera o extra durante il soggiorno | Admin e Operatore |
| Check-out | Conto camera ed extra; pagamento totale, parziale o da pagare; causale; registrazione incasso in cassa | Admin e Operatore |
| Gruppi | Colore univoco, etichetta; conto aggregato e dettaglio per camera; incasso unico o parziale | Configurazione Admin; uso Operatore |
| Listino | Codice, descrizione, categoria, prezzo, unità pz/giorno/forfait, stato attivo | Scrittura Admin; consultazione operativa necessaria |
| Causali | Nome, incasso/spesa, attiva/disattiva | Configurazione Admin |
| Cassa | Incassi dai soggiorni; uscite manuali; data, ora, operatore, turno, causale, riferimento; filtri e totali | Permessi di lettura e uscite da chiarire |
| Report | Occupazione, extra venduti, debiti, saldo; incassi per data, operatore e turno | Alcune sezioni sono Admin nel mockup |
| Magazzino | Articoli pulizia/lavanderia, codice, unità, giacenza, scorta minima; carico/scarico e alert | Admin e Operatore |
| Utenti | Nome, email, ruolo; amministrazione account | Admin nel mockup |
| Impostazioni | Camere, gruppi, colori, etichette rapide | Admin |

## Incongruenze riscontrate

1. **Durata e tariffa:** check-in 25/08/2026 e partenza 10/10/2026 significano 46 notti; il conto riporta 15 notti × 24 € = 360 €. Con 46 notti il calcolo semplice sarebbe 1.104 €. Non si può dedurre la regola tariffaria dalle cifre dimostrative.
2. **Conto gruppo:** gli extra visibili sono 5 + 35 + 8 + 12 = 60 €, mentre riepilogo e residuo indicano 142 €. Mancano righe per 82 €, oppure il riepilogo è da correggere.
3. **Report:** una riga indica camera 360 €, extra 0 €, totale 545 €. La ripartizione non spiega 185 €.
4. **Cassa e crediti:** una riga di extra da pagare è classificata come incasso senza data/ora e operatore completi. Un credito non deve aumentare gli incassi effettivi. Si propone una vista crediti separata o un elenco combinato con totali inequivocabili.
5. **Causali e metodi:** Extra, Soggiorno e Caparra sono mescolati con Contanti, POS e Bonifico. Si propone di mantenere separati motivo economico e metodo di pagamento.
6. **Operatore dell'incasso:** nel mockup è selezionabile liberamente. Si propone di ricavare l'autore dalla sessione e distinguere un eventuale operatore attribuito, modificabile solo con autorizzazione e audit.
7. **Camere:** il testo «38 camere · numerazione 201–304» non identifica le 38 camere reali, le capienze o le tipologie.
8. **Magazzino:** «Detergente multiuso 5L» ha giacenza 3 e unità lt: non è chiaro se siano 3 confezioni o 3 litri. Il form movimenti non contiene ancora una quantità.
9. **Permessi:** il nuovo check-in propone «+ Nuovo gruppo», ma la scheda riserva le impostazioni dei gruppi ad Admin.
10. **Turni:** sono rappresentate etichette Mattina/Pomeriggio/Notte, ma non orari, gestione notturna o chiusure contabili; 11:20 è indicato come Pomeriggio in una riga dimostrativa.
11. **Attribuzione degli extra:** la camera 203 ha 60 € nella scheda individuale, ma nel conto gruppo solo 43 €; caffè e parcheggio sono attribuiti ad altre camere. Il conto aggregato deve usare gli stessi addebiti della scheda camera.
12. **Disponibilità e scorte:** la camera 202 ha partenza prevista a settembre nella lista check-in ma risulta occupata in ottobre; il giorno in cui torna libera varia fra mockup e wireframe. La dashboard indica 2 articoli sotto scorta, l'elenco ne mostra 3 includendo l'esaurito: va definito il conteggio dei KPI.

## Questionario di definizione

Le domande identificano informazioni mancanti; non sono richieste di autorizzazione per il lavoro già commissionato. È possibile rispondere per numero e delegare esplicitamente le scelte tecniche.

1. **Struttura e perimetro:** solo Hotel Tempio o più hotel? Tutte le funzioni della scheda nella prima consegna? Vi sono priorità o una scadenza?
2. **Interfaccia e dispositivi:** mantenere palette viola, sidebar e impostazione dei mockup? Desktop reception, tablet e/o smartphone? Browser o requisiti di accessibilità specifici? Solo italiano, euro e fuso Europe/Rome?
3. **Camere e occupazione:** elenco effettivo, piani, tipologie e capienze? Servono camere fuori servizio, stato pulizia o letti assegnabili separatamente?
4. **Ciclo del soggiorno:** solo check-in immediati o anche prenotazioni, cancellazioni/no-show, cambi camera, proroghe, partenza anticipata e day use? Servono drag-and-drop e aggiornamenti tra operatori in tempo reale? La camera torna disponibile il giorno di partenza?
5. **Tariffe:** prezzo per camera/notte o persona/notte? Prezzo costante, stagionale o giornaliero? Trattamenti, convenzioni, sconti, bambini, forfait, IVA e tassa di soggiorno influenzano il conto? Chi può modificarli e fino a quando?
6. **Pagamenti:** acconti all'ingresso, incassi durante il soggiorno, metodi misti, pagamenti parziali, rimborsi e storni? È ammesso check-out senza saldo? Come si registra un pagamento ricevuto dopo la partenza? È consentito retrodatare e a chi?
7. **Gruppi:** chi è il debitore, il singolo ospite o un ente/organizzatore? Il gruppo è un'anagrafica riutilizzabile o una singola comitiva? Può comprendere soggiorni di periodi diversi? Colore univoco sempre o solo tra gruppi contemporaneamente presenti? Come si assegnano importi parziali a camere ed extra? Serve distinguere ente che paga la camera e ospite che paga gli extra?
8. **Ruoli e rettifiche:** gli operatori possono leggere tutti i movimenti/report o solo i propri? Registrare uscite, creare articoli, variare prezzi, modificare extra e dati ospite? Chi può stornare, riaprire o correggere operazioni chiuse?
9. **Turni e quadratura:** turni da fascia oraria o sessioni aperte/chiuse da ciascun operatore? Servono fondo cassa, conteggio contanti, differenze, consegna cassa e distinzione del giorno contabile a cavallo della mezzanotte?
10. **Ospiti e documenti:** basta referente e PAX o anagrafiche individuali con documenti, cittadinanza e indirizzi? Servono allegati? Quali tempi di conservazione e procedure di accesso/cancellazione sono già definiti dalla struttura?
11. **Integrazioni:** solo contabilità gestionale interna o anche ricevute/fatture e collegamenti a software fiscali, Alloggiati Web, ISTAT, tassa di soggiorno, booking/channel manager o terminale POS? Per ciascuna: quale servizio e quale formato/API?
12. **Magazzino:** quantità e soglie oppure anche confezioni e conversione in litri, fornitori, costi, inventari, rettifiche e collegamento alle spese? Scorte negative consentite? Alert solo in dashboard o anche notifiche?
13. **Dati e output:** esistono file o database da importare? Quali stampe del conto camera/gruppo e quali esportazioni CSV, Excel o PDF? Quali filtri, periodi e formule dei KPI/report sono necessari?
14. **Installazione e carico:** PC Windows con Docker Desktop, server LAN o VPS Linux? Dominio e HTTPS già disponibili? Numero di utenti contemporanei, accesso da internet e necessità di operare senza connessione internet?
15. **Accesso e continuità:** account creati dall'Admin o altro sistema? Recupero password via email, SMTP disponibile, 2FA o SSO? Frequenza, conservazione e destinazione backup? Quanta perdita dati e quanto tempo di ripristino sono accettabili?
16. **Convenzioni e consegna:** esistono linee guida aziendali ulteriori? Preferenze su repository Git, CI, librerie UI e licenze commerciali? In alternativa si propone solo software open source, convenzioni ufficiali Angular/Django, linting e test dei flussi critici.

## Sequenza di implementazione proposta

1. Consolidare risposte, permessi, esempi di tariffazione e criteri di accettazione.
2. Creare struttura frontend/backend, configurazione ambienti, rete Docker, reverse proxy e autenticazione.
3. Implementare camere, gruppi, anagrafiche, planning e check-in.
4. Implementare listino, conti, allocazioni dei pagamenti, check-out e cassa come un unico flusso verificabile.
5. Implementare magazzino, report e amministrazione.
6. Eseguire test su PostgreSQL, build Angular, verifica Docker, flussi end-to-end e procedura di backup/ripristino.

## Stato dell'ambiente

La prima verifica del PATH non individuava gli strumenti. La ricerca successiva ha trovato Node/npm, Python e Docker Desktop gia installati; il motore Docker Linux e attivo. I test e le build sono stati eseguiti con percorsi espliciti e tramite i container. E stato creato un ambiente virtuale Python locale `.venv`; nessuna installazione di sistema e stata necessaria. Gli script PowerShell cercano Docker anche nei percorsi usuali di Docker Desktop.

## Stato della consegna

Il nucleo applicativo e stato implementato e avviato in quattro container separati. Sono presenti frontend Angular, backend Django APIView e PostgreSQL con migrazioni, suite di test e script operativi. Le decisioni confermate sono in DECISIONI.md, i contratti in API-CONTRACT.md, le istruzioni e i limiti nel README principale. La terza sezione del questionario resta aperta; integrazioni esterne e fiscalita non definite non sono simulate.
