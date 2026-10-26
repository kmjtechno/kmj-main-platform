-- KMJ PostgreSQL metadata ONLY, public schema. No table rows or secrets.
-- Designed for psql -X -qAt -v ON_ERROR_STOP=1 -f pg_schema_metadata.sql
-- Caller selects a separately authorized connection. CI uses disposable Unix socket.
BEGIN TRANSACTION READ ONLY;
WITH
relations AS (
  SELECT jsonb_build_object(
      'schema', ns.nspname, 'table', cls.relname,
      'kind', cls.relkind
  ) AS obj
  FROM pg_catalog.pg_class cls
  JOIN pg_catalog.pg_namespace ns ON ns.oid = cls.relnamespace
  WHERE ns.nspname = 'public' AND cls.relkind IN ('r','p')
),
columns AS (
  SELECT jsonb_build_object(
      'schema', ns.nspname, 'table', cls.relname,
      'column', attr.attname,
      'type', pg_catalog.format_type(attr.atttypid,attr.atttypmod),
      'notNull', attr.attnotnull
  ) AS obj
  FROM pg_catalog.pg_attribute attr
  JOIN pg_catalog.pg_class cls ON cls.oid = attr.attrelid
  JOIN pg_catalog.pg_namespace ns ON ns.oid = cls.relnamespace
  WHERE ns.nspname = 'public'
    AND cls.relkind IN ('r','p')
    AND attr.attnum > 0 AND NOT attr.attisdropped
),
constraints AS (
  SELECT jsonb_build_object(
    'schema', ns.nspname, 'table', cls.relname,
    'name', con.conname, 'kind', con.contype
  ) AS obj
  FROM pg_catalog.pg_constraint con
  JOIN pg_catalog.pg_class cls ON cls.oid = con.conrelid
  JOIN pg_catalog.pg_namespace ns ON ns.oid = cls.relnamespace
  WHERE ns.nspname = 'public' AND cls.relkind IN ('r','p')
)
SELECT jsonb_build_object(
  'format','kmj-postgresql-metadata-v1',
  'engine','postgresql',
  'scope','public',
  'serverMajor',current_setting('server_version_num')::integer / 10000,
  'relations',COALESCE((SELECT jsonb_agg(obj ORDER BY obj::text) FROM relations),'[]'::jsonb),
  'columns',COALESCE((SELECT jsonb_agg(obj ORDER BY obj::text) FROM columns),'[]'::jsonb),
  'constraints',COALESCE((SELECT jsonb_agg(obj ORDER BY obj::text) FROM constraints),'[]'::jsonb)
)::text;
COMMIT;
