#!/usr/bin/env node
// Copia para um diretório de build só o que é público (site estático +
// arquivos que o app desktop/atualizador buscam via HTTP no domínio) e
// minifica, no lugar, os .css/.js públicos. Código-fonte de backend/app
// desktop (Python, scripts de build etc.) nunca entra no artefato do
// GitHub Pages — ver EXCLUIR_DIR/EXCLUIR_ARQUIVO abaixo.

import { build } from "esbuild";
import { cp, mkdir, readdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const OUT_DIR = path.join(ROOT, "dist-site");

// Diretórios de código-fonte (backend, app desktop, apps móveis, ferramentas
// internas, testes) que não fazem parte do site público e não devem ser
// publicados no GitHub Pages.
const EXCLUIR_DIR = new Set([
  ".git",
  ".github",
  "node_modules",
  "dist-site",
  "tests",
  "package",
  "api",
  "backend",
  "cloud_server",
  "database",
  "docs",
  "installer",
  "isis",
  "mobile_android",
  "reports",
  "repositories",
  "screens",
  "services",
  "scripts",
  "tools",
]);

// Arquivos de configuração/documentação/segredos internos que não fazem
// parte do site público. Note que app-update.json e mistica-painel-config.json
// NÃO estão aqui: o app desktop os busca via HTTP no domínio público.
const EXCLUIR_ARQUIVO = new Set([
  "playwright.config.js",
  ".env.example",
  ".gitignore",
  ".lighthouserc.json",
  ".secrets.baseline",
  "CHECKLIST_V2.md",
  "README.md",
  "STATUS_ATUAL.md",
  "render.yaml",
  "requirements.txt",
  "requirements-win7-32.txt",
  "requirements-win7-x86.txt",
  "requirements-windows7.txt",
  "package.json",
  "package-lock.json",
]);

async function copiarSite() {
  await rm(OUT_DIR, { recursive: true, force: true });
  await mkdir(OUT_DIR, { recursive: true });
  const entradas = await readdir(ROOT, { withFileTypes: true });
  for (const entrada of entradas) {
    if (EXCLUIR_DIR.has(entrada.name) || EXCLUIR_ARQUIVO.has(entrada.name)) continue;
    // Código-fonte Python/Batch da raiz (app desktop, patches, scripts de
    // build) nunca é público, então nenhum arquivo .py ou .bat vai no artefato.
    if (entrada.isFile() && /\.(py|bat)$/.test(entrada.name)) continue;
    await cp(path.join(ROOT, entrada.name), path.join(OUT_DIR, entrada.name), { recursive: true });
  }
}

async function listarArquivosRaiz(extensao) {
  const entradas = await readdir(OUT_DIR, { withFileTypes: true });
  return entradas
    .filter((item) => item.isFile() && item.name.endsWith(extensao))
    .map((item) => item.name)
    .filter((nome) => !nome.endsWith(".min.js") && !EXCLUIR_ARQUIVO.has(nome));
}

async function minificarArquivos(nomes) {
  for (const nome of nomes) {
    const arquivo = path.join(OUT_DIR, nome);
    const antes = (await stat(arquivo)).size;
    await build({
      entryPoints: [arquivo],
      outfile: arquivo,
      allowOverwrite: true,
      minify: true,
      bundle: false,
      logLevel: "warning",
    });
    const depois = (await stat(arquivo)).size;
    const economia = antes ? Math.round((1 - depois / antes) * 100) : 0;
    console.log(`${nome}: ${antes}B -> ${depois}B (-${economia}%)`);
  }
}

async function main() {
  await copiarSite();
  const arquivosJs = await listarArquivosRaiz(".js");
  const arquivosCss = await listarArquivosRaiz(".css");
  await minificarArquivos([...arquivosJs, ...arquivosCss]);
  console.log(`Build otimizado gerado em ${OUT_DIR}`);
}

main().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
