#!/bin/sh
# swap the 8gb gpu between retrieval (embed + rerank, ~3.5gb) and extraction (4b llm, ~5gb)
# goethe won't fit all three, so ingest wants "extraction", evidence search "retrieval"
set -eu
PATH="$HOME/.local/bin:$PATH"
EMBED=${PAPER_TRAIL_EMBED_ID:-Qwen/Qwen3-Embedding-0.6B}
RERANK=${PAPER_TRAIL_RERANK_ID:-paper-trail/bge-reranker-v2-m3-bf16}
LLM=${PAPER_TRAIL_LLM_ID:-unnobatroo/paper-trail-qwen3-4b-instruct-hu-awq}
case "${1:-}" in
  retrieval)
    goethe unload --all
    goethe load --model "$EMBED" --ctx 2048 --max-conc 4 --yes -- --is-embedding --disable-cuda-graph
    # xlm-roberta cross-encoders assert on radix-cached/chunked positions, so these flags
    goethe load --model "$RERANK" --ctx 2048 --max-conc 4 --yes -- --is-embedding \
      --disable-cuda-graph --disable-radix-cache --chunked-prefill-size -1 --attention-backend triton
    ;;
  extraction)
    goethe unload --all
    # goethe sizes the kv cache off --ctx only: 4096 gave 1965 tokens and chopped answers,
    # 12288 gives ~6100, enough for 3-4 pages in flight (PAPER_TRAIL_LLM_CONCURRENCY=4)
    goethe load --model "$LLM" --ctx 12288 --max-conc 4 --yes
    ;;
  status) goethe ps ;;
  *) echo 'usage: goethe-phase.sh retrieval|extraction|status' >&2; exit 2 ;;
esac
