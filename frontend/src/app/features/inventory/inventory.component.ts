import { Component, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage } from '../../core/api.service';
import { InventoryItem, InventoryMovement } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';
@Component({
  selector: 'app-inventory',
  imports: [ReactiveFormsModule, DatePipe, DecimalPipe, FeedbackComponent],
  template: `<div class="toolbar">
      <div>
        <h1 class="page-title">Magazzino</h1>
        <p class="subtitle">Articoli, scorte minime e movimenti tracciati.</p>
      </div>
      <button class="btn" (click)="editItem(null)">+ Nuovo articolo</button>
    </div>
    <app-feedback [loading]="loading()" [error]="error()" [success]="success()" />
    @if (editing()) {
      <section class="card mb-6">
        <h2 class="mb-4 font-semibold">{{ editId() ? 'Modifica articolo' : 'Nuovo articolo' }}</h2>
        <form [formGroup]="itemForm" (ngSubmit)="saveItem()" class="form-grid">
          <label class="field">Codice<input class="control" formControlName="code" /></label
          ><label class="field">Nome<input class="control" formControlName="name" /></label
          ><label class="field"
            >Unità base (es. pz, litri)<input class="control" formControlName="unit" /></label
          ><label class="field"
            >Scorta minima<input
              class="control"
              type="number"
              min="0"
              step="0.001"
              formControlName="minimum_stock" /></label
          ><label class="flex items-center gap-2 text-sm"
            ><input type="checkbox" formControlName="is_active" /> Articolo attivo</label
          >
          <div class="flex gap-2 sm:col-span-2">
            <button class="btn" [disabled]="busy() || itemForm.invalid">Salva articolo</button
            ><button class="btn-secondary" type="button" (click)="editing.set(false)">
              Chiudi
            </button>
          </div>
        </form>
      </section>
    }
    <div class="mb-6 grid gap-6 xl:grid-cols-[1fr_360px]">
      <section class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Articolo</th>
              <th>Giacenza</th>
              <th>Minimo</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (i of items(); track i.id) {
              <tr>
                <td>
                  <strong>{{ i.name }}</strong>
                  <p class="text-xs text-slate-400">
                    {{ i.code }} · {{ i.is_active ? 'Attivo' : 'Disattivato' }}
                  </p>
                </td>
                <td [class.text-red-600]="+i.quantity < +i.minimum_stock">
                  {{ i.quantity | number: '1.0-3' }} {{ i.unit }}
                  @if (+i.quantity < +i.minimum_stock) {
                    <span class="badge ml-1 !bg-red-50 !text-red-700">Sotto scorta</span>
                  }
                </td>
                <td>{{ i.minimum_stock | number: '1.0-3' }}</td>
                <td><button class="text-xs text-brand" (click)="editItem(i)">Modifica</button></td>
              </tr>
            } @empty {
              <tr>
                <td colspan="4" class="py-8 text-center text-slate-500">
                  Nessun articolo. Crea il primo articolo per iniziare.
                </td>
              </tr>
            }
          </tbody>
        </table>
      </section>
      <section class="card">
        <h2 class="mb-4 font-semibold">Carico / Scarico</h2>
        <form [formGroup]="movementForm" (ngSubmit)="move()" class="space-y-4">
          <label class="field"
            >Articolo<select class="control" formControlName="item">
              <option [ngValue]="null">Seleziona</option>
              @for (i of items(); track i.id) {
                @if (i.is_active) {
                  <option [ngValue]="i.id">{{ i.name }} ({{ i.unit }})</option>
                }
              }
            </select></label
          ><label class="field"
            >Operazione<select class="control" formControlName="direction">
              <option value="in">Carico</option>
              <option value="out">Scarico</option>
            </select></label
          ><label class="field"
            >Quantità nell’unità base<input
              class="control"
              type="number"
              min="0.001"
              step="0.001"
              formControlName="quantity" /></label
          ><label class="field"
            >Motivo<input
              class="control"
              formControlName="reason"
              placeholder="Acquisto, consumo, rettifica…" /></label
          ><button class="btn" [disabled]="busy() || movementForm.invalid">
            Registra movimento
          </button>
        </form>
        <p class="mt-3 text-xs leading-relaxed text-slate-400">
          La giacenza viene aggiornata dai movimenti. Per registrare il costo di un acquisto usa
          un’uscita in Cassa.
        </p>
      </section>
    </div>
    <h2 class="mb-3 font-semibold">Storico movimenti</h2>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Data</th>
            <th>Articolo</th>
            <th>Movimento</th>
            <th>Quantità</th>
            <th>Motivo</th>
          </tr>
        </thead>
        <tbody>
          @for (m of movements(); track m.id) {
            <tr>
              <td>{{ m.created_at | date: 'dd/MM/yy HH:mm' }}</td>
              <td>{{ itemName(m.item) }}</td>
              <td>{{ m.direction === 'in' ? 'Carico' : 'Scarico' }}</td>
              <td>{{ m.quantity | number: '1.0-3' }}</td>
              <td>{{ m.reason }}</td>
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
    </div>`,
})
export class InventoryComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  readonly items = signal<InventoryItem[]>([]);
  readonly movements = signal<InventoryMovement[]>([]);
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly editing = signal(false);
  readonly editId = signal<number | null>(null);
  readonly itemForm = this.fb.group({
    code: ['', Validators.required],
    name: ['', Validators.required],
    unit: ['pz', Validators.required],
    minimum_stock: [0, [Validators.required, Validators.min(0)]],
    is_active: [true],
  });
  readonly movementForm = this.fb.group({
    item: [null as number | null, Validators.required],
    direction: ['in', Validators.required],
    quantity: [null as number | null, [Validators.required, Validators.min(0.001)]],
    reason: ['', Validators.required],
  });
  constructor() {
    void this.load();
  }
  itemName(id: number) {
    return this.items().find((i) => i.id === id)?.name ?? `#${id}`;
  }
  async load() {
    this.loading.set(true);
    try {
      const [i, m] = await Promise.all([
        firstValueFrom(this.api.list<InventoryItem>('inventory/items/')),
        firstValueFrom(this.api.list<InventoryMovement>('inventory/movements/')),
      ]);
      this.items.set(i);
      this.movements.set(m);
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  editItem(i: InventoryItem | null) {
    this.editing.set(true);
    this.editId.set(i?.id ?? null);
    this.itemForm.reset(
      i
        ? { ...i, minimum_stock: +i.minimum_stock }
        : { code: '', name: '', unit: 'pz', minimum_stock: 0, is_active: true },
    );
  }
  async saveItem() {
    if (this.itemForm.invalid) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const v = this.itemForm.getRawValue(),
        body = { ...v, minimum_stock: String(v.minimum_stock) };
      await firstValueFrom(
        this.editId()
          ? this.api.patch(`inventory/items/${this.editId()}/`, body)
          : this.api.post('inventory/items/', body),
      );
      this.editing.set(false);
      this.success.set('Articolo salvato.');
      await this.load();
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
  async move() {
    if (this.movementForm.invalid) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const v = this.movementForm.getRawValue();
      const movement = await firstValueFrom(
        this.api.post<InventoryMovement>('inventory/movements/', {
          ...v,
          quantity: String(v.quantity),
        }),
      );
      this.items.update((items) =>
        items.map((item) =>
          item.id === movement.item ? { ...item, quantity: movement.quantity_after } : item,
        ),
      );
      this.movements.update((movements) => [movement, ...movements]);
      const article = this.items().find((item) => item.id === movement.item);
      this.success.set(
        `Movimento registrato. Giacenza aggiornata: ${movement.quantity_after} ${article?.unit ?? ''}.`,
      );
      this.movementForm.reset({ direction: 'in' });
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}
