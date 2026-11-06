"""Command line interface: python -m tm_rag index|search|translate|eval|report."""

import argparse
import json
from pathlib import Path

from . import index as index_mod
from .evaluate import CROSS_LANG_GOLD, run_eval
from .index import DATA_DIR, DEFAULT_QDRANT, ensure_index, search
from .llm import GenContext, get_provider
from .prompts import PROMPT_VERSION, build_prompt
from .qa import required_terms, run_qa
from .schema import TranslationResult
from .tbx import parse_tbx


def _add_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="directory holding tm.tmx, terms.tbx, gold.jsonl")
    parser.add_argument("--qdrant", default=str(DEFAULT_QDRANT), help="Qdrant local-mode directory")


def cmd_index(args: argparse.Namespace) -> int:
    n = index_mod.build_index(Path(args.data_dir) / "tm.tmx", Path(args.qdrant))
    print(f"Indexed {n} units into {args.qdrant} (collection '{index_mod.COLLECTION}', model {index_mod.MODEL_NAME})")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    qdrant = Path(args.qdrant)
    ensure_index(data_dir / "tm.tmx", qdrant)
    matches = search(
        args.text,
        k=args.k,
        qdrant_path=qdrant,
        target_lang=args.target_lang,
        hybrid=args.hybrid,
    )
    if not matches:
        print("no matches")
        return 0
    for m in matches:
        print(f"{m.score:.4f}\t{m.unit.id}\t{m.unit.src_lang}->{m.unit.tgt_lang}\t{m.unit.source} -> {m.unit.target}")
    return 0


def cmd_translate(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    qdrant = Path(args.qdrant)
    ensure_index(data_dir / "tm.tmx", qdrant)
    terms = parse_tbx(data_dir / "terms.tbx")
    matches = search(args.text, k=args.k, qdrant_path=qdrant)
    prompt = build_prompt(args.text, matches, terms, args.max_chars)
    provider = get_provider(args.provider)
    context = GenContext(source=args.text, matches=matches, terms=terms, max_chars=args.max_chars)
    raw = provider.generate(prompt, context)
    notes = []
    if provider.name == "mock":
        if matches:
            notes.append(f"mock provider copied the closest TM match '{matches[0].unit.id}'; it is not a model")
        else:
            notes.append("mock provider found no TM match and returned an empty string")
    result = TranslationResult(
        translation=raw,
        used_terms=[t.target for t in required_terms(args.text, terms)],
        notes=notes,
    )
    findings = run_qa(args.text, raw, terms, args.max_chars)
    payload = {
        "provider": provider.name,
        "prompt_version": PROMPT_VERSION,
        "source": args.text,
        "result": result.model_dump(),
        "matches": [
            {"id": m.unit.id, "score": round(m.score, 4), "source": m.unit.source, "target": m.unit.target}
            for m in matches
        ],
        "qa": [{"check": f.check, "passed": f.passed, "detail": f.detail} for f in findings],
        "qa_passed": all(f.passed for f in findings),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    result = run_eval(
        data_dir=Path(args.data_dir),
        qdrant_path=Path(args.qdrant),
        results_path=Path(args.results) if args.results else None,
        k_values=args.k,
        provider_name=args.provider,
        target_lang=args.target_lang,
        hybrid=args.hybrid,
        cross_lang=args.cross_lang,
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        timeout=args.timeout,
    )
    print(f"config: {result['config']}  provider: {result['provider']}"
          + (f" ({result['llm_model']} @ {result['llm_base_url']})" if result["llm_model"] else ""))
    print(f"gold file: {result['gold_file']}  gold queries: {result['n_gold']}  units indexed: {result['n_units']}")
    print("k\trecall@k")
    for k in result["k_values"]:
        print(f"{k}\t{result['recall_at_k'][str(k)]:.4f}")
    print(f"MRR: {result['mrr']:.4f}")
    print(f"QA pass rate ({result['provider']} provider): {result['qa_pass_rate']:.4f}")
    if result["provider"] != "mock":
        print(f"bad JSON replies (counted as failures): {result['bad_json_count']}")
    print(f"wall time: {result['wall_time_seconds']:.2f} s")
    out = Path(args.results) if args.results else index_mod.RESULTS_DIR / "eval.json"
    print(f"results written to {out}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from .report import build_report

    written = build_report(
        results_dir=Path(args.results_dir),
        data_dir=Path(args.data_dir),
        out_dir=Path(args.out_dir),
        experiments_path=Path(args.experiments),
    )
    for path in written:
        print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tm_rag", description="Retrieval-augmented translation demo over a synthetic TM.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", help="embed data/tm.tmx into the local Qdrant")
    _add_data_args(p_index)
    p_index.set_defaults(func=cmd_index)

    p_search = sub.add_parser("search", help="search the TM by meaning")
    p_search.add_argument("text")
    p_search.add_argument("--k", type=int, default=5)
    p_search.add_argument("--target-lang", default=None, help="keep only units of this target language (e.g. zh-CN)")
    p_search.add_argument("--hybrid", action="store_true", help="reciprocal rank fusion of vector search with BM25 over the source segments")
    _add_data_args(p_search)
    p_search.set_defaults(func=cmd_search)

    p_translate = sub.add_parser("translate", help="retrieve, prompt, generate and QA one segment")
    p_translate.add_argument("text")
    p_translate.add_argument("--k", type=int, default=5)
    p_translate.add_argument("--provider", default="mock", choices=["mock", "openai", "openai-compatible"])
    p_translate.add_argument("--max-chars", type=int, default=None)
    _add_data_args(p_translate)
    p_translate.set_defaults(func=cmd_translate)

    p_eval = sub.add_parser("eval", help="run the gold-set evaluation and write results/eval.json")
    p_eval.add_argument("--k", type=int, nargs="+", default=[1, 3, 5, 10])
    p_eval.add_argument("--results", default=None, help="override the output path (default results/eval.json)")
    p_eval.add_argument("--target-lang", default=None, help="keep only units of this target language (e.g. zh-CN)")
    p_eval.add_argument("--hybrid", action="store_true", help="reciprocal rank fusion of vector search with BM25 over the source segments")
    p_eval.add_argument("--cross-lang", action="store_true", help=f"evaluate the Chinese gold set ({CROSS_LANG_GOLD}) against the English sources")
    p_eval.add_argument("--provider", default="mock", choices=["mock", "ollama", "openai", "openai-compatible"], help="generation provider; ollama defaults to a local server with no key")
    p_eval.add_argument("--base-url", default=None, help="override the provider base URL")
    p_eval.add_argument("--model", default=None, help="override the provider model")
    p_eval.add_argument("--api-key", default=None, help="override the provider API key (not needed for ollama)")
    p_eval.add_argument("--timeout", type=float, default=120.0, help="per-request timeout in seconds for real providers")
    _add_data_args(p_eval)
    p_eval.set_defaults(func=cmd_eval)

    p_report = sub.add_parser("report", help="build the static results page (docs/index.html) and docs/recall.svg from results/ and data/")
    p_report.add_argument("--results-dir", default=str(index_mod.RESULTS_DIR), help="directory holding results/*.json")
    p_report.add_argument("--out-dir", default=str(index_mod.ROOT / "docs"), help="output directory for index.html and recall.svg")
    p_report.add_argument("--experiments", default=str(index_mod.ROOT / "EXPERIMENTS.md"), help="EXPERIMENTS.md to render as the experiments table")
    _add_data_args(p_report)
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
