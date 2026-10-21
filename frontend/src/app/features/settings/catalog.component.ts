import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { PriceCategory } from '../../core/models';
import { ResourceEditorComponent } from '../../shared/resource-editor.component';
import { priceConfig, rateConfig, reasonConfig, userConfig } from './catalogs';
@Component({
  selector: 'app-catalog',
  imports: [ResourceEditorComponent],
  template: `<div class="mb-6">
      <h1 class="page-title">
        {{ section === 'rates' ? 'Listino' : section === 'reasons' ? 'Causali' : 'Utenti' }}
      </h1>
      <p class="subtitle">Configurazione condivisa della struttura.</p>
    </div>
    @if (section === 'rates') {
      <nav class="mb-6 flex gap-2" aria-label="Tipo listino">
        <button [class]="tab() === 'rates' ? 'btn' : 'btn-secondary'" (click)="tab.set('rates')">
          Soggiorni e stagioni</button
        ><button [class]="tab() === 'extras' ? 'btn' : 'btn-secondary'" (click)="tab.set('extras')">
          Extra e servizi
        </button>
      </nav>
    }
    <app-resource-editor
      [config]="
        section === 'rates'
          ? tab() === 'rates'
            ? rates
            : extras()
          : section === 'reasons'
            ? reasons
            : users
      "
    />`,
})
export class CatalogComponent {
  private readonly api = inject(ApiService);
  readonly section = inject(ActivatedRoute).snapshot.data['section'] as string;
  readonly tab = signal('rates');
  readonly rates = rateConfig;
  readonly extras = signal(priceConfig);
  readonly reasons = reasonConfig;
  readonly users = {
    ...userConfig,
    fields: userConfig.fields.map((field) =>
      field.key === 'role' && !inject(AuthService).isSuperadmin()
        ? { ...field, options: field.options?.filter((option) => option.value !== 'superadmin') }
        : field,
    ),
  };
  constructor() {
    void this.loadCategories();
  }
  private async loadCategories() {
    try {
      const categories = await firstValueFrom(this.api.list<PriceCategory>('extra-categories/'));
      const options = [
        { value: null, label: 'Seleziona una categoria' },
        ...categories
          .filter((category) => category.is_active)
          .map((category) => ({
            value: category.id,
            label: category.name,
          })),
      ];
      this.extras.update((config) => ({
        ...config,
        fields: config.fields.map((field) =>
          field.key === 'category' ? { ...field, options } : field,
        ),
        filters: [
          {
            key: 'category',
            label: 'Filtra per categoria',
            default: '',
            options: [{ value: '', label: 'Tutte le categorie' }, ...options.slice(1)],
          },
        ],
      }));
    } catch {
      // Il listino resta disponibile; al successivo accesso ricaricherà le categorie configurate.
    }
  }
}
