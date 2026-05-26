/**
 * Database factory.
 * 
 * Selects adapter based on DB_DRIVER env:
 *   - "sqlite" (default): local SQLite file
 *   - "mysql": MySQL/MariaDB via mysql2
 *   - "postgres": PostgreSQL via pg (future)
 * 
 * SQLite adapter is synchronous (returns values directly).
 * MySQL/Postgres adapters are async (return Promises).
 * 
 * The application layer uses a unified wrapper that handles both.
 */

const path = require('path');

function createDatabase() {
  const driver = (process.env.DB_DRIVER || 'sqlite').toLowerCase();
  const dataDir = process.env.DATA_DIR || path.join(__dirname, '..', '..', 'db');

  switch (driver) {
    case 'sqlite': {
      const SQLiteAdapter = require('./sqlite');
      const adapter = new SQLiteAdapter(dataDir);
      // Wrap sync methods to also work in async context
      return wrapSync(adapter);
    }

    case 'mysql':
    case 'mariadb': {
      const MySQLAdapter = require('./mysql');
      const adapter = new MySQLAdapter({
        host: process.env.DB_HOST || 'localhost',
        port: parseInt(process.env.DB_PORT) || 3306,
        user: process.env.DB_USER || 'root',
        password: process.env.DB_PASSWORD || '',
        database: process.env.DB_NAME || 'hermes_hub'
      });
      return { ...adapter, _async: true, ready: () => adapter.ready() };
    }

    // case 'postgres':
    //   TODO: PostgreSQL adapter

    default:
      throw new Error(`Unknown DB_DRIVER: ${driver}. Supported: sqlite, mysql`);
  }
}

/**
 * Wrap synchronous SQLite adapter so callers can use await uniformly.
 * Methods return plain values (not Promises) but await on them still works.
 */
function wrapSync(adapter) {
  return new Proxy(adapter, {
    get(target, prop) {
      if (prop === '_async') return false;
      if (prop === 'ready') return () => Promise.resolve();
      const val = target[prop];
      if (typeof val === 'function') {
        return val.bind(target);
      }
      return val;
    }
  });
}

// Singleton
let instance = null;

function getDatabase() {
  if (!instance) {
    instance = createDatabase();
  }
  return instance;
}

module.exports = { getDatabase };
