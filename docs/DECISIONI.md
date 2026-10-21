# Decisioni confermate e assunzioni esplicite

Le risposte dell'utente del 19 ottobre 2026 prevalgono sulle restrizioni e sugli esempi dei mockup.

## Confermato dall'utente

- Una singola struttura alla volta; configurazione adattabile dalle impostazioni.
- Prima versione con il maggior numero possibile di funzionalità descritte.
- Grafica dei mockup approvata come riferimento.
- Planning con prenotazioni future, cancellazioni, cambi camera, proroghe e day use.
- Camere, tipologie e capienza configurabili prima dell'uso; nessuna numerazione di 38 camere assunta dal prototipo.
- Listino di base per stagione e trattamento e possibilità di sovrascrivere il prezzo al check-in.
- Pagamenti interni con acconti, metodi misti, parziali, rimborsi e saldo dopo il check-out.
- Gruppo con referente unico; assegnazione predefinita del gruppo alla camera, modificabile sul singolo soggiorno. Addebiti camera ed extra confluiscono nel conto del referente del gruppo.
- Operatori con pieno controllo del gestionale: le restrizioni Admin/Operatore dei prototipi non sono applicate alle funzioni operative.
- Turni con apertura, chiusura e conteggio del contante accumulato.

## Scelte implementative dichiarate

Queste scelte rendono il nucleo operativo; non sono risposte implicite alle domande ancora aperte.

- Una cassa fisica aperta alla volta per struttura; i movimenti conservano l'autore effettivo anche quando più operatori lavorano nello stesso turno.
- Euro, italiano, Europe/Rome come impostazione iniziale.
- Listino configurabile per camera/notte o persona/notte. Importi gestionali lordi; nessuna elaborazione fiscale o trasmissione esterna automatica.
- Allocazioni pagamenti deterministiche per data/ID degli addebiti, con possibilità di selezionare camera, extra o intero conto; per gruppo ripartizione tra soggiorni collegati.
- Gli acconti vengono registrati a fronte degli addebiti del soggiorno già calcolati; niente credito non assegnato o pagamento superiore al debito.
- Nessuna cancellazione irreversibile di incassi: rimborsi e storni tracciati.
- Modifiche agli addebiti camera già pagati richiedono prima la rettifica dei pagamenti, per preservare la coerenza del conto.
- Accesso con account creati nel gestionale e sessione cookie; primo account inizializzato da variabili di ambiente con password generata casualmente.
- Articoli magazzino con unità base configurabile e quantità decimali; scarichi non possono creare giacenze negative.
- Assegnazione camera su intervalli temporali; day use con ingresso e uscita nello stesso giorno e orari effettivi distinti.
- Installazione locale di verifica su porta 18080; porte 80/8080 già occupate da un'altra applicazione esistente, che viene conservata.

## Informazioni ancora da ricevere

Resta pendente la terza sezione del questionario originale: dati e documenti ospiti, integrazioni/fiscalità, importazioni ed esportazioni specifiche, hosting/dominio, carico, recupero password/2FA/SMTP, strategia backup, unità e fornitori magazzino, linee guida aziendali. Il nucleo non simula integrazioni non definite.

Questa consegna non comporta pubblicazione su internet, attivazione di collegamenti esterni o migrazione di dati reali.
