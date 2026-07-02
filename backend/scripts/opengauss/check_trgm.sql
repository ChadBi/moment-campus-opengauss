\echo '===== pg_trgm 扩展 ====='
SELECT extname, extversion FROM pg_extension WHERE extname IN ('pg_trgm','zhparser');

\echo '===== posts 上 GIN 索引 ====='
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname='public' AND tablename='posts' AND indexdef ILIKE '%gin%';

\echo '===== 所有 GIN 索引 ====='
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname='public' AND indexdef ILIKE '%gin%'
ORDER BY tablename, indexname;

\echo '===== posts 表行数（按分区）====='
SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname LIKE 'posts%' ORDER BY relname;
