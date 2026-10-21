import { Component, inject, signal } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage, today } from '../../core/api.service';
import { StaysService } from '../../core/stays.service';
import { BOARDS, Group, Hotel, Quote, Room } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';
@Component({
  selector: 'app-stay-create',
  imports: [ReactiveFormsModule, CurrencyPipe, RouterLink, FeedbackComponent],
  template: `<div class="toolbar">
      <div>
        <a routerLink="/planning" class="text-sm text-brand">← Torna al planning</a>
        <h1 class="page-title mt-2">Nuovo soggiorno</h1>
        <p class="subtitle">Prenota la camera o registra subito l’arrivo dell’ospite.</p>
      </div>
    </div>
    <app-feedback [loading]="loading()" [error]="error()" />
    <form [formGroup]="form" (ngSubmit)="submit()" class="grid gap-6 xl:grid-cols-[1fr_320px]">
      <div class="space-y-6">
        <section class="card">
          <h2 class="mb-5 font-semibold">Camera e periodo</h2>
          <div class="form-grid">
            <label class="field"
              >Camera<select class="control" formControlName="room" (change)="roomChanged()">
                <option [ngValue]="null">Seleziona una camera</option>
                @for (r of rooms(); track r.id) {
                  <option [ngValue]="r.id">
                    {{ r.number }} · {{ r.room_type }} · max {{ r.capacity }}
                  </option>
                }
              </select></label
            ><label class="field"
              >Ospiti<input
                class="control"
                type="number"
                min="1"
                formControlName="guest_count" /></label
            ><label class="field"
              >Arrivo<input
                class="control"
                type="datetime-local"
                formControlName="arrival" /></label
            ><label class="field"
              >Partenza<input
                class="control"
                type="datetime-local"
                formControlName="departure" /></label
            ><label class="field"
              >Trattamento<select class="control" formControlName="board">
                @for (b of boards; track b.value) {
                  <option [value]="b.value">{{ b.label }}</option>
                }
              </select></label
            ><label class="field"
              >Gruppo / Referente<select class="control" formControlName="group">
                <option [ngValue]="null">Individuale</option>
                @for (g of groups(); track g.id) {
                  <option [ngValue]="g.id">{{ g.name }} · {{ g.reference_name }}</option>
                }
              </select></label
            >
          </div>
          <label class="mt-5 flex items-center gap-2 text-sm"
            ><input type="checkbox" formControlName="is_day_use" /> Day use (arrivo e partenza nello
            stesso giorno)</label
          >
        </section>
        <section class="card">
          <h2 class="mb-5 font-semibold">Ospite / Intestatario</h2>
          <div class="form-grid">
            <label class="field sm:col-span-2"
              >Nome e cognome<input
                class="control"
                formControlName="guest_name"
                autocomplete="name" /></label
            ><label class="field"
              >Email<input
                class="control"
                formControlName="guest_email"
                type="email"
                autocomplete="email" /></label
            ><label class="field"
              >Telefono<input
                class="control"
                formControlName="guest_phone"
                type="tel"
                autocomplete="tel" /></label
            ><label class="field sm:col-span-2"
              >Note<textarea class="control" rows="3" formControlName="notes"></textarea>
            </label>
          </div>
        </section>
      </div>
      <aside class="space-y-5">
        <section class="card">
          <h2 class="mb-4 font-semibold">Tariffa e preventivo</h2>
          <p class="mb-4 text-xs leading-relaxed text-slate-500">
            Il listino applica stagioni e trattamento. L’override sostituisce il prezzo per
            camera/notte; per il day use vale per il soggiorno.
          </p>
          <label class="field"
            >Override tariffa (€), facoltativo<input
              class="control"
              type="number"
              min="0"
              step="0.01"
              formControlName="nightly_rate"
              placeholder="Usa listino" /></label
          ><button
            type="button"
            class="btn-secondary mt-4 w-full"
            [disabled]="busy() || loading()"
            (click)="quote()"
          >
            Calcola preventivo
          </button>
          @if (estimate(); as q) {
            <div class="mt-5 rounded-lg bg-violet-50 p-4">
              <p class="text-xs text-slate-500">{{ q.nights }} notti · soggiorno</p>
              <strong class="text-2xl text-brand">{{ q.total | currency: 'EUR' }}</strong>
            </div>
          }
        </section>
        <section class="card">
          <label class="mb-5 flex items-center gap-2 text-sm"
            ><input type="checkbox" formControlName="check_in_now" /> Effettua subito il
            check-in</label
          ><button class="btn w-full" [disabled]="busy() || loading()">
            {{ busy() ? 'Salvataggio…' : 'Conferma soggiorno' }}
          </button>
          <p class="mt-3 text-xs text-slate-400">
            Disponibilità e tariffa vengono verificate dal server.
          </p>
        </section>
      </aside>
    </form>`,
})
export class StayCreateComponent {
  private readonly api = inject(ApiService);
  private readonly service = inject(StaysService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  readonly boards = BOARDS;
  readonly rooms = signal<Room[]>([]);
  readonly groups = signal<Group[]>([]);
  readonly error = signal('');
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly estimate = signal<Quote | null>(null);
  readonly form = this.fb.group({
    room: this.fb.control<number | null>(null, Validators.required),
    guest_name: ['', Validators.required],
    guest_email: ['', Validators.email],
    guest_phone: [''],
    guest_count: [1, [Validators.required, Validators.min(1)]],
    board: ['BB', Validators.required],
    group: this.fb.control<number | null>(null),
    arrival: [today() + 'T14:00', Validators.required],
    departure: [this.nextDay() + 'T10:00', Validators.required],
    is_day_use: [false],
    nightly_rate: this.fb.control<number | null>(null, [Validators.min(0)]),
    notes: [''],
    check_in_now: [false],
  });
  constructor() {
    void this.load();
    this.form.valueChanges.subscribe(() => this.estimate.set(null));
  }
  nextDay() {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  async load() {
    try {
      const [rooms, groups, hotel] = await Promise.all([
        firstValueFrom(this.api.list<Room>('rooms/')),
        firstValueFrom(this.api.list<Group>('groups/')),
        firstValueFrom(this.api.get<Hotel>('settings/')),
      ]);
      this.rooms.set(rooms.filter((r) => r.is_active));
      this.groups.set(groups.filter((g) => g.is_active));
      const date = this.route.snapshot.queryParamMap.get('date') || today();
      const next = new Date(date + 'T12:00:00');
      next.setDate(next.getDate() + 1);
      const end = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}-${String(next.getDate()).padStart(2, '0')}`;
      this.form.patchValue({
        arrival: date + 'T' + hotel.check_in_time.slice(0, 5),
        departure: end + 'T' + hotel.check_out_time.slice(0, 5),
      });
      const id = Number(this.route.snapshot.queryParamMap.get('room'));
      if (rooms.some((r) => r.id === id)) {
        this.form.patchValue({ room: id });
        this.roomChanged();
      }
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  roomChanged() {
    const r = this.rooms().find((r) => r.id === this.form.controls.room.value);
    this.form.controls.group.setValue(r?.default_group ?? null);
  }
  payload() {
    const v = this.form.getRawValue();
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      throw new Error('Completa i campi obbligatori: camera, ospite, date e numero di persone.');
    }
    if (Date.parse(v.departure!) <= Date.parse(v.arrival!))
      throw new Error('La partenza deve seguire l’arrivo.');
    return {
      ...v,
      arrival: new Date(v.arrival!).toISOString(),
      departure: new Date(v.departure!).toISOString(),
      nightly_rate: v.nightly_rate === null ? null : String(v.nightly_rate),
    };
  }
  async quote() {
    this.error.set('');
    this.busy.set(true);
    try {
      this.estimate.set(await firstValueFrom(this.service.quote(this.payload())));
    } catch (e) {
      this.error.set(
        e instanceof Error && !(e as { status?: number }).status ? e.message : errorMessage(e),
      );
    } finally {
      this.busy.set(false);
    }
  }
  async submit() {
    this.busy.set(true);
    this.error.set('');
    try {
      const p = this.payload();
      const s = await firstValueFrom(this.service.create(p));
      if (p.check_in_now) {
        try {
          await firstValueFrom(this.service.action(s.id, 'check-in'));
        } catch {
          await this.router.navigate(['/soggiorni', s.id], { queryParams: { checkin_error: '1' } });
          return;
        }
      }
      await this.router.navigate(['/soggiorni', s.id]);
    } catch (e) {
      this.error.set(
        e instanceof Error && !(e as { status?: number }).status ? e.message : errorMessage(e),
      );
    } finally {
      this.busy.set(false);
    }
  }
}
