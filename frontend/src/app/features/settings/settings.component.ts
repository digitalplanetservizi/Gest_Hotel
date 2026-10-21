import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage, saveBlob } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Group, Hotel } from '../../core/models';
import { FeedbackComponent } from '../../shared/feedback.component';
import { ResourceConfig, ResourceEditorComponent } from '../../shared/resource-editor.component';
import { groupConfig, priceCategoryConfig } from './catalogs';
@Component({
  selector: 'app-settings',
  imports: [ReactiveFormsModule, RouterLink, FeedbackComponent, ResourceEditorComponent],
  template: `<div class="mb-6">
      <h1 class="page-title">Impostazioni</h1>
      <p class="subtitle">Configura struttura, camere e referenti prima di iniziare a operare.</p>
    </div>
    <nav class="mb-6 flex flex-wrap gap-2" aria-label="Sezioni impostazioni">
      @for (t of tabs; track t.value) {
        <button [class]="tab() === t.value ? 'btn' : 'btn-secondary'" (click)="tab.set(t.value)">
          {{ t.label }}
        </button>
      }
    </nav>
    <app-feedback [loading]="loading()" [error]="error()" [success]="success()" />
    @if (tab() === 'hotel') {
      <section class="card max-w-4xl">
        <h2 class="mb-5 font-semibold">Dati della struttura</h2>
        <form [formGroup]="form" (ngSubmit)="save()" class="form-grid">
          <label class="field sm:col-span-2"
            >Nome struttura<input class="control" formControlName="name" /></label
          ><label class="field sm:col-span-2"
            >Indirizzo<input class="control" formControlName="address" /></label
          ><label class="field"
            >Email<input class="control" type="email" formControlName="email" /></label
          ><label class="field">Telefono<input class="control" formControlName="phone" /></label
          ><label class="field"
            >Orario check-in<input
              class="control"
              type="time"
              formControlName="check_in_time" /></label
          ><label class="field"
            >Orario check-out<input
              class="control"
              type="time"
              formControlName="check_out_time" /></label
          ><label class="field"
            >Valuta<input class="control" formControlName="currency" readonly /><span
              class="text-xs text-slate-400"
              >Contabilità gestionale in euro.</span
            ></label
          ><label class="field"
            >Fuso orario IANA<input
              class="control"
              formControlName="timezone"
              placeholder="Europe/Rome"
          /></label>
          <div class="sm:col-span-2">
            <button class="btn" [disabled]="loading() || busy() || form.invalid">
              Salva struttura
            </button>
          </div>
        </form>
      </section>
      <div class="card mt-5 max-w-4xl">
        <h2 class="mb-2 font-semibold">Completa la configurazione</h2>
        <p class="text-sm text-slate-500">
          Definisci le tipologie delle camere e usa gli stessi nomi nel listino stagionale. Assegna
          i gruppi alle camere come proposta modificabile per ogni soggiorno.
        </p>
        <a class="btn-secondary mt-4" routerLink="/listino">Configura il listino →</a>
      </div>
    }
    @if (tab() === 'rooms') {
      <app-resource-editor [config]="roomConfig()" />
    }
    @if (tab() === 'groups') {
      <app-resource-editor [config]="groups" (changed)="loadGroups()" />
    }
    @if (tab() === 'price-categories') {
      <app-resource-editor [config]="priceCategories" />
    }
    @if (tab() === 'backup' && auth.isAdmin()) {
      <section class="card max-w-3xl">
        <h2 class="mb-2 font-semibold">Archivio completo dei dati</h2>
        <p class="mb-5 text-sm text-slate-500">
          Scarica un file ZIP in formato JSON con tutti i dati del gestionale: struttura, utenti,
          camere, listini, soggiorni, conti, cassa, magazzino e registro attività. Per creare un
          backup ripristinabile dalla piattaforma usa la sezione Superadmin.
        </p>
        <button class="btn" [disabled]="busy()" (click)="downloadBackup()">
          {{ busy() ? 'Preparazione archivio…' : 'Scarica backup dati' }}
        </button>
      </section>
    }`,
})
export class SettingsComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder).nonNullable;
  readonly tab = signal('hotel');
  readonly tabs: { value: string; label: string }[] = [
    { value: 'hotel', label: 'Struttura' },
    { value: 'rooms', label: 'Camere e capienze' },
    { value: 'groups', label: 'Gruppi e referenti' },
    { value: 'price-categories', label: 'Categorie extra' },
  ];
  readonly groups = groupConfig;
  readonly priceCategories = priceCategoryConfig;
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly form = this.fb.group({
    name: ['', Validators.required],
    address: [''],
    phone: [''],
    email: ['', Validators.email],
    check_in_time: ['14:00', Validators.required],
    check_out_time: ['10:00', Validators.required],
    currency: ['EUR', Validators.required],
    timezone: ['Europe/Rome', Validators.required],
  });
  readonly roomConfig = signal<ResourceConfig>({
    title: 'Camere',
    subtitle:
      'Numerazione libera, tipologia e capienza configurabili. Disattiva una camera per escluderla dalle nuove prenotazioni.',
    endpoint: 'rooms/',
    singular: 'Camera',
    fields: [
      { key: 'number', label: 'Numero / Nome', required: true },
      { key: 'floor', label: 'Piano', default: '' },
      {
        key: 'room_type',
        label: 'Tipologia',
        required: true,
        hint: 'Usa lo stesso nome nel listino.',
      },
      {
        key: 'capacity',
        label: 'Capienza',
        type: 'number',
        min: 1,
        step: '1',
        default: 2,
        required: true,
      },
      {
        key: 'default_group',
        label: 'Gruppo predefinito',
        type: 'select',
        default: null,
        options: [{ value: null, label: 'Nessuno' }],
      },
      { key: 'is_active', label: 'Attiva', type: 'checkbox', default: true },
    ],
  });
  constructor() {
    if (this.auth.isAdmin()) this.tabs.push({ value: 'backup', label: 'Backup dati' });
    void this.load();
  }
  async load() {
    this.loading.set(true);
    try {
      this.form.patchValue(await firstValueFrom(this.api.get<Hotel>('settings/')));
      await this.loadGroups();
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  async loadGroups() {
    try {
      const groups = await firstValueFrom(this.api.list<Group>('groups/'));
      this.roomConfig.update((c) => ({
        ...c,
        fields: c.fields.map((f) =>
          f.key === 'default_group'
            ? {
                ...f,
                options: [
                  { value: null, label: 'Nessuno' },
                  ...groups.filter((g) => g.is_active).map((g) => ({ value: g.id, label: g.name })),
                ],
              }
            : f,
        ),
      }));
    } catch (e) {
      this.error.set(errorMessage(e));
    }
  }
  async save() {
    if (this.form.invalid) return;
    this.busy.set(true);
    this.error.set('');
    this.success.set('');
    try {
      this.form.patchValue(
        await firstValueFrom(this.api.patch<Hotel>('settings/', this.form.getRawValue())),
      );
      this.success.set('Impostazioni della struttura salvate.');
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
  async downloadBackup() {
    this.busy.set(true);
    this.error.set('');
    this.success.set('');
    try {
      const archive = await firstValueFrom(this.api.download('backup/export/'));
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      saveBlob(archive, `backup-hotel-${stamp}.zip`);
      this.success.set('Archivio dati scaricato. Conservalo in un luogo protetto.');
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}
