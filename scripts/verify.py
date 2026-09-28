#!/usr/bin/env python3
"""Verifica cada entrada de data/servers.yaml e regenera o README.

Para cada entrada:
  * HTTP: a URL responde 200 (segue redirects)?
  * GitHub (se tiver `repo`): repositório existe? está arquivado? stars, último push.
    Usa a REST API do GitHub via urllib; envia `GITHUB_TOKEN` se existir no ambiente
    (na Action existe; localmente funciona sem, dentro de 60 req/h).
  * Registro oficial (se `registro_oficial: sim`): confere se ainda está listado em
    registry.modelcontextprotocol.io (best-effort — o registro às vezes demora).

Escreve data/status.json e, por fim, chama scripts/build_readme.py.
Exit code 0 sempre que conseguiu rodar (problemas viram badges na tabela e um
resumo em stdout), para o workflow poder abrir o PR com o diff.

Uso:
    python3 scripts/verify.py            # verifica tudo e regenera README
    python3 scripts/verify.py --no-net   # só regenera README (sem rede)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "servers.yaml"
STATUS = ROOT / "data" / "status.json"
UA = "awesome-mcp-brasil-verify/1.0 (+https://github.com/daniel-filius/awesome-mcp-brasil)"
TIMEOUT = 20


def fetch(url: str, headers: dict | None = None, method: str = "GET") -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001 — rede indisponível, DNS, timeout
        return 0, b""


def http_ok(url: str) -> bool:
    code, _ = fetch(url)
    if code == 405:  # alguns hosts recusam GET sem browser; tenta HEAD
        code, _ = fetch(url, method="HEAD")
    return 200 <= code < 400


def github_info(repo: str) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    code, body = fetch(f"https://api.github.com/repos/{repo}", headers)
    if code == 200:
        d = json.loads(body)
        return {
            "exists": True,
            "archived": bool(d.get("archived")),
            "stars": int(d.get("stargazers_count", 0)),
            "pushed_at": (d.get("pushed_at") or "")[:10],
            "license": (d.get("license") or {}).get("spdx_id"),
        }
    if code == 404:
        return {"exists": False}
    return {"exists": None, "api_status": code}  # rate limit / indisponível: não conclui nada


def registry_listed(registro_nome: str, repo_url: str | None) -> bool | None:
    termo = registro_nome.split("/")[-1]
    q = urllib.parse.quote(termo)
    code, body = fetch(f"https://registry.modelcontextprotocol.io/v0/servers?search={q}&limit=50")
    if code != 200:
        return None
    try:
        servers = json.loads(body).get("servers", [])
    except json.JSONDecodeError:
        return None
    for s in servers:
        srv = s.get("server", s)
        if srv.get("name") == registro_nome:
            return True
        rurl = (srv.get("repository") or {}).get("url") or ""
        if repo_url and rurl.rstrip("/").lower() == repo_url.rstrip("/").lower():
            return True
    return False


def main(argv: list[str]) -> int:
    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    status: dict = {}
    if STATUS.exists():
        try:
            status = json.loads(STATUS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            status = {}

    problemas: list[str] = []
    if "--no-net" not in argv:
        for s in data["servidores"]:
            key = s.get("repo") or s["url"]
            info = status.get(key, {})
            info["url"] = s["url"]
            info["http_ok"] = http_ok(s["url"])
            if not info["http_ok"]:
                problemas.append(f"link fora do ar: {s['url']}")
            if s.get("repo"):
                gi = github_info(s["repo"])
                if gi.get("exists") is not None:
                    info.update(gi)
                    if gi.get("exists") is False:
                        problemas.append(f"repo não existe: {s['repo']}")
                    elif gi.get("archived"):
                        problemas.append(f"repo arquivado: {s['repo']}")
                else:
                    info["api_status"] = gi.get("api_status")
            if str(s.get("registro_oficial", "")).lower() == "sim" and s.get("registro_nome"):
                listed = registry_listed(s["registro_nome"], s["url"])
                if listed is not None:
                    info["registro_ok"] = listed
                    if not listed:
                        problemas.append(f"não encontrado no registro oficial: {s['registro_nome']}")
            info["verificado_em"] = time.strftime("%Y-%m-%d")
            status[key] = info
            time.sleep(0.2)

        STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    n = len(data["servidores"])
    ok = sum(1 for s in data["servidores"] if status.get(s.get("repo") or s["url"], {}).get("http_ok"))
    print(f"verificadas {n} entradas · {ok} links OK · {len(problemas)} problema(s)")
    for p in problemas:
        print(" -", p)

    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_readme.py")], check=False)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
