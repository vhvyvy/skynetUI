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
  notion_id TEXT,
  date DATE,
  model TEXT,
  chatter TEXT,
  amount NUMERIC,
  shift_id TEXT,
  shift_name TEXT,
  month_source TEXT,
  synced_at TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_notion_id ON transactions(notion_id);

CREATE TABLE IF NOT EXISTS shifts (
  id TEXT PRIMARY KEY,
  name TEXT
);

-- Планы, события, KPI (постоянное хранение)
CREATE TABLE IF NOT EXISTS plans (
  year INT NOT NULL,
  month INT NOT NULL,
  model TEXT NOT NULL,
  plan_amount NUMERIC NOT NULL,
  PRIMARY KEY (year, month, model)
);

CREATE TABLE IF NOT EXISTS events (
  id SERIAL PRIMARY KEY,
  date DATE NOT NULL,
  description TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);

CREATE TABLE IF NOT EXISTS chatter_kpi (
  year INT NOT NULL,
  month INT NOT NULL,
  chatter TEXT NOT NULL,
  ppv_open_rate NUMERIC,
  apv NUMERIC,
  total_chats NUMERIC,
  model TEXT,
  source TEXT DEFAULT 'manual',
  PRIMARY KEY (year, month, chatter)
);

-- Настройки приложения (проценты, флаги) — сохраняются между сессиями
CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- Маппинг Onlymonster user_id → отображаемое имя (чаттер). Редактируется в UI.
CREATE TABLE IF NOT EXISTS chatter_onlymonster_mapping (
  onlymonster_id TEXT PRIMARY KEY,
  display_names TEXT NOT NULL
);
