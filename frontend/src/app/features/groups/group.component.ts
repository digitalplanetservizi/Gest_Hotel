import { Component, inject, signal } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage } from '../../core/api.service';
import { Hotel, Statement } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';
import { PaymentFormComponent } from '../../shared/payment-form.component';
import { PaymentTableComponent } from '../../shared/payment-table.component';
import { StayTableComponent } from '../../shared/stay-table.component';
import { HotelDateTimePipe } from '../../shared/hotel-date-time.pipe';
import { ExtraStatementDownloadComponent } from '../../shared/extra-statement-download.component';
@Component({
  selector: 'app-group',
  imports: [
    CurrencyPipe,
    RouterLink,
    FeedbackComponent,
    PaymentFormComponent,
    PaymentTableComponent,
    StayTableComponent,
    HotelDateTimePipe,
    ExtraStatementDownloadComponent,
  ],
  template: `<app-feedback [loading]="loading()" [error]="error()" />
    @if (data(); as d) {
      <div class="toolbar">
        <div>
          <a routerLink="/planning" class="text-sm text-brand">← Planning</a>
          <h1 class="page-title mt-2">{{ d.group.name }}</h1>
          <p class="subtitle">
            Referente: {{ d.group.reference_name }} · {{ d.group.reference_email }} ·
            {{ d.group.reference_phone }}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <app-extra-statement-download
            scope="groups"
            [accountId]="id"
            [filename]="'extras-gruppo-' + id + '.pdf'"
          />
          <button class="btn-secondary" (click)="print()">Stampa conto gruppo</button>
        </div>
      </div>
      <div class="mb-6 grid gap-4 sm:grid-cols-3">
        <div class="card">
          <p class="subtitle">Totale gruppo</p>
          <strong class="text-2xl">{{ d.total | currency: 'EUR' }}</strong>
        </div>
        <div class="card">
          <p class="subtitle">Pagato</p>
          <strong class="text-2xl text-emerald-600">{{ d.paid | currency: 'EUR' }}</strong>
        </div>
        <div class="card">
          <p class="subtitle">Saldo referente</p>
          <strong class="text-2xl text-brand">{{ d.balance | currency: 'EUR' }}</strong>
        </div>
      </div>
      <div class="grid gap-6 xl:grid-cols-2">
        <div class="space-y-6">
          <section>
            <h2 class="mb-3 font-semibold">Camere e soggiorni</h2>
            <app-stay-table [stays]="d.stays" />
          </section>
          <app-payment-table [payments]="d.payments" (saved)="load()" />
        </div>
        <div class="space-y-6">
          <div class="no-print"><app-payment-form [groupId]="id" (saved)="load()" /></div>
          <section>
            <h2 class="mb-3 font-semibold">Addebiti gruppo</h2>
            <div class="table-wrap">
              <table class="table">
                <thead>
                  <tr>
                    <th>Soggiorno</th>
                    <th>Descrizione</th>
                    <th>Data e ora</th>
                    <th>Totale</th>
                  </tr>
                </thead>
                <tbody>
                  @for (c of d.charges; track c.id) {
                    <tr>
                      <td>
                        <a class="text-brand" [routerLink]="['/soggiorni', c.stay]"
                          >#{{ c.stay }}</a
                        >
                      </td>
                      <td>
                        {{ c.description }}
                        @if (c.voided_at) {
                          <span class="badge ml-1" [title]="c.void_reason">Stornato</span>
                        }
                      </td>
                      <td class="whitespace-nowrap">
                        {{ c.kind === 'extra' ? (c.consumed_at | hotelDateTime: timezone()) : '—' }}
                      </td>
                      <td>{{ c.amount | currency: 'EUR' }}</td>
                    </tr>
                  } @empty {
                    <tr>
                      <td colspan="4">Nessun addebito.</td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </div>
    }`,
})
export class GroupComponent {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  readonly id = Number(this.route.snapshot.paramMap.get('id'));
  readonly data = signal<Statement | null>(null);
  readonly loading = signal(false);
  readonly timezone = signal('Europe/Rome');
  readonly error = signal('');
  constructor() {
    void this.load();
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const [statement, hotel] = await Promise.all([
        firstValueFrom(this.api.get<Statement>(`groups/${this.id}/statement/`)),
        firstValueFrom(this.api.get<Hotel>('settings/')),
      ]);
      this.data.set(statement);
      this.timezone.set(hotel.timezone);
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  print() {
    window.print();
  }
}
