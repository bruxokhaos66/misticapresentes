(() => {
  function validarBackup(payload) {
    return payload && typeof payload === "object" && Array.isArray(payload.sales) && payload.stock && typeof payload.stock === "object";
  }

  function aplicarProdutosBackup(lista) {
    if (!Array.isArray(lista) || typeof products === "undefined") return;
    products.splice(0, products.length, ...lista);
  }

  function aplicarBackup(payload) {
    if (!validarBackup(payload)) throw new Error("Arquivo de backup inválido ou incompleto.");
    if (Array.isArray(payload.products)) aplicarProdutosBackup(payload.products);
    if (Array.isArray(payload.clients)) clients = payload.clients;
    if (Array.isArray(payload.sales)) sales = payload.sales;
    if (payload.stock && typeof payload.stock === "object") stock = payload.stock;
    if (Array.isArray(payload.suppliers)) suppliers = payload.suppliers;

    localStorage.setItem("misticaCart", JSON.stringify([]));
    saveState();
    renderAll();
  }

  function escolherArquivoBackup() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/json,.json";
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const payload = JSON.parse(String(reader.result || "{}"));
          if (!confirm("Restaurar este backup e substituir os dados locais atuais?")) return;
          aplicarBackup(payload);
          alert("Backup restaurado com sucesso.");
        } catch (error) {
          alert(`Não foi possível restaurar o backup: ${error.message}`);
        }
      };
      reader.readAsText(file, "utf-8");
    });
    input.click();
  }

  function instalarRestauracaoBackup() {
    const oldButton = document.querySelector("[data-restore-backup]");
    if (!oldButton || window.__misticaBackupRestoreInstalled) return;
    window.__misticaBackupRestoreInstalled = true;
    const newButton = oldButton.cloneNode(true);
    newButton.textContent = "Restaurar backup JSON";
    newButton.addEventListener("click", escolherArquivoBackup);
    oldButton.replaceWith(newButton);
  }

  window.misticaBackupRestore = {
    restore: aplicarBackup,
    chooseFile: escolherArquivoBackup,
  };

  window.addEventListener("load", instalarRestauracaoBackup);
})();
