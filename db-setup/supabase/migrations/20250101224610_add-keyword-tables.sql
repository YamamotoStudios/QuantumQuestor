-- Migration: Add tables for keyword management
CREATE TABLE raw_keywords (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    volume INT DEFAULT 0,
    competition_level TEXT,
    trend FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE filtered_keywords (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    similarity FLOAT DEFAULT 0.0,
    score FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE blacklist (
    id SERIAL PRIMARY KEY,
    term TEXT UNIQUE NOT NULL
);

CREATE TABLE intent_patterns (
    id SERIAL PRIMARY KEY,
    pattern TEXT UNIQUE NOT NULL
);

CREATE TABLE seed_keywords (
    id SERIAL PRIMARY KEY,
    keyword TEXT UNIQUE NOT NULL
);
