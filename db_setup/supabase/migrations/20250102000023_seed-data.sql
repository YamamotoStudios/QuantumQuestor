-- Seed data for blacklist table
INSERT INTO blacklist (term) VALUES 
('game'),
('games'),
('technology'),
('news'),
('trends')
ON CONFLICT (term) DO NOTHING;

-- Seed data for intent_patterns table
INSERT INTO intent_patterns (pattern) VALUES 
('how to'),
('review'),
('guide'),
('analysis')
ON CONFLICT (pattern) DO NOTHING;

-- Seed data for seed_keywords table
INSERT INTO seed_keywords (keyword) VALUES 
('top gaming monitors'),
('Nvidia RTX graphics cards'),
('RPG gaming tips'),
('PC building for gamers'),
('quantum technology in games'),
('cloud gaming services'),
('indie video games'),
('headsets for gaming'),
('4K gaming graphics cards'),
('AI in video games'),
('popular gaming mice'),
('Cyberpunk 2077 news'),
('portable gaming screens'),
('Steam Deck gaming tips'),
('affordable gaming PCs'),
('gaming chairs for comfort'),
('mechanical keyboards for gaming'),
('GPU tips for performance'),
('multiplayer role-playing games')
ON CONFLICT (keyword) DO NOTHING;
