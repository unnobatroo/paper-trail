"""fine-tune a small multilingual encoder to say "this passage holds a commitment/target"

Runs on the gpu with plain torch + transformers (the vllm env in wsl has both). Picks the
threshold that maximises F1 on the validation file. The locked test files are scored only
with --final, once per decision, never during tuning.

  python scripts/ml/train_detector.py --data data/eval_ext/detector --out data/eval_ext/detector/m1
"""

import argparse
import json
import random
from pathlib import Path

import torch
from binary_metrics import prf
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def scored(gold: list[int], pred: list[int]) -> dict:
    """counts and scores rounded for the report"""
    return {k: round(v, 3) if isinstance(v, float) else v for k, v in prf(gold, pred).items()}


@torch.no_grad()
def scores(model, tok, rows: list[dict], maxlen: int, device) -> list[float]:
    model.eval()
    out = []
    for i in range(0, len(rows), 32):
        enc = tok([r["text"] for r in rows[i:i + 32]], truncation=True, max_length=maxlen,
                  padding=True, return_tensors="pt").to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(**enc).logits.float()
        out += torch.softmax(logits, -1)[:, 1].tolist()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="microsoft/mdeberta-v3-base")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--maxlen", type=int, default=384)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--final", action="store_true", help="score the locked test files")
    args = ap.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda")
    tok = AutoTokenizer.from_pretrained(args.model)
    # transformers 5 loads this checkpoint in half precision, and AdamW turns half-precision
    # weights into NaN after one step; train in float32 and let autocast use bf16 for speed.
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=2, dtype=torch.float32).to(device)
    train, val = load(args.data / "train.jsonl"), load(args.data / "val.jsonl")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps = args.epochs * ((len(train) + args.batch - 1) // args.batch)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / (0.1 * steps)) * max(0.0, (steps - s) / steps))
    best, best_state = -1.0, None
    for epoch in range(args.epochs):
        model.train()
        random.shuffle(train)
        for i in range(0, len(train), args.batch):
            chunk = train[i:i + args.batch]
            enc = tok([r["text"] for r in chunk], truncation=True, max_length=args.maxlen,
                      padding=True, return_tensors="pt").to(device)
            labels = torch.tensor([r["label"] for r in chunk], device=device)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss = torch.nn.functional.cross_entropy(model(**enc).logits.float(), labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
        vs = scores(model, tok, val, args.maxlen, device)
        gold = [r["label"] for r in val]
        # best threshold on val for this epoch
        # the grid plus every score, so a threshold can sit exactly between two close scores
        cand = max(((t, scored(gold, [int(s >= t) for s in vs]))
                    for t in sorted({i / 20 for i in range(2, 19)} | set(vs))),
                   key=lambda x: x[1]["f1"])
        print(f"epoch {epoch + 1} loss {loss.item():.3f} val F1 {cand[1]['f1']} @ {cand[0]}",
              flush=True)
        if cand[1]["f1"] > best:
            best, thr = cand[1]["f1"], cand[0]
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    report = {"model": args.model, "threshold": thr, "val_f1": best, "epochs": args.epochs,
              "lr": args.lr, "maxlen": args.maxlen, "train_rows": len(train), "seed": args.seed}
    if args.final:
        for name in ("test_cpr", "test_hu", "test_hu2", "test_hu_strat"):
            rows = load(args.data / f"{name}.jsonl")
            sc = scores(model, tok, rows, args.maxlen, device)
            report[name] = scored([r["label"] for r in rows], [int(s >= thr) for s in sc])
            (args.out / f"{name}_scores.json").write_text(json.dumps(sc))
            print(name, report[name], flush=True)
    (args.out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
