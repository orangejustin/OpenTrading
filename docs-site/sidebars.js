// @ts-check
// Runs in Node.js — no browser APIs / JSX here.

/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Tutorial',
      collapsed: false,
      items: ['getting-started', 'web-dashboard', 'daily-email'],
    },
    {
      type: 'category',
      label: 'Concepts',
      collapsed: false,
      items: ['prediction-desk', 'smart-money', 'methodology'],
    },
  ],
};

export default sidebars;
