-- Запуск: psql -h HOST -U USER -d DBNAME -f scripts/init_db.sql
-- Или в консоли Neon/Supabase → SQL Editor → вставить и Run

CREATE TABLE IF NOT EXISTS expenses (
  id SERIAL PRIMARY KEY,
  notion_id TEXT UNIQUE,
  date DATE,
  model TEXT,
  category TEXT,
  vendor TEXT,
  payment_method TEXT,
  amount NUMERIC
);

CREATE TABLE IF NOT EXISTS transactions (
  id SERIAL PRIMARY KEY,
  date DATE,
  model TEXT,
  chatter TEXT,
  amount NUMERIC,
  shift_id TEXT,
  shift_name TEXT,
  month_source TEXT,
  synced_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shifts (
  id TEXT PRIMARY KEY,
  name TEXT
);
