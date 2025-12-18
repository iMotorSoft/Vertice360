// Place any global data in this file.
// You can import this data from anywhere in your site by using the `import` keyword.

export const SITE_TITLE = 'Astrofy | Personal Portfolio Website Template';
export const SITE_DESCRIPTION =
  'Astrofy is a free and open-source template for your Personal Portfolio Website built with Astro and TailwindCSS. Create in minutes a website with Blog, CV, Project Section, Store and RSS Feed.';

const URL_REST_DEV = 'http://localhost:7062';
const URL_REST_PRO = 'https://demo.vertice360.imotorsoft.com';

export const URL_REST = URL_REST_DEV; // cambialo a URL_REST_PRO para apuntar al backend remoto
export const URL_SSE = `${URL_REST}/api/agui/stream`;

const CLOUDFLARE_SITEKEY_DEV = '0x4AAAAAAA9n8PW8yOWCn_6j';
const CLOUDFLARE_SITEKEY_PRO = '0x4AAAAAAA9glDuv7vktGmhn';

export const CLOUDFLARE_SITEKEY = CLOUDFLARE_SITEKEY_DEV; // usa el dev si trabajas en local
