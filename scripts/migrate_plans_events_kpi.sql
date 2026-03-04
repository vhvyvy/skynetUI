-- Планы, события, KPI — постоянное хранение в PostgreSQL
-- Выполнить в Neon SQL Editor

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
