-- Keywords Table
CREATE TABLE keywords (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text TEXT NOT NULL,
    volume INT NOT NULL,
    trend FLOAT NOT NULL,
    competition_level TEXT CHECK (competition_level IN ('low', 'medium', 'high')) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Articles Table
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    keywords JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for optimization
CREATE INDEX idx_keywords_volume ON keywords (volume DESC);
CREATE INDEX idx_keywords_trend ON keywords (trend DESC);
CREATE INDEX idx_articles_created_at ON articles (created_at DESC);
