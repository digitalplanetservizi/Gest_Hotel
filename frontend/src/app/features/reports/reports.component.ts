import { Component, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage, saveBlob, today } from '../../core/api.service';
import { inclusiveToExclusiveEnd } from '../../core/date-range';
import { METHODS, Report, Shift, User } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';
@Component({
  selector: 'app-reports',
  imports: [CurrencyPipe, DatePipe, ReactiveFormsModule, FeedbackComponent],
  template: `<div class="toolbar">
      <div>
        <h1 class="page-title">Report</h1>
        <p class="subtitle">Entrate, uscite e saldi basati sui movimenti effettivi.</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button class="btn-secondary" (click)="export()" [disabled]="loading() || exporting()">
          {{ exporting() ? 'Esportazione…' : '↓ Esporta CSV' }}
        </button>
        <button class="btn" (click)="openPdf()" [disabled]="loading() || exporting()">
          ↗ Apri PDF rapporto
        </button>
      </div>
    </div>
    <form [formGroup]="form" (ngSubmit)="load()" class="card mb-5 flex flex-wrap items-end gap-4">
      <label class="field">Dal<input class="control" type="date" formControlName="start" /></label
      ><label class="field">Al<input class="control" type="date" formControlName="end" /></label
      ><label class="field"
        >Operatore<select class="control" formControlName="operator">
          <option value="">Tutti</option>
          @for (u of users(); track u.id) {
            <option [value]="u.id">{{ u.first_name }} {{ u.last_name }} · {{ u.email }}</option>
          }
        </select></label
      ><label class="field"
        >Metodo<select class="control" formControlName="method">
          <option value="">Tutti</option>
          @for (m of methods; track m.value) {
            <option [value]="m.value">{{ m.label }}</option>
          }
        </select></label
      ><label class="field"
        >Turno<select class="control" formControlName="shift">
          <option value="">Tutti</option>
          @for (s of shifts(); track s.id) {
            <option [value]="s.id">
              #{{ s.id }} · {{ s.operator_name }} · {{ s.opened_at | date: 'dd/MM/yy' }}
            </option>
          }
        </select></label
      ><label class="field"
        >Direzione<select class="control" formControlName="direction">
          <option value="">Tutte</option>
          <option value="in">Entrate</option>
          <option value="out">Uscite</option>
        </select></label
      ><button class="btn" [disabled]="loading()">Applica filtri</button>
    </form>
    <app-feedback [loading]="loading()" [error]="error()" />
    @if (data(); as d) {
      <div class="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div class="card">
          <p class="subtitle">Entrate</p>
          <strong class="mt-2 block text-2xl text-emerald-600">{{
            d.income | currency: 'EUR'
          }}</strong>
        </div>
        <div class="card">
          <p class="subtitle">Uscite</p>
          <strong class="mt-2 block text-2xl text-red-600">{{
            d.expenses | currency: 'EUR'
          }}</strong>
        </div>
        <div class="card">
          <p class="subtitle">Saldo movimenti</p>
          <strong class="mt-2 block text-2xl text-brand">{{ d.balance | currency: 'EUR' }}</strong>
        </div>
        <div class="card">
          <p class="subtitle">Credito complessivo da riscuotere</p>
          <strong class="mt-2 block text-2xl">{{ d.outstanding | currency: 'EUR' }}</strong>
        </div>
      </div>
      <h2 class="mb-3 font-semibold">Incassi per giorno, operatore e turno</h2>
      <div class="table-wrap mb-6">
        <table class="table">
          <thead>
            <tr>
              <th>Giorno</th>
              <th>Operatore</th>
              <th>Turno</th>
              <th>Camere</th>
              <th>Extra</th>
              <th>Entrate</th>
              <th>Uscite</th>
              <th>Saldo</th>
            </tr>
          </thead>
          <tbody>
            @for (row of d.by_operator_shift; track $index) {
              <tr>
                <td>{{ row.day | date: 'dd/MM/yyyy' }}</td>
                <td>{{ row.operator_name }}</td>
                <td>{{ row.shift === null ? 'Senza turno' : '#' + row.shift }}</td>
                <td>{{ row.room_income | currency: 'EUR' }}</td>
                <td>{{ row.extra_income | currency: 'EUR' }}</td>
                <td class="text-emerald-600">{{ row.income | currency: 'EUR' }}</td>
                <td class="text-red-600">{{ row.expenses | currency: 'EUR' }}</td>
                <td>{{ row.balance | currency: 'EUR' }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="8" class="py-8 text-center text-slate-500">
                  Nessun riepilogo disponibile per i filtri selezionati.
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <h2 class="mb-3 font-semibold">Dettaglio per sezione</h2>
      @for (section of d.sections; track section.key) {
        <section class="mb-6">
          <div class="mb-3 flex items-center justify-between gap-3">
            <h3 class="font-semibold text-slate-800">{{ section.label }}</h3>
            <span class="badge">{{ section.total | currency: 'EUR' }}</span>
          </div>
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Camera / conto</th>
                  <th>Causale</th>
                  <th>Operatore</th>
                  <th>Metodo</th>
                  <th>Turno</th>
                  <th>Importo</th>
                </tr>
              </thead>
              <tbody>
                @for (row of section.rows; track row.id) {
                  <tr>
                    <td>{{ row.created_at | date: 'dd/MM/yy HH:mm' }}</td>
                    <td>{{ row.account }}</td>
                    <td>
                      {{ row.reason }}
                      @if (row.description) {
                        <p class="text-xs text-slate-400">{{ row.description }}</p>
                      }
                    </td>
                    <td>{{ row.operator_name }}</td>
                    <td>{{ method(row.method) }}</td>
                    <td>{{ row.shift === null ? 'Senza turno' : '#' + row.shift }}</td>
                    <td [class.text-red-600]="row.direction === 'out'" [class.text-emerald-600]="row.direction === 'in'">
                      {{ row.amount | currency: 'EUR' }}
                    </td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="7" class="py-7 text-center text-slate-500">
                      Nessun movimento nella sezione.
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </section>
      }
    }`,
})
export class ReportsComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder).nonNullable;
  readonly methods = METHODS;
  readonly users = signal<User[]>([]);
  readonly shifts = signal<Shift[]>([]);
  readonly data = signal<Report | null>(null);
  readonly loading = signal(false);
  readonly exporting = signal(false);
  readonly error = signal('');
  readonly form = this.fb.group({
    start: today().slice(0, 8) + '01',
    end: today(),
    operator: '',
    method: '',
    shift: '',
    direction: '',
  });
  constructor() {
    void this.load();
    void firstValueFrom(this.api.list<User>('users/'))
      .then((u) => this.users.set(u))
      .catch((e) => this.error.set(errorMessage(e)));
    void firstValueFrom(this.api.list<Shift>('cash/shifts/'))
      .then((s) => this.shifts.set(s))
      .catch((e) => this.error.set(errorMessage(e)));
  }
  method(v: string) {
    return METHODS.find((m) => m.value === v)?.label ?? v;
  }
  params() {
    const v = this.form.getRawValue();
    return Object.fromEntries(
      Object.entries({ ...v, end: inclusiveToExclusiveEnd(v.end) }).filter(
        ([, value]) => value !== '',
      ),
    );
  }
  async load() {
    if (this.form.controls.end.value < this.form.controls.start.value) {
      this.error.set('Il periodo selezionato non è valido.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    try {
      this.data.set(await firstValueFrom(this.api.get<Report>('reports/', this.params())));
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  async export() {
    this.exporting.set(true);
    this.error.set('');
    try {
      saveBlob(
        await firstValueFrom(this.api.download('reports/export/', this.params())),
        `report-${this.form.controls.start.value}-${this.form.controls.end.value}.csv`,
      );
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.exporting.set(false);
    }
  }
  openPdf() {
    this.error.set('');
    const query = new URLSearchParams(this.params()).toString();
    window.open(`/api/v1/reports/pdf/?${query}`, '_blank', 'noopener');
  }
}
