#!/usr/bin/env python3
"""Gera o README.md a partir de data/servers.yaml.

Sem dependências além de PyYAML. Não precisa de token: os badges são imagens
estáticas do shields.io. Se existir data/status.json (escrito por
scripts/verify.py), usa stars/último commit/arquivado para ordenar e marcar
entradas — sem ele, a ordem é a do YAML.

Uso:
    python3 scripts/build_readme.py            # escreve README.md
    python3 scripts/build_readme.py --check    # só compara (exit 1 se difere)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "servers.yaml"
STATUS = ROOT / "data" / "status.json"
PIX = ROOT / "data" / "pix.txt"
README = ROOT / "README.md"

REPO_SLUG = "daniel-filius/awesome-mcp-brasil"
SHIELDS = "https://img.shields.io"

PACOTE_BADGE = {
    "npm": ("npm", "CB3837", "npm"),
    "pypi": ("PyPI", "3775A9", "pypi"),
    "oci": ("OCI", "2496ED", "docker"),
    "mcpb": ("MCPB", "6B46C1", None),
    "remoto": ("remoto", "0F766E", None),
    "git": ("só git", "6E7781", "git"),
}


def load() -> dict:
    with DATA.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_status() -> dict:
    if STATUS.exists():
        try:
            return json.loads(STATUS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def as_list(v) -> list[str]:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def badge(label: str, msg: str, color: str, logo: str | None = None) -> str:
    def enc(s: str) -> str:
        return s.replace("-", "--").replace("_", "__").replace(" ", "_")

    url = f"{SHIELDS}/badge/{enc(label)}-{enc(msg)}-{color}?style=flat-square"
    if logo:
        url += f"&logo={logo}&logoColor=white"
    return f"![{label}: {msg}]({url})"


def badge_pacote(p: str) -> str:
    nome, cor, logo = PACOTE_BADGE.get(p, (p, "lightgrey", None))
    url = f"{SHIELDS}/badge/{nome.replace(' ', '_')}-{cor}?style=flat-square"
    if logo:
        url += f"&logo={logo}&logoColor=white"
    return f"![{nome}]({url})"


def badge_stars(repo: str) -> str:
    return (f"![stars]({SHIELDS}/github/stars/{repo}?style=flat-square&label=%E2%98%85)")


def badge_commit(repo: str) -> str:
    return (f"![último commit]({SHIELDS}/github/last-commit/{repo}?style=flat-square&label=commit)")


def badge_sim_nao(label: str, valor: str, cor_sim: str, cor_nao: str) -> str:
    sim = str(valor).lower() in ("sim", "true", "yes")
    return badge(label, "sim" if sim else "não", cor_sim if sim else cor_nao)


def row(s: dict, st: dict) -> str:
    repo = s.get("repo")
    nome = s["nome"].replace("|", "\\|")
    link = f"[{nome}]({s['url']})"
    info = st.get(repo or s["url"], {})
    flags = []
    if info.get("archived"):
        flags.append(badge("repo", "arquivado", "red"))
    if info.get("http_ok") is False:
        flags.append(badge("link", "fora do ar", "red"))
    desc = s["descricao"].replace("|", "\\|")
    if flags:
        desc = " ".join(flags) + " " + desc

    if s.get("tipo") == "guia":
        stars = badge_stars(repo) if repo else "—"
        commit = badge_commit(repo) if repo else "—"
        return f"| {link} | {desc} | {stars} | {commit} | — | — | — |"

    stars = badge_stars(repo) if repo else "—"
    commit = badge_commit(repo) if repo else "—"
    pacotes = " ".join(badge_pacote(p) for p in as_list(s.get("pacote"))) or "—"
    chave = badge_sim_nao("chave", s.get("exige_chave", "nao"), "orange", "brightgreen")
    reg = badge_sim_nao("registro", s.get("registro_oficial", "nao"), "blue", "lightgrey")
    if str(s.get("registro_oficial", "nao")).lower() == "sim" and s.get("registro_nome"):
        reg = (f"[{reg}](https://registry.modelcontextprotocol.io/v0/servers?search="
               f"{s['registro_nome'].split('/')[-1]})")
    return f"| {link} | {desc} | {stars} | {commit} | {pacotes} | {chave} | {reg} |"


def sort_key(st: dict):
    def key(s: dict):
        info = st.get(s.get("repo") or s["url"], {})
        return (-int(info.get("stars", 0) or 0), s["nome"].lower())

    return key


def render(data: dict, st: dict, pix: str | None) -> str:
    cats = data["categorias"]
    servers = data["servidores"]
    by_cat: dict[str, list[dict]] = {c["id"]: [] for c in cats}
    for s in servers:
        by_cat[s["categoria"]].append(s)

    n_total = len(servers)
    n_reg = sum(1 for s in servers if str(s.get("registro_oficial", "")).lower() == "sim")
    n_sem_chave = sum(1 for s in servers if str(s.get("exige_chave", "")).lower() == "nao")
    hoje = date.today().isoformat()

    out: list[str] = []
    out.append("# awesome-mcp-brasil")
    out.append("")
    out.append(
        f"[![Awesome](https://awesome.re/badge-flat.svg)](https://awesome.re) "
        f"![entradas]({SHIELDS}/badge/entradas-{n_total}-blue?style=flat-square) "
        f"![no registro oficial]({SHIELDS}/badge/no_registro_oficial-{n_reg}-blue?style=flat-square) "
        f"![sem chave]({SHIELDS}/badge/sem_chave-{n_sem_chave}-brightgreen?style=flat-square) "
        f"[![verificação semanal]({SHIELDS}/github/actions/workflow/status/{REPO_SLUG}/verify.yml"
        f"?style=flat-square&label=verifica%C3%A7%C3%A3o%20semanal)]"
        f"(https://github.com/{REPO_SLUG}/actions/workflows/verify.yml) "
        f"[![stars]({SHIELDS}/github/stars/{REPO_SLUG}?style=flat-square)](https://github.com/{REPO_SLUG}/stargazers)"
    )
    out.append("")
    out.append(
        "Lista **curada e auto-verificada** de servidores MCP (Model Context Protocol) e skills de agente "
        "**brasileiros** — dados públicos, fiscal, jurídico, SaaS BR, Pix, eleições — para usar no Claude Code, "
        "Claude Desktop, Cursor, Windsurf, Gemini CLI ou qualquer cliente MCP. Cada entrada mostra stars e último "
        "commit (ao vivo), tipo de pacote, se **exige conta/chave** e se está no "
        "[registro oficial do MCP](https://registry.modelcontextprotocol.io). Uma GitHub Action roda toda semana, "
        "checa link morto e repositório arquivado e abre um PR com a tabela regenerada — o hub não fica com link quebrado."
    )
    out.append("")
    out.append(f"> Fonte única: [`data/servers.yaml`](data/servers.yaml) · README gerado em {hoje} por "
               f"`scripts/build_readme.py`. **Não edite o README à mão** — edite o YAML ou "
               f"[abra uma issue](https://github.com/{REPO_SLUG}/issues/new?template=adicionar-servidor.yml).")
    out.append("")

    # Sumário
    out.append("## Sumário")
    out.append("")
    for c in cats:
        # regra de âncora do GitHub: minúsculas, remove pontuação (mantém letras acentuadas), espaço -> hífen
        anchor = re.sub(r"[^\w\s-]", "", c["nome"].lower()).replace(" ", "-")
        out.append(f"- [{c['nome']}](#{anchor}) ({len(by_cat[c['id']])})")
    out.append("- [Como instalar um servidor MCP](#como-instalar-um-servidor-mcp-no-claude-code--cursor)")
    out.append("- [Apoiadores](#apoiadores)")
    out.append("- [Apoie a curadoria](#apoie-a-curadoria)")
    out.append("- [Como contribuir](#como-contribuir)")
    out.append("")

    # Legenda
    out.append("## Legenda")
    out.append("")
    out.append("| Coluna | Significado |")
    out.append("|---|---|")
    out.append("| ★ / commit | Stars e data do último commit, direto do GitHub (badge ao vivo) |")
    out.append("| Pacote | " + " ".join(badge_pacote(p) for p in PACOTE_BADGE) +
               " — como instalar: `npx`, `pip/uvx`, imagem Docker/OCI, bundle `.mcpb`, servidor hospedado (HTTP/SSE) ou só clonar |")
    out.append(f"| Chave | {badge('chave', 'não', 'brightgreen')} funciona sem conta/token · "
               f"{badge('chave', 'sim', 'orange')} exige conta, API key, certificado ou pagamento |")
    out.append(f"| Registro | {badge('registro', 'sim', 'blue')} publicado no registro oficial "
               f"`registry.modelcontextprotocol.io` (clique no badge para ver) |")
    out.append("")

    header = ("| Projeto | Descrição | ★ | Último commit | Pacote | Chave? | Registro oficial? |\n"
              "|---|---|---|---|---|---|---|")
    for c in cats:
        items = sorted(by_cat[c["id"]], key=sort_key(st))
        out.append(f"## {c['nome']}")
        out.append("")
        out.append(f"_{c['descricao']}_")
        out.append("")
        out.append(header)
        for s in items:
            out.append(row(s, st))
        out.append("")

    out.append("## Como instalar um servidor MCP no Claude Code / Cursor")
    out.append("")
    out.append("Pegue o comando de instalação no README do projeto (coluna **Pacote** diz se é `npx`, `uvx`/`pip`, Docker ou remoto). Exemplos com dois servidores desta lista:")
    out.append("")
    out.append("**Claude Code** (terminal):")
    out.append("")
    out.append("```bash")
    out.append("# pacote npm (stdio)")
    out.append("claude mcp add ibge-br -- npx -y ibge-br-mcp")
    out.append("# pacote PyPI (stdio)")
    out.append("claude mcp add fiscal-brasil -- uvx mcp-fiscal-brasil")
    out.append("# servidor remoto (HTTP)")
    out.append("claude mcp add --transport http senado-br https://<url-do-servidor>/mcp")
    out.append("```")
    out.append("")
    out.append("**Cursor / Claude Desktop / Windsurf** (`~/.cursor/mcp.json`, `claude_desktop_config.json`…):")
    out.append("")
    out.append("```json")
    out.append("{")
    out.append('  "mcpServers": {')
    out.append('    "ibge-br": { "command": "npx", "args": ["-y", "ibge-br-mcp"] },')
    out.append('    "fiscal-brasil": { "command": "uvx", "args": ["mcp-fiscal-brasil"] }')
    out.append("  }")
    out.append("}")
    out.append("```")
    out.append("")
    out.append("Servidores marcados com " + badge("chave", "sim", "orange") +
               " precisam de variáveis de ambiente (token, client id, certificado) — veja o README de cada um. "
               "Guia oficial em português: [Claude Code — MCP](https://code.claude.com/docs/pt/mcp).")
    out.append("")

    out.append("## Apoiadores")
    out.append("")
    out.append("_Ainda sem apoiadores._ Empresas do ecossistema brasileiro de dados/agentes podem ter logo e link aqui — "
               f"[abra uma issue \"Quero apoiar\"](https://github.com/{REPO_SLUG}/issues/new?template=quero-apoiar.yml). "
               "Sem links de afiliado na lista: a curadoria é neutra.")
    out.append("")

    out.append("## Apoie a curadoria")
    out.append("")
    out.append("Projeto voluntário, mantido por [@daniel-filius](https://github.com/daniel-filius) com verificação automatizada. "
               "Se a lista te poupou uma busca manual, um Pix de qualquer valor ajuda a manter a Action rodando e a curadoria viva.")
    out.append("")
    if pix:
        out.append("Pix copia-e-cola (valor livre):")
        out.append("")
        out.append("```")
        out.append(pix)
        out.append("```")
        out.append("")
    out.append("Outras formas de apoiar que não custam nada: dê uma ⭐ no repositório e indique um servidor que falta.")
    out.append("")

    out.append("## Como contribuir")
    out.append("")
    out.append(f"1. **Sem escrever código:** [abra uma issue \"Adicionar servidor\"](https://github.com/{REPO_SLUG}/issues/new?template=adicionar-servidor.yml) com URL, categoria, descrição, tipo de pacote e se exige chave.")
    out.append("2. **Por PR:** edite [`data/servers.yaml`](data/servers.yaml) (nunca o README), rode `python3 scripts/build_readme.py && python3 -m unittest discover tests` e envie.")
    out.append("3. **Critérios:** projeto brasileiro ou focado em dados/plataformas do Brasil; repositório público, não arquivado, com README que explique como instalar; servidores MCP, skills de agente ou guias em pt-BR. Sem links de afiliado, sem projetos vazios (README só com título).")
    out.append("4. **Remoção:** entradas com link morto ou repositório arquivado por 2 verificações semanais seguidas saem da lista (ficam no histórico do git).")
    out.append("")
    out.append("Projetos irmãos deste hub: [apuracao-2026-mcp](https://github.com/daniel-filius/apuracao-2026-mcp) (eleições 2026 via TSE).")
    out.append("")
    out.append("## Licença")
    out.append("")
    out.append("[CC0 1.0](LICENSE) — domínio público. Os projetos listados têm suas próprias licenças.")
    out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    data = load()
    st = load_status()
    pix = PIX.read_text(encoding="utf-8").strip() if PIX.exists() else None
    novo = render(data, st, pix)
    if "--check" in argv:
        atual = README.read_text(encoding="utf-8") if README.exists() else ""
        # ignora a linha da data ao comparar
        strip = lambda t: "\n".join(l for l in t.splitlines() if "README gerado em" not in l)  # noqa: E731
        if strip(atual) != strip(novo):
            print("README.md desatualizado em relação ao data/servers.yaml", file=sys.stderr)
            return 1
        print("README.md em dia")
        return 0
    README.write_text(novo, encoding="utf-8")
    print(f"README.md gerado: {len(data['servidores'])} entradas em {len(data['categorias'])} categorias")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
