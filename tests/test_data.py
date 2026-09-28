"""Testes mínimos: YAML válido, campos obrigatórios, sem URL duplicada, README contém todas as entradas.

Rodar:  python3 -m unittest discover tests
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "servers.yaml"
README = ROOT / "README.md"

PACOTES = {"npm", "pypi", "oci", "mcpb", "remoto", "git"}
SIM_NAO = {"sim", "nao"}


def _as_list(v):
    return list(v) if isinstance(v, (list, tuple)) else [v]


class TestServersYaml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
        cls.cats = {c["id"] for c in cls.data["categorias"]}
        cls.servers = cls.data["servidores"]

    def test_yaml_tem_categorias_e_servidores(self):
        self.assertGreaterEqual(len(self.cats), 8)
        self.assertGreaterEqual(len(self.servers), 25, "o brief exige >= 25 entradas no D0")

    def test_campos_obrigatorios(self):
        for s in self.servers:
            with self.subTest(nome=s.get("nome")):
                for campo in ("nome", "url", "descricao", "categoria"):
                    self.assertTrue(s.get(campo), f"campo obrigatório ausente: {campo}")
                self.assertIn(s["categoria"], self.cats)
                self.assertTrue(s["url"].startswith("https://"))
                self.assertNotIn("\n", s["descricao"], "descrição deve ter 1 linha")
                self.assertLessEqual(len(s["descricao"]), 160, "descrição longa demais para a tabela")
                if s.get("tipo", "servidor") != "guia":
                    for campo in ("pacote", "exige_chave", "registro_oficial"):
                        self.assertIn(campo, s, f"campo obrigatório ausente: {campo}")
                    for p in _as_list(s["pacote"]):
                        self.assertIn(p, PACOTES)
                    self.assertIn(str(s["exige_chave"]).lower(), SIM_NAO)
                    self.assertIn(str(s["registro_oficial"]).lower(), SIM_NAO)
                    if str(s["registro_oficial"]).lower() == "sim":
                        self.assertTrue(s.get("registro_nome"), "registro_oficial: sim exige registro_nome")
                if s.get("repo"):
                    self.assertRegex(s["repo"], r"^[\w.-]+/[\w.-]+$")
                    self.assertIn(s["repo"].lower(), s["url"].lower())

    def test_sem_url_ou_repo_duplicado(self):
        urls = [s["url"].rstrip("/").lower() for s in self.servers]
        self.assertEqual(len(urls), len(set(urls)), "URL duplicada")
        repos = [s["repo"].lower() for s in self.servers if s.get("repo")]
        self.assertEqual(len(repos), len(set(repos)), "repo duplicado")
        nomes = [s["nome"] for s in self.servers]
        self.assertEqual(len(nomes), len(set(nomes)), "nome duplicado")

    def test_cada_categoria_tem_pelo_menos_uma_entrada(self):
        usadas = {s["categoria"] for s in self.servers}
        self.assertEqual(usadas, self.cats)

    def test_venture_irma_listada(self):
        self.assertIn("daniel-filius/apuracao-2026-mcp", [s.get("repo") for s in self.servers])


class TestReadme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
        cls.readme = README.read_text(encoding="utf-8") if README.exists() else ""

    def test_readme_existe_e_contem_todas_as_entradas(self):
        self.assertTrue(self.readme, "README.md não existe — rode scripts/build_readme.py")
        for s in self.data["servidores"]:
            with self.subTest(nome=s["nome"]):
                self.assertIn(f"]({s['url']})", self.readme)
        for c in self.data["categorias"]:
            self.assertIn(f"## {c['nome']}", self.readme)

    def test_readme_secoes_fixas(self):
        for sec in ("## Como instalar um servidor MCP", "## Apoiadores", "## Apoie a curadoria",
                    "## Como contribuir", "## Licença"):
            self.assertIn(sec, self.readme)
        self.assertIn("issues/new?template=quero-apoiar.yml", self.readme)
        self.assertIn("issues/new?template=adicionar-servidor.yml", self.readme)

    def test_readme_em_dia_com_yaml(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_readme.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_pix_payload_valido_se_presente(self):
        m = re.search(r"```\n(000201[^\n]+)\n```", self.readme)
        if not m:
            self.skipTest("sem payload Pix no README")
        payload = m.group(1)
        self.assertTrue(payload.startswith("000201"))
        self.assertRegex(payload, r"6304[0-9A-F]{4}$")
        self.assertIn("br.gov.bcb.pix", payload)


if __name__ == "__main__":
    unittest.main()
