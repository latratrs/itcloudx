import { getPermalink, getBlogPermalink, getAsset } from './utils/permalinks';

const BOOKING_URL = 'https://calendar.google.com/calendar/appointments/schedules/AcZssZ2SQsxPh728ktuzEnrQ1jy8bAXrrZNwprTNUMz2sxFxw-5rwZ4dj2ekqMt72U840Dvpx-a5r5Z1';

export const headerData = {
  links: [
    { text: 'Home', href: getPermalink('/') },
    {
      text: 'AI Services',
      links: [
        { text: 'AI Consulting for Small Businesses in Los Angeles', href: getPermalink('/services/ai-consulting-los-angeles') },
        { text: 'AI Integration SMB Compliance Mistakes Fix', href: getPermalink('/services/ai-smb-compliance-mistakes-fix') },
        { text: 'BTRC Automation', href: getPermalink('/services/btrc-automation') },
      ],
    },
    { text: 'About Us', href: getPermalink('/about') },
    { text: 'Contact', href: getPermalink('/contact') },
  ],
  actions: [{ text: 'Book A Call', href: BOOKING_URL, target: '_blank' }],
};

export const footerData = {
  links: [
    {
      title: 'Our Focus',
      links: [
        { text: 'AI Consulting', href: getPermalink('/services/ai-consulting-los-angeles') },
        { text: 'Compliance Fix', href: getPermalink('/services/ai-smb-compliance-mistakes-fix') },
      ],
    },
    {
      title: 'Company',
      links: [
        { text: 'About ITCloudX', href: getPermalink('/about') },
        { text: 'Contact', href: getPermalink('/contact') },
      ],
    },
  ],
  secondaryLinks: [
    { text: 'Terms', href: getPermalink('/terms') },
    { text: 'Privacy', href: getPermalink('/privacy') },
  ],
  footNote: `© 2026 ITCloudX · Los Angeles AI Compliance & Automation`,
};