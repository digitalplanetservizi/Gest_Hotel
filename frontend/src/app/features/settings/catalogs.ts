import { ResourceConfig } from '../../shared/resource-editor.component';
import { BOARDS } from '../../core/models';
export const rateConfig: ResourceConfig = {
  title: 'Tariffe soggiorno',
  subtitle:
    'Listino per stagione, tipologia e trattamento. Periodi inclusivi senza sovrapposizioni.',
  endpoint: 'rates/',
  singular: 'Tariffa',
  fields: [
    { key: 'name', label: 'Nome stagione', required: true },
    { key: 'room_type', label: 'Tipologia camera', required: true },
    {
      key: 'board',
      label: 'Trattamento',
      type: 'select',
      required: true,
      default: 'BB',
      options: BOARDS,
    },
    { key: 'start_date', label: 'Dal', type: 'date', required: true },
    { key: 'end_date', label: 'Al', type: 'date', required: true },
    { key: 'amount', label: 'Importo (€)', type: 'number', min: 0, step: '0.01', required: true },
    {
      key: 'basis',
      label: 'Base tariffa',
      type: 'select',
      default: 'room',
      options: [
        { value: 'room', label: 'Camera / notte' },
        { value: 'person', label: 'Persona / notte' },
      ],
    },
    { key: 'is_active', label: 'Attiva', type: 'checkbox', default: true },
  ],
};
export const priceConfig: ResourceConfig = {
  title: 'Listino extra',
  subtitle:
    'Articoli e servizi con prezzo di base. Il codice interno viene assegnato automaticamente dal sistema.',
  endpoint: 'price-items/',
  singular: 'Extra',
  allowDelete: true,
  fields: [
    { key: 'description', label: 'Descrizione', required: true },
    {
      key: 'category',
      label: 'Categoria',
      type: 'select',
      required: true,
      default: null,
      options: [{ value: null, label: 'Seleziona una categoria' }],
      displayKey: 'category_name',
      hint: 'Gestisci le categorie da Impostazioni.',
    },
    { key: 'unit', label: 'Unità', default: 'pz', required: true },
    { key: 'price', label: 'Prezzo (€)', type: 'number', required: true, min: 0, step: '0.01' },
    { key: 'is_active', label: 'Attivo', type: 'checkbox', default: true },
  ],
};
export const priceCategoryConfig: ResourceConfig = {
  title: 'Categorie extra',
  subtitle: 'Organizza articoli e servizi del listino in categorie riutilizzabili.',
  endpoint: 'extra-categories/',
  singular: 'Categoria',
  allowDelete: true,
  deleteConfirm:
    'Eliminare definitivamente questa categoria? Prima occorre spostare o eliminare gli extra collegati.',
  fields: [
    { key: 'name', label: 'Nome categoria', required: true },
    { key: 'is_active', label: 'Attiva', type: 'checkbox', default: true },
  ],
};
export const reasonConfig: ResourceConfig = {
  title: 'Causali di cassa',
  subtitle: 'Le causali distinguono entrate e uscite del gestionale.',
  endpoint: 'cash/reasons/',
  singular: 'Causale',
  fields: [
    { key: 'name', label: 'Nome', required: true },
    {
      key: 'direction',
      label: 'Direzione',
      type: 'select',
      default: 'in',
      required: true,
      options: [
        { value: 'in', label: 'Entrata' },
        { value: 'out', label: 'Uscita' },
      ],
    },
    { key: 'is_active', label: 'Attiva', type: 'checkbox', default: true },
  ],
};
export const userConfig: ResourceConfig = {
  title: 'Account e privilegi',
  subtitle:
    'Operatori: attività quotidiane. Admin: configurazione e utenti. Superadmin: anche backup e licenza.',
  endpoint: 'users/',
  singular: 'Utente',
  fields: [
    { key: 'first_name', label: 'Nome', required: true },
    { key: 'last_name', label: 'Cognome', required: true },
    { key: 'email', label: 'Email', type: 'email', required: true },
    {
      key: 'password',
      label: 'Password',
      type: 'password',
      hint: 'Obbligatoria per i nuovi utenti. Lascia vuota per mantenere quella attuale.',
    },
    {
      key: 'role',
      label: 'Ruolo',
      type: 'select',
      default: 'operator',
      options: [
        { value: 'operator', label: 'Operatore' },
        { value: 'admin', label: 'Amministratore' },
        { value: 'superadmin', label: 'Superadmin' },
      ],
    },
    { key: 'is_active', label: 'Account attivo', type: 'checkbox', default: true },
  ],
};
export const groupConfig: ResourceConfig = {
  title: 'Gruppi e referenti',
  subtitle: 'Un solo referente per incassi, camere ed extra di ciascun gruppo.',
  endpoint: 'groups/',
  singular: 'Gruppo',
  fields: [
    { key: 'name', label: 'Nome gruppo', required: true },
    { key: 'label', label: 'Etichetta planning', required: true },
    { key: 'color', label: 'Colore', type: 'color', default: '#7367f0', required: true },
    { key: 'reference_name', label: 'Referente', required: true },
    { key: 'reference_email', label: 'Email referente', type: 'email' },
    { key: 'reference_phone', label: 'Telefono referente' },
    { key: 'is_active', label: 'Attivo', type: 'checkbox', default: true },
  ],
};
