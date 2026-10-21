import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService, errorMessage, saveBlob } from '../../core/api.service';
import { FeedbackComponent } from '../../shared/feedback.component';

interface License {
  enabled: boolean;
  expires_on: string | null;
  active: boolean;
  status: string;
  timezone: string;
}
interface RecoveryBackup {
  id: number;
  created_at: string;
}

@Component({
  selector: 'app-superadmin',
  imports: [ReactiveFormsModule, FeedbackComponent, DatePipe],
  template: `<div class="mb-6">
      <h1 class="page-title">Superadmin</h1>
      <p class="subtitle">Licenza della piattaforma e ripristino dei dati.</p>
    </div>
    <app-feedback [loading]="loading()" [error]="error()" [success]="success()" />
    <div class="grid gap-6 xl:grid-cols-2">
      <section class="card">
        <h2 class="text-lg font-semibold">Licenza</h2>
        @if (license(); as current) {
          <p class="my-4 font-medium" [class.text-red-700]="!current.active">
            Stato:
            {{
              current.active ? 'Attiva' : current.status === 'expired' ? 'Scaduta' : 'Disattivata'
            }}
          </p>
        }
        <form [formGroup]="licenseForm" (ngSubmit)="saveLicense()" class="space-y-5">
          <label class="flex items-center gap-2 text-sm"
            ><input type="checkbox" formControlName="enabled" />Licenza abilitata</label
          >
          <label class="field"
            >Scadenza<input class="control" type="date" formControlName="expires_on" />
            <span class="text-xs text-slate-500"
              >Valida fino alla fine del giorno indicato ({{
                license()?.timezone || 'Europe/Rome'
              }}). Lascia vuoto per nessuna scadenza.</span
            >
          </label>
          <button class="btn" [disabled]="busy() || loading()">Salva licenza</button>
        </form>
      </section>
      <section class="card">
        <h2 class="text-lg font-semibold">Backup dei dati</h2>
        <p class="my-4 text-sm text-slate-600">
          Scarica un backup di struttura, camere, soggiorni, conti, cassa, listini e magazzino.
          Account, licenza e registro attività vengono conservati al ripristino.
        </p>
        <button class="btn-secondary" [disabled]="busy() || loading()" (click)="download()">
          Scarica backup
        </button>
        <p class="mt-4 text-xs text-slate-500">
          Formato .hotel-backup.json, massimo 20 MB, valido per questa installazione. I dump
          PostgreSQL .dump si ripristinano tramite gli strumenti del server.
        </p>
      </section>
      <section class="card xl:col-span-2">
        <h2 class="text-lg font-semibold">Ripristina da backup</h2>
        <p class="my-4 text-sm text-red-700">
          Il ripristino sostituisce i dati operativi attuali con quelli del backup. Viene prima
          salvata una copia di sicurezza scaricabile qui sotto. Se il ripristino fallisce, i dati
          attuali restano integri.
        </p>
        <form [formGroup]="restoreForm" (ngSubmit)="restore()" class="form-grid">
          <label class="field sm:col-span-2"
            >File di backup<input
              class="control"
              type="file"
              accept=".json"
              (change)="selectFile($event)"
          /></label>
          <label class="field"
            >Password superadmin<input
              class="control"
              type="password"
              autocomplete="current-password"
              formControlName="password"
          /></label>
          <label class="field"
            >Scrivi RIPRISTINA<input
              class="control"
              autocomplete="off"
              formControlName="confirmation"
          /></label>
          <div class="sm:col-span-2">
            <button class="btn" [disabled]="busy() || loading() || restoreForm.invalid || !file()">
              {{ busy() ? 'Operazione in corso…' : 'Ripristina dati' }}
            </button>
          </div>
        </form>
      </section>
      <section class="card xl:col-span-2">
        <h2 class="mb-4 text-lg font-semibold">Copie di sicurezza prima dei ripristini</h2>
        <div class="space-y-3">
          @for (backup of recoveries(); track backup.id) {
            <div
              class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3"
            >
              <span
                >Copia #{{ backup.id }} · {{ backup.created_at | date: 'dd/MM/yyyy HH:mm' }}</span
              >
              <button class="btn-secondary" [disabled]="busy()" (click)="download(backup.id)">
                Scarica copia
              </button>
            </div>
          } @empty {
            <p class="text-sm text-slate-500">Nessun ripristino eseguito.</p>
          }
        </div>
      </section>
    </div>`,
})
export class SuperadminComponent {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder).nonNullable;
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  readonly license = signal<License | null>(null);
  readonly recoveries = signal<RecoveryBackup[]>([]);
  readonly file = signal<File | null>(null);
  readonly licenseForm = this.fb.group({ enabled: true, expires_on: '' });
  readonly restoreForm = this.fb.group({
    password: ['', Validators.required],
    confirmation: ['', [Validators.required, Validators.pattern(/^RIPRISTINA$/)]],
  });
  constructor() {
    void this.load();
  }
  async load() {
    this.loading.set(true);
    try {
      const [license, copies] = await Promise.all([
        firstValueFrom(this.api.get<License>('superadmin/license/')),
        firstValueFrom(this.api.get<RecoveryBackup[]>('superadmin/recovery-backups/')),
      ]);
      this.license.set(license);
      this.licenseForm.patchValue({
        enabled: license.enabled,
        expires_on: license.expires_on ?? '',
      });
      this.recoveries.set(copies);
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
  selectFile(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.file.set(file && file.size <= 20 * 1024 * 1024 ? file : null);
    this.error.set(file && !this.file() ? 'Il backup supera il limite di 20 MB.' : '');
  }
  async saveLicense() {
    await this.run(async () => {
      const value = this.licenseForm.getRawValue();
      this.license.set(
        await firstValueFrom(
          this.api.patch<License>('superadmin/license/', {
            ...value,
            expires_on: value.expires_on || null,
          }),
        ),
      );
      this.success.set('Licenza aggiornata.');
    });
  }
  async download(id?: number) {
    await this.run(async () => {
      const path = id ? `superadmin/recovery-backups/${id}/` : 'superadmin/backup/';
      saveBlob(
        await firstValueFrom(this.api.download(path)),
        `hotel-${id ?? Date.now()}.hotel-backup.json`,
      );
    });
  }
  async restore() {
    const file = this.file();
    if (!file || this.restoreForm.invalid) return;
    await this.run(async () => {
      const body = new FormData();
      body.append('file', file);
      body.append('password', this.restoreForm.getRawValue().password);
      body.append('confirmation', this.restoreForm.getRawValue().confirmation);
      const result = await firstValueFrom(
        this.api.post<{ detail: string }>('superadmin/restore/', body),
      );
      this.restoreForm.reset();
      this.success.set(result.detail);
      await this.load();
    });
  }
  private async run(action: () => Promise<void>) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.success.set('');
    try {
      await action();
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}
