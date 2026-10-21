import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { errorMessage } from '../../core/api.service';
import { FeedbackComponent } from '../../shared/feedback.component';
@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, FeedbackComponent],
  template: `<main class="grid min-h-screen lg:grid-cols-2">
    <section class="hidden flex-col justify-between bg-sidebar p-14 text-white lg:flex">
      <div class="text-xl font-bold">◫ Hotel Tempio</div>
      <div>
        <span class="text-sm uppercase tracking-[.25em] text-violet-300"
          >La tua struttura, con semplicità</span
        >
        <h1 class="mt-6 max-w-lg text-5xl font-semibold leading-tight">
          Ogni soggiorno.<br />Ogni dettaglio.<br />Un unico spazio.
        </h1>
        <p class="mt-7 max-w-md leading-relaxed text-slate-300">
          Planning, ospiti e conti sempre a portata di mano. Il tuo lavoro quotidiano, organizzato.
        </p>
      </div>
      <p class="text-sm text-slate-400">Gestionale alberghiero · V2</p>
    </section>
    <section class="flex items-center justify-center px-6 py-12">
      <div class="w-full max-w-sm">
        <div
          class="mb-8 flex size-12 items-center justify-center rounded-xl bg-brand text-xl text-white"
        >
          H
        </div>
        <h1 class="page-title">Accedi al gestionale</h1>
        <p class="subtitle mb-8">Inserisci le credenziali del tuo account.</p>
        <app-feedback [error]="error()" />
        <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-5">
          <label class="field"
            >Email<input
              class="control"
              type="email"
              formControlName="email"
              autocomplete="username"
              required /></label
          ><label class="field"
            >Password<input
              class="control"
              type="password"
              formControlName="password"
              autocomplete="current-password"
              required /></label
          ><button class="btn w-full" [disabled]="busy() || form.invalid">
            {{ busy() ? 'Accesso in corso…' : 'Accedi' }}
          </button>
        </form>
        <p class="mt-8 text-xs leading-relaxed text-slate-400">
          Per creare o recuperare un account, contatta l’amministratore della struttura.
        </p>
      </div>
    </section>
  </main>`,
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });
  async submit() {
    if (this.form.invalid) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const v = this.form.getRawValue();
      await this.auth.login(v.email, v.password);
      await this.router.navigate(['/dashboard']);
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}
