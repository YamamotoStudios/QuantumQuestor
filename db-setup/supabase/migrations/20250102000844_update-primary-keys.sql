-- Migration: Convert existing tables to use UUID primary keys and add necessary indexes

-- Update raw_keywords table to use UUID
ALTER TABLE raw_keywords ADD COLUMN uuid UUID DEFAULT gen_random_uuid();
UPDATE raw_keywords SET uuid = gen_random_uuid();
ALTER TABLE raw_keywords DROP CONSTRAINT raw_keywords_pkey, ADD PRIMARY KEY (uuid);
-- Optional: Drop old SERIAL column if no longer needed
-- ALTER TABLE raw_keywords DROP COLUMN id;

-- Update filtered_keywords table to use UUID
ALTER TABLE filtered_keywords ADD COLUMN uuid UUID DEFAULT gen_random_uuid();
UPDATE filtered_keywords SET uuid = gen_random_uuid();
ALTER TABLE filtered_keywords DROP CONSTRAINT filtered_keywords_pkey, ADD PRIMARY KEY (uuid);
-- ALTER TABLE filtered_keywords DROP COLUMN id;

-- Update blacklist table to use UUID
ALTER TABLE blacklist ADD COLUMN uuid UUID DEFAULT gen_random_uuid();
UPDATE blacklist SET uuid = gen_random_uuid();
ALTER TABLE blacklist DROP CONSTRAINT blacklist_pkey, ADD PRIMARY KEY (uuid);
-- ALTER TABLE blacklist DROP COLUMN id;

-- Update intent_patterns table to use UUID
ALTER TABLE intent_patterns ADD COLUMN uuid UUID DEFAULT gen_random_uuid();
UPDATE intent_patterns SET uuid = gen_random_uuid();
ALTER TABLE intent_patterns DROP CONSTRAINT intent_patterns_pkey, ADD PRIMARY KEY (uuid);
-- ALTER TABLE intent_patterns DROP COLUMN id;

-- Update seed_keywords table to use UUID
ALTER TABLE seed_keywords ADD COLUMN uuid UUID DEFAULT gen_random_uuid();
UPDATE seed_keywords SET uuid = gen_random_uuid();
ALTER TABLE seed_keywords DROP CONSTRAINT seed_keywords_pkey, ADD PRIMARY KEY (uuid);
-- ALTER TABLE seed_keywords DROP COLUMN id;

-- Add necessary indexes for optimization
-- Optimize queries filtering by text in raw_keywords
CREATE INDEX idx_raw_keywords_text ON raw_keywords (text);

-- Optimize queries filtering by text in filtered_keywords
CREATE INDEX idx_filtered_keywords_text ON filtered_keywords (text);

-- Optimize queries filtering by term in blacklist
CREATE INDEX idx_blacklist_term ON blacklist (term);

-- Optimize queries filtering by pattern in intent_patterns
CREATE INDEX idx_intent_patterns_pattern ON intent_patterns (pattern);

-- Optimize queries filtering by keyword in seed_keywords
CREATE INDEX idx_seed_keywords_keyword ON seed_keywords (keyword);
