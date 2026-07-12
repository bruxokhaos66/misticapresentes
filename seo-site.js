(() => {
  const cfg = window.misticaSiteConfig || {};
  const baseUrl = (cfg.publicBaseUrl || "https://www.misticaesotericos.com.br").replace(/\/$/, "");
  const defaultTitle = "Mística Presentes | Incensos, Cristais, Velas e Artigos Espiritualistas";
  const defaultDescription = "Loja física e virtual de artigos místicos, incensos, cristais, velas ritualísticas, aromaterapia, banhos de ervas e presentes com significado em Pinhalzinho-SC.";
  const defaultImage = `${baseUrl}/assets/mistica-logo-novo.webp`;
  const storeAddress = {
    streetAddress: "Galeria Ody - Av. Brasília, 2400 - Sala 07 - Centro",
    addressLocality: "Pinhalzinho",
    addressRegion: "SC",
    postalCode: "89870-000",
    addressCountry: "BR",
  };

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

  function setBreadcrumbJsonLd(product, url) {
    const items = [
      {
        "@type": "ListItem",
        position: 1,
        name: "Início",
        item: `${baseUrl}/`,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "Produtos",
        item: `${baseUrl}/#produtos`,
      },
    ];

    if (product) {
      items.push({
        "@type": "ListItem",
        position: 3,
        name: product.name,
        item: url,
      });
    }

    setJsonLd("seo-breadcrumbs", {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: items,
    });
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
    upsertMeta('meta[name="author"]', { name: "author", content: "Mística Presentes" });
    upsertMeta('meta[name="geo.region"]', { name: "geo.region", content: "BR-SC" });
    upsertMeta('meta[name="geo.placename"]', { name: "geo.placename", content: "Pinhalzinho" });
    upsertMeta('meta[property="og:locale"]', { property: "og:locale", content: "pt_BR" });
    upsertMeta('meta[property="og:type"]', { property: "og:type", content: product ? "product" : "website" });
    upsertMeta('meta[property="og:title"]', { property: "og:title", content: title });
    upsertMeta('meta[property="og:description"]', { property: "og:description", content: description });
    upsertMeta('meta[property="og:url"]', { property: "og:url", content: url });
    upsertMeta('meta[property="og:image"]', { property: "og:image", content: image });
    upsertMeta('meta[property="og:image:alt"]', { property: "og:image:alt", content: product ? product.name : "Logo da Mística Presentes" });
    upsertMeta('meta[property="og:site_name"]', { property: "og:site_name", content: "Mística Presentes" });
    upsertMeta('meta[name="twitter:card"]', { name: "twitter:card", content: "summary_large_image" });
    upsertMeta('meta[name="twitter:title"]', { name: "twitter:title", content: title });
    upsertMeta('meta[name="twitter:description"]', { name: "twitter:description", content: description });
    upsertMeta('meta[name="twitter:image"]', { name: "twitter:image", content: image });
    upsertMeta('meta[name="twitter:image:alt"]', { name: "twitter:image:alt", content: product ? product.name : "Logo da Mística Presentes" });
    upsertLink("canonical", url);
    upsertLink("manifest", "/site.webmanifest");

    setJsonLd("seo-local-business", {
      "@context": "https://schema.org",
      "@type": "Store",
      "@id": `${baseUrl}/#loja`,
      name: "Mística Presentes",
      legalName: "Mística Presentes",
      url: baseUrl,
      description: defaultDescription,
      image: defaultImage,
      logo: defaultImage,
      telephone: "+55 49 99917-2137",
      priceRange: "$$",
      currenciesAccepted: "BRL",
      paymentAccepted: "Pix, Dinheiro, Cartão",
      address: {
        "@type": "PostalAddress",
        ...storeAddress,
      },
      geo: {
        "@type": "GeoCoordinates",
        latitude: -26.8367,
        longitude: -52.9906,
      },
      contactPoint: {
        "@type": "ContactPoint",
        telephone: "+55 49 99917-2137",
        contactType: "Atendimento ao cliente",
        areaServed: "BR",
        availableLanguage: ["Portuguese"],
      },
      sameAs: ["https://www.instagram.com/misticaprodutos"],
      areaServed: [
        "Pinhalzinho, Santa Catarina, Brasil",
        "Oeste de Santa Catarina",
      ],
      knowsAbout: [
        "Incensos",
        "Cristais",
        "Velas ritualísticas",
        "Aromaterapia",
        "Banhos de ervas",
        "Presentes místicos",
      ],
    });

    setJsonLd("seo-website", {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "@id": `${baseUrl}/#website`,
      name: "Mística Presentes",
      url: baseUrl,
      inLanguage: "pt-BR",
      publisher: { "@id": `${baseUrl}/#loja` },
      potentialAction: {
        "@type": "SearchAction",
        target: `${baseUrl}/?busca={search_term_string}`,
        "query-input": "required name=search_term_string",
      },
    });

    setBreadcrumbJsonLd(product, url);

    if (product) {
      setJsonLd("seo-product", {
        "@context": "https://schema.org",
        "@type": "Product",
        name: product.name,
        description,
        image: product.images?.length ? product.images : [image],
        category: product.category,
        sku: product.codigo || product.apiId || product.id,
        url,
        brand: {
          "@type": "Brand",
          name: "Mística Presentes",
        },
        offers: {
          "@type": "Offer",
          priceCurrency: "BRL",
          price: Number(product.price || 0).toFixed(2),
          availability: Number(product.stock || 0) > 0 ? "https://schema.org/InStock" : "https://schema.org/PreOrder",
          url,
          seller: { "@id": `${baseUrl}/#loja` },
        },
      });
      applyProductRatingSeo(product);
    }
  }

  function applyProductRatingSeo(product) {
    if (!product.apiId) return;
    const apiBase = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
    fetch(`${apiBase}/api/produtos/${encodeURIComponent(product.apiId)}/avaliacoes`)
      .then(response => (response.ok ? response.json() : null))
      .then(data => {
        if (!data || !data.total) return;
        const el = document.getElementById("seo-product");
        if (!el) return;
        const schema = JSON.parse(el.textContent);
        schema.aggregateRating = {
          "@type": "AggregateRating",
          ratingValue: data.media,
          reviewCount: data.total,
        };
        el.textContent = JSON.stringify(schema, null, 2);
      })
      .catch(() => {});
  }

  window.addEventListener("load", () => setTimeout(applyBaseSeo, 700));
})();
