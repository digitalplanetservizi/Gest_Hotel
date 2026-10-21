import { Component, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage, localDateTime } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { StaysService } from '../../core/stays.service';
import { Charge, Hotel, Payment, PriceItem, Room, Stay, STATUS_LABELS } from '../../core/models';
import { hotelDateTimeInput, hotelDateTimeToIso } from '../../core/hotel-date-time';
import { FeedbackComponent } from '../../shared/feedback.component';
import { PaymentFormComponent } from '../../shared/payment-form.component';
import { PaymentTableComponent } from '../../shared/payment-table.component';
import { HotelDateTimePipe } from '../../shared/hotel-date-time.pipe';
import { ExtraStatementDownloadComponent } from '../../shared/extra-statement-download.component';
@Component({
  selector: 'app-stay-detail',
  imports: [
    CurrencyPipe,
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    FeedbackComponent,
    PaymentFormComponent,
    PaymentTableComponent,
    HotelDateTimePipe,
    ExtraStatementDownloadComponent,
  ],
  template: ` <app-feedback [loading]="loading()" [error]="error()" [success]="success()" />
    @if (stay(); as s) {
      <div class="toolbar">
        <div>
          <a routerLink="/planning" class="text-sm text-brand">← Planning</a>
          <h1 class="page-title mt-2">Camera {{ s.room_number }} · {{ s.guest_name }}</h1>
          <p class="subtitle">
            {{ s.arrival | date: 'dd/MM/yyyy HH:mm' }} →
            {{ s.departure | date: 'dd/MM/yyyy HH:mm' }} · {{ s.guest_count }} ospiti ·
            {{ s.board }}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="badge">{{ labels[s.status] }}</span>
          @if (s.is_day_use) {
            <span class="badge">Day use</span>
          }
          <button class="btn-secondary" (click)="print()">Stampa conto</button>
        </div>
      </div>
      <div class="mb-6 grid gap-4 sm:grid-cols-3">
        <div class="card">
          <p class="text-sm text-slate-500">Totale soggiorno ed extra</p>
          <strong class="mt-2 block text-2xl">{{ s.total | currency: 'EUR' }}</strong>
        </div>
        <div class="card">
          <p class="text-sm text-slate-500">Pagato</p>
          <strong class="mt-2 block text-2xl text-emerald-600">{{
            s.paid | currency: 'EUR'
          }}</strong>
        </div>
        <div class="card border-violet-200">
          <p class="text-sm text-slate-500">Saldo da pagare</p>
          <strong class="mt-2 block text-2xl text-brand">{{ s.balance | currency: 'EUR' }}</strong>
          <p class="mt-1 text-xs text-slate-400">
            Camere {{ s.room_balance | currency: 'EUR' }} · Extra
            {{ s.extras_balance | currency: 'EUR' }}
          </p>
        </div>
      </div>
      @if (s.group) {
        <div class="card mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="font-semibold">Gruppo: {{ s.group_name }}</h2>
            <p class="subtitle">Pagamenti intestati al referente unico del gruppo.</p>
          </div>
          <a class="btn-secondary" [routerLink]="['/gruppi', s.group]">Apri conto gruppo →</a>
        </div>
      }
      <section class="card mb-6 no-print">
        <h2 class="mb-4 font-semibold">Gestisci soggiorno</h2>
        <div class="flex flex-wrap gap-2">
          @if (s.status === 'reserved') {
            <button class="btn" [disabled]="busy()" (click)="actionMode.set('check-in')">
              Effettua check-in</button
            ><button class="btn-danger" [disabled]="busy()" (click)="actionMode.set('cancel')">
              Annulla prenotazione</button
            ><button class="btn-secondary" [disabled]="busy()" (click)="actionMode.set('no-show')">
              Segna no-show
            </button>
          }
          @if (s.status === 'checked_in') {
            <button
              class="btn"
              [disabled]="busy() || !canCheckOut(s)"
              (click)="actionMode.set('check-out')"
            >
              Effettua check-out
            </button>
            @if (!canCheckOut(s)) {
              <p class="w-full text-sm text-red-600">
                Incassa prima il saldo residuo di {{ s.balance | currency: 'EUR' }} per effettuare
                il check-out.
              </p>
            }
          }
          @if (s.status === 'checked_in' || s.status === 'reserved') {
            <button class="btn-secondary" [disabled]="busy()" (click)="actionMode.set('extend')">
              Proroga soggiorno</button
            ><button class="btn-secondary" [disabled]="busy()" (click)="actionMode.set('move')">
              Cambia camera
            </button>
          }
        </div>
        @if (actionMode(); as mode) {
          <div class="mt-5 rounded-lg border border-violet-200 bg-violet-50 p-4">
            <h3 class="mb-3 font-semibold">{{ actionTitle(mode) }}</h3>
            <form [formGroup]="actionForm" (ngSubmit)="performAction()" class="space-y-3">
              @if (mode === 'check-in') {
                <label class="field max-w-sm"
                  >Override tariffa camera/notte (€), facoltativo<input
                    type="number"
                    min="0"
                    step="0.01"
                    class="control"
                    formControlName="nightly_rate"
                    placeholder="Mantieni prezzo prenotazione"
                /></label>
                <p class="text-xs text-slate-500">
                  Una tariffa già pagata non può essere sovrascritta.
                </p>
              }
              @if (mode === 'check-out') {
                @if (+s.balance > 0 && auth.isAdmin()) {
                  <p class="text-sm text-amber-700">
                    Il saldo residuo di {{ s.balance | currency: 'EUR' }} rimarrà aperto. Questa
                    eccezione sarà registrata nel registro attività.
                  </p>
                } @else {
                  <p class="text-sm text-slate-600">
                    Il conto è saldato: il check-out chiuderà la presenza e libererà la camera.
                  </p>
                }
              }
              @if (mode === 'cancel' || mode === 'no-show') {
                <p class="text-sm text-slate-600">
                  Conferma il cambio di stato della prenotazione. Eventuali pagamenti richiedono un
                  rimborso separato.
                </p>
              }
              @if (mode === 'extend') {
                <label class="field max-w-sm"
                  >Nuova partenza<input
                    class="control"
                    type="datetime-local"
                    formControlName="departure"
                /></label>
              }
              @if (mode === 'move') {
                <div class="form-grid">
                  <label class="field"
                    >Nuova camera<select class="control" formControlName="room">
                      <option [ngValue]="null">Seleziona</option>
                      @for (r of rooms(); track r.id) {
                        @if (r.id !== s.room) {
                          <option [ngValue]="r.id">{{ r.number }} · {{ r.room_type }}</option>
                        }
                      }
                    </select></label
                  ><label class="field"
                    >Trasferimento dal<input
                      class="control"
                      type="datetime-local"
                      formControlName="effective_at"
                  /></label>
                </div>
              }
              <div class="flex gap-2">
                <button class="btn" [disabled]="busy()">Conferma</button
                ><button class="btn-secondary" type="button" (click)="actionMode.set('')">
                  Chiudi
                </button>
              </div>
            </form>
          </div>
        }
      </section>
      <div class="grid gap-6 xl:grid-cols-2">
        <div class="space-y-6">
          <section>
            <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 class="font-semibold">Dettaglio conto</h2>
              <app-extra-statement-download
                scope="stays"
                [accountId]="s.id"
                [filename]="'extras-camera-' + s.room_number + '-' + s.id + '.pdf'"
              />
            </div>
            <div class="table-wrap">
              <table class="table">
                <thead>
                  <tr>
                    <th>Descrizione</th>
                    <th>Data e ora</th>
                    <th>Quantità</th>
                    <th>Totale</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  @for (c of charges(); track c.id) {
                    <tr>
                      <td>
                        {{ c.description }}
                        <p class="text-xs text-slate-400">
                          {{ c.kind === 'room' ? 'Camera' : 'Extra' }} ·
                          {{ c.unit_price | currency: 'EUR' }}
                        </p>
                      </td>
                      <td class="whitespace-nowrap">
                        {{ c.kind === 'extra' ? (c.consumed_at | hotelDateTime: timezone()) : '—' }}
                      </td>
                      <td>{{ c.quantity }}</td>
                      <td>{{ c.amount | currency: 'EUR' }}</td>
                      <td>
                        @if (!c.voided_at) {
                          <button class="text-xs text-red-600" (click)="voidCharge.set(c.id)">
                            Storna
                          </button>
                        } @else {
                          <span class="badge" [title]="c.void_reason">Stornato</span>
                        }
                      </td>
                    </tr>
                  } @empty {
                    <tr>
                      <td colspan="5">Nessun addebito.</td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
            @if (voidCharge()) {
              <form [formGroup]="voidForm" (ngSubmit)="voidSelected()" class="card mt-3">
                <label class="field"
                  >Motivo storno<input class="control" formControlName="reason"
                /></label>
                <div class="mt-3 flex gap-2">
                  <button class="btn-danger" [disabled]="busy() || voidForm.invalid">
                    Conferma storno</button
                  ><button type="button" class="btn-secondary" (click)="voidCharge.set(null)">
                    Annulla
                  </button>
                </div>
              </form>
            }
          </section>
          <app-payment-table [payments]="payments()" (saved)="load()" />
          <section class="card">
            <h2 class="mb-3 font-semibold">Informazioni ospite</h2>
            <p class="text-sm">
              {{ s.guest_email || 'Email non indicata' }} ·
              {{ s.guest_phone || 'Telefono non indicato' }}
            </p>
            <p class="mt-3 whitespace-pre-line text-sm text-slate-500">
              {{ s.notes || 'Nessuna nota.' }}
            </p>
          </section>
        </div>
        <div class="space-y-6 no-print">
          @if (s.status === 'checked_in' || s.status === 'reserved') {
            <section class="card">
              <h2 class="mb-4 font-semibold">Aggiungi extra</h2>
              <form [formGroup]="chargeForm" (ngSubmit)="addCharge()" class="form-grid">
                <label class="field sm:col-span-2"
                  >Articolo da listino<select
                    class="control"
                    formControlName="price_item"
                    (change)="priceChanged()"
                  >
                    <option [ngValue]="null">Extra libero</option>
                    @for (p of priceItems(); track p.id) {
                      <option [ngValue]="p.id">
                        {{ p.description }} · {{ p.price | currency: 'EUR' }}
                      </option>
                    }
                  </select></label
                ><label class="field sm:col-span-2"
                  >Descrizione<input class="control" formControlName="description" /></label
                ><label class="field"
                  >Quantità<input
                    class="control"
                    type="number"
                    min="0.01"
                    step="0.01"
                    formControlName="quantity" /></label
                ><label class="field"
                  >Prezzo unitario (€)<input
                    class="control"
                    type="number"
                    min="0"
                    step="0.01"
                    formControlName="unit_price"
                /></label>
                <label class="field sm:col-span-2">
                  Data e ora consumazione
                  <input class="control" type="datetime-local" formControlName="consumed_at" />
                  <span class="text-xs text-slate-500">Fuso della struttura: {{ timezone() }}</span>
                </label>
                <div class="sm:col-span-2">
                  <button class="btn" [disabled]="busy() || chargeForm.invalid">
                    Aggiungi al conto
                  </button>
                </div>
              </form>
            </section>
          }
          @if (!s.group && !['cancelled', 'no_show'].includes(s.status)) {
            <app-payment-form [stayId]="s.id" (saved)="load()" />
          }
        </div>
      </div>
    }`,
})
export class StayDetailComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  private readonly service = inject(StaysService);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);
  private readonly id = Number(this.route.snapshot.paramMap.get('id'));
  readonly stay = signal<Stay | null>(null);
  readonly charges = signal<Charge[]>([]);
  readonly payments = signal<Payment[]>([]);
  readonly rooms = signal<Room[]>([]);
  readonly priceItems = signal<PriceItem[]>([]);
  readonly timezone = signal('Europe/Rome');
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly labels = STATUS_LABELS;
  readonly actionMode = signal('');
  readonly voidCharge = signal<number | null>(null);
  readonly actionForm = this.fb.group({
    nightly_rate: [null as number | null],
    departure: [''],
    room: [null as number | null],
    effective_at: [localDateTime(new Date().toISOString())],
  });
  readonly voidForm = this.fb.nonNullable.group({ reason: ['', Validators.required] });
  readonly chargeForm = this.fb.group({
    price_item: [null as number | null],
    description: ['', Validators.required],
    quantity: [1, [Validators.required, Validators.min(0.01)]],
    unit_price: [null as number | null, [Validators.required, Validators.min(0)]],
    consumed_at: [hotelDateTimeInput(new Date().toISOString()), Validators.required],
  });
  constructor() {
    void this.load();
    if (this.route.snapshot.queryParamMap.has('checkin_error'))
      this.error.set(
        'Prenotazione creata. Il check-in non è riuscito: verifica data di arrivo e ripeti l’operazione.',
      );
  }
  async load() {
    this.loading.set(true);
    try {
      const [s, c, p, r, items, hotel] = await Promise.all([
        firstValueFrom(this.service.get(this.id)),
        firstValueFrom(this.service.charges(this.id)),
        firstValueFrom(this.api.list<Payment>('payments/', { stay: this.id })),
        firstValueFrom(this.api.list<Room>('rooms/')),
        firstValueFrom(this.api.list<PriceItem>('price-items/')),
        firstValueFrom(this.api.get<Hotel>('settings/')),
      ]);
      if (this.timezone() !== hotel.timezone) {
        this.timezone.set(hotel.timezone);
        this.chargeForm.controls.consumed_at.setValue(
          hotelDateTimeInput(new Date().toISOString(), hotel.timezone),
        );
      }
      this.stay.set(s);
      this.charges.set(c);
      this.payments.set(p);
      this.rooms.set(r.filter((x) => x.is_active));
      this.priceItems.set(items.filter((x) => x.is_active));
      this.actionForm.controls.departure.setValue(localDateTime(s.departure));
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  actionTitle(mode: string) {
    return (
      (
        {
          'check-in': 'Conferma arrivo',
          'check-out': 'Conferma partenza',
          cancel: 'Annulla prenotazione',
          'no-show': 'Ospite non arrivato',
          extend: 'Proroga soggiorno',
          move: 'Trasferisci ospite',
        } as Record<string, string>
      )[mode] ?? mode
    );
  }
  canCheckOut(stay: Stay) {
    return +stay.balance <= 0 || this.auth.isAdmin();
  }
  async performAction() {
    const mode = this.actionMode(),
      v = this.actionForm.getRawValue();
    let body: unknown = {};
    if (mode === 'check-in' && v.nightly_rate !== null)
      body = { nightly_rate: String(v.nightly_rate) };
    if (mode === 'extend') {
      if (!v.departure) {
        this.error.set('Inserisci la nuova data di partenza.');
        return;
      }
      body = { departure: new Date(v.departure).toISOString() };
    }
    if (mode === 'move') {
      if (!v.room || !v.effective_at) {
        this.error.set('Seleziona camera e data del trasferimento.');
        return;
      }
      body = { room: v.room, effective_at: new Date(v.effective_at).toISOString() };
    }
    await this.mutate(async () => {
      await firstValueFrom(this.service.action(this.id, mode, body));
      this.actionMode.set('');
    }, 'Soggiorno aggiornato.');
  }
  async mutate(fn: () => Promise<void>, message: string) {
    this.busy.set(true);
    this.error.set('');
    this.success.set('');
    try {
      await fn();
      this.success.set(message);
      await this.load();
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
  priceChanged() {
    const p = this.priceItems().find((x) => x.id === this.chargeForm.controls.price_item.value);
    if (p) this.chargeForm.patchValue({ description: p.description, unit_price: +p.price });
  }
  async addCharge() {
    if (this.chargeForm.invalid) return;
    let consumedAt: string;
    try {
      consumedAt = hotelDateTimeToIso(
        this.chargeForm.controls.consumed_at.value ?? '',
        this.timezone(),
      );
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'Data e ora di consumazione non valida.');
      return;
    }
    await this.mutate(async () => {
      const v = this.chargeForm.getRawValue();
      const body = {
        description: v.description,
        quantity: String(v.quantity),
        unit_price: String(v.unit_price),
        consumed_at: consumedAt,
        ...(v.price_item ? { price_item: v.price_item } : {}),
      };
      await firstValueFrom(this.service.addCharge(this.id, body));
      this.chargeForm.reset({
        quantity: 1,
        price_item: null,
        consumed_at: hotelDateTimeInput(new Date().toISOString(), this.timezone()),
      });
    }, 'Extra aggiunto al conto.');
  }
  async voidSelected() {
    if (this.voidForm.invalid) return;
    await this.mutate(async () => {
      await firstValueFrom(
        this.api.post(`charges/${this.voidCharge()}/void/`, this.voidForm.getRawValue()),
      );
      this.voidCharge.set(null);
      this.voidForm.reset();
    }, 'Addebito stornato.');
  }
  print() {
    window.print();
  }
}
