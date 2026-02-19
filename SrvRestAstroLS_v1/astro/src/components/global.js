// Place any global data in this file.
// You can import this data from anywhere in your site by using the `import` keyword.

export const SITE_TITLE = 'Astrofy | Personal Portfolio Website Template';
export const SITE_DESCRIPTION =
  'Astrofy is a free and open-source template for your Personal Portfolio Website built with Astro and TailwindCSS. Create in minutes a website with Blog, CV, Project Section, Store and RSS Feed.';

const URL_REST_DEV = 'http://localhost:7062';
const URL_REST_PRO = 'https://demo.vertice360.imotorsoft.com';

export const URL_REST = URL_REST_DEV; // cambialo a URL_REST_PRO para apuntar al backend remoto

// Source of truth for all REST clients in Astro demos.
export const getRestBaseUrl = () => String(URL_REST || '').replace(/\/+$/, '');

export const URL_SSE = `${getRestBaseUrl()}/api/agui/stream`;

// Centralized URL constants: avoid hardcoded URLs outside this file.
export const URL_WA_ME = 'https://wa.me';
export const URL_SVG_XMLNS = 'http://www.w3.org/2000/svg';
export const URL_FONT_OUTFIT =
  'https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap';
export const URL_FONT_SPACE_GROTESK =
  'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap';

const CLOUDFLARE_SITEKEY_DEV = '0x4AAAAAAA9n8PW8yOWCn_6j';
const CLOUDFLARE_SITEKEY_PRO = '0x4AAAAAAA9glDuv7vktGmhn';

export const CLOUDFLARE_SITEKEY = CLOUDFLARE_SITEKEY_DEV; // usa el dev si trabajas en local
