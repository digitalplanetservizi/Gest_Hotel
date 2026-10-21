# Frontend Hotel Tempio

Angular 22 standalone, TypeScript strict, Tailwind CSS 4. Nessuna dipendenza da CDN o dati simulati. API relative `/api/v1/` con cookie di sessione Django e CSRF. Tutte le funzionalità sono caricate tramite routing lazy.

## Sviluppo

Node.js 24 LTS e pnpm 11.25.0. Dalla radice avvia `docker compose -f compose.yaml -f compose.dev.yaml up -d --build`. Per il server di sviluppo aggiungi `http://localhost:4200` a `CSRF_TRUSTED_ORIGINS` nel `.env`, mantenendo le origini esistenti, e riavvia il backend. In questa cartella:

```powershell
pnpm install --frozen-lockfile
pnpm start
```

Il proxy inoltra `/api` al backend esposto solo in loopback sulla porta 18000. Il browser usa `http://localhost:4200`, il reverse proxy di produzione usa la porta 18080. Non esporre il server Angular di sviluppo pubblicamente.

```powershell
pnpm check
pnpm test
pnpm lint
pnpm build
```

Il build per Nginx è `dist/hotel/browser`. Budget iniziale massimo 600 kB. Il progetto usa font di sistema, controlli HTML accessibili, signals per lo stato locale e reactive forms. I componenti condivisi gestiscono feedback, conti, pagamenti e form risorse; i servizi del dominio mantengono separate API e presentazione. Gli intervalli API hanno fine esclusiva; le date finali selezionate nell'interfaccia sono inclusive e vengono convertite prima della richiesta.

Prima del primo soggiorno configurare struttura, camere e listino. I pagamenti sono sul conto individuale o sul referente del gruppo; gli incassi contanti richiedono un turno di cassa aperto. Le autorizzazioni e tutti i conteggi sono verificati dal backend.
