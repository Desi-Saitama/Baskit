/**
 * utils.ts — Shared utility functions
 */

/** Format Indian currency amounts. */
export function formatAmount(amount: number): string {
  if (amount >= 100000) {
    return `${(amount / 100000).toFixed(1)}L`;
  }
  return amount.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

/** Format currency with ₹ prefix */
export function rupees(amount: number): string {
  return `₹${formatAmount(amount)}`;
}

/** Get brand color for a delivery app */
export function appColor(appName: string): string {
  const colors: Record<string, string> = {
    zepto: '#8b5cf6',
    blinkit: '#f59e0b',
    instamart: '#16a34a',
    swiggy: '#ea580c',
    zomato: '#ef4444',
    bigbasket: '#84cc16',
    jiomart: '#2563eb',
  };
  return colors[appName?.toLowerCase()] || '#8b5cf6';
}

/** All supported apps */
export const ALL_APPS = [
  { name: 'Zepto', color: '#8b5cf6' },
  { name: 'Blinkit', color: '#f59e0b' },
  { name: 'Instamart', color: '#16a34a' },
  { name: 'Swiggy', color: '#ea580c' },
  { name: 'Zomato', color: '#ef4444' },
  { name: 'BigBasket', color: '#84cc16' },
  { name: 'JioMart', color: '#2563eb' },
];

/** Standard categories */
export const CATEGORIES = [
  'Fruits & Vegetables', 'Dairy & Eggs', 'Grains & Pulses', 'Snacks',
  'Beverages', 'Personal Care', 'Household', 'Bakery',
  'Spices & Condiments', 'Ready to Eat', 'Restaurant Food',
  'Meat & Seafood', 'Other',
];

/** Capitalize first letter */
export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Format date to readable */
export function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
}
