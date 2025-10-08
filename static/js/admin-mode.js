(function () {
  const body = document.body;
  if (!body || body.dataset.adminMode !== '1') {
    return;
  }

  const pageKey = body.dataset.pageKey;
  const editor = document.querySelector('.page-editor[data-page-editor]');
  const form = editor ? editor.querySelector('[data-editor-form]') : null;

  if (!pageKey || !editor || !form) {
    return;
  }

  const debounce = (fn, delay = 250) => {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  };

  const renderers = {
    home: renderHome,
    services: renderServices,
    contact: renderContact,
    store: renderStore,
  };

  const render = renderers[pageKey];
  if (!render) {
    return;
  }

  const toggleButton = editor.querySelector('[data-editor-toggle]');
  if (toggleButton) {
    toggleButton.addEventListener('click', () => {
      const isOpen = editor.classList.toggle('is-open');
      toggleButton.textContent = isOpen ? 'Hide editor' : 'Show editor';
    });
  }

  enhanceCollections(form);

  const submitDraft = debounce(() => {
    const formData = new FormData(form);
    fetch(`/admin/draft/${pageKey}` , {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then((response) => response.json())
      .then((data) => {
        if (!data || data.error) {
          console.error(data ? data.error : 'Unknown error updating draft');
          return;
        }
        render(data.page || {}, data.site || {});
      })
      .catch((error) => {
        console.error('Error updating draft', error);
      });
  }, 250);

  form.addEventListener('input', submitDraft);
  form.addEventListener('change', submitDraft);
  form.addEventListener('submit', (event) => event.preventDefault());

  function enhanceCollections(scope) {
    scope.querySelectorAll('.add-item').forEach((button) => {
      button.addEventListener('click', () => {
        const templateId = button.dataset.template;
        const template = templateId ? document.getElementById(templateId) : null;
        if (!template || !template.content.firstElementChild) {
          return;
        }
        const clone = template.content.firstElementChild.cloneNode(true);
        const collection = button.closest('.collection-wrapper')?.querySelector('.collection');
        if (!collection) {
          return;
        }
        collection.appendChild(clone);
        attachRemoveHandlers(clone);
        submitDraft();
      });
    });

    attachRemoveHandlers(scope);
  }

  function attachRemoveHandlers(scope) {
    scope.querySelectorAll('.remove-item').forEach((button) => {
      if (button.dataset.bound === '1') {
        return;
      }
      button.dataset.bound = '1';
      button.addEventListener('click', () => {
        const item = button.closest('.collection-item');
        item?.remove();
        submitDraft();
      });
    });
  }

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (!element) {
      return;
    }
    element.textContent = value || '';
  }

  function setLink(selector, text, href) {
    const element = document.querySelector(selector);
    if (!element) {
      return;
    }
    element.textContent = text || '';
    if (href) {
      element.setAttribute('href', href);
    } else {
      element.removeAttribute('href');
    }
  }

  function renderImage(container, src, alt) {
    if (!container) {
      return;
    }
    container.innerHTML = '';
    if (src) {
      container.hidden = false;
      const img = document.createElement('img');
      img.src = src;
      img.alt = alt || '';
      img.loading = 'lazy';
      container.appendChild(img);
    } else {
      container.hidden = true;
    }
  }

  function renderList(containerSelector, templateId, items, configure) {
    const container = typeof containerSelector === 'string'
      ? document.querySelector(containerSelector)
      : containerSelector;
    const template = templateId ? document.getElementById(templateId) : null;
    if (!container || !template || !template.content.firstElementChild) {
      return;
    }
    container.innerHTML = '';
    (items || []).forEach((item) => {
      const node = template.content.firstElementChild.cloneNode(true);
      configure(node, item);
      container.appendChild(node);
    });
  }

  function renderHome(page) {
    const hero = page.hero || {};
    setText('[data-slot="home.hero.badge"]', hero.badge);
    setText('[data-slot="home.hero.title"]', hero.title);
    setText('[data-slot="home.hero.description"]', hero.description);
    setLink('[data-slot-link="home.hero.cta"]', hero.cta_text, hero.cta_link || '#');
    renderImage(document.querySelector('[data-slot-container="home.hero.image"]'), hero.image, hero.image_alt);

    const whatWePrint = page.what_we_print || {};
    setText('[data-slot="home.what_we_print.title"]', whatWePrint.title);
    renderList('[data-repeat="home.what_we_print.items"]', 'tpl-home-what-we-print', whatWePrint.items || [], (node, item) => {
      const cardImage = node.querySelector('[data-image-container]');
      renderImage(cardImage, item.image, item.image_alt);
      const title = node.querySelector('h3');
      const description = node.querySelector('p');
      if (title) title.textContent = item.title || '';
      if (description) description.textContent = item.description || '';
      const list = node.querySelector('[data-list]');
      if (list) {
        list.innerHTML = '';
        if (item.bullets && item.bullets.length) {
          list.hidden = false;
          item.bullets.forEach((bullet) => {
            const li = document.createElement('li');
            li.textContent = bullet;
            list.appendChild(li);
          });
        } else {
          list.hidden = true;
        }
      }
    });

    const whyChoose = page.why_choose || {};
    setText('[data-slot="home.why_choose.title"]', whyChoose.title);
    renderList('[data-repeat="home.why_choose.items"]', 'tpl-home-why-choose', whyChoose.items || [], (node, item) => {
      const cardImage = node.querySelector('[data-image-container]');
      renderImage(cardImage, item.image, item.image_alt);
      const title = node.querySelector('h3');
      const description = node.querySelector('p');
      if (title) title.textContent = item.title || '';
      if (description) description.textContent = item.description || '';
    });

    const testimonials = page.testimonials || {};
    setText('[data-slot="home.testimonials.title"]', testimonials.title);
    renderList('[data-repeat="home.testimonials.items"]', 'tpl-home-testimonial', testimonials.items || [], (node, item) => {
      const quote = node.querySelector('p');
      const cite = node.querySelector('cite');
      if (quote) quote.textContent = item.quote || '';
      if (cite) cite.textContent = item.author || '';
    });
  }

  function renderServices(page) {
    const hero = page.hero || {};
    setText('[data-slot="services.hero.badge"]', hero.badge);
    setText('[data-slot="services.hero.title"]', hero.title);
    setText('[data-slot="services.hero.description"]', hero.description);

    const capabilities = page.capabilities || {};
    setText('[data-slot="services.capabilities.title"]', capabilities.title);
    renderList('[data-repeat="services.capabilities.items"]', 'tpl-services-capability', capabilities.items || [], (node, item) => {
      renderImage(node.querySelector('[data-image-container]'), item.image, item.image_alt);
      const title = node.querySelector('h3');
      const description = node.querySelector('p');
      if (title) title.textContent = item.title || '';
      if (description) description.textContent = item.description || '';
      const list = node.querySelector('[data-list]');
      if (list) {
        list.innerHTML = '';
        if (item.bullets && item.bullets.length) {
          list.hidden = false;
          item.bullets.forEach((bullet) => {
            const li = document.createElement('li');
            li.textContent = bullet;
            list.appendChild(li);
          });
        } else {
          list.hidden = true;
        }
      }
    });

    const bundles = page.bundles || {};
    setText('[data-slot="services.bundles.title"]', bundles.title);
    renderList('[data-repeat="services.bundles.items"]', 'tpl-services-bundle', bundles.items || [], (node, item) => {
      renderImage(node.querySelector('[data-image-container]'), item.image, item.image_alt);
      const title = node.querySelector('h3');
      const price = node.querySelector('.price');
      const description = node.querySelector('p');
      if (title) title.textContent = item.title || '';
      if (price) price.textContent = item.price || '';
      if (description) description.textContent = item.description || '';
      const list = node.querySelector('[data-list]');
      if (list) {
        list.innerHTML = '';
        if (item.bullets && item.bullets.length) {
          list.hidden = false;
          item.bullets.forEach((bullet) => {
            const li = document.createElement('li');
            li.textContent = bullet;
            list.appendChild(li);
          });
        } else {
          list.hidden = true;
        }
      }
    });

    const process = page.process || {};
    setText('[data-slot="services.process.title"]', process.title);
    renderList('[data-repeat="services.process.steps"]', 'tpl-services-step', process.steps || [], (node, item) => {
      const title = node.querySelector('h3');
      const description = node.querySelector('p');
      if (title) title.textContent = item.title || '';
      if (description) description.textContent = item.description || '';
    });
    const cta = process.cta || {};
    setText('[data-slot="services.process.cta.title"]', cta.title);
    setText('[data-slot="services.process.cta.description"]', cta.description);
    setLink('[data-slot-link="services.process.cta"]', cta.text, cta.link || '#');
  }

  function renderContact(page) {
    const hero = page.hero || {};
    setText('[data-slot="contact.hero.badge"]', hero.badge);
    setText('[data-slot="contact.hero.title"]', hero.title);
    setText('[data-slot="contact.hero.description"]', hero.description);

    const studio = page.studio || {};
    setText('[data-slot="contact.studio.visit_title"]', studio.visit_title);
    renderSimpleList('[data-list="contact.studio.address"]', studio.address || []);
    setText('[data-slot="contact.studio.hours_title"]', studio.hours_title);
    renderSimpleList('[data-list="contact.studio.hours"]', studio.hours || []);
    setLink('[data-slot-link="contact.studio.phone"]', studio.phone, studio.phone_href ? `tel:${studio.phone_href}` : '');
    setLink('[data-slot-link="contact.studio.email"]', studio.email, studio.email ? `mailto:${studio.email}` : '');
    setText('[data-slot="contact.studio.phone_title"]', studio.phone_title);
    setText('[data-slot="contact.studio.email_title"]', studio.email_title);

    const formData = page.form || {};
    setText('[data-slot="contact.form.title"]', formData.title);
    const formContainer = document.querySelector('[data-repeat="contact.form.fields"]');
    const formTemplate = document.getElementById('tpl-contact-form-field');
    if (formContainer && formTemplate && formTemplate.content.firstElementChild) {
      formContainer.innerHTML = '';
      (formData.fields || []).forEach((field) => {
        const node = formTemplate.content.firstElementChild.cloneNode(true);
        const label = node.querySelector('.field-label');
        const input = node.querySelector('input, textarea');
        if (label) label.textContent = field.label || '';
        if (input) {
          if (field.type === 'textarea') {
            const textarea = document.createElement('textarea');
            textarea.placeholder = field.placeholder || '';
            textarea.name = field.name || '';
            node.replaceChild(textarea, input);
          } else {
            input.type = field.type || 'text';
            input.placeholder = field.placeholder || '';
            input.name = field.name || '';
          }
        }
        formContainer.appendChild(node);
      });
    }
    setText('[data-slot="contact.form.submit_text"]', formData.submit_text);

    const about = page.about || {};
    setText('[data-slot="contact.about.title"]', about.title);
    setText('[data-slot="contact.about.description"]', about.description);
    renderList('[data-repeat="contact.about.cards"]', 'tpl-contact-about-card', about.cards || [], (node, item) => {
      const title = node.querySelector('h3');
      const description = node.querySelector('p');
      if (title) title.textContent = item.title || '';
      if (description) description.textContent = item.description || '';
    });
  }

  function renderStore(page) {
    const hero = page.hero || {};
    setText('[data-slot="store.hero.badge"]', hero.badge);
    setText('[data-slot="store.hero.title"]', hero.title);
    setText('[data-slot="store.hero.description"]', hero.description);
    setLink('[data-slot-link="store.hero.cta"]', hero.cta_text, hero.cta_link || '#');

    const promises = page.promises || {};
    setText('[data-slot="store.promises.title"]', promises.title);
    renderList('[data-repeat="store.promises.items"]', 'tpl-store-promise', promises.items || [], (node, item) => {
      const title = node.querySelector('h3');
      const description = node.querySelector('p');
      if (title) title.textContent = item.title || '';
      if (description) description.textContent = item.description || '';
    });

    const support = page.support || {};
    setText('[data-slot="store.support.title"]', support.title);
    setText('[data-slot="store.support.description"]', support.description);
    setLink('[data-slot-link="store.support.cta"]', support.cta_text, support.cta_link || '#');
  }

  function renderSimpleList(selector, items) {
    const container = document.querySelector(selector);
    if (!container) {
      return;
    }
    container.innerHTML = '';
    (items || []).forEach((item) => {
      const div = document.createElement('div');
      div.textContent = item;
      container.appendChild(div);
    });
  }
})();
