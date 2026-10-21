import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { today, errorMessage } from '../../core/api.service';
import {
  addCalendarDays,
  inclusiveToExclusiveEnd,
  segmentOverlapsDay,
} from '../../core/date-range';
import { StaysService } from '../../core/stays.service';
import { Planning, STATUS_LABELS } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';
import { StayTableComponent } from '../../shared/stay-table.component';
@Component({
  selector: 'app-planning',
  imports: [DatePipe, ReactiveFormsModule, RouterLink, FeedbackComponent, StayTableComponent],
  template: ` <div class="toolbar">
      <div>
        <h1 class="page-title">Planning camere</h1>
        <p class="subtitle">Disponibilità, arrivi e soggiorni della struttura.</p>
      </div>
      <a class="btn" routerLink="/soggiorni/nuovo">+ Prenotazione / Check-in</a>
    </div>
    <form [formGroup]="form" (ngSubmit)="load()" class="card mb-5 flex flex-wrap items-end gap-4">
      <label class="field">Dal<input class="control" type="date" formControlName="start" /></label
      ><label class="field">Al<input class="control" type="date" formControlName="end" /></label
      ><label class="field min-w-44"
        >Cerca ospite / camera<input
          class="control"
          [value]="search()"
          (input)="search.set($any($event.target).value)"
          placeholder="Nome, gruppo o camera" /></label
      ><button class="btn" [disabled]="loading()">Aggiorna</button
      ><button
        type="button"
        class="btn-secondary"
        (click)="mode.set(mode() === 'grid' ? 'list' : 'grid')"
      >
        Vista {{ mode() === 'grid' ? 'elenco' : 'griglia' }}
      </button>
    </form>
    <app-feedback [loading]="loading()" [error]="error()" />
    @if (data(); as d) {
      @if (mode() === 'grid') {
        <div class="table-wrap">
          <table class="table planning">
            <thead>
              <tr>
                <th class="sticky left-0 z-10 min-w-32">Camera</th>
                @for (day of days(); track day) {
                  <th class="min-w-40 text-center">{{ day | date: 'EEE dd/MM' }}</th>
                }
              </tr>
            </thead>
            <tbody>
              @for (room of d.rooms; track room.id) {
                <tr>
                  <td class="sticky left-0 z-10 bg-white">
                    <strong class="block text-slate-800">{{ room.number }}</strong
                    ><span class="text-xs text-slate-400"
                      >{{ room.room_type }} · {{ room.capacity }} ospiti</span
                    >
                  </td>
                  @for (day of days(); track day) {
                    <td class="!p-1 align-top">
                      @for (stay of staysAt(room.id, day); track stay.id) {
                        <a
                          [routerLink]="['/soggiorni', stay.id]"
                          class="mb-1 block rounded-lg border-l-4 bg-violet-50 px-2 py-2 text-xs hover:ring-2 hover:ring-violet-200"
                          [style.border-left-color]="safeColor(stay.group_color)"
                          ><span class="block truncate font-semibold text-slate-700">{{
                            stay.guest_name
                          }}</span
                          ><span class="mt-1 block text-slate-500"
                            >{{ stay.group_label || stay.board }} · {{ labels[stay.status] }}</span
                          ><span class="mt-1 flex gap-1"
                            ><span
                              class="rounded bg-white px-1"
                              [class.text-red-600]="+stay.room_balance > 0"
                              >Camera {{ +stay.room_balance > 0 ? 'da saldare' : '✓' }}</span
                            ><span
                              class="rounded bg-white px-1"
                              [class.text-red-600]="+stay.extras_balance > 0"
                              >Extra {{ +stay.extras_balance > 0 ? 'da saldare' : '✓' }}</span
                            ></span
                          ></a
                        >
                      } @empty {
                        <a
                          class="block min-h-16 rounded-lg p-2 text-center text-xs text-slate-300 hover:bg-slate-50 hover:text-brand"
                          routerLink="/soggiorni/nuovo"
                          [queryParams]="{ room: room.id, date: day }"
                          >+ Libera</a
                        >
                      }
                    </td>
                  }
                </tr>
              } @empty {
                <tr>
                  <td [attr.colspan]="days().length + 1" class="py-12 text-center">
                    Nessuna camera configurata.
                    <a routerLink="/impostazioni" class="text-brand">Configura la struttura</a>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      } @else {
        <app-stay-table [stays]="visibleStays()" />
      }
      <div class="mt-4 flex flex-wrap gap-3">
        @for (g of d.groups; track g.id) {
          <a
            class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs"
            [routerLink]="['/gruppi', g.id]"
            ><i class="size-2 rounded-full" [style.background]="safeColor(g.color)"></i
            >{{ g.name }}</a
          >
        }
      </div>
    }`,
})
export class PlanningComponent {
  private readonly service = inject(StaysService);
  private readonly fb = inject(FormBuilder).nonNullable;
  readonly form = this.fb.group({ start: today(), end: this.addDays(today(), 13) });
  readonly data = signal<Planning | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly search = signal('');
  readonly mode = signal<'grid' | 'list'>('grid');
  readonly labels = STATUS_LABELS;
  readonly days = signal<string[]>([]);
  readonly visibleStays = computed(() => {
    const q = this.search().toLocaleLowerCase();
    return (this.data()?.stays ?? []).filter((s) =>
      `${s.guest_name} ${s.room_number} ${s.group_name}`.toLocaleLowerCase().includes(q),
    );
  });
  constructor() {
    void this.load();
  }
  addDays(day: string, n: number) {
    return addCalendarDays(day, n);
  }
  async load() {
    const v = this.form.getRawValue();
    if (v.end < v.start) {
      this.error.set('La fine del periodo deve seguire la data iniziale.');
      return;
    }
    const span = Math.round((Date.parse(v.end) - Date.parse(v.start)) / 86400000);
    if (span > 60) {
      this.error.set('Seleziona un intervallo massimo di 61 giorni per la griglia.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    try {
      this.data.set(
        await firstValueFrom(this.service.planning(v.start, inclusiveToExclusiveEnd(v.end))),
      );
      this.days.set(Array.from({ length: span + 1 }, (_, i) => this.addDays(v.start, i)));
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  staysAt(room: number, day: string) {
    return this.visibleStays().filter(
      (s) =>
        !['cancelled', 'no_show'].includes(s.status) &&
        (s.segments?.length
          ? s.segments
          : [{ room: s.room, arrival: s.arrival, departure: s.departure }]
        ).some((seg) => segmentOverlapsDay(seg, room, day)),
    );
  }
  safeColor(color: string) {
    return /^#[0-9a-f]{6}$/i.test(color || '') ? color : '#7367f0';
  }
}
