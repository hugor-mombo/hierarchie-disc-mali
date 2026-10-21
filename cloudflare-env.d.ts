declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    BUCKET?: R2Bucket;
    DHIS_USER?: string;
    DHIS_PASSWORD?: string;
    DISC_USER?: string;
    DISC_PASSWORD?: string;
  }
}
