(() => {
  const API_BASE = String((window.misticaSiteConfig || {}).apiBaseUrl || 'https://api.misticaesotericos.com.br').replace(/\/$/, '');
  const ready = (fn) => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', fn) : fn();

  const MODOS = [
    { valor: 'novos_rascunho', rotulo: 'Criar somente novos produtos como rascunho (padrão e mais seguro)', perigoso: false },
    { valor: 'novos_ativos', rotulo: 'Criar somente novos produtos como ativos', perigoso: true },
    { valor: 'novos_e_atualizar', rotulo: 'Criar novos e atualizar existentes pelo SKU', perigoso: true },
    { valor: 'novos_e_atualizar_rascunho', rotulo: 'Criar e atualizar pelo SKU, deixando todos como rascunho', perigoso: false },
  ];

  const AVISOS_MODO = {
    novos_ativos: 'Atenção: os produtos novos desta planilha serão publicados imediatamente (visíveis no site) assim que você confirmar.',
    novos_e_atualizar: 'Atenção: produtos existentes com o mesmo SKU serão atualizados com os dados desta planilha.',
  };

  const FILTROS = [
    { valor: '', rotulo: 'Todas' },
    { valor: 'novo', rotulo: 'Novos' },
    { valor: 'atualizacao', rotulo: 'Atualizações' },
    { valor: 'ignorado', rotulo: 'Ignorados' },
    { valor: 'erro', rotulo: 'Erros' },
  ];

  ready(() => {
    const adminContent = document.getElementById('adminContent');
    if (!adminContent) return;

    const panel = document.createElement('section');
    panel.className = 'form-panel import-produtos-panel';
    panel.innerHTML = `
      <p class="eyebrow">Produtos em massa</p>
      <h2>Importar produtos</h2>
      <p class="privacy-note">Envie uma planilha (.xlsx ou .csv em UTF-8) para cadastrar ou atualizar vários produtos de uma vez, com imagens opcionais em um arquivo ZIP. Nada é gravado até você confirmar a prévia.</p>

      <div class="import-toolbar">
        <button class="btn btn-ghost" type="button" data-baixar-modelo>Baixar planilha-modelo</button>
      </div>

      <form class="import-form-grid" data-import-form>
        <label>Planilha (.xlsx ou .csv)
          <input type="file" accept=".xlsx,.csv" data-import-planilha required>
        </label>
        <label>Imagens (ZIP opcional)
          <input type="file" accept=".zip" data-import-zip>
        </label>
        <label>Modo de importação
          <select data-import-modo></select>
        </label>
        <div class="checkout-actions" style="align-self:end">
          <button class="btn" type="submit" data-validar-planilha>Validar e visualizar</button>
        </div>
      </form>
      <p class="import-modo-aviso" data-modo-aviso role="alert"></p>

      <div class="import-progress-estado" data-estado-importacao hidden>Aguardando envio</div>
      <div class="warning-box" data-import-status hidden></div>

      <div data-import-previa hidden>
        <div class="import-resumo" data-import-resumo></div>
        <div class="import-filtros" data-import-filtros></div>
        <div class="import-tabela-wrap">
          <table class="import-tabela">
            <thead><tr><th>Linha</th><th>SKU</th><th>Nome</th><th>Situação</th><th>Imagem</th><th>Mensagens</th></tr></thead>
            <tbody data-import-tbody></tbody>
          </table>
        </div>
        <div class="import-paginacao">
          <button class="btn btn-small btn-ghost" type="button" data-pagina-anterior>Anterior</button>
          <span data-import-pagina-label>Página 1</span>
          <button class="btn btn-small btn-ghost" type="button" data-pagina-proxima>Próxima</button>
        </div>
        <div class="checkout-actions" style="margin-top:14px">
          <button class="btn" type="button" data-confirmar-importacao>Confirmar importação</button>
          <button class="btn btn-ghost" type="button" data-cancelar-previa>Cancelar</button>
        </div>
      </div>

      <h3 style="margin-top:28px">Últimas importações</h3>
      <div data-import-historico></div>
    `;

    const audioPanel = adminContent.querySelector('.audio-admin-panel');
    adminContent.insertBefore(panel, audioPanel || adminContent.firstChild);

    const status = panel.querySelector('[data-import-status]');
    const estadoEl = panel.querySelector('[data-estado-importacao]');
    const form = panel.querySelector('[data-import-form]');
    const modoSelect = panel.querySelector('[data-import-modo]');
    const modoAviso = panel.querySelector('[data-modo-aviso]');
    const previaBox = panel.querySelector('[data-import-previa]');
    const resumoBox = panel.querySelector('[data-import-resumo]');
    const filtrosBox = panel.querySelector('[data-import-filtros]');
    const tbody = panel.querySelector('[data-import-tbody]');
    const paginaLabel = panel.querySelector('[data-import-pagina-label]');
    const historicoBox = panel.querySelector('[data-import-historico]');

    let previaAtual = null; // { token, resumo }
    let filtroAtivo = '';
    let paginaAtual = 1;
    let enviando = false;

    MODOS.forEach((modo) => {
      const opt = document.createElement('option');
      opt.value = modo.valor;
      opt.textContent = modo.rotulo;
      modoSelect.appendChild(opt);
    });

    FILTROS.forEach((filtro) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = filtro.rotulo;
      btn.dataset.filtro = filtro.valor;
      if (filtro.valor === '') btn.classList.add('is-active');
      filtrosBox.appendChild(btn);
    });

    const setEstado = (texto, visivel = true) => {
      estadoEl.textContent = texto;
      estadoEl.hidden = !visivel;
    };

    const setStatus = (mensagem, ok = false) => {
      if (!mensagem) { status.hidden = true; return; }
      status.hidden = false;
      status.textContent = mensagem;
      status.className = ok ? 'warning-box' : 'warning-box warning-danger';
    };

    const atualizarAvisoModo = () => {
      const aviso = AVISOS_MODO[modoSelect.value];
      modoAviso.textContent = aviso || '';
      modoAviso.classList.toggle('is-visible', !!aviso);
    };
    modoSelect.addEventListener('change', atualizarAvisoModo);
    atualizarAvisoModo();

    panel.querySelector('[data-baixar-modelo]').addEventListener('click', async () => {
      try {
        const response = await fetch(`${API_BASE}/api/produtos/importacao/modelo`, { credentials: 'include' });
        if (!response.ok) throw new Error('Falha ao baixar a planilha-modelo.');
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'modelo-importacao-produtos.xlsx';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
      } catch (error) {
        setStatus(error.message || 'Erro ao baixar planilha-modelo.');
      }
    });

    const renderResumo = (resumo) => {
      const itens = [
        ['Linhas', resumo.total_linhas],
        ['Válidas', resumo.validas],
        ['Com erro', resumo.com_erro],
        ['Novos', resumo.novos],
        ['Atualizações', resumo.atualizacoes],
        ['Ignorados', resumo.ignorados],
        ['Com imagem', resumo.com_imagem],
        ['Sem imagem', resumo.sem_imagem],
      ];
      resumoBox.textContent = '';
      itens.forEach(([rotulo, valor]) => {
        const item = document.createElement('div');
        item.className = 'import-resumo-item';
        const strong = document.createElement('strong');
        strong.textContent = String(valor ?? 0);
        const span = document.createElement('span');
        span.textContent = rotulo;
        item.append(strong, span);
        resumoBox.appendChild(item);
      });
      if ((resumo.colunas_desconhecidas || []).length) {
        setStatus(`Colunas ignoradas (não reconhecidas): ${resumo.colunas_desconhecidas.join(', ')}`, true);
      }
    };

    // Nunca usa innerHTML para dados vindos da planilha: todo texto entra
    // via textContent, para não permitir HTML/JS injetado na prévia.
    const renderLinhas = (linhas) => {
      tbody.textContent = '';
      linhas.forEach((linha) => {
        const tr = document.createElement('tr');
        tr.className = linha.classificacao === 'erro' ? 'linha-erro' : linha.classificacao === 'ignorado' ? 'linha-ignorado' : '';

        const tdNumero = document.createElement('td');
        tdNumero.textContent = String(linha.numero);
        const tdSku = document.createElement('td');
        tdSku.textContent = linha.sku || '—';
        const tdNome = document.createElement('td');
        tdNome.textContent = linha.nome || '—';
        const tdSituacao = document.createElement('td');
        tdSituacao.textContent = linha.classificacao;
        const tdImagem = document.createElement('td');
        tdImagem.textContent = linha.tem_imagem ? 'Sim' : 'Não';
        const tdMsg = document.createElement('td');
        [...linha.erros, ...linha.avisos].forEach((msg) => {
          const p = document.createElement('div');
          p.textContent = `${msg.coluna ? msg.coluna + ': ' : ''}${msg.mensagem}`;
          tdMsg.appendChild(p);
        });

        tr.append(tdNumero, tdSku, tdNome, tdSituacao, tdImagem, tdMsg);
        tbody.appendChild(tr);
      });
    };

    const carregarPagina = async () => {
      if (!previaAtual) return;
      const params = new URLSearchParams({ pagina: String(paginaAtual), tamanho_pagina: '50' });
      if (filtroAtivo) params.set('status', filtroAtivo);
      const response = await fetch(`${API_BASE}/api/produtos/importacao/previews/${previaAtual.token}?${params.toString()}`, { credentials: 'include' });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) { setStatus(data.detail || 'Prévia expirada. Envie a planilha novamente.'); previaBox.hidden = true; return; }
      renderLinhas(data.linhas);
      paginaLabel.textContent = `Página ${data.pagina} — ${data.total_filtrado} linha(s)`;
    };

    filtrosBox.addEventListener('click', (event) => {
      const btn = event.target.closest('button[data-filtro]');
      if (!btn) return;
      filtroAtivo = btn.dataset.filtro;
      paginaAtual = 1;
      [...filtrosBox.children].forEach((el) => el.classList.toggle('is-active', el === btn));
      carregarPagina();
    });

    panel.querySelector('[data-pagina-anterior]').addEventListener('click', () => {
      if (paginaAtual > 1) { paginaAtual -= 1; carregarPagina(); }
    });
    panel.querySelector('[data-pagina-proxima]').addEventListener('click', () => {
      paginaAtual += 1; carregarPagina();
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (enviando) return;
      const planilhaInput = panel.querySelector('[data-import-planilha]');
      const zipInput = panel.querySelector('[data-import-zip]');
      if (!planilhaInput.files[0]) { setStatus('Selecione uma planilha .xlsx ou .csv.'); return; }

      const modo = modoSelect.value;
      const modoInfo = MODOS.find((m) => m.valor === modo);
      if (modoInfo && modoInfo.perigoso) {
        const confirmado = confirm('Este modo pode publicar ou alterar produtos existentes assim que a importação for confirmada. Deseja continuar?');
        if (!confirmado) return;
      }

      enviando = true;
      const botao = panel.querySelector('[data-validar-planilha]');
      botao.disabled = true;
      previaBox.hidden = true;
      setStatus('');
      setEstado('Enviando planilha...');

      try {
        const fd = new FormData();
        fd.append('planilha', planilhaInput.files[0]);
        if (zipInput.files[0]) fd.append('zip_imagens', zipInput.files[0]);
        fd.append('modo', modo);
        setEstado('Validando planilha...');
        const response = await fetch(`${API_BASE}/api/produtos/importacao/validar`, {
          method: 'POST', credentials: 'include', body: fd,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Falha ao validar a planilha.');

        previaAtual = { token: data.token, resumo: data.resumo, modo };
        paginaAtual = 1;
        filtroAtivo = '';
        [...filtrosBox.children].forEach((el) => el.classList.toggle('is-active', el.dataset.filtro === ''));
        renderResumo(data.resumo);
        renderLinhas(data.linhas.slice(0, 50));
        paginaLabel.textContent = `Página 1 — ${data.linhas.length} linha(s)`;
        previaBox.hidden = false;
        setEstado('Aguardando confirmação do administrador.');
        setStatus(`Prévia gerada. Expira em ${Math.round((data.expira_em_segundos || 0) / 60)} minuto(s).`, true);
      } catch (error) {
        setEstado('Falha ao validar.', true);
        setStatus(error.message || 'Erro ao validar planilha.');
      } finally {
        enviando = false;
        botao.disabled = false;
      }
    });

    panel.querySelector('[data-cancelar-previa]').addEventListener('click', async () => {
      if (!previaAtual) return;
      try {
        await fetch(`${API_BASE}/api/produtos/importacao/previews/${previaAtual.token}`, { method: 'DELETE', credentials: 'include' });
      } catch { /* melhor esforço */ }
      previaAtual = null;
      previaBox.hidden = true;
      setEstado('', false);
      setStatus('Prévia cancelada. Nenhum produto foi alterado.', true);
    });

    const carregarHistorico = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/produtos/importacao/historico?tamanho_pagina=10`, { credentials: 'include' });
        const data = await response.json().catch(() => ({}));
        historicoBox.textContent = '';
        if (!response.ok || !(data.itens || []).length) {
          const vazio = document.createElement('p');
          vazio.className = 'privacy-note';
          vazio.textContent = 'Nenhuma importação registrada ainda.';
          historicoBox.appendChild(vazio);
          return;
        }
        data.itens.forEach((item) => {
          const linha = document.createElement('div');
          linha.className = 'import-historico-item';
          const esquerda = document.createElement('span');
          esquerda.textContent = `${item.iniciado_em} — ${item.planilha_nome || 'planilha'} (${item.modo})`;
          const direita = document.createElement('span');
          direita.textContent = `${item.status} — criados: ${item.criados}, atualizados: ${item.atualizados}, ignorados: ${item.ignorados}, erros: ${item.com_erro}`;
          linha.append(esquerda, direita);
          historicoBox.appendChild(linha);
        });
      } catch {
        /* histórico é informativo; falha aqui não bloqueia o restante do painel */
      }
    };

    panel.querySelector('[data-confirmar-importacao]').addEventListener('click', async (event) => {
      if (!previaAtual || enviando) return;
      const btn = event.currentTarget;
      if (btn.disabled) return;
      btn.disabled = true;
      enviando = true;
      setEstado('Importando...');
      setStatus('');
      try {
        const response = await fetch(`${API_BASE}/api/produtos/importacao/confirmar`, {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: previaAtual.token }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Falha ao confirmar importação.');

        const comAvisos = data.status === 'concluido_com_avisos';
        setEstado(comAvisos ? 'Concluído com avisos.' : 'Concluído.');
        setStatus(
          `Importação concluída: ${data.criados} criado(s), ${data.atualizados} atualizado(s), ${data.ignorados} ignorado(s), ${data.com_erro} com erro, ${data.sem_imagem} sem imagem.`,
          true,
        );
        previaBox.hidden = true;
        previaAtual = null;
        await carregarHistorico();
      } catch (error) {
        setEstado('Falha na importação.', true);
        setStatus(error.message || 'Erro ao confirmar importação.');
      } finally {
        btn.disabled = false;
        enviando = false;
      }
    });

    carregarHistorico();
  });
})();
