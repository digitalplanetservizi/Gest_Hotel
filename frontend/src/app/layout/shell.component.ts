import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { DatePipe } from '@angular/common';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../core/auth.service';
import { ApiService, errorMessage } from '../core/api.service';
import { Hotel } from '../core/models';
@Component({
  selector: 'app-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, DatePipe],
  template: ` <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-white focus:p-4"
      >Vai al contenuto</a
    >
    @if (menuOpen()) {
      <button
        aria-label="Chiudi menu"
        class="fixed inset-0 z-30 bg-black/40 lg:hidden"
        (click)="menuOpen.set(false)"
      ></button>
    }
    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-sidebar p-4 text-white transition-transform lg:translate-x-0"
      [class.-translate-x-full]="!menuOpen()"
    >
      <a routerLink="/dashboard" class="mb-8 flex items-center gap-3 px-2 pt-3"
        ><span class="flex size-10 items-center justify-center rounded-xl bg-brand text-xl">H</span
        ><span
          ><strong class="block text-lg">{{ hotelName() }}</strong
          ><span class="text-xs text-slate-400">Gestione della struttura</span></span
        ></a
      >
      <p class="mb-3 px-3 text-[10px] font-semibold tracking-[.2em] text-slate-400">
        AREA OPERATIVA
      </p>
      <nav aria-label="Navigazione principale" class="flex-1 space-y-1 overflow-y-auto">
        @for (link of visibleLinks(); track link.path) {
          <a
            [routerLink]="link.path"
            routerLinkActive="bg-brand text-white shadow-lg shadow-violet-900/20"
            (click)="menuOpen.set(false)"
            class="flex items-center gap-3 rounded-lg px-3 py-3 text-sm text-slate-300 hover:bg-white/10"
            ><span class="w-5 text-center text-base" aria-hidden="true">{{ link.icon }}</span
            >{{ link.label }}</a
          >
        }
      </nav>
      <div class="mt-4 border-t border-white/10 pt-4 text-xs text-slate-400">
        Una struttura, tutto sotto controllo.
        <p class="mt-2">{{ now | date: 'dd MMMM yyyy' }}</p>
      </div>
    </aside>
    <div class="min-h-screen lg:pl-64">
      <header
        class="sticky top-0 z-20 flex min-h-20 items-center justify-between gap-4 border-b border-slate-200 bg-white/95 px-5 backdrop-blur md:px-8"
      >
        <div class="flex items-center gap-3">
          <button
            class="btn-secondary lg:hidden"
            aria-label="Apri menu"
            (click)="menuOpen.set(true)"
          >
            ☰
          </button>
          <div>
            <p class="text-sm font-semibold text-slate-700">
              Benvenuto, {{ auth.user()?.first_name || 'operatore' }}
            </p>
            <p class="text-xs text-slate-400">Hotel management · V2</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <span
            class="hidden rounded-full bg-violet-50 px-3 py-1 text-xs font-medium text-brand sm:inline"
            >{{
              auth.isSuperadmin() ? 'Superadmin' : auth.isAdmin() ? 'Amministratore' : 'Operatore'
            }}</span
          ><button class="btn-secondary" [disabled]="leaving()" (click)="logout()">Esci</button>
        </div>
      </header>
      @if (error()) {
        <p role="alert" class="m-4 text-red-700">{{ error() }}</p>
      }
      <main id="main-content" class="mx-auto max-w-[1800px] p-4 md:p-8"><router-outlet /></main>
    </div>`,
})
export class ShellComponent {
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  readonly menuOpen = signal(false);
  readonly leaving = signal(false);
  readonly error = signal('');
  readonly hotelName = signal('Hotel Tempio');
  readonly now = new Date();
  readonly links = [
    { path: '/dashboard', label: 'Dashboard', icon: '◫' },
    { path: '/planning', label: 'Planning', icon: '▦' },
    { path: '/cassa', label: 'Cassa', icon: '€' },
    { path: '/mance', label: 'Mance', icon: '♥' },
    { path: '/listino', label: 'Listino', icon: '≡', adminOnly: true },
    { path: '/causali', label: 'Causali', icon: '↔', adminOnly: true },
    { path: '/magazzino', label: 'Magazzino', icon: '▤' },
    { path: '/report', label: 'Report', icon: '▥' },
    { path: '/utenti', label: 'Utenti', icon: '♙', adminOnly: true },
    { path: '/impostazioni', label: 'Impostazioni', icon: '⚙', adminOnly: true },
    { path: '/registro-attivita', label: 'Registro attività', icon: '◷', adminOnly: true },
    { path: '/superadmin', label: 'Superadmin', icon: '◆', superadminOnly: true },
  ];
  visibleLinks() {
    return this.links.filter(
      (link) =>
        (!link.adminOnly || this.auth.isAdmin()) &&
        (!link.superadminOnly || this.auth.isSuperadmin()),
    );
  }
  constructor() {
    void firstValueFrom(this.api.get<Hotel>('settings/'))
      .then((h) => this.hotelName.set(h.name))
      .catch(() => {});
  }
  async logout() {
    this.leaving.set(true);
    try {
      await this.auth.logout();
      await this.router.navigate(['/login']);
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.leaving.set(false);
    }
  }
}
