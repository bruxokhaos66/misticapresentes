(() => {
  const cfg = window.misticaSiteConfig || {};
  const baseUrl = (cfg.publicBaseUrl || "https://misticaesotericos.com.br").replace(/\/$/, "");
  const defaultTitle = "Mística Presentes | Incensos, Cristais, Velas e Artigos Espiritualistas";
  const defaultDescription = "Loja física e virtual de artigos místicos, incensos, cristais, velas ritualísticas, aromaterapia, banhos de ervas e presentes com significado.";
  const defaultImage = `${baseUrl}/assets/logo-mistica-final.webp`;

  function upsertMeta(selector, attrs) {
    let el = document.head.querySelector(selector);
    if (!el) {
      el = document.createElement("meta");
      document.head.appendChild(el);
    }
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
  }

  function upsertLink(rel, href) {
    let el = document.head.querySelector(`link[rel="${rel}"]`);
    if (!el) {
      el = document.createElement("link");
      el.rel = rel;
      document.head.appendChild(el);
    }
    el.href = href;
  }

  function setJsonLd(id, data) {
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement("script");
      el.id = id;
      el.type = "application/ld+json";
      document.head.appendChild(el);
    }
    el.textContent = JSON.stringify(data, null, 2);
  }

  function currentUrl() {
    const path = window.location.pathname.replace(/\/index\.html$/, "/");
    return `${baseUrl}${path}${window.location.search || ""}`;
  }

  function productFromPage() {
    if (!/produto\.html/i.test(window.location.pathname) || typeof products === "undefined") return null;
    const params = new URLSearchParams(window.location.search);
    const id = params.get("id") || params.get("produto") || "";
    return products.find(product => String(product.id) === id) || null;
  }

  function applyBaseSeo() {
    const product = productFromPage();
    const title = product ? `${product.name} | Mística Presentes` : defaultTitle;
    const description = product
      ? `${product.name}: ${product.description || "produto especial da Mística Presentes"}. Consulte disponibilidade pelo WhatsApp.`
      : defaultDescription;
    const image = product?.imageUrl || product?.images?.[0] || defaultImage;
    const url = currentUrl();

    document.title = title;
    upsertMeta('meta[name="description"]', { name: "description", content: description });
    upsertMeta('meta[name="robots"]', { name: "robots", content: "index, follow, max-image-preview:large" });
    upsertMeta('meta[property="og:type"]', { property: "og:type", content: product ? "product" : "website" });
    upsertMeta('meta[property="og:title"]', { property: "og:title", content: title });
    upsertMeta('meta[property="og:description"]', { property: "og:description", content: description });
    upsertMeta('meta[property="og:url"]', { property: "og:url", content: url });
    upsertMeta('meta[property="og:image"]', { property: "og:image", content: image });
    upsertMeta('meta[property="og:site_name"]', { property: "og:site_name", content: "Mística Presentes" });
    upsertMeta('meta[name="twitter:card"]', { name: "twitter:card", content: "summary_large_image" });
    upsertMeta('meta[name="twitter:title"]', { name: "twitter:title", content: title });
    upsertMeta('meta[name="twitter:description"]', { name: "twitter:description", content: description });
    upsertMeta('meta[name="twitter:image"]', { name: "twitter:image", content: image });
    upsertLink("canonical", url);
    upsertLink("manifest", `${baseUrl}/site.webmanifest`);

    setJsonLd("seo-local-business", {
      "@context": "https://schema.org",
      "@type": "Store",
      name: "Mística Presentes",
      url: baseUrl,
      description: defaultDescription,
      image: defaultImage,
      telephone: "+55 49 99917-2137",
      sameAs: ["https://www.instagram.com/misticaprodutos"],
      paymentAccepted: "Pix",
      areaServed: "Pinhalzinho, Santa Catarina, Brasil"
    });

    if (product) {
      setJsonLd("seo-product", {
        "@context": "https://schema.org",
        "@type": "Product",
        name: product.name,
        description,
        image: product.images?.length ? product.images : [image],
        category: product.category,
        offers: {
          "@type": "Offer",
          priceCurrency: "BRL",
          price: Number(product.price || 0).toFixed(2),
          availability: Number(product.stock || 0) > 0 ? "https://schema.org/InStock" : "https://schema.org/PreOrder",
          url
        }
      });
    }
  }

  window.addEventListener("load", () => setTimeout(applyBaseSeo, 700));
})();
