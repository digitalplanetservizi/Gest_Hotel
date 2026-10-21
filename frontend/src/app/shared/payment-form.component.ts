import { Component, inject, input, output, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage } from '../core/api.service';
import { RetryIntent } from '../core/retry-intent';
import { METHODS, Reason } from '../core/models';
import { FeedbackComponent } from './feedback.component';
@Component({
  selector: 'app-payment-form',
  imports: [ReactiveFormsModule, FeedbackComponent],
  template: `<section class="card">
    <h2 class="mb-2 font-semibold">Registra incasso</h2>
    <p class="mb-5 text-xs text-slate-500">
      @if (form.controls.kind.value === 'tip') {
        Registra una mancia autonoma, senza modificare il saldo
        {{ groupId() ? 'del gruppo' : 'del soggiorno' }}. Per i contanti è necessario un turno aperto.
      } @else {
        Il pagamento viene ripartito sul debito aperto
        {{ groupId() ? 'del gruppo, intestato al referente unico' : 'del soggiorno' }}. Per i contanti
        è necessario un turno aperto.
      }
    </p>
    <app-feedback [error]="error()" [success]="success()" />
    <form [formGroup]="form" (ngSubmit)="submit()" class="form-grid">
      <label class="field"
        >Tipo incasso<select class="control" formControlName="kind">
          <option value="settlement">Pagamento conto</option>
          <option value="tip">Solo mancia</option>
        </select></label
      ><label class="field"
        >Metodo<select class="control" formControlName="method">
          @for (m of methods; track m.value) {
            <option [value]="m.value">{{ m.label }}</option>
          }
        </select></label
      >@if (form.controls.kind.value === 'tip') {
        <label class="field sm:col-span-2"
          >Importo mancia (€)<input
            class="control"
            type="number"
            min="0.01"
            step="0.01"
            formControlName="tip_amount" /></label
        >
      } @else {
        <label class="field"
          >Importo pagamento (€)<input
            class="control"
            type="number"
            min="0.01"
            step="0.01"
            formControlName="amount" /></label
        ><label class="field"
          >Mancia (€) <span class="text-xs font-normal text-slate-400">facoltativa</span><input
            class="control"
            type="number"
            min="0"
            step="0.01"
            formControlName="tip_amount" /></label
        ><label class="field"
          >Destinazione<select class="control" formControlName="scope">
            <option value="all">Camere ed extra</option>
            <option value="room">Solo camere</option>
            <option value="extra">Solo extra</option>
          </select></label
        >
      }
      ><label class="field"
        >Causale<select class="control" formControlName="reason">
          <option [ngValue]="null">Seleziona causale</option>
          @for (r of reasons(); track r.id) {
            <option [ngValue]="r.id">{{ r.name }}</option>
          }
        </select></label
      ><label class="field sm:col-span-2"
        >Nota<input class="control" formControlName="note"
      /></label>
      <div class="sm:col-span-2">
        <button class="btn" [disabled]="busy() || form.invalid">
          {{ busy() ? 'Registrazione…' : 'Conferma pagamento' }}
        </button>
      </div>
    </form>
  </section>`,
})
export class PaymentFormComponent {
  private readonly intent = new RetryIntent();
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  readonly stayId = input<number | null>(null);
  readonly groupId = input<number | null>(null);
  readonly saved = output<void>();
  readonly methods = METHODS;
  readonly reasons = signal<Reason[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly form = this.fb.group({
    amount: [null as number | null, [Validators.required, Validators.min(0.01)]],
    tip_amount: [0, Validators.min(0)],
    kind: ['settlement', Validators.required],
    method: ['cash', Validators.required],
    scope: ['all', Validators.required],
    reason: [null as number | null, Validators.required],
    note: [''],
  });
  constructor() {
    this.form.controls.kind.valueChanges.subscribe((kind) => this.configureKind(kind));
    void firstValueFrom(this.api.list<Reason>('cash/reasons/'))
      .then((r) => this.reasons.set(r.filter((v) => v.is_active && v.direction === 'in')))
      .catch((e) => this.error.set(errorMessage(e)));
  }
  async submit() {
    if (this.form.invalid) return;
    this.busy.set(true);
    this.error.set('');
    this.success.set('');
    try {
      const v = this.form.getRawValue();
      const body = {
        ...v,
        amount: String(v.amount ?? 0),
        tip_amount: String(v.tip_amount ?? 0),
        reason: this.reasons().find((r) => r.id === v.reason)?.name ?? '',
        ...(this.groupId() ? { group: this.groupId() } : { stay: this.stayId() }),
      };
      await firstValueFrom(this.api.post('payments/', body, this.intent.forPayload(body)));
      this.intent.succeeded();
      this.success.set(v.kind === 'tip' ? 'Mancia registrata.' : +v.tip_amount! > 0 ? 'Pagamento e mancia registrati.' : 'Pagamento registrato.');
      this.form.controls.amount.reset();
      this.form.controls.tip_amount.reset(0);
      this.form.controls.kind.reset('settlement');
      this.form.controls.note.reset('');
      this.saved.emit();
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
  private configureKind(kind: string | null) {
    const amount = this.form.controls.amount;
    const tip = this.form.controls.tip_amount;
    if (kind === 'tip') {
      amount.setValue(0);
      amount.clearValidators();
      tip.setValidators([Validators.required, Validators.min(0.01)]);
    } else {
      amount.setValue(null);
      amount.setValidators([Validators.required, Validators.min(0.01)]);
      tip.setValidators([Validators.min(0)]);
    }
    amount.updateValueAndValidity();
    tip.updateValueAndValidity();
  }
}
