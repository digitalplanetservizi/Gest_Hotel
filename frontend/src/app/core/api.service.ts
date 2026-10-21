import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { defer, firstValueFrom, Observable } from 'rxjs';
import { ListResponse } from './models';
@Injectable({ providedIn: 'root' })
export class ApiService {
  readonly http = inject(HttpClient);
  get<T>(path: string, params: Record<string, string | number> = {}): Observable<T> {
    return this.http.get<T>('/api/v1/' + path, { params: new HttpParams({ fromObject: params }) });
  }
  list<T>(path: string, params: Record<string, string | number> = {}): Observable<T[]> {
    return defer(async () => {
      const rows: T[] = [];
      let page = 1;
      let count = Infinity;
      while (rows.length < count) {
        const data = await firstValueFrom(
          this.get<ListResponse<T> | T[]>(path, { ...params, page, page_size: 500 }),
        );
        if (Array.isArray(data)) return data;
        count = data.count;
        rows.push(...data.results);
        if (data.results.length === 0) break;
        page++;
      }
      return rows;
    });
  }
  post<T>(path: string, body: unknown, idempotencyKey?: string): Observable<T> {
    return this.http.post<T>(
      '/api/v1/' + path,
      body,
      idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : {},
    );
  }
  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<T>('/api/v1/' + path, body);
  }
  delete(path: string): Observable<void> {
    return this.http.delete<void>('/api/v1/' + path);
  }
  download(path: string, params: Record<string, string> = {}): Observable<Blob> {
    return this.http.get('/api/v1/' + path, { params, responseType: 'blob' });
  }
}
export function errorMessage(error: unknown): string {
  if (!(error instanceof HttpErrorResponse)) return 'Operazione non riuscita. Riprova.';
  if (error.status === 0)
    return 'Il server non è raggiungibile. Controlla la connessione e riprova.';
  const body: unknown = error.error;
  if (typeof body === 'object' && body !== null) {
    const data = body as Record<string, unknown>;
    if (typeof data['detail'] === 'string') return data['detail'];
    return Object.entries(data)
      .map(
        ([key, value]) =>
          `${key}: ${Array.isArray(value) ? value.join(' ') : typeof value === 'object' ? JSON.stringify(value) : String(value)}`,
      )
      .join(' · ');
  }
  return 'Operazione non riuscita. Verifica i dati e riprova.';
}
export function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}
export function localDateTime(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
