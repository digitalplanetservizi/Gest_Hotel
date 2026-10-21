import { bootstrapApplication } from '@angular/platform-browser';
import { provideHttpClient, withInterceptors, withXsrfConfiguration } from '@angular/common/http';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { LOCALE_ID } from '@angular/core';
import { registerLocaleData } from '@angular/common';
import localeIt from '@angular/common/locales/it';
import { AppComponent } from './app/app.component';
import { routes } from './app/app.routes';
import { sessionInterceptor } from './app/core/auth.service';
registerLocaleData(localeIt);
bootstrapApplication(AppComponent, {
  providers: [
    { provide: LOCALE_ID, useValue: 'it-IT' },
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(
      withXsrfConfiguration({ cookieName: 'csrftoken', headerName: 'X-CSRFToken' }),
      withInterceptors([sessionInterceptor]),
    ),
  ],
}).catch((error) => console.error(error));
