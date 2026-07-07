(() => {
  if (document.getElementById("misticaLocalBusinessSchema")) return;
  const schema = document.createElement("script");
  schema.id = "misticaLocalBusinessSchema";
  schema.type = "application/ld+json";
  schema.textContent = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "Store",
    "name": "Mística Presentes",
    "url": "https://www.misticaesotericos.com.br/",
    "telephone": "+55 49 99917-2137",
    "priceRange": "R$",
    "description": "Produtos místicos, cristais, incensos, velas, aromas, banhos de ervas e presentes com significado em Pinhalzinho-SC.",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "Galeria Ody - Av. Brasília, 2400 - Sala 07 - Centro",
      "addressLocality": "Pinhalzinho",
      "addressRegion": "SC",
      "postalCode": "89870-000",
      "addressCountry": "BR"
    },
    "sameAs": ["https://www.instagram.com/misticaprodutos"]
  });
  document.head.appendChild(schema);
})();
