// @ts-check
// OpenTrading documentation site — Docusaurus classic.
// This runs in Node.js — no browser APIs / JSX here.
import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'OpenTrading',
  tagline: 'A local-first, keyless prediction desk for short-term trading',
  favicon: 'img/favicon.png',

  future: {
    v4: true,
  },

  // --- Deployment --------------------------------------------------------
  // Defaults target a user/org GitHub Pages site or Vercel/Cloudflare Pages
  // (baseUrl '/'). For a PROJECT GitHub Pages site, set baseUrl to
  // '/OpenTrading/'. See README.md in this folder.
  url: 'https://orangejustin.github.io',
  baseUrl: '/',
  organizationName: 'orangejustin',
  projectName: 'OpenTrading',
  trailingSlash: false,

  onBrokenLinks: 'warn',
  onBrokenAnchors: 'warn',

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          editUrl: 'https://github.com/orangejustin/OpenTrading/tree/main/docs-site/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/logo.png',
      colorMode: {
        defaultMode: 'light',
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'OpenTrading',
        logo: {
          alt: 'OpenTrading',
          src: 'img/logo.png',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'docsSidebar',
            position: 'left',
            label: 'Docs',
          },
          {
            to: '/docs/getting-started',
            label: 'Tutorial',
            position: 'left',
          },
          {
            href: 'https://github.com/orangejustin/OpenTrading',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {label: 'Introduction', to: '/docs/intro'},
              {label: 'Getting started', to: '/docs/getting-started'},
              {label: 'The prediction desk', to: '/docs/prediction-desk'},
              {label: 'Methodology', to: '/docs/methodology'},
            ],
          },
          {
            title: 'Project',
            items: [
              {label: 'GitHub', href: 'https://github.com/orangejustin/OpenTrading'},
              {label: 'Report an issue', href: 'https://github.com/orangejustin/OpenTrading/issues'},
            ],
          },
        ],
        copyright: `Educational only — not financial advice. Built with Docusaurus. © ${new Date().getFullYear()} OpenTrading.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
        additionalLanguages: ['bash', 'python', 'json'],
      },
    }),
};

export default config;
