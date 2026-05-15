import { Pool } from "pg";

declare global {
  // eslint-disable-next-line no-var
  var __nycBlockPulsePool: Pool | undefined;
}

const connectionString = process.env.DATABASE_URL;
const useSsl =
  connectionString?.includes("sslmode=require") ||
  process.env.PGSSLMODE === "require";

export const pool =
  globalThis.__nycBlockPulsePool ??
  new Pool({
    connectionString,
    max: 5,
    ssl: useSsl ? { rejectUnauthorized: false } : undefined,
  });

if (process.env.NODE_ENV !== "production") {
  globalThis.__nycBlockPulsePool = pool;
}
