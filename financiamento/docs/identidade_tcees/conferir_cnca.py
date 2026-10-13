"""Confere a aba "CNCA — Evidências" no dashboard gerado.

    python docs/identidade_tcees/conferir_cnca.py

Substitui a conferência da aba anterior ("CNCA — Auditoria", um checklist manual
guardado no localStorage). A aba de hoje é papel de trabalho gerado pelo ETL, e o
que precisa ser conferido é outro:

* as seis visões renderizam sem erro de console;
* nenhuma célula do painel usa a palavra "achado" para o que é indício;
* lacuna aparece como "sem dado público", nunca como zero;
* o "ver fonte" de uma evidência abre e mostra a consulta que produziu o número;
* o CSV exportado traz as colunas de proveniência preenchidas.

Sai com código 1 se houver erro de console ou se alguma conferência falhar.
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PASTA = Path(__file__).resolve().parent
DASHBOARD = PASTA.parent.parent / "dashboard.html"
SAIDA = PASTA / "conferencia"

VISOES = ["matriz", "mapa", "municipio", "perguntas", "cobertura", "exportar"]

#: Palavras que NÃO podem aparecer como rótulo de status na tela. O vocabulário da
#: fiscalização distingue indício de achado, e a interface tem de refletir isso.
PROIBIDAS = ("achado de auditoria confirmado", "irregularidade constatada", "achado confirmado")


def main() -> int:
    for fluxo in (sys.stdout, sys.stderr):  # console do Windows (cp1252) não derruba a conferência
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="replace")
    SAIDA.mkdir(exist_ok=True)
    erros: list[str] = []
    falhas: list[str] = []

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1440, "height": 1000})
        pagina.on("console", lambda m: erros.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        pagina.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
        pagina.goto(DASHBOARD.as_uri())
        pagina.wait_for_load_state("networkidle")

        # A aba do CNCA é a última da navegação principal.
        pagina.get_by_role("tab", name="CNCA — Evidências").click()
        pagina.wait_for_timeout(400)

        for visao in VISOES:
            botao = pagina.locator("nav.cn-abas button", has_text=_rotulo(visao))
            if not botao.count():
                falhas.append(f"visão {visao}: aba não encontrada")
                continue
            botao.first.click()
            pagina.wait_for_timeout(350)
            corpo = pagina.locator("#conteudo")
            if not corpo.inner_text().strip():
                falhas.append(f"visão {visao}: conteúdo vazio")
            pagina.screenshot(path=str(SAIDA / f"cnca-{visao}.png"), full_page=(visao != "mapa"))

        # Vocabulário: indício não é achado.
        pagina.locator("nav.cn-abas button", has_text="Matriz").first.click()
        pagina.wait_for_timeout(300)
        texto = pagina.locator("#conteudo").inner_text().lower()
        for palavra in PROIBIDAS:
            if palavra in texto:
                falhas.append(f"a tela usa {palavra!r}, que confunde indício com achado")
        if "indício" not in texto:
            falhas.append("a visão da matriz não diz 'indício' em lugar nenhum")

        # Lacuna não vira zero: a ficha de um município tem de dizer "sem dado".
        pagina.locator("nav.cn-abas button", has_text="Ficha do município").first.click()
        pagina.wait_for_timeout(400)
        ficha = pagina.locator("#conteudo").inner_text()
        if "sem dado" not in ficha.lower():
            falhas.append("a ficha do município não mostra nenhuma lacuna como 'sem dado'")

        # "Ver fonte" de uma evidência abre e mostra a consulta que produziu o número.
        # Nem toda evidência tem consulta: um achado documental sem ato localizado não
        # tem requisição por trás, e o diálogo dele mostra só a fórmula e a ressalva —
        # o que é correto. A conferência procura uma que TENHA, até achar.
        botoes = pagina.locator("#conteudo button", has_text="ver fonte")
        total = botoes.count()
        if not total:
            falhas.append("a ficha não oferece 'ver fonte' em nenhuma evidência")
        else:
            achou_url = False
            dialogo = pagina.locator("#dialogo-fonte")
            for i in range(min(total, 40)):
                botoes.nth(i).click()
                pagina.wait_for_timeout(180)
                if not dialogo.is_visible():
                    falhas.append("'ver fonte' não abriu o diálogo de proveniência")
                    break
                texto_dlg = dialogo.inner_text()
                if "http" in texto_dlg.lower() or "postgresql://" in texto_dlg.lower():
                    achou_url = True
                    pagina.screenshot(path=str(SAIDA / "cnca-ver-fonte.png"))
                    pagina.keyboard.press("Escape")
                    break
                pagina.keyboard.press("Escape")
                pagina.wait_for_timeout(120)
            if not achou_url:
                falhas.append("nenhuma das evidências da ficha abriu o diálogo com a consulta")

        # O CSV exportado tem proveniência.
        pagina.locator("nav.cn-abas button", has_text="Exportar").first.click()
        pagina.wait_for_timeout(300)
        with pagina.expect_download() as baixado:
            pagina.locator("#conteudo button", has_text="Baixar evidências").first.click()
        caminho = baixado.value.path()
        texto_csv = Path(caminho).read_text(encoding="utf-8-sig")
        linhas = list(csv.DictReader(io.StringIO(texto_csv), delimiter=";"))
        if not linhas:
            falhas.append("CSV exportado sem linhas")
        else:
            faltam = {"municipio_ibge", "achado_id", "status", "nota",
                      "endpoint_ou_arquivo", "hash_bruto"} - set(linhas[0])
            if faltam:
                falhas.append(f"CSV sem colunas de proveniência: {sorted(faltam)}")
            com_valor = [l for l in linhas if l.get("valor")]
            sem_proveniencia = [l for l in com_valor if not l.get("endpoint_ou_arquivo")]
            if com_valor and sem_proveniencia:
                falhas.append(f"{len(sem_proveniencia)} linhas com valor e sem proveniência no CSV")
            print(f"CSV: {len(linhas)} linhas, {len(com_valor)} com valor")

        navegador.close()

    for e in erros:
        print(f"ERRO DE CONSOLE: {e}")
    for f in falhas:
        print(f"FALHA: {f}")
    if not erros and not falhas:
        print(f"OK — seis visões renderizadas, screenshots em {SAIDA}")
    return 1 if (erros or falhas) else 0


def _rotulo(visao: str) -> str:
    return {"matriz": "Matriz", "mapa": "Mapa de evidências", "municipio": "Ficha do município",
            "perguntas": "Perguntas", "cobertura": "Cobertura", "exportar": "Exportar"}[visao]


if __name__ == "__main__":
    raise SystemExit(main())
