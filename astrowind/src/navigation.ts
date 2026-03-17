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
      ],
    },
  ],
  secondaryLinks: [
    { text: 'Terms', href: getPermalink('/terms') },
    { text: 'Privacy', href: getPermalink('/privacy') },
    { text: 'Contact: yaltshul@itcloudx.com', href: 'mailto:yaltshul@itcloudx.com' },
  ],
  socialLinks: [],
  footNote: `© 2026 TradeShield AI · Powered by <a class="underline">Deccod</a>`,
  footNoteExtra: `Built on Google Cloud & Firebase`,
};