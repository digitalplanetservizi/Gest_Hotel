import { Component, effect, inject, input, output, signal } from '@angular/core';
import { FormControl, FormRecord, ReactiveFormsModule, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { FeedbackComponent } from './feedback.component';
export type FieldValue = string | number | boolean | null;
export interface EditorField {
  key: string;
  label: string;
  type?:
    | 'text'
    | 'number'
    | 'email'
    | 'date'
    | 'time'
    | 'password'
    | 'color'
    | 'select'
    | 'checkbox';
  required?: boolean;
  default?: FieldValue;
  min?: number;
  step?: string;
  options?: { value: FieldValue; label: string }[];
  displayKey?: string;
  table?: boolean;
  hint?: string;
}
export interface EditorFilter {
  key: string;
  label: string;
  options: { value: FieldValue; label: string }[];
  default?: FieldValue;
}
export interface ResourceConfig {
  title: string;
  subtitle: string;
  endpoint: string;
  singular: string;
  fields: EditorField[];
  filters?: EditorFilter[];
  allowDelete?: boolean;
  deleteConfirm?: string;
}
type Row = Record<string, unknown> & { id: number };
@Component({
  selector: 'app-resource-editor',
  imports: [ReactiveFormsModule, FeedbackComponent],
  template: ` <div class="toolbar">
      <div>
        <h2 class="text-lg font-semibold text-slate-800">{{ config().title }}</h2>
        <p class="subtitle">{{ config().subtitle }}</p>
      </div>
      <button class="btn" (click)="edit(null)">+ {{ config().singular }}</button>
    </div>
    @if (config().filters?.length) {
      <div class="mb-5 flex flex-wrap items-end gap-3" aria-label="Filtri elenco">
        @for (filter of config().filters; track filter.key) {
          <label class="field w-full max-w-xs"
            >{{ filter.label }}
            <select
              class="control"
              [value]="filterValue(filter.key)"
              (change)="setFilter(filter, $event)"
            >
              @for (option of filter.options; track $index) {
                <option [value]="option.value ?? ''">{{ option.label }}</option>
              }
            </select>
          </label>
        }
      </div>
    }
    <app-feedback [loading]="loading()" [error]="error()" [success]="success()" />
    @if (editing()) {
      <section class="card mb-5">
        <h3 class="mb-4 font-semibold">
          {{ selected() ? 'Modifica' : 'Nuovo' }} {{ config().singular.toLowerCase() }}
        </h3>
        <form [formGroup]="form" (ngSubmit)="save()" class="form-grid">
          @for (f of config().fields; track f.key) {
            @if (f.type === 'checkbox') {
              <label class="flex items-center gap-2 text-sm"
                ><input type="checkbox" [formControlName]="f.key" />{{ f.label }}</label
              >
            } @else {
              <label class="field" [attr.for]="'resource-' + f.key"
                >{{ f.label }} {{ f.required ? '*' : '' }}
                @if (f.type === 'select') {
                  <select class="control" [id]="'resource-' + f.key" [formControlName]="f.key">
                    @for (o of f.options; track $index) {
                      <option [ngValue]="o.value">{{ o.label }}</option>
                    }
                  </select>
                } @else {
                  <input
                    class="control"
                    [id]="'resource-' + f.key"
                    [type]="f.type || 'text'"
                    [formControlName]="f.key"
                    [attr.min]="f.min ?? null"
                    [attr.step]="f.step ?? null"
                    [attr.autocomplete]="f.type === 'password' ? 'new-password' : null"
                  />
                }
                @if (f.hint) {
                  <span class="text-xs font-normal text-slate-400">{{ f.hint }}</span>
                }
                @if (form.controls[f.key].touched && form.controls[f.key].invalid) {
                  <span class="text-xs text-red-600">Controlla il valore del campo.</span>
                }
              </label>
            }
          }
          <div class="flex gap-2 sm:col-span-2">
            <button class="btn" [disabled]="busy() || form.invalid">
              {{ busy() ? 'Salvataggio…' : 'Salva' }}</button
            ><button class="btn-secondary" type="button" (click)="editing.set(false)">
              Annulla
            </button>
          </div>
        </form>
      </section>
    }
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            @for (f of columns(); track f.key) {
              <th>{{ f.label }}</th>
            }
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (row of rows(); track row.id) {
            <tr>
              @for (f of columns(); track f.key) {
                <td>
                  @if (f.type === 'color') {
                    <span
                      class="inline-block size-4 rounded"
                      [style.background]="color(row[f.key])"
                    ></span>
                  } @else {
                    {{ display(row[f.key], f, row) }}
                  }
                </td>
              }
              <td class="whitespace-nowrap">
                <button
                  class="font-medium text-brand hover:underline disabled:opacity-40"
                  [disabled]="!canEdit(row)"
                  (click)="edit(row)"
                >
                  Modifica
                </button>
                @if (canDelete()) {
                  <button
                    class="ml-3 font-medium text-red-600 hover:underline disabled:opacity-50"
                    [disabled]="busy()"
                    (click)="remove(row)"
                  >
                    Elimina
                  </button>
                }
              </td>
            </tr>
          } @empty {
            <tr>
              <td [attr.colspan]="columns().length + 1" class="py-8 text-center text-slate-500">
                Nessun elemento configurato.
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>`,
})
export class ResourceEditorComponent {
  readonly config = input.required<ResourceConfig>();
  readonly changed = output<void>();
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  readonly rows = signal<Row[]>([]);
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly editing = signal(false);
  readonly selected = signal<number | null>(null);
  readonly error = signal('');
  readonly success = signal('');
  readonly activeFilters = signal<Record<string, FieldValue>>({});
  readonly form = new FormRecord<FormControl<FieldValue>>({});
  constructor() {
    effect(() => {
      const c = this.config();
      for (const key of Object.keys(this.form.controls)) this.form.removeControl(key);
      for (const f of c.fields) {
        const validators = [];
        if (f.required) validators.push(Validators.required);
        if (f.type === 'email') validators.push(Validators.email);
        if (f.min !== undefined) validators.push(Validators.min(f.min));
        this.form.addControl(
          f.key,
          new FormControl<FieldValue>(
            f.default !== undefined ? f.default : f.type === 'checkbox' ? true : '',
            validators,
          ),
        );
      }
      this.editing.set(false);
      this.success.set('');
      this.activeFilters.set(
        Object.fromEntries((c.filters ?? []).map((filter) => [filter.key, filter.default ?? ''])),
      );
      void this.load(c.endpoint);
    });
  }
  columns() {
    return this.config().fields.filter((f) => f.type !== 'password' && f.table !== false);
  }
  display(v: unknown, f: EditorField, row?: Row) {
    if (f.type === 'checkbox') return v ? 'Attivo' : 'Disattivato';
    if (f.type === 'select') {
      const resolved = f.displayKey ? row?.[f.displayKey] : undefined;
      if (resolved !== null && resolved !== undefined && resolved !== '') return String(resolved);
      return f.options?.find((o) => o.value === v)?.label ?? String(v ?? '—');
    }
    return v === null || v === undefined || v === '' ? '—' : String(v);
  }
  color(v: unknown) {
    return typeof v === 'string' && /^#[0-9a-f]{6}$/i.test(v) ? v : '#7367f0';
  }
  canDelete() {
    return this.config().allowDelete === true && this.auth.isAdmin();
  }
  canEdit(row: Row) {
    return (
      this.config().endpoint !== 'users/' ||
      row['role'] !== 'superadmin' ||
      this.auth.isSuperadmin()
    );
  }
  filterValue(key: string) {
    return String(this.activeFilters()[key] ?? '');
  }
  setFilter(filter: EditorFilter, event: Event) {
    const rawValue = (event.target as HTMLSelectElement).value;
    const option = filter.options.find((item) => String(item.value ?? '') === rawValue);
    this.activeFilters.update((current) => ({
      ...current,
      [filter.key]: option?.value ?? rawValue,
    }));
    void this.load();
  }
  async load(endpoint = this.config().endpoint) {
    this.loading.set(true);
    this.error.set('');
    try {
      const params = Object.fromEntries(
        Object.entries(this.activeFilters()).filter(([, value]) => value !== '' && value !== null),
      ) as Record<string, string | number>;
      this.rows.set(await firstValueFrom(this.api.list<Row>(endpoint, params)));
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  edit(row: Row | null) {
    this.selected.set(row?.id ?? null);
    this.editing.set(true);
    this.error.set('');
    for (const f of this.config().fields) {
      const control = this.form.controls[f.key];
      control.setValue(
        f.type === 'password'
          ? ''
          : ((row && Object.prototype.hasOwnProperty.call(row, f.key)
              ? row[f.key]
              : f.default !== undefined
                ? f.default
                : f.type === 'checkbox'
                  ? true
                  : '') as FieldValue),
      );
      if (f.type === 'password') {
        control.setValidators(row ? [] : Validators.required);
        control.updateValueAndValidity();
      }
      control.markAsUntouched();
    }
  }
  async save() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.success.set('');
    const body = { ...this.form.getRawValue() };
    for (const f of this.config().fields) {
      if (f.type === 'password' && !body[f.key]) delete body[f.key];
      if (f.type === 'number' && body[f.key] !== null && body[f.key] !== '')
        body[f.key] = Number(body[f.key]);
    }
    try {
      const path = this.config().endpoint;
      await firstValueFrom(
        this.selected()
          ? this.api.patch(path + this.selected() + '/', body)
          : this.api.post(path, body),
      );
      this.editing.set(false);
      this.success.set('Configurazione salvata.');
      await this.load();
      this.changed.emit();
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
  async remove(row: Row) {
    const message =
      this.config().deleteConfirm ??
      `Eliminare definitivamente questo ${this.config().singular.toLowerCase()}?`;
    if (!window.confirm(message)) return;
    this.busy.set(true);
    this.error.set('');
    this.success.set('');
    try {
      await firstValueFrom(this.api.delete(`${this.config().endpoint}${row.id}/`));
      if (this.selected() === row.id) this.editing.set(false);
      this.success.set('Elemento eliminato.');
      await this.load();
      this.changed.emit();
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}
