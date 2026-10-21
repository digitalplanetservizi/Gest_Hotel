import { inject, Injectable } from '@angular/core';
import { ApiService } from './api.service';
import { Charge, Planning, Quote, Stay } from './models';
@Injectable({ providedIn: 'root' })
export class StaysService {
  private readonly api = inject(ApiService);
  list(params: Record<string, string | number> = {}) {
    return this.api.list<Stay>('stays/', params);
  }
  get(id: number) {
    return this.api.get<Stay>(`stays/${id}/`);
  }
  planning(start: string, end: string) {
    return this.api.get<Planning>('planning/', { start, end });
  }
  create(body: unknown) {
    return this.api.post<Stay>('stays/', body);
  }
  quote(body: unknown) {
    return this.api.post<Quote>('stays/quote/', body);
  }
  action(id: number, action: string, body: unknown = {}) {
    return this.api.post<Stay>(`stays/${id}/${action}/`, body);
  }
  charges(id: number) {
    return this.api.list<Charge>(`stays/${id}/charges/`);
  }
  addCharge(id: number, body: unknown) {
    return this.api.post<Charge>(`stays/${id}/charges/`, body);
  }
}
