#!/usr/bin/env node
// Copia o repositório para um diretório de build e minifica, no lugar, os
// arquivos .css/.js públicos do site (raiz do projeto). O restante dos
// arquivos (HTML, imagens, backend Python etc.) é copiado sem alteração,
// então nenhuma referência precisa mudar nos HTMLs — só o conteúdo dos
// próprios .css/.js fica menor.

import { build } from "esbuild";
import { cp, mkdir, readdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const OUT_DIR = path.join(ROOT, "dist-site");

const EXCLUIR_DIR = new Set([
  ".git",
  "node_modules",
  "dist-site",
  "tests",
  "package",
]);

const EXCLUIR_ARQUIVO = new Set([
  "playwright.config.js",
]);

async function copiarSite() {
  await rm(OUT_DIR, { recursive: true, force: true });
  await mkdir(OUT_DIR, { recursive: true });
  const entradas = await readdir(ROOT, { withFileTypes: true });
  for (const entrada of entradas) {
    if (EXCLUIR_DIR.has(entrada.name)) continue;
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
