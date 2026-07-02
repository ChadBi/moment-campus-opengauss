\echo '===== posts 索引 ====='
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname='public' AND tablename='posts'
ORDER BY indexname;

\echo '===== notifications 索引 ====='
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname='public' AND tablename='notifications'
ORDER BY indexname;

\echo '===== comments 索引 ====='
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname='public' AND tablename='comments'
ORDER BY indexname;

\echo '===== 关键表统计信息 ====='
SELECT relname, n_live_tup, last_analyze, last_autoanalyze
FROM pg_stat_user_tables
WHERE relname IN ('posts','notifications','comments')
ORDER BY relname;
