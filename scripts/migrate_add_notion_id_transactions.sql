-- Миграция: notion_id для дедупликации transactions
-- Запустить в Neon SQL Editor, затем sync с --truncate-transactions

ALTER TABLE transactions ADD COLUMN IF NOT EXISTS notion_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_notion_id ON transactions(notion_id);
