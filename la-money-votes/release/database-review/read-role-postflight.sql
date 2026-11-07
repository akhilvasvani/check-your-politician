-- READ ONLY. Run each transaction separately and retain both results.
-- Target: pwbothxnfjnxkhrcxyvd. No application RPC is invoked.
BEGIN READ ONLY;
SET LOCAL statement_timeout='10s';
SET LOCAL ROLE anon;
SELECT current_user AS role, current_setting('transaction_read_only') AS read_only,
 count(*) AS chunks, count(*) FILTER(WHERE sub_chunk_idx=0) AS parent_turns,
 count(DISTINCT video_id) AS recordings FROM public.transcript_chunks;
ROLLBACK;

BEGIN READ ONLY;
SET LOCAL statement_timeout='10s';
SET LOCAL ROLE authenticated;
SELECT current_user AS role, current_setting('transaction_read_only') AS read_only,
 count(*) AS chunks, count(*) FILTER(WHERE sub_chunk_idx=0) AS parent_turns,
 count(DISTINCT video_id) AS recordings FROM public.transcript_chunks;
ROLLBACK;
