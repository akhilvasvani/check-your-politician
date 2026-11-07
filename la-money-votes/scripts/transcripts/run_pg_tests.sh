#!/usr/bin/env bash
# Bring up a disposable Postgres + pgvector cluster and run the M3.1
# replacement-RPC integration tests against it, then tear it down.
#
# Nothing here touches the real Supabase project. The cluster lives in a
# temporary directory and is deleted on exit.
#
# Requirements: postgres 16 server binaries, the pgvector extension, and
# psycopg2. On Debian/Ubuntu:
#   apt-get install -y postgresql-16 postgresql-16-pgvector && pip install psycopg2-binary
set -euo pipefail

PYTHON="${PYTHON:-python3}"
if [[ "$(id -u)" -eq 0 ]]; then
  echo "run this disposable test runner as an existing unprivileged user" >&2
  exit 2
fi
if [[ -z "${PGBIN:-}" ]]; then
  if command -v pg_config >/dev/null 2>&1; then
    PGBIN="$(pg_config --bindir)"
  else
    PGBIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | tail -1 || true)"
  fi
fi
if [[ -z "${PGBIN}" || ! -x "${PGBIN}/initdb" ]]; then
  echo "postgres server binaries not found; set PGBIN" >&2
  exit 2
fi

# Pick a free ephemeral port so concurrent or leftover clusters never collide.
PORT="${PGPORT:-$("${PYTHON}" -c "import socket;s=socket.socket();s.bind((\"127.0.0.1\",0));print(s.getsockname()[1]);s.close()")}"
WORKDIR="$(mktemp -d)"

cleanup() {
  "${PGBIN}/pg_ctl" -D "${WORKDIR}/pgdata" stop -m immediate >/dev/null 2>&1 || true
  rm -rf "${WORKDIR}"
}
trap cleanup EXIT

# The checked-in SQL contains UTF-8 punctuation, so force a UTF-8 cluster
# rather than inheriting a possibly ASCII default locale.
"${PGBIN}/initdb" -D "${WORKDIR}/pgdata" -U postgres --auth=trust \
  -E UTF8 --locale=C >/dev/null
"${PGBIN}/pg_ctl" -D "${WORKDIR}/pgdata" \
  -o "-p ${PORT} -k '' -c listen_addresses=127.0.0.1" \
  -l "${WORKDIR}/pg.log" -w start >/dev/null

export TRANSCRIPT_TEST_PG_DSN="postgresql://postgres@127.0.0.1:${PORT}/postgres"
cd "$(dirname "$0")/../.."
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "${PYTHON}" -m unittest \
  scripts.transcripts.tests.test_replace_transcript_chunks "$@"
