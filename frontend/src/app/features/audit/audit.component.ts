import { Component, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage } from '../../core/api.service';
import { AuditEvent, User } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';
import { HotelDateTimePipe } from '../../shared/hotel-date-time.pipe';

@Component({
  selector: 'app-audit',
  imports: [FeedbackComponent, HotelDateTimePipe],
  template: `<div class="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="page-title">Registro attività</h1>
        <p class="subtitle">Operazioni eseguite dagli operatori, con data e ora.</p>
      </div>
      <button class="btn-secondary" [disabled]="loading()" (click)="load()">Aggiorna</button>
    </div>
    <section class="card">
      <div class="mb-5 flex flex-wrap items-end gap-3">
        <label class="field w-full max-w-sm"
          >Operatore
          <select class="control" [value]="operatorId()" (change)="changeOperator($event)">
            <option value="">Tutti gli operatori</option>
            @for (operator of operators(); track operator.id) {
              <option [value]="operator.id">
                {{ operator.first_name || operator.email }} {{ operator.last_name }}
              </option>
            }
          </select>
        </label>
      </div>
      <app-feedback [loading]="loading()" [error]="error()" />
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Data e ora</th>
              <th>Operatore</th>
              <th>Operazione</th>
              <th>Elemento</th>
              <th>Dettagli</th>
            </tr>
          </thead>
          <tbody>
            @for (event of events(); track event.id) {
              <tr>
                <td class="whitespace-nowrap">{{ event.created_at | hotelDateTime }}</td>
                <td>{{ event.actor_name }}</td>
                <td>{{ event.action_label }}</td>
                <td>{{ event.object_label }}</td>
                <td>{{ detail(event) }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="5" class="py-8 text-center text-slate-500">
                  Nessuna operazione registrata.
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>`,
})
export class AuditComponent {
  private readonly api = inject(ApiService);
  readonly events = signal<AuditEvent[]>([]);
  readonly operators = signal<User[]>([]);
  readonly operatorId = signal('');
  readonly loading = signal(false);
  readonly error = signal('');

  constructor() {
    void this.loadOperators();
    void this.load();
  }

  async loadOperators() {
    try {
      this.operators.set(await firstValueFrom(this.api.list<User>('users/')));
    } catch (error) {
      this.error.set(errorMessage(error));
    }
  }

  changeOperator(event: Event) {
    this.operatorId.set((event.target as HTMLSelectElement).value);
    void this.load();
  }

  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const actor = this.operatorId();
      this.events.set(
        await firstValueFrom(this.api.list<AuditEvent>('audit-events/', actor ? { actor } : {})),
      );
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  detail(event: AuditEvent) {
    const label = event.data['label'];
    if (typeof label === 'string') return label;
    const fields = event.data['fields'];
    if (Array.isArray(fields)) return `Campi modificati: ${fields.join(', ')}`;
    const reason = event.data['reason'];
    if (typeof reason === 'string') return `Motivo: ${reason}`;
    const difference = event.data['difference'];
    if (typeof difference === 'string') return `Differenza cassa: ${difference} €`;
    const outstandingBalance = event.data['outstanding_balance'];
    if (typeof outstandingBalance === 'string')
      return `Saldo residuo autorizzato: ${outstandingBalance} €`;
    return '—';
  }
}
