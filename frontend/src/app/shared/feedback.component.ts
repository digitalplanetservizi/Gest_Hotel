import { Component, input } from '@angular/core';
@Component({
  selector: 'app-feedback',
  template: `@if (loading()) {
      <p role="status" class="mb-4 rounded-lg bg-violet-50 p-3 text-sm text-violet-700">
        Caricamento in corso…
      </p>
    }
    @if (error()) {
      <p
        role="alert"
        class="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        {{ error() }}
      </p>
    }
    @if (success()) {
      <p
        role="status"
        class="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700"
      >
        {{ success() }}
      </p>
    }`,
})
export class FeedbackComponent {
  readonly loading = input(false);
  readonly error = input('');
  readonly success = input('');
}
