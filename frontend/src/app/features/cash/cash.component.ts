import { Component, computed, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage } from '../../core/api.service';
import { CashMovement, METHODS, Reason, Shift } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';
@Component({
  selector: 'app-cash',
  imports: [CurrencyPipe, DatePipe, ReactiveFormsModule, FeedbackComponent, RouterLink],
  template: `<div class="toolbar">
      <div>
        <h1 class="page-title">Cassa e turni</h1>
        <p class="subtitle">Apertura, movimenti effettivi e conteggio del contante.</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <a class="btn-secondary" routerLink="/report">Filtra movimenti e turni</a
        ><a class="btn-secondary" routerLink="/mance">Consulta mance</a
        ><button class="btn-secondary" (click)="load()" [disabled]="loading()">Aggiorna</button>
      </div>
    </div>
    <app-feedback [loading]="loading()" [error]="error()" [success]="success()" />
    <div class="mb-6 grid gap-6 xl:grid-cols-2">
      <section class="card">
        @if (current(); as shift) {
          <div class="mb-4 flex items-center justify-between">
            <h2 class="font-semibold">Turno #{{ shift.id }} aperto</h2>
            <span class="badge">{{ shift.operator_name }}</span>
          </div>
          <p class="text-sm text-slate-500">Dal {{ shift.opened_at | date: 'dd/MM/yyyy HH:mm' }}</p>
          <div class="my-5 grid grid-cols-2 gap-4">
            <div>
              <p class="text-xs text-slate-400">Fondo iniziale</p>
              <strong class="text-xl">{{ shift.opening_cash | currency: 'EUR' }}</strong>
            </div>
            <div>
              <p class="text-xs text-slate-400">Contante atteso</p>
              <strong class="text-xl text-brand">{{
                shift.expected_cash | currency: 'EUR'
              }}</strong>
            </div>
          </div>
          <form [formGroup]="closeForm" (ngSubmit)="close(shift.id)" class="space-y-4">
            <div
              class="rounded-lg border border-violet-100 bg-violet-50/60 p-3 text-sm text-slate-600"
            >
              <p class="font-medium text-slate-700">Come chiudere il turno</p>
              <p class="mt-1 leading-relaxed">
                Conta banconote e monete realmente presenti nel cassetto e inserisci qui il totale
                fisico. Non inserire la differenza: viene calcolata automaticamente rispetto al
                contante atteso.
              </p>
            </div>
            <label class="field"
              >Totale contante fisico contato (€)<input
                class="control"
                type="number"
                min="0"
                step="0.01"
                formControlName="counted_cash"
            /></label>
            @if (closingDifference(); as difference) {
              <p
                class="rounded-lg px-3 py-2 text-sm"
                [class.bg-emerald-50]="difference.value === 0"
                [class.text-emerald-700]="difference.value === 0"
                [class.bg-amber-50]="difference.value !== 0"
                [class.text-amber-800]="difference.value !== 0"
              >
                {{ difference.label }}:
                <strong>{{ difference.value | currency: 'EUR' }}</strong>
              </p>
            } @else {
              <p class="text-xs text-slate-500">
                Il contante atteso è {{ shift.expected_cash | currency: 'EUR' }}. Inserisci il
                totale contato per visualizzare l'eventuale differenza.
              </p>
            }
            <label class="field"
              >Note chiusura<textarea class="control" formControlName="note" rows="2"></textarea>
            </label>
            <button class="btn" [disabled]="busy() || closeForm.invalid">
              Chiudi turno e registra differenza
            </button>
          </form>
        } @else {
          <h2 class="mb-3 font-semibold">Apri un turno di cassa</h2>
          <p class="mb-5 text-sm leading-relaxed text-slate-500">
            Per registrare movimenti in contanti è necessario aprire un turno. La struttura usa una
            sola cassa fisica condivisa dagli operatori.
          </p>
          <form [formGroup]="openForm" (ngSubmit)="open()" class="space-y-4">
            <label class="field"
              >Fondo iniziale contanti (€)<input
                class="control"
                type="number"
                min="0"
                step="0.01"
                formControlName="opening_cash" /></label
            ><button class="btn" [disabled]="busy() || openForm.invalid">Apri turno</button>
          </form>
        }
      </section>
      <section class="card">
        <h2 class="mb-2 font-semibold">Movimento manuale</h2>
        <div class="mb-4 inline-flex rounded-lg bg-slate-100 p-1 text-sm font-medium">
          <button
            type="button"
            class="rounded-md px-3 py-2 transition-colors"
            [class.bg-white]="movementDirection() === 'in'"
            [class.text-emerald-700]="movementDirection() === 'in'"
            [class.shadow-sm]="movementDirection() === 'in'"
            (click)="setMovementDirection('in')"
          >
            Registra entrata
          </button>
          <button
            type="button"
            class="rounded-md px-3 py-2 transition-colors"
            [class.bg-white]="movementDirection() === 'out'"
            [class.text-red-700]="movementDirection() === 'out'"
            [class.shadow-sm]="movementDirection() === 'out'"
            (click)="setMovementDirection('out')"
          >
            Registra uscita
          </button>
        </div>
        <p class="mb-5 text-xs leading-relaxed text-slate-500">
          @if (movementDirection() === 'in') {
            Usa questa voce per entrate manuali, ad esempio reintegro del fondo o rimborso di una
            spesa. Gli incassi dei soggiorni si registrano dal conto della camera o del gruppo.
          } @else {
            Registra qui prelievi e spese manuali. Gli incassi dei soggiorni si registrano dal conto
            della camera o del gruppo.
          }
        </p>
        <form [formGroup]="movementForm" (ngSubmit)="registerMovement()" class="form-grid">
          <label class="field"
            >Importo (€)<input
              class="control"
              type="number"
              min="0.01"
              step="0.01"
              formControlName="amount" /></label
          ><label class="field"
            >Metodo<select class="control" formControlName="method">
              @for (m of methods; track m.value) {
                <option [value]="m.value">{{ m.label }}</option>
              }
            </select></label
          ><label class="field sm:col-span-2"
            >Causale<select class="control" formControlName="reason">
              <option [ngValue]="null">Seleziona</option>
              @for (r of availableReasons(); track r.id) {
                <option [ngValue]="r.id">{{ r.name }}</option>
              }
            </select>
            @if (!availableReasons().length) {
              <span class="text-xs text-slate-500"
                >Nessuna causale attiva per questo movimento.
                <a class="underline" routerLink="/causali">Crea una causale</a>.</span
              >
            }</label
          ><label class="field sm:col-span-2"
            >Descrizione<input class="control" formControlName="description"
          /></label>
          <div class="sm:col-span-2">
            <button class="btn" [disabled]="busy() || movementForm.invalid">
              Registra {{ movementDirection() === 'in' ? 'entrata' : 'uscita' }}
            </button>
          </div>
        </form>
      </section>
    </div>
    <section class="mb-6">
      <h2 class="mb-3 font-semibold">Storico turni</h2>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Turno / Operatore</th>
              <th>Apertura / Chiusura</th>
              <th>Fondo</th>
              <th>Atteso</th>
              <th>Contato</th>
              <th>Differenza</th>
            </tr>
          </thead>
          <tbody>
            @for (s of shifts(); track s.id) {
              <tr>
                <td>#{{ s.id }} · {{ s.operator_name }}</td>
                <td>
                  {{ s.opened_at | date: 'dd/MM/yy HH:mm' }}<br />{{
                    s.closed_at ? (s.closed_at | date: 'dd/MM/yy HH:mm') : 'Aperto'
                  }}
                </td>
                <td>{{ s.opening_cash | currency: 'EUR' }}</td>
                <td>{{ s.expected_cash | currency: 'EUR' }}</td>
                <td>{{ s.counted_cash === null ? '—' : (s.counted_cash | currency: 'EUR') }}</td>
                <td [class.text-red-600]="s.difference && +s.difference !== 0">
                  {{ s.difference === null ? '—' : (s.difference | currency: 'EUR') }}
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6" class="py-8 text-center text-slate-500">
                  Nessun turno registrato.
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
    <section>
      <h2 class="mb-3 font-semibold">Movimenti di cassa</h2>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Data</th>
              <th>Descrizione / Operatore</th>
              <th>Metodo</th>
              <th>Entrata</th>
              <th>Uscita</th>
            </tr>
          </thead>
          <tbody>
            @for (m of movements(); track m.id) {
              <tr>
                <td>{{ m.created_at | date: 'dd/MM/yy HH:mm' }}</td>
                <td>
                  {{ m.description }}
                  <p class="text-xs text-slate-400">{{ m.operator_name }}</p>
                </td>
                <td>{{ method(m.method) }}</td>
                <td class="text-emerald-600">
                  {{ m.direction === 'in' ? (m.amount | currency: 'EUR') : '—' }}
                </td>
                <td class="text-red-600">
                  {{ m.direction === 'out' ? (m.amount | currency: 'EUR') : '—' }}
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="5" class="py-8 text-center text-slate-500">
                  Nessun movimento registrato.
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>`,
})
export class CashComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  readonly methods = METHODS;
  readonly shifts = signal<Shift[]>([]);
  readonly movements = signal<CashMovement[]>([]);
  readonly reasons = signal<Reason[]>([]);
  readonly current = computed(() => this.shifts().find((s) => !s.closed_at));
  readonly movementDirection = signal<'in' | 'out'>('out');
  readonly availableReasons = computed(() =>
    this.reasons().filter((reason) => reason.direction === this.movementDirection()),
  );
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly openForm = this.fb.group({
    opening_cash: [0, [Validators.required, Validators.min(0)]],
  });
  readonly closeForm = this.fb.group({
    counted_cash: [null as number | null, [Validators.required, Validators.min(0)]],
    note: this.fb.nonNullable.control(''),
  });
  readonly movementForm = this.fb.group({
    amount: [null as number | null, [Validators.required, Validators.min(0.01)]],
    method: ['cash', Validators.required],
    reason: [null as number | null, Validators.required],
    description: ['', Validators.required],
  });
  readonly countedCash = signal<number | null>(null);
  readonly closingDifference = computed(() => {
    const shift = this.current();
    const counted = this.countedCash();
    if (!shift || counted === null || !Number.isFinite(counted)) return null;
    const value = Math.round((counted - Number(shift.expected_cash)) * 100) / 100;
    return {
      value,
      label: value === 0 ? 'Quadratura' : value > 0 ? 'Eccedenza rilevata' : 'Ammanco rilevato',
    };
  });
  constructor() {
    this.closeForm.controls.counted_cash.valueChanges.subscribe((value) =>
      this.countedCash.set(value),
    );
    void this.load();
  }
  method(v: string) {
    return METHODS.find((m) => m.value === v)?.label ?? v;
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const [s, m, r] = await Promise.all([
        firstValueFrom(this.api.list<Shift>('cash/shifts/')),
        firstValueFrom(this.api.list<CashMovement>('cash/movements/')),
        firstValueFrom(this.api.list<Reason>('cash/reasons/')),
      ]);
      this.shifts.set(s);
      this.movements.set(m);
      this.reasons.set(r.filter((x) => x.is_active));
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  async mutate(path: string, body: unknown, message: string) {
    this.busy.set(true);
    this.error.set('');
    this.success.set('');
    try {
      await firstValueFrom(this.api.post(path, body));
      this.success.set(message);
      this.closeForm.reset({ counted_cash: null, note: '' });
      this.movementForm.reset({ amount: null, method: 'cash', reason: null, description: '' });
      await this.load();
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
  open() {
    if (this.openForm.valid)
      void this.mutate(
        'cash/shifts/',
        { opening_cash: String(this.openForm.getRawValue().opening_cash) },
        'Turno di cassa aperto.',
      );
  }
  close(id: number) {
    if (this.closeForm.valid) {
      const v = this.closeForm.getRawValue();
      void this.mutate(
        `cash/shifts/${id}/close/`,
        { ...v, counted_cash: String(v.counted_cash), note: v.note ?? '' },
        'Turno chiuso e conteggio registrato.',
      );
    }
  }
  setMovementDirection(direction: 'in' | 'out') {
    this.movementDirection.set(direction);
    this.movementForm.controls.reason.setValue(null);
  }
  registerMovement() {
    if (this.movementForm.valid) {
      const v = this.movementForm.getRawValue();
      const isIncome = this.movementDirection() === 'in';
      void this.mutate(
        isIncome ? 'cash/movements/income/' : 'cash/movements/',
        { ...v, amount: String(v.amount) },
        isIncome ? 'Entrata registrata.' : 'Uscita registrata.',
      );
    }
  }
}
