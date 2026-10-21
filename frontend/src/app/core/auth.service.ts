import { inject, Injectable, signal } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, firstValueFrom, throwError } from 'rxjs';
import { ApiService } from './api.service';
import { User } from './models';
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  readonly user = signal<User | null>(null);
  isAdmin(): boolean {
    return ['admin', 'superadmin'].includes(this.user()?.role ?? '');
  }
  isSuperadmin(): boolean {
    return this.user()?.role === 'superadmin';
  }
  async restore(): Promise<boolean> {
    try {
      this.user.set(await firstValueFrom(this.api.get<User>('auth/me/')));
      return true;
    } catch {
      this.user.set(null);
      return false;
    }
  }
  async login(email: string, password: string): Promise<void> {
    await firstValueFrom(this.api.get('auth/csrf/'));
    await firstValueFrom(this.api.post('auth/login/', { email, password }));
    if (!(await this.restore())) throw new Error('Impossibile verificare la sessione. Riprova.');
  }
  async logout(): Promise<void> {
    await firstValueFrom(this.api.post('auth/logout/', {}));
    this.user.set(null);
  }
}
export const authGuard: CanActivateFn = async () => {
  const auth = inject(AuthService),
    router = inject(Router);
  return auth.user() || (await auth.restore()) ? true : router.createUrlTree(['/login']);
};
export const adminGuard: CanActivateFn = async () => {
  const auth = inject(AuthService),
    router = inject(Router);
  const user = auth.user() || ((await auth.restore()) ? auth.user() : null);
  return user && auth.isAdmin() ? true : router.createUrlTree(['/dashboard']);
};
export const superadminGuard: CanActivateFn = async () => {
  const auth = inject(AuthService),
    router = inject(Router);
  if (!auth.user()) await auth.restore();
  return auth.isSuperadmin() ? true : router.createUrlTree(['/dashboard']);
};
export const sessionInterceptor: HttpInterceptorFn = (request, next) => {
  const router = inject(Router);
  const auth = inject(AuthService);
  return next(request).pipe(
    catchError((error) => {
      if (error.error?.code === 'license_inactive') void router.navigate(['/licenza-scaduta']);
      if (
        (error.status === 401 || error.error?.code === 'not_authenticated') &&
        !request.url.includes('/auth/')
      ) {
        auth.user.set(null);
        void router.navigate(['/login']);
      }
      return throwError(() => error);
    }),
  );
};
