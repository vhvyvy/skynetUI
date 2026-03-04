-- Индексы для ускорения запросов по дате
-- Выполнить в Neon SQL Editor

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
