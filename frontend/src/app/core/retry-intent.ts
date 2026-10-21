/** Preserve one idempotency key when a committed payment's response is lost. */
export class RetryIntent {
  private fingerprint = '';
  private key = '';
  private readonly createKey: () => string;
  constructor(createKey: () => string = () => crypto.randomUUID()) {
    this.createKey = createKey;
  }
  forPayload(payload: unknown): string {
    const fingerprint = JSON.stringify(payload);
    if (fingerprint !== this.fingerprint || !this.key) {
      this.fingerprint = fingerprint;
      this.key = this.createKey();
    }
    return this.key;
  }
  succeeded(): void {
    this.fingerprint = '';
    this.key = '';
  }
}
