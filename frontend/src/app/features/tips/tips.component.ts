import { Component, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage, today } from '../../core/api.service';
import { METHODS, Payment, TipReport } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';

@Component({
  selector: 'app-tips',
  imports: [CurrencyPipe, DatePipe, ReactiveFormsModule, FeedbackComponent],
  template: `<div class="toolbar">
      <div>
        <h1 class="page-title">Mance</h1>
        <p class="subtitle">Riepilogo delle mance registrate con gli incassi, separate dai ricavi.</p>
      </div>
      <button class="btn-secondary" (click)="load()" [disabled]="loading()">Aggiorna</button>
    </div>
    <form [formGroup]="form" (ngSubmit)="load()" class="card mb-5 flex flex-wrap items-end gap-4">
      <label class="field"
        >Periodo<select class="control" formControlName="period">
          <option value="week">Settimana</option>
          <option value="month">Mese</option>
          <option value="year">Anno</option>
        </select></label
      ><label class="field"
        >Data di riferimento<input class="control" type="date" formControlName="date" /></label
      ><button class="btn" [disabled]="loading()">Applica filtri</button>
    </form>
    <app-feedback [loading]="loading()" [error]="error()" />
    @if (data(); as d) {
      <div class="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <section class="card">
          <p class="subtitle">Totale mance</p>
          <strong class="mt-2 block text-3xl text-violet-700">{{ d.total | currency: 'EUR' }}</strong>
        </section>
        <section class="card">
          <p class="subtitle">Registrazioni</p>
          <strong class="mt-2 block text-3xl">{{ d.count }}</strong>
        </section>
        <section class="card">
          <p class="subtitle">Periodo visualizzato</p>
          <strong class="mt-2 block text-lg">{{ d.start_date | date: 'dd/MM/yyyy' }} – {{ d.end_date | date: 'dd/MM/yyyy' }}</strong>
        </section>
      </div>
      <section>
        <h2 class="mb-3 font-semibold">Dettaglio mance</h2>
        @if (d.count > d.payments.length) {
          <p class="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
            Sono mostrate le prime {{ d.payments.length }} registrazioni su {{ d.count }}.
          </p>
        }
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Data e ora</th>
                <th>Operatore</th>
                <th>Conto</th>
                <th>Metodo</th>
                <th>Mancia</th>
              </tr>
            </thead>
            <tbody>
              @for (payment of d.payments; track payment.id) {
                <tr>
                  <td>{{ payment.created_at | date: 'dd/MM/yy HH:mm' }}</td>
                  <td>{{ payment.operator_name }}</td>
                  <td>{{ account(payment) }}</td>
                  <td>{{ method(payment.method) }}</td>
                  <td class="font-semibold text-violet-700">{{ payment.tip_amount | currency: 'EUR' }}</td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="5" class="py-8 text-center text-slate-500">
                    Nessuna mancia nel periodo selezionato.
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>
    }`,
})
export class TipsComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder).nonNullable;
  readonly form = this.fb.group({ period: 'month', date: today() });
  readonly data = signal<TipReport | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');

  constructor() {
    void this.load();
  }

  method(value: string) {
    return METHODS.find((method) => method.value === value)?.label ?? value;
  }

  account(payment: Payment) {
    return payment.group ? `Gruppo #${payment.group}` : `Soggiorno #${payment.stay}`;
  }

  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const value = this.form.getRawValue();
      this.data.set(await firstValueFrom(this.api.get<TipReport>('tips/', value)));
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
}
