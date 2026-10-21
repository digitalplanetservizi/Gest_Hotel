import { Routes } from '@angular/router';
import { adminGuard, authGuard, superadminGuard } from './core/auth.service';
export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell.component').then((m) => m.ShellComponent),
    children: [
      {
        path: 'superadmin',
        canActivate: [superadminGuard],
        loadComponent: () =>
          import('./features/settings/superadmin.component').then((m) => m.SuperadminComponent),
      },
      {
        path: 'licenza-scaduta',
        loadComponent: () =>
          import('./features/settings/license-expired.component').then(
            (m) => m.LicenseExpiredComponent,
          ),
      },
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'planning',
        loadComponent: () =>
          import('./features/planning/planning.component').then((m) => m.PlanningComponent),
      },
      {
        path: 'soggiorni/nuovo',
        loadComponent: () =>
          import('./features/stays/stay-create.component').then((m) => m.StayCreateComponent),
      },
      {
        path: 'soggiorni/:id',
        loadComponent: () =>
          import('./features/stays/stay-detail.component').then((m) => m.StayDetailComponent),
      },
      {
        path: 'gruppi/:id',
        loadComponent: () =>
          import('./features/groups/group.component').then((m) => m.GroupComponent),
      },
      {
        path: 'cassa',
        loadComponent: () => import('./features/cash/cash.component').then((m) => m.CashComponent),
      },
      {
        path: 'mance',
        loadComponent: () => import('./features/tips/tips.component').then((m) => m.TipsComponent),
      },
      {
        path: 'magazzino',
        loadComponent: () =>
          import('./features/inventory/inventory.component').then((m) => m.InventoryComponent),
      },
      {
        path: 'report',
        loadComponent: () =>
          import('./features/reports/reports.component').then((m) => m.ReportsComponent),
      },
      {
        path: 'impostazioni',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./features/settings/settings.component').then((m) => m.SettingsComponent),
      },
      {
        path: 'listino',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./features/settings/catalog.component').then((m) => m.CatalogComponent),
        data: { section: 'rates' },
      },
      {
        path: 'causali',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./features/settings/catalog.component').then((m) => m.CatalogComponent),
        data: { section: 'reasons' },
      },
      {
        path: 'utenti',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./features/settings/catalog.component').then((m) => m.CatalogComponent),
        data: { section: 'users' },
      },
      {
        path: 'registro-attivita',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./features/audit/audit.component').then((m) => m.AuditComponent),
      },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
