import { Component, input } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Stay, STATUS_LABELS } from '../core/models';
@Component({
  selector: 'app-stay-table',
  imports: [CurrencyPipe, DatePipe, RouterLink],
  template: `<div class="table-wrap">
    <table class="table">
      <thead>
        <tr>
          <th>Camera / Ospite</th>
          <th>Periodo</th>
          <th>Stato</th>
          <th>Saldo</th>
        </tr>
      </thead>
      <tbody>
        @for (s of stays(); track s.id) {
          <tr>
            <td>
              <a
                class="font-semibold text-brand hover:underline"
                [routerLink]="['/soggiorni', s.id]"
                >{{ s.room_number }} · {{ s.guest_name }}</a
              >
              <p class="text-xs text-slate-500">{{ s.group_name || 'Individuale' }}</p>
            </td>
            <td>
              {{ s.arrival | date: 'dd/MM/yy HH:mm' }}<br />{{
                s.departure | date: 'dd/MM/yy HH:mm'
              }}
            </td>
            <td>
              <span class="badge">{{ labels[s.status] }}</span>
              @if (s.is_day_use) {
                <span class="badge ml-1">Day use</span>
              }
            </td>
            <td [class.text-red-600]="+s.balance > 0">{{ s.balance | currency: 'EUR' }}</td>
          </tr>
        } @empty {
          <tr>
            <td colspan="4" class="py-8 text-center text-slate-500">
              Nessun soggiorno nel periodo.
            </td>
          </tr>
        }
      </tbody>
    </table>
  </div>`,
})
export class StayTableComponent {
  readonly stays = input<Stay[]>([]);
  readonly labels = STATUS_LABELS;
}
