-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.articles (
  title text NOT NULL,
  content text NOT NULL,
  keywords jsonb NOT NULL,
  metadata jsonb,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp without time zone DEFAULT now(),
  CONSTRAINT articles_pkey PRIMARY KEY (id)
);
CREATE TABLE public.blacklist (
  term text NOT NULL UNIQUE,
  uuid uuid NOT NULL DEFAULT gen_random_uuid(),
  id integer NOT NULL DEFAULT nextval('blacklist_id_seq'::regclass),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT blacklist_pkey PRIMARY KEY (uuid)
);
CREATE TABLE public.filtered_keywords (
  text text NOT NULL,
  similarity double precision DEFAULT 0.0,
  score double precision DEFAULT 0.0,
  created_at timestamp without time zone DEFAULT now(),
  uuid uuid NOT NULL DEFAULT gen_random_uuid(),
  id integer NOT NULL DEFAULT nextval('filtered_keywords_id_seq'::regclass),
  CONSTRAINT filtered_keywords_pkey PRIMARY KEY (uuid)
);
CREATE TABLE public.intent_patterns (
  pattern text NOT NULL UNIQUE,
  uuid uuid NOT NULL DEFAULT gen_random_uuid(),
  id integer NOT NULL DEFAULT nextval('intent_patterns_id_seq'::regclass),
  CONSTRAINT intent_patterns_pkey PRIMARY KEY (uuid)
);
CREATE TABLE public.keywords (
  text text NOT NULL,
  volume integer NOT NULL,
  trend double precision NOT NULL,
  competition_level text NOT NULL CHECK (competition_level = ANY (ARRAY['low'::text, 'medium'::text, 'high'::text])),
  metadata jsonb,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp without time zone DEFAULT now(),
  CONSTRAINT keywords_pkey PRIMARY KEY (id)
);
CREATE TABLE public.raw_keywords (
  text text NOT NULL,
  competition_level text,
  volume integer DEFAULT 0,
  trend double precision DEFAULT 0.0,
  id integer NOT NULL DEFAULT nextval('raw_keywords_id_seq'::regclass),
  created_at timestamp without time zone DEFAULT now(),
  uuid uuid NOT NULL DEFAULT gen_random_uuid(),
  CONSTRAINT raw_keywords_pkey PRIMARY KEY (uuid)
);
CREATE TABLE public.seed_keywords (
  keyword text NOT NULL UNIQUE,
  uuid uuid NOT NULL DEFAULT gen_random_uuid(),
  id integer NOT NULL DEFAULT nextval('seed_keywords_id_seq'::regclass),
  category text,
  CONSTRAINT seed_keywords_pkey PRIMARY KEY (uuid)
);
