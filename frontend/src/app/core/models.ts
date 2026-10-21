export interface ListResponse<T> {
  count: number;
  results: T[];
}
export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active?: boolean;
}
export interface Hotel {
  name: string;
  address: string;
  phone: string;
  email: string;
  check_in_time: string;
  check_out_time: string;
  currency: string;
  timezone: string;
}
export interface Room {
  id: number;
  number: string;
  floor: string;
  room_type: string;
  capacity: number;
  is_active: boolean;
  default_group: number | null;
}
export interface Group {
  id: number;
  name: string;
  label: string;
  color: string;
  reference_name: string;
  reference_email: string;
  reference_phone: string;
  is_active: boolean;
}
export type StayStatus = 'reserved' | 'checked_in' | 'checked_out' | 'cancelled' | 'no_show';
export interface Stay {
  id: number;
  room: number;
  room_number: string;
  guest_name: string;
  guest_email: string;
  guest_phone: string;
  guest_count: number;
  board: string;
  group: number | null;
  group_name: string;
  group_color: string;
  group_label: string;
  arrival: string;
  departure: string;
  status: StayStatus;
  is_day_use: boolean;
  nightly_rate: string | null;
  notes: string;
  total: string;
  paid: string;
  balance: string;
  room_balance: string;
  extras_balance: string;
  segments?: { room: number; arrival: string; departure: string; active?: boolean }[];
}
export interface Rate {
  id: number;
  name: string;
  room_type: string;
  board: string;
  start_date: string;
  end_date: string;
  amount: string;
  basis: string;
  is_active: boolean;
}
export interface PriceItem {
  id: number;
  description: string;
  category: number | null;
  category_name: string | null;
  unit: string;
  price: string;
  is_active: boolean;
}
export interface PriceCategory {
  id: number;
  name: string;
  is_active: boolean;
}
export interface AuditEvent {
  id: number;
  actor: number | null;
  actor_name: string;
  actor_email: string | null;
  action: string;
  action_label: string;
  object_type: string;
  object_id: number;
  object_label: string;
  data: Record<string, unknown>;
  created_at: string;
}
export interface Charge {
  id: number;
  stay: number;
  kind: string;
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
  paid: string;
  balance: string;
  created_at: string;
  consumed_at: string | null;
  is_void?: boolean;
  voided_at?: string | null;
  void_reason?: string;
}
export interface Payment {
  id: number;
  stay: number | null;
  group: number | null;
  amount: string;
  kind: 'settlement' | 'tip';
  tip_amount: string;
  method: string;
  reason: string | number;
  scope: string;
  note: string;
  created_at: string;
  operator_name: string;
  shift: number | null;
  reverses?: number;
}
export interface Shift {
  id: number;
  operator_name: string;
  opened_at: string;
  closed_at: string | null;
  opening_cash: string;
  expected_cash: string;
  counted_cash: string | null;
  difference: string | null;
  status: string;
}
export interface CashMovement {
  id: number;
  direction: string;
  amount: string;
  tip_amount: string;
  method: string;
  reason: string | number;
  description: string;
  operator_name: string;
  created_at: string;
}
export interface Reason {
  id: number;
  name: string;
  direction: string;
  is_active: boolean;
}
export interface InventoryItem {
  id: number;
  code: string;
  name: string;
  unit: string;
  quantity: string;
  minimum_stock: string;
  is_active: boolean;
}
export interface InventoryMovement {
  id: number;
  item: number;
  item_name?: string;
  direction: string;
  quantity: string;
  quantity_after: string;
  reason: string;
  created_at: string;
}
export interface Dashboard {
  rooms_total: number;
  rooms_occupied: number;
  arrivals_today: number;
  departures_today: number;
  outstanding: string;
  income_today: string;
  low_stock_count: number;
  arrivals?: Stay[];
  departures?: Stay[];
}
export interface Planning {
  rooms: Room[];
  stays: Stay[];
  groups: Group[];
}
export interface Quote {
  total: string;
  nights: number;
  lines: unknown[];
}
export interface Statement {
  group: Group;
  stays: Stay[];
  total: string;
  paid: string;
  balance: string;
  charges: Charge[];
  payments: Payment[];
}
export interface Report {
  income: string;
  expenses: string;
  balance: string;
  outstanding: string;
  occupancy: number | string;
  operators: User[];
  movements: CashMovement[];
  movements_count: number;
  by_operator_shift: {
    operator_id: number;
    operator_name: string;
    shift: number | null;
    day: string;
    movements_count: number;
    room_income: string;
    extra_income: string;
    income: string;
    expenses: string;
    balance: string;
  }[];
  sections: ReportSection[];
}
export interface ReportSection {
  key: 'rooms' | 'extras' | 'tips' | 'expenses' | 'other_income';
  label: string;
  total: string;
  rows: {
    id: string;
    created_at: string;
    display_date: string;
    account: string;
    direction: string;
    amount: string;
    method: string;
    reason: string;
    description: string;
    operator_name: string;
    shift: number | null;
  }[];
}
export interface TipReport {
  period: 'week' | 'month' | 'year';
  start_date: string;
  end_date: string;
  total: string;
  count: number;
  payments: Payment[];
}
export const STATUS_LABELS: Record<StayStatus, string> = {
  reserved: 'Prenotato',
  checked_in: 'In struttura',
  checked_out: 'Partito',
  cancelled: 'Annullato',
  no_show: 'No-show',
};
export const METHODS = [
  { value: 'cash', label: 'Contanti' },
  { value: 'card', label: 'Carta' },
  { value: 'transfer', label: 'Bonifico' },
];
export const BOARDS = [
  { value: 'RO', label: 'Solo camera' },
  { value: 'BB', label: 'Camera e colazione' },
  { value: 'HB', label: 'Mezza pensione' },
  { value: 'FB', label: 'Pensione completa' },
];
