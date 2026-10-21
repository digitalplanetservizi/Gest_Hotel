import { Component, inject, input, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService, saveBlob } from '../core/api.service';

@Component({
  selector: 'app-extra-statement-download',
  template: `
    <div class="no-print">
      <button class="btn-secondary" type="button" [disabled]="busy()" (click)="download()">
        {{ busy() ? 'Preparazione PDF…' : 'Scarica PDF extra' }}
      </button>
      @if (error()) {
        <p role="alert" class="mt-2 max-w-xs text-sm text-red-600">{{ error() }}</p>
      }
    </div>
  `,
})
export class ExtraStatementDownloadComponent {
  private readonly api = inject(ApiService);
  readonly scope = input.required<'stays' | 'groups'>();
  readonly accountId = input.required<number>();
  readonly filename = input.required<string>();
  readonly busy = signal(false);
  readonly error = signal('');

  async download() {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      saveBlob(
        await firstValueFrom(this.api.download(`${this.scope()}/${this.accountId()}/extras/pdf/`)),
        this.filename(),
      );
    } catch {
      this.error.set('Download del PDF non riuscito. Verifica la connessione e riprova.');
    } finally {
      this.busy.set(false);
    }
  }
}
