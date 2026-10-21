import { Component, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage } from '../../core/api.service';
import { Dashboard, Stay } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';
import { StayTableComponent } from '../../shared/stay-table.component';
@Component({
  selector: 'app-dashboard',
  imports: [CurrencyPipe, DatePipe, RouterLink, FeedbackComponent, StayTableComponent],
  template: ` <div class="toolbar">
      <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="subtitle">
          Una vista chiara della giornata · {{ now | date: 'EEEE d MMMM yyyy' }}
        </p>
      </div>
      <a routerLink="/soggiorni/nuovo" class="btn">+ Nuovo soggiorno</a>
    </div>
    <app-feedback [loading]="loading()" [error]="error()" />
    @if (data(); as d) {
      <section
        aria-label="Indicatori della struttura"
        class="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <div class="card border-l-4 border-l-brand">
          <p class="text-sm text-slate-500">Camere occupate</p>
          <p class="mt-3 text-3xl font-semibold text-slate-800">
            {{ d.rooms_occupied }}
            <span class="text-lg font-normal text-slate-400">/ {{ d.rooms_total }}</span>
          </p>
          <p class="mt-2 text-xs text-brand">Disponibilità della struttura</p>
        </div>
        <div class="card border-l-4 border-l-amber-400">
          <p class="text-sm text-slate-500">Arrivi / Partenze di oggi</p>
          <p class="mt-3 text-3xl font-semibold text-slate-800">
            {{ d.arrivals_today }}
            <span class="text-lg font-normal text-slate-400">/ {{ d.departures_today }}</span>
          </p>
          <p class="mt-2 text-xs text-amber-600">Soggiorni in programma</p>
        </div>
        <div class="card border-l-4 border-l-rose-400">
          <p class="text-sm text-slate-500">Credito da riscuotere</p>
          <p class="mt-3 text-3xl font-semibold text-slate-800">
            {{ d.outstanding | currency: 'EUR' }}
          </p>
          <p class="mt-2 text-xs text-rose-600">Camere ed extra ancora da saldare</p>
        </div>
        <div class="card border-l-4 border-l-emerald-400">
          <p class="text-sm text-slate-500">Incassi di oggi</p>
          <p class="mt-3 text-3xl font-semibold text-slate-800">
            {{ d.income_today | currency: 'EUR' }}
          </p>
          <p class="mt-2 text-xs text-emerald-600">Pagamenti effettivamente registrati</p>
        </div>
      </section>
      @if (d.rooms_total === 0) {
        <div class="card mb-6 border-violet-200 bg-violet-50">
          <h2 class="font-semibold">Configura la tua struttura</h2>
          <p class="my-2 text-sm text-slate-600">
            Prima di lavorare inserisci camere, capienze, gruppi e listini.
          </p>
          <a class="btn" routerLink="/impostazioni">Apri impostazioni</a>
        </div>
      }
      <div class="grid gap-6 xl:grid-cols-2">
        <section class="min-w-0">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="font-semibold">Arrivi di oggi</h2>
            <a class="text-sm text-brand" routerLink="/planning">Apri planning →</a>
          </div>
          <app-stay-table [stays]="arrivals()" />
        </section>
        <section class="min-w-0">
          <h2 class="mb-3 font-semibold">Partenze di oggi</h2>
          <app-stay-table [stays]="departures()" />
        </section>
      </div>
      <div class="card mt-6 flex items-center justify-between gap-4">
        <div>
          <h2 class="font-semibold">Magazzino e scorte</h2>
          <p class="subtitle">{{ d.low_stock_count }} articoli sotto la scorta minima.</p>
        </div>
        <a routerLink="/magazzino" class="btn-secondary">Controlla scorte</a>
      </div>
    }
    @if (error()) {
      <button class="btn-secondary" (click)="load()">Riprova</button>
    }`,
})
export class DashboardComponent {
  private readonly api = inject(ApiService);
  readonly data = signal<Dashboard | null>(null);
  readonly arrivals = signal<Stay[]>([]);
  readonly departures = signal<Stay[]>([]);
  readonly error = signal('');
  readonly loading = signal(true);
  readonly now = new Date();
  constructor() {
    void this.load();
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const d = await firstValueFrom(this.api.get<Dashboard>('dashboard/'));
      this.data.set(d);
      this.arrivals.set(d.arrivals ?? []);
      this.departures.set(d.departures ?? []);
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
}
