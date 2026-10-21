import { Pipe, PipeTransform } from '@angular/core';
import { formatHotelDateTime } from '../core/hotel-date-time';

@Pipe({ name: 'hotelDateTime' })
export class HotelDateTimePipe implements PipeTransform {
  transform(value: string | null, timeZone = 'Europe/Rome'): string {
    return formatHotelDateTime(value, timeZone);
  }
}
