import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-license-expired',
  imports: [RouterLink],
  template: `<section class="card max-w-2xl">
    <h1 class="page-title">Licenza non attiva</h1>
    <p class="my-5 text-slate-600">
      La licenza è scaduta o è stata disattivata. Contatta il superadmin per riattivare l'accesso
      alla piattaforma. I dati sono conservati.
    </p>
    @if (auth.isSuperadmin()) {
      <a class="btn" routerLink="/superadmin">Gestisci licenza</a>
    } @else {
      <a class="btn-secondary" routerLink="/dashboard">Verifica nuovamente</a>
    }
  </section>`,
})
export class LicenseExpiredComponent {
  readonly auth = inject(AuthService);
}
