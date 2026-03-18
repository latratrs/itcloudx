import { getPermalink, getBlogPermalink } from './utils/permalinks';

export const headerData = {
  links: [
    { text: 'Free Audit', href: getPermalink('/audit') },
    { text: 'How It Works', href: getPermalink('/#how-it-works') },
    { text: 'Pricing', href: getPermalink('/pricing') },
    { text: 'Blog', href: getBlogPermalink() },
  ],
  actions: [{ text: 'Start Free Scan →', href: getPermalink('/audit') }],
};

export const footerData = {
  links: [
    {
      title: 'Product',
      links: [
        { text: 'Free Audit Tool', href: getPermalink('/audit') },
        { text: 'Pricing', href: getPermalink('/pricing') },
        { text: 'How It Works', href: getPermalink('/#how-it-works') },
        { text: 'HS Code Lookup', href: getPermalink('/tools/hs-lookup') },
      ],
    },
    {
      title: 'Company',
      links: [
        { text: 'About', href: getPermalink('/about') },
        { text: 'Blog', href: getBlogPermalink() },
        { text: 'Contact', href: getPermalink('/contact') },
        { text: 'Services', href: getPermalink('/services') },
      ],
    },
    {
      title: 'Trade Intelligence',
      links: [
        { text: 'Tariff News', href: `${getBlogPermalink()}category/tariffs/` },
        { text: 'Sanctions Updates', href: `${getBlogPermalink()}category/sanctions/` },
        { text: 'HS Code Guides', href: `${getBlogPermalink()}category/hs-codes/` },
        { text: 'All Articles', href: getBlogPermalink() },
      ],
    },
  ],
  secondaryLinks: [
    { text: 'Terms', href: getPermalink('/terms') },
    { text: 'Privacy', href: getPermalink('/privacy') },
    { text: 'Contact', href: getPermalink('/contact') },
  ],
  socialLinks: [],
  footNote: `© 2026 TradeShield AI · Powered by <a class="underline">Deccod</a> · Built on Google Cloud & Firebase · Contact: yaltshul@itcloudx.com`,
};
