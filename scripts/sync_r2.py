"""Cloudflare R2 journal sync (spec 07 §7 off-box) — S3-compatible, no egress fees.

VPS pushes the live journal + state to R2; the local PC pulls it for the Reviewer and
backtests. R2 credentials come from the environment / .env (never committed):

    TBOT_R2_ENDPOINT           the S3 API URL Cloudflare shows (e.g.
                               https://<accountid>.r2.cloudflarestorage.com)
    TBOT_R2_ACCOUNT_ID         (optional) used only if TBOT_R2_ENDPOINT is unset
    TBOT_R2_ACCESS_KEY_ID      R2 API token access key id
    TBOT_R2_SECRET_ACCESS_KEY  R2 API token secret
    TBOT_R2_BUCKET             bucket name (e.g. ftmo-bot-state)

Usage:
    # VPS (push the journal + config up):
    py scripts/sync_r2.py push --paths journal live.sqlite config --prefix vps
    # Local (pull it down for the Reviewer):
    py scripts/sync_r2.py pull --prefix vps --dest C:/ftmo-sync
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.config import load_config  # noqa: E402  (loads .env into env)


def _r2_settings() -> dict:
    cfg = load_config()  # side effect: merges .env into the resolved env for this process
    # load_config doesn't expose R2 directly; read straight from the merged environment.
    from src.common.config import read_env_file
    merged = {**read_env_file(".env"), **os.environ}
    account_id = merged.get("TBOT_R2_ACCOUNT_ID")
    endpoint = merged.get("TBOT_R2_ENDPOINT")  # full S3 URL; preferred if provided
    if not endpoint and account_id:
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    return {
        "endpoint": endpoint,
        "key_id": merged.get("TBOT_R2_ACCESS_KEY_ID"),
        "secret": merged.get("TBOT_R2_SECRET_ACCESS_KEY"),
        "bucket": merged.get("TBOT_R2_BUCKET"),
        "state_dir": str(cfg.state_dir),
    }


def _client(s):
    if not all((s["endpoint"], s["key_id"], s["secret"], s["bucket"])):
        raise SystemExit("R2 not configured — set TBOT_R2_ENDPOINT (or TBOT_R2_ACCOUNT_ID), "
                         "TBOT_R2_ACCESS_KEY_ID, TBOT_R2_SECRET_ACCESS_KEY, TBOT_R2_BUCKET in .env.")
    import boto3  # lazy: only needed once configured
    return boto3.client(
        "s3", endpoint_url=s["endpoint"],
        aws_access_key_id=s["key_id"], aws_secret_access_key=s["secret"],
        region_name="auto")


def iter_files(base: Path, paths: list[str]):
    """Yield (absolute_file, key_relative_to_base) for each path (file or dir) under base."""
    for rel in paths:
        p = base / rel
        if p.is_file():
            yield p, rel.replace("\\", "/")
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    yield f, f.relative_to(base).as_posix()


def s3_key(prefix: str, key_rel: str) -> str:
    return f"{prefix.strip('/')}/{key_rel}" if prefix else key_rel


def push(args) -> int:
    s = _r2_settings()
    client = _client(s)
    base = Path(s["state_dir"])
    n = 0
    for f, key_rel in iter_files(base, args.paths):
        client.upload_file(str(f), s["bucket"], s3_key(args.prefix, key_rel))
        n += 1
    print(f"pushed {n} files to r2://{s['bucket']}/{args.prefix}/")
    return 0


def pull(args) -> int:
    s = _r2_settings()
    client = _client(s)
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix.strip("/") + "/"
    paginator = client.get_paginator("list_objects_v2")
    n = 0
    for page in paginator.paginate(Bucket=s["bucket"], Prefix=prefix):
        for obj in page.get("Contents", []):
            rel = obj["Key"][len(prefix):]
            if not rel:
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(s["bucket"], obj["Key"], str(out))
            n += 1
    print(f"pulled {n} files from r2://{s['bucket']}/{args.prefix}/ -> {dest}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cloudflare R2 state sync")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("push", help="upload state paths to R2")
    pp.add_argument("--paths", nargs="+", default=["journal", "live.sqlite"],
                    help="paths under the state dir to upload")
    pp.add_argument("--prefix", default="vps")
    pp.set_defaults(func=push)
    pl = sub.add_parser("pull", help="download from R2 into a local dir")
    pl.add_argument("--prefix", default="vps")
    pl.add_argument("--dest", required=True, help="local folder to write into")
    pl.set_defaults(func=pull)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
