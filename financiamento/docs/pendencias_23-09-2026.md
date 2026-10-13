- cliquei em ver fonte e depois no link: ftp://ftp.fnde.gov.br/web/siope/RREO/RREO_Municipal_320020_6_2024.pdf, e não consegui abrir o PDF. não funcionou.
- tentei também o link : ftp://ftp.fnde.gov.br/web/siope/RREO/RREO_Municipal_320230_6_2024.pdf e não funcionou

**Resolvido em 24/09/2026.** O link estava certo e o FTP do FNDE responde (baixei os
dois PDFs por `curl`, idênticos ao cache). O que não funciona é o navegador: Chrome
removeu o esquema `ftp://` na versão 95 e o Firefox na 90, e o FNDE não publica esses
arquivos por HTTP anônimo (porta 443 fechada, `/siope/` responde 401). Os 390 PDFs
passaram a ir embutidos no `dashboard.html`, com o SHA-256 conferido contra a
proveniência na montagem; o diálogo "ver fonte" mostra o botão *abrir PDF* e deixa a
URL do FTP como texto, para quem for reproduzir a coleta por fora. A página foi de
23 MB para 45 MB. Ver a seção do SIOPE no README.
