import { Component, inject, input, output, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage } from '../core/api.service';
import { RetryIntent } from '../core/retry-intent';
import { Payment, Reason } from '../core/models';
import { FeedbackComponent } from './feedback.component';
@Component({
  selector: 'app-payment-table',
  imports: [CurrencyPipe, DatePipe, ReactiveFormsModule, FeedbackComponent],
  template: `<h2 class="mb-3 font-semibold">Pagamenti e rimborsi</h2>
    <app-feedback [error]="error()" [success]="success()" />
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Data</th>
            <th>Operatore / Metodo</th>
            <th>Importo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (p of payments(); track p.id) {
            <tr>
              <td>
                {{ p.created_at | date: 'dd/MM/yy HH:mm' }}
                <p class="text-xs text-slate-400">{{ p.note }}</p>
              </td>
              <td>
                {{ p.operator_name }}
                <p class="text-xs text-slate-500">
                  {{ kind(p.kind) }} · {{ method(p.method) }} · {{ scope(p.scope) }}
                </p>
              </td>
              <td>
                @if (p.kind === 'tip') {
                  <span class="font-semibold text-violet-700">Mancia {{ p.tip_amount | currency: 'EUR' }}</span>
                } @else {
                  {{ p.amount | currency: 'EUR' }}
                }
                @if (p.kind !== 'tip' && +p.tip_amount > 0) {
                  <p class="mt-1 text-xs font-medium text-violet-700">
                    Mancia {{ p.tip_amount | currency: 'EUR' }}
                  </p>
                }
                @if (p.reverses) {
                  <span class="badge ml-1">Rimborso #{{ p.reverses }}</span>
                }
              </td>
              <td>
                @if (!p.reverses && +p.amount > 0) {
                  <button class="text-xs text-brand hover:underline" (click)="openRefund(p)">
                    Rimborsa
                  </button>
                }
              </td>
            </tr>
          } @empty {
            <tr>
              <td colspan="4" class="py-7 text-center text-slate-500">
                Nessun pagamento registrato.
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
    @if (refund(); as p) {
      <section class="card mt-4 border-amber-200">
        <h3 class="mb-4 font-semibold">Rimborso pagamento #{{ p.id }}</h3>
        <form [formGroup]="form" (ngSubmit)="submit()" class="form-grid">
          <label class="field"
            >Importo da rimborsare<input
              class="control"
              type="number"
              min="0.01"
              [max]="p.amount"
              step="0.01"
              formControlName="amount" /></label
          ><label class="field"
            >Causale<select class="control" formControlName="reason">
              <option [ngValue]="null">Seleziona</option>
              @for (r of reasons(); track r.id) {
                <option [ngValue]="r.id">{{ r.name }}</option>
              }
            </select></label
          ><label class="field sm:col-span-2"
            >Motivo / Nota<input class="control" formControlName="note"
          /></label>
          <div class="flex gap-2 sm:col-span-2">
            <button class="btn-danger" [disabled]="busy() || form.invalid">Conferma rimborso</button
            ><button class="btn-secondary" type="button" (click)="refund.set(null)">Annulla</button>
          </div>
        </form>
      </section>
    }`,
})
export class PaymentTableComponent {
  private readonly intent = new RetryIntent();
  readonly payments = input<Payment[]>([]);
  readonly saved = output<void>();
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  readonly refund = signal<Payment | null>(null);
  readonly reasons = signal<Reason[]>([]);
  readonly error = signal('');
  readonly success = signal('');
  readonly busy = signal(false);
  readonly form = this.fb.group({
    amount: [null as number | null, [Validators.required, Validators.min(0.01)]],
    reason: [null as number | null, Validators.required],
    note: ['', Validators.required],
  });
  method(v: string) {
    return (
      ({ cash: 'Contanti', card: 'Carta', transfer: 'Bonifico' } as Record<string, string>)[v] ?? v
    );
  }
  scope(v: string) {
    return (
      ({ all: 'Camere ed extra', room: 'Camere', extra: 'Extra' } as Record<string, string>)[v] ?? v
    );
  }
  kind(v: Payment['kind']) {
    return v === 'tip' ? 'Solo mancia' : 'Pagamento conto';
  }
  async openRefund(p: Payment) {
    this.refund.set(p);
    this.form.patchValue({ amount: +p.amount, reason: null, note: '' });
    try {
      this.reasons.set(
        (await firstValueFrom(this.api.list<Reason>('cash/reasons/'))).filter(
          (r) => r.is_active && r.direction === 'out',
        ),
      );
    } catch (e) {
      this.error.set(errorMessage(e));
    }
  }
  async submit() {
    if (this.form.invalid || !this.refund()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const v = this.form.getRawValue();
      const body = {
        ...v,
        amount: String(v.amount),
        reason: this.reasons().find((r) => r.id === v.reason)?.name ?? '',
      };
      const path = `payments/${this.refund()!.id}/refund/`;
      await firstValueFrom(this.api.post(path, body, this.intent.forPayload({ path, body })));
      this.intent.succeeded();
      this.refund.set(null);
      this.success.set('Rimborso registrato.');
      this.saved.emit();
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}
